"""Validation shared by HTTP routes and direct citizen-ticket service calls."""

from __future__ import annotations

from api.contracts import (
    CitizenAttemptLookupInput,
    CitizenMatchInput,
    CitizenTicketCreateInput,
    UNSET,
    Unset,
)
from api.errors import ApplicationError
from api.services.users.user_validation import validate_email

_DEFAULT_DESCRIPTION_MAX_LENGTH = 4_000


def validate_citizen_ticket_create(
    data: CitizenTicketCreateInput,
    *,
    description_max_length: int = _DEFAULT_DESCRIPTION_MAX_LENGTH,
    correlation_id: str | None = None,
) -> CitizenTicketCreateInput:
    """Validate citizen-owned values without normalizing submitted text."""

    if not isinstance(data, CitizenTicketCreateInput):
        raise ApplicationError.invalid_value(
            "data",
            "La entrada no corresponde al contrato de registro ciudadano.",
            correlation_id=correlation_id,
        )
    if type(description_max_length) is not int or description_max_length <= 0:
        raise ValueError("description_max_length must be a positive integer")

    _validate_request_key(data.request_key, correlation_id=correlation_id)
    _validate_positive_int(data.failure_type_id, "failure_type_id", correlation_id=correlation_id)
    _validate_positive_int(data.address_id, "address_id", correlation_id=correlation_id)
    _validate_description(data.description, maximum=description_max_length, correlation_id=correlation_id)
    _validate_contact_email(data.contact_email, correlation_id=correlation_id)
    _validate_contact_phone(data.contact_phone, correlation_id=correlation_id)
    _validate_temporary_upload_ids(data.temporary_upload_ids, correlation_id=correlation_id)
    _validate_email_notifications(data.email_notifications, correlation_id=correlation_id)
    return data


def validate_citizen_match(
    data: CitizenMatchInput,
    *,
    correlation_id: str | None = None,
) -> CitizenMatchInput:
    if not isinstance(data, CitizenMatchInput):
        raise ApplicationError.invalid_value(
            "data",
            "La entrada no corresponde a la búsqueda de coincidencias.",
            correlation_id=correlation_id,
        )
    _validate_positive_int(data.address_id, "address_id", correlation_id=correlation_id)
    _validate_positive_int(data.failure_type_id, "failure_type_id", correlation_id=correlation_id)
    return data


def validate_citizen_attempt_lookup(
    data: CitizenAttemptLookupInput,
    *,
    correlation_id: str | None = None,
) -> CitizenAttemptLookupInput:
    if not isinstance(data, CitizenAttemptLookupInput):
        raise ApplicationError.invalid_value(
            "data",
            "La entrada no corresponde a la recuperación del intento ciudadano.",
            correlation_id=correlation_id,
        )
    _validate_request_key(data.request_key, correlation_id=correlation_id)
    return data


def effective_email_notifications(value: bool | Unset) -> bool:
    """Resolve the initial false default only after input validation."""

    if value is UNSET:
        return False
    if type(value) is not bool:
        raise ValueError("email_notifications must be a boolean after validation")
    return value


def _validate_request_key(value: object, *, correlation_id: str | None) -> None:
    if type(value) is not str:
        raise ApplicationError.invalid_value(
            "request_key",
            "La clave del intento debe ser texto.",
            correlation_id=correlation_id,
        )
    if value == "":
        raise ApplicationError.required_field("request_key", correlation_id=correlation_id)
    if len(value) > 128:
        raise ApplicationError.invalid_value(
            "request_key",
            "La clave del intento supera la longitud permitida.",
            correlation_id=correlation_id,
        )


def _validate_positive_int(value: object, field: str, *, correlation_id: str | None) -> None:
    if type(value) is not int or value <= 0:
        raise ApplicationError.invalid_value(
            field,
            "El identificador debe ser un entero positivo.",
            correlation_id=correlation_id,
        )


def _validate_description(value: object, *, maximum: int, correlation_id: str | None) -> None:
    if type(value) is not str:
        raise ApplicationError.invalid_value(
            "description",
            "La descripción debe ser texto.",
            correlation_id=correlation_id,
        )
    if not value.strip():
        raise ApplicationError.required_field("description", correlation_id=correlation_id)
    if len(value) > maximum:
        raise ApplicationError.invalid_value(
            "description",
            "La descripción supera la longitud permitida.",
            correlation_id=correlation_id,
        )


def _validate_contact_email(value: str | None | Unset, *, correlation_id: str | None) -> None:
    if value is UNSET or value is None:
        return
    if type(value) is not str:
        raise ApplicationError.invalid_value(
            "contact_email",
            "El correo de contacto debe ser texto.",
            correlation_id=correlation_id,
        )
    try:
        validate_email(value, correlation_id=correlation_id)
    except ApplicationError as error:
        raise ApplicationError.invalid_value(
            "contact_email",
            "El correo de contacto no tiene un formato válido.",
            correlation_id=correlation_id,
            cause=error,
        ) from error


def _validate_contact_phone(value: str | None | Unset, *, correlation_id: str | None) -> None:
    if value is UNSET or value is None:
        return
    if type(value) is not str:
        raise ApplicationError.invalid_value(
            "contact_phone",
            "El teléfono de contacto debe ser texto.",
            correlation_id=correlation_id,
        )
    if not value or len(value) > 32:
        raise ApplicationError.invalid_value(
            "contact_phone",
            "El teléfono de contacto no cumple la longitud permitida.",
            correlation_id=correlation_id,
        )


def _validate_temporary_upload_ids(value: list[str] | Unset, *, correlation_id: str | None) -> None:
    if value is UNSET:
        return
    if type(value) is not list:
        raise ApplicationError.invalid_value(
            "temporary_upload_ids",
            "Las referencias temporales deben ser una lista.",
            correlation_id=correlation_id,
        )
    if len(value) > 3:
        raise ApplicationError.invalid_value(
            "temporary_upload_ids",
            "Se permiten hasta tres referencias temporales.",
            correlation_id=correlation_id,
        )
    if any(type(item) is not str or not item for item in value):
        raise ApplicationError.invalid_value(
            "temporary_upload_ids",
            "Cada referencia temporal debe ser texto opaco.",
            correlation_id=correlation_id,
        )
    if len(set(value)) != len(value):
        raise ApplicationError.invalid_value(
            "temporary_upload_ids",
            "Las referencias temporales no pueden repetirse.",
            correlation_id=correlation_id,
        )


def _validate_email_notifications(value: bool | Unset, *, correlation_id: str | None) -> None:
    if value is UNSET:
        return
    if type(value) is not bool:
        raise ApplicationError.invalid_value(
            "email_notifications",
            "La preferencia de correo debe ser verdadera o falsa.",
            correlation_id=correlation_id,
        )


__all__ = [
    "effective_email_notifications",
    "validate_citizen_attempt_lookup",
    "validate_citizen_match",
    "validate_citizen_ticket_create",
]
