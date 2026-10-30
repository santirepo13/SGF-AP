"""Internal access-token contracts shared by authentication components."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from api.contracts.common_types import ensure_aware


@dataclass(frozen=True, slots=True)
class IssuedAccessToken:
    """Opaque access credential and the exact instant used as its expiry."""

    access_token: str = field(repr=False)
    expires_at: datetime

    def __post_init__(self) -> None:
        if type(self.access_token) is not str or not self.access_token:
            raise ValueError("access_token must be a non-empty string")
        _ensure_utc(self.expires_at, "expires_at")


@dataclass(frozen=True, slots=True)
class ValidatedAccessToken:
    """Trusted claims extracted only after a credential has been verified."""

    user_id: int
    token_id: str
    issued_at: datetime
    expires_at: datetime
    auth_version: int = 1

    def __post_init__(self) -> None:
        if type(self.user_id) is not int or self.user_id <= 0:
            raise ValueError("user_id must be a positive integer")
        if type(self.auth_version) is not int or self.auth_version <= 0:
            raise ValueError("auth_version must be a positive integer")
        if type(self.token_id) is not str or not self.token_id:
            raise ValueError("token_id must be a non-empty string")
        _ensure_utc(self.issued_at, "issued_at")
        _ensure_utc(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be after issued_at")


def _ensure_utc(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    ensure_aware(value, field_name)
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must use UTC")


__all__ = ["IssuedAccessToken", "ValidatedAccessToken"]
