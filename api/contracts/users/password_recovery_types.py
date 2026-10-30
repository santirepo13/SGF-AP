"""Strict contracts for the three-step password-recovery flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from api.contracts.common_types import ensure_aware


@dataclass(frozen=True, slots=True)
class PasswordRecoveryRequestInput:
    email: str

    def __post_init__(self) -> None:
        if type(self.email) is not str:
            raise ValueError("email must be a string")


@dataclass(frozen=True, slots=True)
class PasswordRecoveryRequestOutput:
    request_id: str
    message: str


@dataclass(frozen=True, slots=True)
class PasswordRecoveryVerifyInput:
    request_id: str
    code: str = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.request_id) is not str or type(self.code) is not str:
            raise ValueError("request_id and code must be strings")


@dataclass(frozen=True, slots=True)
class PasswordRecoveryVerifyOutput:
    reset_token: str = field(repr=False)
    expires_at: datetime

    def __post_init__(self) -> None:
        if type(self.reset_token) is not str or not self.reset_token:
            raise ValueError("reset_token must be a non-empty string")
        ensure_aware(self.expires_at, "expires_at")


@dataclass(frozen=True, slots=True)
class PasswordResetInput:
    reset_token: str = field(repr=False)
    new_password: str = field(repr=False)
    password_confirmation: str = field(repr=False)

    def __post_init__(self) -> None:
        for name in ("reset_token", "new_password", "password_confirmation"):
            if type(getattr(self, name)) is not str:
                raise ValueError(f"{name} must be a string")


@dataclass(frozen=True, slots=True)
class PasswordResetOutput:
    completed_at: datetime

    def __post_init__(self) -> None:
        ensure_aware(self.completed_at, "completed_at")


__all__ = [
    "PasswordRecoveryRequestInput",
    "PasswordRecoveryRequestOutput",
    "PasswordRecoveryVerifyInput",
    "PasswordRecoveryVerifyOutput",
    "PasswordResetInput",
    "PasswordResetOutput",
]
