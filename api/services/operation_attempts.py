"""Deterministic digesting and safe result restoration for idempotent operations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import hashlib
import json
from typing import Any

from api.contracts import (
    CitizenMatchOutput,
    CitizenTicketConfirmation,
    CitizenTicketCreateInput,
    CitizenTicketRegistrationOutput,
    UNSET,
)

_REGISTER_CITIZEN_SCHEMA_VERSION = "1"


def citizen_registration_digest(data: CitizenTicketCreateInput) -> str:
    """Hash the complete typed intent while retaining omitted-versus-null fields."""

    payload = {
        "schema_version": _REGISTER_CITIZEN_SCHEMA_VERSION,
        "operation": "TicketService.register_citizen",
        "request_key": data.request_key,
        "failure_type_id": data.failure_type_id,
        "address_id": data.address_id,
        "description": data.description,
        "contact_email": _intent_value(data.contact_email),
        "contact_phone": _intent_value(data.contact_phone),
        "temporary_upload_ids": _intent_value(data.temporary_upload_ids),
        "email_notifications": _intent_value(data.email_notifications),
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def registration_result_payload(result: CitizenTicketRegistrationOutput) -> dict[str, object]:
    """Persist only the whitelisted, public result representation."""

    return {
        "request_key": result.request_key,
        "outcome": result.outcome,
        "ticket": _confirmation_payload(result.ticket),
        "matches": [_match_payload(match) for match in result.matches],
    }


def registration_result_from_payload(payload: Mapping[str, object]) -> CitizenTicketRegistrationOutput:
    """Reconstruct a typed public result from a committed ledger payload."""

    if set(payload) != {"request_key", "outcome", "ticket", "matches"}:
        raise ValueError("operation attempt result has an incompatible shape")
    request_key = payload["request_key"]
    outcome = payload["outcome"]
    raw_ticket = payload["ticket"]
    raw_matches = payload["matches"]
    if type(request_key) is not str or type(outcome) is not str or not isinstance(raw_matches, list):
        raise ValueError("operation attempt result has incompatible values")
    ticket = _confirmation_from_payload(raw_ticket)
    matches = tuple(_match_from_payload(item) for item in raw_matches)
    return CitizenTicketRegistrationOutput(
        request_key=request_key,
        outcome=outcome,
        ticket=ticket,
        matches=matches,
    )


def _intent_value(value: object) -> object:
    if value is UNSET:
        return {"state": "unset"}
    if isinstance(value, list):
        return list(value)
    return value


def _confirmation_payload(value: CitizenTicketConfirmation | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "code": value.code,
        "created_at": value.created_at.isoformat(),
        "status": value.status,
        "evidence_count": value.evidence_count,
    }


def _match_payload(value: CitizenMatchOutput) -> dict[str, object]:
    return {
        "code": value.code,
        "status": value.status,
        "created_at": value.created_at.isoformat(),
        "progress_label": value.progress_label,
    }


def _confirmation_from_payload(value: object) -> CitizenTicketConfirmation | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {"code", "created_at", "status", "evidence_count"}:
        raise ValueError("operation attempt ticket result has an incompatible shape")
    return CitizenTicketConfirmation(
        code=_required_str(value, "code"),
        created_at=_datetime(value, "created_at"),
        status=_required_str(value, "status"),
        evidence_count=_required_int(value, "evidence_count"),
    )


def _match_from_payload(value: object) -> CitizenMatchOutput:
    if not isinstance(value, Mapping) or set(value) != {"code", "status", "created_at", "progress_label"}:
        raise ValueError("operation attempt match result has an incompatible shape")
    return CitizenMatchOutput(
        code=_required_str(value, "code"),
        status=_required_str(value, "status"),
        created_at=_datetime(value, "created_at"),
        progress_label=_required_str(value, "progress_label"),
    )


def _required_str(value: Mapping[str, object], field: str) -> str:
    result = value.get(field)
    if type(result) is not str:
        raise ValueError(f"{field} must be a string")
    return result


def _required_int(value: Mapping[str, object], field: str) -> int:
    result = value.get(field)
    if type(result) is not int:
        raise ValueError(f"{field} must be an integer")
    return result


def _datetime(value: Mapping[str, object], field: str) -> datetime:
    raw = _required_str(value, field)
    try:
        result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO datetime") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{field} must include timezone information")
    return result


__all__ = [
    "citizen_registration_digest",
    "registration_result_from_payload",
    "registration_result_payload",
]
