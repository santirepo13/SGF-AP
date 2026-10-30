"""Small coordinator for restoring and invalidating a previously saved access."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol
from uuid import uuid4

from .access_storage import AccessStorage, AccessStorageError, StoredAccess
from .authentication import AuthenticationState, SUPPORTED_ROLE_NAMES


class AccessStatus(str, Enum):
    SIGNED_OUT = "signed_out"
    CHECKING = "checking"
    AUTHENTICATED = "authenticated"
    UNAVAILABLE = "unavailable"
    REAUTHENTICATION_REQUIRED = "reauthentication_required"
    INACTIVE = "inactive"


@dataclass(frozen=True, slots=True)
class AccessState:
    status: AccessStatus
    message: str | None = None


class CurrentUserConnector(Protocol):
    def current_user(self, *, access_token: str) -> object: ...


class AccessCoordinator:
    """Keep a candidate credential private until ``GET /users/me`` confirms it."""

    def __init__(
        self,
        authentication: AuthenticationState,
        storage: AccessStorage,
        connector: CurrentUserConnector | object,
    ) -> None:
        self.authentication = authentication
        self._storage = storage
        self._connector = connector
        self._state = AccessState(AccessStatus.SIGNED_OUT)
        self._candidate: StoredAccess | None = None
        self._generation = 0
        self._transition_lock = asyncio.Lock()
        self._storage_lock = asyncio.Lock()

    @property
    def state(self) -> AccessState:
        return self._state

    @property
    def access_allowed(self) -> bool:
        return self._state.status is AccessStatus.AUTHENTICATED and self.authentication.authenticated

    async def accept_login(
        self,
        *,
        user: Mapping[str, object],
        access_token: str,
        expires_at: datetime,
    ) -> AccessState:
        """Publish an accepted login immediately, then persist it best-effort."""

        record = StoredAccess(uuid4().hex, access_token, expires_at)
        async with self._transition_lock:
            self._generation += 1
            self._candidate = record
            self.authentication.establish(user=user, access_token=access_token, expires_at=expires_at)
            self._state = AccessState(AccessStatus.AUTHENTICATED)
        try:
            async with self._storage_lock:
                await self._storage.save(record)
        except AccessStorageError:
            # A valid current login remains usable even if persistence is down.
            pass
        return self._state

    async def restore(self) -> AccessState:
        """Load a protected candidate and validate it before showing private UI."""

        if self.authentication.authenticated or self._candidate is not None:
            return await self.recheck()

        async with self._transition_lock:
            if self._state.status is AccessStatus.CHECKING:
                return self._state
            self._generation += 1
            generation = self._generation
            self._state = AccessState(AccessStatus.CHECKING)

        try:
            candidate = await self._storage.load()
        except AccessStorageError:
            return await self._finish_without_candidate(
                generation,
                "No fue posible recuperar el acceso anterior. Ingresa nuevamente.",
            )
        if candidate is None:
            return await self._finish_without_candidate(generation, None)

        async with self._transition_lock:
            if generation != self._generation:
                return self._state
            self._candidate = candidate
        return await self._confirm(candidate, generation)

    async def recheck(self) -> AccessState:
        """Confirm the saved or in-memory credential when the app resumes."""

        async with self._transition_lock:
            if self._state.status is AccessStatus.CHECKING:
                return self._state
            candidate = self._candidate
            if candidate is None:
                session = self.authentication.session
                if session is None:
                    return self._state
                candidate = StoredAccess(uuid4().hex, session.access_token, session.expires_at)
                self._candidate = candidate
            self._generation += 1
            generation = self._generation
            self.authentication.clear()
            self._state = AccessState(AccessStatus.CHECKING)
        return await self._confirm(candidate, generation)

    async def retry(self) -> AccessState:
        return await (self.recheck() if self._candidate is not None else self.restore())

    async def show_login(self) -> AccessState:
        """Stop an unconfirmed restore without deleting a credential not rejected by the API."""

        async with self._transition_lock:
            self._generation += 1
            self.authentication.clear()
            self._state = AccessState(AccessStatus.SIGNED_OUT)
        return self._state

    async def sign_out(self) -> AccessState:
        """Explicitly remove the current credential and private in-memory state."""

        async with self._transition_lock:
            self._generation += 1
            candidate = self._candidate
            self._candidate = None
            self.authentication.clear()
            self._state = AccessState(AccessStatus.SIGNED_OUT)
        try:
            async with self._storage_lock:
                await self._storage.clear(candidate.record_id if candidate is not None else None)
        except AccessStorageError:
            pass
        return self._state

    async def forget_process(self) -> None:
        """Drop only memory when the app session disconnects; keep secure storage."""

        async with self._transition_lock:
            self._generation += 1
            self._candidate = None
            self.authentication.clear()
            self._state = AccessState(AccessStatus.SIGNED_OUT)

    async def _confirm(self, candidate: StoredAccess, generation: int) -> AccessState:
        try:
            response = await asyncio.to_thread(self._request_current_user, candidate.access_token)
        except BaseException:
            return await self._mark_unavailable(generation, candidate)

        status_code, payload = _response_parts(response)
        user = _confirmed_user(status_code, payload)
        if user is not None:
            async with self._transition_lock:
                if not self._is_current(generation, candidate):
                    return self._state
                self.authentication.establish(
                    user=user,
                    access_token=candidate.access_token,
                    expires_at=candidate.expires_at,
                )
                self._state = AccessState(AccessStatus.AUTHENTICATED)
                return self._state

        code = _error_code(payload)
        if code == "USR-001":
            return await self._invalidate(
                generation,
                candidate,
                AccessStatus.INACTIVE,
                "La cuenta no se encuentra habilitada.",
            )
        if code in {"USR-003", "USR-004"}:
            return await self._invalidate(
                generation,
                candidate,
                AccessStatus.REAUTHENTICATION_REQUIRED,
                "Tu acceso ya no está vigente. Ingresa nuevamente.",
            )
        if code == "USR-005":
            return await self._finish_without_candidate(
                generation,
                "Ingresa nuevamente para continuar.",
            )
        return await self._mark_unavailable(generation, candidate)

    def _request_current_user(self, access_token: str) -> object:
        method = getattr(self._connector, "current_user", None) or getattr(self._connector, "get_current_user", None)
        if not callable(method):
            raise TypeError("access connector does not expose current_user")
        return method(access_token=access_token)

    async def _invalidate(
        self,
        generation: int,
        candidate: StoredAccess,
        status: AccessStatus,
        message: str,
    ) -> AccessState:
        async with self._transition_lock:
            if not self._is_current(generation, candidate):
                return self._state
            self._generation += 1
            self._candidate = None
            self.authentication.clear()
            self._state = AccessState(status, message)
        try:
            async with self._storage_lock:
                await self._storage.clear(candidate.record_id)
        except AccessStorageError:
            pass
        return self._state

    async def _finish_without_candidate(self, generation: int, message: str | None) -> AccessState:
        async with self._transition_lock:
            if generation != self._generation:
                return self._state
            self._candidate = None
            self.authentication.clear()
            self._state = AccessState(AccessStatus.SIGNED_OUT, message)
            return self._state

    async def _mark_unavailable(self, generation: int, candidate: StoredAccess) -> AccessState:
        async with self._transition_lock:
            if not self._is_current(generation, candidate):
                return self._state
            self.authentication.clear()
            self._state = AccessState(
                AccessStatus.UNAVAILABLE,
                "No fue posible comprobar el acceso. Inténtalo nuevamente.",
            )
            return self._state

    def _is_current(self, generation: int, candidate: StoredAccess) -> bool:
        return self._generation == generation and self._candidate is not None and self._candidate.record_id == candidate.record_id


def _response_parts(response: object) -> tuple[int, object]:
    if isinstance(response, Mapping):
        status = response.get("status_code", response.get("status"))
        payload = response.get("payload", response)
    else:
        status = getattr(response, "status_code", getattr(response, "status", None))
        payload = getattr(response, "payload", None)
    return (status if type(status) is int else 0, payload)


def _confirmed_user(status_code: int, payload: object) -> dict[str, object] | None:
    if status_code != 200 or not isinstance(payload, Mapping) or set(payload) != {"success", "data", "error"}:
        return None
    user = payload.get("data")
    if payload.get("success") is not True or payload.get("error") is not None or not isinstance(user, Mapping):
        return None
    required = {"id", "first_name", "last_name", "email", "role_id", "role_name", "active"}
    if set(user) != required:
        return None
    if type(user["id"]) is not int or type(user["role_id"]) is not int or type(user["active"]) is not bool:
        return None
    if any(type(user[name]) is not str for name in ("first_name", "last_name", "email", "role_name")):
        return None
    if user["role_name"] not in SUPPORTED_ROLE_NAMES:
        return None
    return dict(user)


def _error_code(payload: object) -> str | None:
    if not isinstance(payload, Mapping) or payload.get("success") is not False:
        return None
    error = payload.get("error")
    if not isinstance(error, Mapping):
        return None
    code = error.get("code")
    return code if isinstance(code, str) else None


__all__ = [
    "AccessCoordinator",
    "AccessState",
    "AccessStatus",
    "CurrentUserConnector",
]
