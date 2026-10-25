"""Serialization of application results into stable JSON HTTP responses."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import date, datetime, time
from enum import Enum
from typing import Any

from fastapi.responses import JSONResponse

from api.contracts import ErrorOutput, OperationResult, UNSET
from api.errors import ApplicationError, ErrorHandler
from api.errors.http.status_mapping import status_for_error_code


def operation_response(result: OperationResult[Any], *, success_status: int = 200) -> JSONResponse:
    """Return the public success/data/error envelope for a completed operation."""

    if not result.success:
        if result.error is None:
            error = ErrorHandler.handle(ApplicationError.unexpected())
            return error_response(error)
        return error_response(result.error)

    try:
        payload = {"success": True, "data": to_json_value(result.data), "error": None}
    except BaseException as exc:
        error = ErrorHandler.handle(ApplicationError.unexpected(cause=exc))
        return error_response(error)
    return JSONResponse(status_code=success_status, content=payload)


def error_response(error: ErrorOutput, *, status_code: int | None = None, headers: dict[str, str] | None = None) -> JSONResponse:
    """Return a sanitized failed-operation envelope from a public error contract."""

    return JSONResponse(
        status_code=status_code or status_for_error_code(error.code),
        headers=headers,
        content={"success": False, "data": None, "error": to_json_value(error)},
    )


def to_json_value(value: Any) -> Any:
    """Serialize only public contract values and standard JSON-compatible types."""

    if value is UNSET:
        raise TypeError("UNSET is internal and cannot be serialized")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return to_json_value(value.value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, (list, tuple)):
        return [to_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_json_value(item) for key, item in value.items()}
    raise TypeError("value is not a supported public response type")
