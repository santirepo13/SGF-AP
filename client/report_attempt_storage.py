"""Secure persistence for one uncertain citizen report attempt per account."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
from typing import Any, Protocol

_PREFIX = "sgfap.citizen-report-attempt.v1"
_VERSION = 1
_REQUIRED_PAYLOAD_FIELDS = frozenset({"request_key", "failure_type_id", "address_id", "description"})
_OPTIONAL_PAYLOAD_FIELDS = frozenset(
    {
        "contact_email",
        "contact_phone",
        "temporary_upload_ids",
        "email_notifications",
        "contribution_target_code",
    }
)


class ReportAttemptStorageError(RuntimeError):
    """The protected attempt store could not preserve a pending report."""


class ReportAttemptStorageUnavailable(ReportAttemptStorageError):
    """The platform keystore is unavailable."""


@dataclass(frozen=True, slots=True)
class StoredReportAttempt:
    """A recovery-safe report payload with no credential or image bytes."""

    account_id: int
    request_key: str
    payload: Mapping[str, object] = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.account_id) is not int or self.account_id <= 0:
            raise ValueError("account_id must be a positive integer")
        if type(self.request_key) is not str or not self.request_key or len(self.request_key) > 128:
            raise ValueError("request_key must be a non-empty string up to 128 characters")
        _validated_payload(self.payload, expected_request_key=self.request_key)


class ReportAttemptStorage(Protocol):
    async def load(self, account_id: int) -> StoredReportAttempt | None: ...
    async def save(self, value: StoredReportAttempt) -> None: ...
    async def clear(self, account_id: int, request_key: str | None = None) -> None: ...


class SecureReportAttemptStorage:
    """Store each account's pending report under a namespace separate from access."""

    def __init__(self, backend: Any, *, prefix: str = _PREFIX) -> None:
        self._backend = backend
        self._prefix = prefix

    async def load(self, account_id: int) -> StoredReportAttempt | None:
        key = self._key(account_id)
        try:
            raw = await self._backend.get(key)
        except BaseException as error:
            raise ReportAttemptStorageUnavailable("No se pudo acceder al almacenamiento protegido del reporte.") from error
        if raw is None:
            return None
        try:
            return _decode(raw, account_id)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            try:
                await self._backend.remove(key)
            except BaseException:
                pass
            raise ReportAttemptStorageError("No se pudo recuperar el intento de reporte guardado.") from error

    async def save(self, value: StoredReportAttempt) -> None:
        try:
            await self._backend.set(self._key(value.account_id), _encode(value))
        except BaseException as error:
            raise ReportAttemptStorageUnavailable("No se pudo guardar el intento de reporte protegido.") from error

    async def clear(self, account_id: int, request_key: str | None = None) -> None:
        key = self._key(account_id)
        try:
            if request_key is not None:
                raw = await self._backend.get(key)
                if raw is None:
                    return
                try:
                    saved = _decode(raw, account_id)
                except (TypeError, ValueError, json.JSONDecodeError):
                    saved = None
                if saved is not None and saved.request_key != request_key:
                    return
            await self._backend.remove(key)
        except BaseException as error:
            raise ReportAttemptStorageUnavailable("No se pudo eliminar el intento de reporte protegido.") from error

    def _key(self, account_id: int) -> str:
        if type(account_id) is not int or account_id <= 0:
            raise ValueError("account_id must be a positive integer")
        return f"{self._prefix}.{account_id}"


class UnavailableReportAttemptStorage:
    async def load(self, account_id: int) -> StoredReportAttempt | None:
        raise ReportAttemptStorageUnavailable("El almacenamiento protegido no está disponible.")

    async def save(self, value: StoredReportAttempt) -> None:
        raise ReportAttemptStorageUnavailable("El almacenamiento protegido no está disponible.")

    async def clear(self, account_id: int, request_key: str | None = None) -> None:
        raise ReportAttemptStorageUnavailable("El almacenamiento protegido no está disponible.")


class MemoryReportAttemptStorage:
    """Test double; production composition uses Flet SecureStorage."""

    def __init__(self) -> None:
        self._values: dict[int, StoredReportAttempt] = {}

    async def load(self, account_id: int) -> StoredReportAttempt | None:
        return self._values.get(account_id)

    async def save(self, value: StoredReportAttempt) -> None:
        self._values[value.account_id] = value

    async def clear(self, account_id: int, request_key: str | None = None) -> None:
        value = self._values.get(account_id)
        if value is not None and (request_key is None or value.request_key == request_key):
            del self._values[account_id]


def _encode(value: StoredReportAttempt) -> str:
    payload = _validated_payload(value.payload, expected_request_key=value.request_key)
    return json.dumps(
        {
            "version": _VERSION,
            "account_id": value.account_id,
            "request_key": value.request_key,
            "payload": payload,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def _decode(raw: object, account_id: int) -> StoredReportAttempt:
    if not isinstance(raw, str):
        raise ValueError("stored attempt must be text")
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {"version", "account_id", "request_key", "payload"}:
        raise ValueError("stored attempt format is invalid")
    if value["version"] != _VERSION or value["account_id"] != account_id:
        raise ValueError("stored attempt scope is invalid")
    return StoredReportAttempt(
        account_id=value["account_id"],
        request_key=value["request_key"],
        payload=value["payload"],
    )


def _validated_payload(value: Mapping[str, object], *, expected_request_key: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("report payload must be an object")
    if set(value) - (_REQUIRED_PAYLOAD_FIELDS | _OPTIONAL_PAYLOAD_FIELDS):
        raise ValueError("report payload contains unsupported fields")
    if not _REQUIRED_PAYLOAD_FIELDS <= set(value):
        raise ValueError("report payload is incomplete")
    request_key = value["request_key"]
    if request_key != expected_request_key or type(request_key) is not str:
        raise ValueError("report payload request key is invalid")
    if type(value["failure_type_id"]) is not int or value["failure_type_id"] <= 0:
        raise ValueError("report payload failure type is invalid")
    if type(value["address_id"]) is not int or value["address_id"] <= 0:
        raise ValueError("report payload address is invalid")
    if type(value["description"]) is not str:
        raise ValueError("report payload description is invalid")
    contact_email = value.get("contact_email")
    if "contact_email" in value and contact_email is not None and type(contact_email) is not str:
        raise ValueError("report payload contact email is invalid")
    contact_phone = value.get("contact_phone")
    if "contact_phone" in value and contact_phone is not None and type(contact_phone) is not str:
        raise ValueError("report payload contact phone is invalid")
    upload_ids = value.get("temporary_upload_ids")
    if "temporary_upload_ids" in value and (
        type(upload_ids) is not list
        or len(upload_ids) > 3
        or any(type(item) is not str for item in upload_ids)
    ):
        raise ValueError("report payload temporary uploads are invalid")
    notifications = value.get("email_notifications")
    if "email_notifications" in value and type(notifications) is not bool:
        raise ValueError("report payload notification preference is invalid")
    return json.loads(json.dumps(dict(value), ensure_ascii=False, allow_nan=False))


__all__ = [
    "MemoryReportAttemptStorage",
    "ReportAttemptStorage",
    "ReportAttemptStorageError",
    "ReportAttemptStorageUnavailable",
    "SecureReportAttemptStorage",
    "StoredReportAttempt",
    "UnavailableReportAttemptStorage",
]
