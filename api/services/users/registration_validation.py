"""Citizen-registration validation composed from shared user rules."""

from __future__ import annotations

from api.contracts import CitizenRegistrationInput
from api.errors import ApplicationError

from .user_validation import validate_email, validate_name, validate_password


def validate_registration(
    data: CitizenRegistrationInput,
    *,
    correlation_id: str | None = None,
) -> CitizenRegistrationInput:
    """Validate every registration field and preserve accepted values."""

    if not isinstance(data, CitizenRegistrationInput):
        raise ApplicationError.invalid_value(
            "data",
            "La entrada no corresponde al contrato de registro.",
            correlation_id=correlation_id,
        )
    validate_name(data.first_name, "first_name", correlation_id=correlation_id)
    validate_name(data.last_name, "last_name", correlation_id=correlation_id)
    validate_email(data.email, correlation_id=correlation_id)
    validate_password(data.password, correlation_id=correlation_id)
    return data


# Descriptive aliases for callers that use the file-level responsibility as
# the function name.
validate_registration_input = validate_registration
validate_citizen_registration = validate_registration


__all__ = [
    "validate_citizen_registration",
    "validate_registration",
    "validate_registration_input",
]
