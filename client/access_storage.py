"""Protected persistence for the minimum data needed to restore one access."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from typing import Any, Protocol


_STORAGE_KEY = "sgfap.access.v1"
_FORMAT_VERSION = 1


class AccessStorageError(RuntimeError):
    """The protected store could not safely provide the previous access."""


class AccessStorageCorrupted(AccessStorageError):
    """The stored value exists but is not a valid SGF-AP access record."""


class AccessStorageUnavailable(AccessStorageError):
    """The platform secure-store service is unavailable."""


@dataclass(frozen=True, slots=True)
class StoredAccess:
    """Opaque credential and its original expiry; never an authenticated identity."""

    record_id: str
    access_token: str = field(repr=False)
    expires_at: datetime

    def __post_init__(self) -> None:
        if type(self.record_id) is not str or not self.record_id:
            raise ValueError("record_id must be a non-empty string")
        if type(self.access_token) is not str or not self.access_token:
            raise ValueError("access_token must be a non-empty string")
        if not isinstance(self.expires_at, datetime) or self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("expires_at must include timezone information")


class AccessStorage(Protocol):
    async def load(self) -> StoredAccess | None: ...

    async def save(self, value: StoredAccess) -> None: ...

    async def clear(self, record_id: str | None = None) -> None: ...


class SecureAccessStorage:
    """Adapter for Flet SecureStorage, backed by the device secure keystore."""

    def __init__(self, backend: Any, *, key: str = _STORAGE_KEY) -> None:
        self._backend = backend
        self._key = key

    async def load(self) -> StoredAccess | None:
        try:
            raw = await self._backend.get(self._key)
        except BaseException as error:
            raise AccessStorageUnavailable("No se pudo acceder al almacenamiento protegido.") from error
        if raw is None:
            return None
        try:
            return _decode(raw)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            try:
                await self._backend.remove(self._key)
            except BaseException:
                pass
            raise AccessStorageCorrupted("No se pudo recuperar el acceso guardado.") from error

    async def save(self, value: StoredAccess) -> None:
        try:
            await self._backend.set(self._key, _encode(value))
        except BaseException as error:
            raise AccessStorageUnavailable("No se pudo guardar el acceso protegido.") from error

    async def clear(self, record_id: str | None = None) -> None:
        try:
            if record_id is not None:
                raw = await self._backend.get(self._key)
                if raw is None:
                    return
                try:
                    saved = _decode(raw)
                except (TypeError, ValueError, json.JSONDecodeError):
                    saved = None
                if saved is not None and saved.record_id != record_id:
                    return
            await self._backend.remove(self._key)
        except BaseException as error:
            raise AccessStorageUnavailable("No se pudo eliminar el acceso protegido.") from error


class UnavailableAccessStorage:
    """Safe fallback: no session is restored if the secure-store package is absent."""

    async def load(self) -> StoredAccess | None:
        raise AccessStorageUnavailable("El almacenamiento protegido no está disponible.")

    async def save(self, value: StoredAccess) -> None:
        raise AccessStorageUnavailable("El almacenamiento protegido no está disponible.")

    async def clear(self, record_id: str | None = None) -> None:
        raise AccessStorageUnavailable("El almacenamiento protegido no está disponible.")


class MemoryAccessStorage:
    """Test double; production code must use ``SecureAccessStorage`` instead."""

    def __init__(self, value: StoredAccess | None = None) -> None:
        self._value = value

    async def load(self) -> StoredAccess | None:
        return self._value

    async def save(self, value: StoredAccess) -> None:
        self._value = value

    async def clear(self, record_id: str | None = None) -> None:
        if record_id is None or (self._value is not None and self._value.record_id == record_id):
            self._value = None

    def __repr__(self) -> str:
        return f"{type(self).__name__}(has_value={self._value is not None})"


def _encode(value: StoredAccess) -> str:
    return json.dumps(
        {
            "version": _FORMAT_VERSION,
            "record_id": value.record_id,
            "access_token": value.access_token,
            "expires_at": value.expires_at.isoformat(),
        },
        separators=(",", ":"),
    )


def _decode(raw: object) -> StoredAccess:
    if not isinstance(raw, str):
        raise ValueError("stored access must be text")
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {"version", "record_id", "access_token", "expires_at"}:
        raise ValueError("stored access format is invalid")
    if value["version"] != _FORMAT_VERSION:
        raise ValueError("stored access version is unsupported")
    expires_at_value = value["expires_at"]
    if not isinstance(expires_at_value, str):
        raise ValueError("stored access expiry is invalid")
    expires_at = datetime.fromisoformat(expires_at_value.replace("Z", "+00:00"))
    return StoredAccess(
        record_id=value["record_id"],
        access_token=value["access_token"],
        expires_at=expires_at,
    )


__all__ = [
    "AccessStorage",
    "AccessStorageCorrupted",
    "AccessStorageError",
    "AccessStorageUnavailable",
    "MemoryAccessStorage",
    "SecureAccessStorage",
    "StoredAccess",
    "UnavailableAccessStorage",
]
