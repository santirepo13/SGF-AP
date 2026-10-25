"""Central mapping between SGF-AP public error codes and HTTP statuses."""

from __future__ import annotations

from fastapi import status

from api.errors import ErrorCode

_ERROR_STATUSES: dict[str, int] = {
    ErrorCode.REQUIRED_FIELD_MISSING.value: status.HTTP_400_BAD_REQUEST,
    ErrorCode.INVALID_VALUE.value: status.HTTP_400_BAD_REQUEST,
    ErrorCode.RESOURCE_NOT_FOUND.value: status.HTTP_404_NOT_FOUND,
    ErrorCode.INVALID_REFERENCE.value: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.UNIQUE_CONFLICT.value: status.HTTP_409_CONFLICT,
    ErrorCode.INACTIVE_USER.value: status.HTTP_403_FORBIDDEN,
    ErrorCode.FORBIDDEN_OPERATION.value: status.HTTP_403_FORBIDDEN,
    ErrorCode.INVALID_TICKET_STATE.value: status.HTTP_409_CONFLICT,
    ErrorCode.CATALOG_VALUE_UNAVAILABLE.value: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.API_AUTHENTICATION_REQUIRED.value: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.PERSISTENCE_FAILURE.value: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.UNEXPECTED_ERROR.value: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.HTTP_ROUTE_NOT_FOUND.value: status.HTTP_404_NOT_FOUND,
    ErrorCode.HTTP_METHOD_NOT_ALLOWED.value: status.HTTP_405_METHOD_NOT_ALLOWED,
}


def status_for_error_code(code: ErrorCode | str) -> int:
    """Return the defined status or a safe internal-error default."""

    value = code.value if isinstance(code, ErrorCode) else code
    return _ERROR_STATUSES.get(value, status.HTTP_500_INTERNAL_SERVER_ERROR)
