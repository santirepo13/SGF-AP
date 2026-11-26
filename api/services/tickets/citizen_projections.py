"""Safe citizen status/action projections and opaque cursor codec."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any

from api.contracts import (
    CitizenHistoryItem,
    CitizenTicketListItem,
    PublicTicketOutput,
)
from api.enums import ActionName, StatusName

logger = logging.getLogger("sgf_ap.api")


_STATUS_TEXT = {
    StatusName.REGISTERED.value: ("Registered", "Registrado", "El reporte fue recibido y está pendiente de revisión."),
    StatusName.VALIDATED.value: ("Validated", "Validado", "El reporte fue validado y continúa en el proceso de atención."),
    StatusName.PRIORITIZED.value: ("Prioritized", "Priorizado", "El reporte fue priorizado para su atención."),
    StatusName.ASSIGNED.value: ("Assigned", "Asignado", "El reporte fue asignado para atención."),
    StatusName.IN_PROGRESS.value: ("InProgress", "En atención", "La atención del reporte está en curso."),
    StatusName.BLOCKED.value: ("Blocked", "Bloqueado", "La atención está temporalmente bloqueada."),
    StatusName.PENDING_CLOSURE.value: ("PendingClosure", "Pendiente de cierre", "El resultado de la atención está pendiente de revisión."),
    StatusName.RESOLVED.value: ("Resolved", "Resuelto", "Se registró la resolución del reporte."),
}
_ACTION_LABELS = {
    ActionName.REGISTRATION.value: "Reporte registrado",
    ActionName.VALIDATION.value: "Reporte validado",
    ActionName.PRIORITIZATION.value: "Reporte priorizado",
    ActionName.ASSIGNMENT.value: "Atención programada",
    ActionName.ATTENTION.value: "Atención registrada",
    ActionName.BLOCKAGE.value: "Atención temporalmente bloqueada",
    ActionName.UNBLOCK.value: "Atención reanudada",
    ActionName.CLOSURE_REQUEST.value: "Resultado en revisión",
    ActionName.APPROVAL.value: "Reporte resuelto",
    ActionName.REJECTION.value: "El reporte continúa en atención",
}


class CitizenCursorError(ValueError):
    pass


class CitizenCursorCodec:
    VERSION = 1
    MAX_LENGTH = 512

    def __init__(self, secret: bytes) -> None:
        if type(secret) is not bytes or len(secret) < 32:
            raise ValueError("citizen cursor secret must contain at least 32 bytes")
        self._secret = secret

    def encode(self, scope: str, binding: str, timestamp: datetime, tie_breaker: str) -> str:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise CitizenCursorError("cursor datetime must be timezone-aware")
        if scope not in {"reports", "history"} or not binding or type(tie_breaker) is not str:
            raise CitizenCursorError("invalid cursor binding")
        if scope == "reports" and (
            not 1 <= len(tie_breaker) <= 24
            or any(ord(character) < 32 or character.isspace() or character in "/\\" for character in tie_breaker)
        ):
            raise CitizenCursorError("invalid report cursor ordering key")
        if scope == "history" and (not tie_breaker.isascii() or not tie_breaker.isdigit() or int(tie_breaker) <= 0):
            raise CitizenCursorError("invalid history cursor ordering key")
        payload = {"v": self.VERSION, "s": scope, "b": binding, "t": timestamp.isoformat(), "k": tie_breaker}
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        signature = hmac.new(self._secret, raw, hashlib.sha256).digest()
        result = base64.urlsafe_b64encode(raw + b"." + signature).decode().rstrip("=")
        if len(result) > self.MAX_LENGTH:
            raise CitizenCursorError("cursor is too long")
        return result

    def decode(self, cursor: str, scope: str, binding: str) -> tuple[datetime, str]:
        if type(cursor) is not str or not cursor or len(cursor) > self.MAX_LENGTH:
            raise CitizenCursorError("invalid cursor")
        try:
            encoded = cursor + "=" * (-len(cursor) % 4)
            signed = base64.b64decode(encoded, altchars=b"-_", validate=True)
            if base64.urlsafe_b64encode(signed).decode().rstrip("=") != cursor:
                raise CitizenCursorError("invalid cursor encoding")
            if len(signed) <= hashlib.sha256().digest_size:
                raise CitizenCursorError("invalid cursor")
            raw, signature = signed[:-hashlib.sha256().digest_size], signed[-hashlib.sha256().digest_size:]
            if not raw.endswith(b"."):
                raise CitizenCursorError("invalid cursor")
            raw = raw[:-1]
            expected = hmac.new(self._secret, raw, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                raise CitizenCursorError("invalid cursor")
            payload = json.loads(raw)
            timestamp = datetime.fromisoformat(payload["t"])
            if payload.get("v") != self.VERSION or payload.get("s") != scope or payload.get("b") != binding:
                raise CitizenCursorError("invalid cursor scope")
            if timestamp.tzinfo is None or timestamp.utcoffset() is None or not isinstance(payload["k"], str):
                raise CitizenCursorError("invalid cursor")
            tie_breaker = payload["k"]
            if scope == "reports":
                if not 1 <= len(tie_breaker) <= 24 or any(
                    ord(character) < 32 or character.isspace() or character in "/\\"
                    for character in tie_breaker
                ):
                    raise CitizenCursorError("invalid report cursor ordering key")
            elif scope == "history":
                if not tie_breaker.isascii() or not tie_breaker.isdigit() or int(tie_breaker) <= 0:
                    raise CitizenCursorError("invalid history cursor ordering key")
            return timestamp, payload["k"]
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, binascii.Error) as error:
            raise CitizenCursorError("invalid cursor") from error


def status_projection(value: object) -> tuple[str, str, str]:
    key = value.value if isinstance(value, StatusName) else value if isinstance(value, str) else ""
    if key not in _STATUS_TEXT:
        logger.warning("unrecognized citizen ticket status projected as unavailable")
    return _STATUS_TEXT.get(key, ("Unavailable", "Estado no disponible", "No es posible mostrar el avance en este momento."))


def action_projection(value: object) -> tuple[str, str]:
    key = value.value if isinstance(value, ActionName) else value if isinstance(value, str) else ""
    if key not in _ACTION_LABELS:
        logger.warning("unrecognized citizen history action projected as unavailable")
    return (key, _ACTION_LABELS.get(key, "Actualización no disponible")) if key in _ACTION_LABELS else ("Unavailable", "Actualización no disponible")


def list_item(row: dict) -> CitizenTicketListItem:
    status, label, _summary = status_projection(row.get("status"))
    return CitizenTicketListItem(row["code"], row["created_at"], status, label, row["failure_type_label"], row["last_updated_at"])


def public_output(row: dict) -> PublicTicketOutput:
    status, label, summary = status_projection(row.get("status"))
    return PublicTicketOutput(row["code"], status, label, row["last_updated_at"], summary)


from api.contracts import CitizenTicketDetailOutput


def detail_output(row: dict[str, Any], evidences: tuple) -> CitizenTicketDetailOutput:
    status, label, summary = status_projection(row.get("status"))
    return CitizenTicketDetailOutput(
        code=row["code"],
        created_at=row["created_at"],
        status=status,
        status_label=label,
        failure_type_label=row["failure_type_label"],
        last_updated_at=row["last_updated_at"],
        public_summary=summary,
        description=row["description"],
        formatted_address=formatted_address(row),
        contact_email=row["contact_email"],
        contact_phone=row["contact_phone"],
        email_notifications=row.get("email_notifications", False),
        evidences=evidences,
    )


def formatted_address(row: dict) -> str | None:
    if row.get("address_id") is None:
        return None
    road = f'{row["road_type_name"]} {row["road_number"]}'
    if row.get("road_suffix_letter_code"):
        road += row["road_suffix_letter_code"]
    if row.get("road_bis_code"):
        road += f' {row["road_bis_code"]}'
    if row.get("road_bis_suffix"):
        road += row["road_bis_suffix"]
    if row.get("road_quadrant_name"):
        road += f' {row["road_quadrant_name"]}'
    cross = str(row["cross_road_number"])
    if row.get("cross_suffix_letter_code"):
        cross += row["cross_suffix_letter_code"]
    if row.get("cross_bis_code"):
        cross += f' {row["cross_bis_code"]}'
    if row.get("cross_bis_suffix"):
        cross += row["cross_bis_suffix"]
    if row.get("cross_quadrant_name"):
        cross += f' {row["cross_quadrant_name"]}'
    result = f'{road} # {cross} - {row["door_plate_number"]}'
    if row.get("neighborhood_name"):
        result += f', {row["neighborhood_name"]}'
    return result


__all__ = ["CitizenCursorCodec", "CitizenCursorError", "action_projection", "detail_output", "formatted_address", "list_item", "public_output", "status_projection"]
