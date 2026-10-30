"""In-memory authenticated state for the current client process only."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from types import MappingProxyType


SUPPORTED_ROLE_NAMES = frozenset({"Citizen", "Operator", "Coordinator", "Crew", "Admin"})
_PUBLIC_USER_FIELDS = frozenset({"id", "first_name", "last_name", "email", "role_id", "role_name", "active"})


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    """Complete access state established atomically after an accepted login."""

    user: Mapping[str, object]
    access_token: str = field(repr=False)
    expires_at: datetime

    def __post_init__(self) -> None:
        if type(self.access_token) is not str or not self.access_token:
            raise ValueError("access_token must be a non-empty string")
        if not isinstance(self.expires_at, datetime) or self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("expires_at must include timezone information")
        if not isinstance(self.user, Mapping) or set(self.user) != _PUBLIC_USER_FIELDS:
            raise ValueError("user must contain exactly the public user fields")
        if type(self.user["id"]) is not int or type(self.user["role_id"]) is not int or type(self.user["active"]) is not bool:
            raise ValueError("user must contain a valid public identity")
        if any(type(self.user[name]) is not str for name in ("first_name", "last_name", "email", "role_name")):
            raise ValueError("user must contain valid public text fields")
        role_name = self.user["role_name"]
        if role_name not in SUPPORTED_ROLE_NAMES:
            raise ValueError("user must contain an approved role_name")

    def public_snapshot(self) -> dict[str, object]:
        """Return only non-sensitive data suitable for an in-process view refresh."""

        return {"user": dict(self.user), "expires_at": self.expires_at.isoformat()}


class AuthenticationState:
    """Own the unauthenticated/authenticated transition without persistence."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._session: AuthenticatedSession | None = None

    @property
    def session(self) -> AuthenticatedSession | None:
        with self._lock:
            return self._session

    @property
    def authenticated(self) -> bool:
        return self.session is not None

    def establish(
        self,
        *,
        user: Mapping[str, object],
        access_token: str,
        expires_at: datetime,
    ) -> AuthenticatedSession:
        """Validate all three login outputs before publishing any of them."""

        session = AuthenticatedSession(
            user=MappingProxyType(dict(user)),
            access_token=access_token,
            expires_at=expires_at,
        )
        with self._lock:
            self._session = session
        return session

    def clear(self) -> None:
        with self._lock:
            self._session = None

    def access_token_for_request(self) -> str | None:
        """Read a current token at request construction time, never from globals."""

        session = self.session
        return None if session is None else session.access_token

    def public_snapshot(self) -> dict[str, object] | None:
        session = self.session
        return None if session is None else session.public_snapshot()


AuthState = AuthenticationState


__all__ = [
    "AuthenticatedSession",
    "AuthenticationState",
    "AuthState",
    "SUPPORTED_ROLE_NAMES",
]
