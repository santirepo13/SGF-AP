"""Reusable user-field validation rules.

These helpers return the original values unchanged.  In particular, email and
password values are never normalized here because authentication and uniqueness
semantics belong to the application and database respectively.
"""

from __future__ import annotations

import re
import unicodedata

from api.contracts import CitizenRegistrationInput, UserLoginInput
from api.errors import ApplicationError


_EMAIL_PATTERN = re.compile(
    r"^[^\s@]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$"
)


def validate_text_field(
    value: object,
    field: str,
    *,
    correlation_id: str | None = None,
    allow_whitespace: bool = False,
) -> str:
    """Validate a required string without coercing other Python types."""

    if type(value) is not str:
        raise ApplicationError.invalid_value(
            field,
            "El valor debe ser texto.",
            correlation_id=correlation_id,
        )
    if value == "" or (not allow_whitespace and not value.strip()):
        raise ApplicationError.required_field(field, correlation_id=correlation_id)
    return value


def validate_name(value: object, field: str, *, correlation_id: str | None = None) -> str:
    """Validate a personal name while allowing Unicode name punctuation."""

    value = validate_text_field(value, field, correlation_id=correlation_id)
    for character in value:
        category = unicodedata.category(character)
        if character.isspace() or character in "-'’ʼ" or category.startswith(("L", "M")):
            continue
        raise ApplicationError.invalid_value(
            field,
            "El nombre solo puede contener letras, espacios, guiones o apóstrofes.",
            correlation_id=correlation_id,
        )
    return value


def validate_email(value: object, *, correlation_id: str | None = None) -> str:
    """Validate email syntax and return the exact accepted spelling."""

    value = validate_text_field(value, "email", correlation_id=correlation_id, allow_whitespace=True)
    if _EMAIL_PATTERN.fullmatch(value) is None:
        raise ApplicationError.invalid_value(
            "email",
            "El correo electrónico no tiene un formato válido.",
            correlation_id=correlation_id,
        )
    return value


def validate_password(value: object, *, correlation_id: str | None = None) -> str:
    """Validate a password without trimming or otherwise transforming it."""

    if type(value) is not str:
        raise ApplicationError.invalid_value(
            "password",
            "El valor debe ser texto.",
            correlation_id=correlation_id,
        )
    if value == "":
        raise ApplicationError.required_field("password", correlation_id=correlation_id)
    return value


def validate_shared_user_fields(
    *,
    email: object,
    password: object,
    correlation_id: str | None = None,
) -> tuple[str, str]:
    """Validate fields shared by registration and future authentication."""

    return (
        validate_email(email, correlation_id=correlation_id),
        validate_password(password, correlation_id=correlation_id),
    )


def validate_user_registration_contract(
    data: CitizenRegistrationInput,
    *,
    correlation_id: str | None = None,
) -> CitizenRegistrationInput:
    """Validate the shared fields of a registration contract.

    Name-specific checks are deliberately left to ``registration_validation``.
    """

    if not isinstance(data, CitizenRegistrationInput):
        raise ApplicationError.invalid_value(
            "data",
            "La entrada no corresponde al contrato de registro.",
            correlation_id=correlation_id,
        )
    validate_shared_user_fields(
        email=data.email,
        password=data.password,
        correlation_id=correlation_id,
    )
    return data


def validate_user_login_contract(
    data: UserLoginInput,
    *,
    correlation_id: str | None = None,
) -> UserLoginInput:
    """Validate only the fields that form an authentication attempt."""

    if not isinstance(data, UserLoginInput):
        raise ApplicationError.invalid_value(
            "data",
            "La entrada no corresponde al contrato de ingreso.",
            correlation_id=correlation_id,
        )
    validate_shared_user_fields(
        email=data.email,
        password=data.password,
        correlation_id=correlation_id,
    )
    return data


# Explicit aliases make the shared rules convenient for callers without
# coupling the login flow to the registration module.
validate_login = validate_user_login_contract
validate_login_input = validate_user_login_contract
validate_email_format = validate_email
validate_non_empty_password = validate_password
validate_user_fields = validate_shared_user_fields


__all__ = [
    "validate_email",
    "validate_email_format",
    "validate_login",
    "validate_login_input",
    "validate_name",
    "validate_non_empty_password",
    "validate_password",
    "validate_shared_user_fields",
    "validate_user_fields",
    "validate_user_login_contract",
    "validate_text_field",
    "validate_user_registration_contract",
]
