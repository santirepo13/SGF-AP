"""Validation for password-recovery contracts without exposing proofs."""

from __future__ import annotations

import re

from api.contracts import (
    PasswordRecoveryRequestInput,
    PasswordRecoveryVerifyInput,
    PasswordResetInput,
)
from api.errors import ApplicationError

from .user_validation import validate_email, validate_text_field

_CODE = re.compile(r"^[0-9]{8}$")


def validate_recovery_request(data: PasswordRecoveryRequestInput, *, correlation_id: str | None = None) -> PasswordRecoveryRequestInput:
    if not isinstance(data, PasswordRecoveryRequestInput):
        raise ApplicationError.invalid_value("data", "La entrada no corresponde a la recuperación.", correlation_id=correlation_id)
    validate_email(data.email, correlation_id=correlation_id)
    return data


def validate_recovery_verify(data: PasswordRecoveryVerifyInput, *, correlation_id: str | None = None) -> PasswordRecoveryVerifyInput:
    if not isinstance(data, PasswordRecoveryVerifyInput):
        raise ApplicationError.invalid_value("data", "La entrada no corresponde a la recuperación.", correlation_id=correlation_id)
    validate_text_field(data.request_id, "request_id", correlation_id=correlation_id, allow_whitespace=True)
    if type(data.code) is not str:
        raise ApplicationError.invalid_value("code", "El código debe ser texto.", correlation_id=correlation_id)
    if data.code == "":
        raise ApplicationError.required_field("code", correlation_id=correlation_id)
    if _CODE.fullmatch(data.code) is None:
        raise ApplicationError.invalid_value("code", "El código debe tener ocho dígitos.", correlation_id=correlation_id)
    return data


def validate_password_reset(data: PasswordResetInput, *, correlation_id: str | None = None) -> PasswordResetInput:
    if not isinstance(data, PasswordResetInput):
        raise ApplicationError.invalid_value("data", "La entrada no corresponde a la recuperación.", correlation_id=correlation_id)
    validate_text_field(data.reset_token, "reset_token", correlation_id=correlation_id, allow_whitespace=True)
    validate_text_field(data.new_password, "new_password", correlation_id=correlation_id, allow_whitespace=True)
    validate_text_field(data.password_confirmation, "password_confirmation", correlation_id=correlation_id, allow_whitespace=True)
    if data.new_password != data.password_confirmation:
        raise ApplicationError.invalid_value(
            "password_confirmation",
            "La confirmación no coincide con la nueva contraseña.",
            correlation_id=correlation_id,
        )
    return data


__all__ = ["validate_password_reset", "validate_recovery_request", "validate_recovery_verify"]
