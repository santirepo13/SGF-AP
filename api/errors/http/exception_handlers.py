"""FastAPI exception handlers that preserve SGF-AP's public error contract."""

from __future__ import annotations

from collections.abc import Mapping
import json
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from api.contracts import ErrorDetail, ExecutionContext
from api.errors import ApplicationError, ErrorCode, ErrorHandler
from api.http.context import correlation_id_for_request
from api.http.responses import error_response

logger = logging.getLogger("sgf_ap.api")


_NO_STORE_PATHS = frozenset({
    "/users/login",
    "/users/me",
    "/users/password-recovery/request",
    "/users/password-recovery/verify",
    "/users/password-recovery/complete",
})


def register_http_error_handlers(app: FastAPI) -> None:
    """Register the application's single HTTP error translation boundary."""

    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(json.JSONDecodeError, malformed_json_handler)
    app.add_exception_handler(StarletteHTTPException, transport_http_exception_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)


async def application_error_handler(request: Request, error: ApplicationError) -> Response:
    context = _http_context(request)
    return _with_cache_policy(
        request,
        error_response(ErrorHandler.to_public(error, context), headers=_headers_for_application_error(error)),
    )


def authentication_error_response(request: Request) -> Response:
    """Build the common HTTP Basic challenge response without exposing credentials."""

    context = _http_context(request)
    error = ApplicationError.with_code(ErrorCode.API_AUTHENTICATION_REQUIRED, correlation_id=context.correlation_id)
    return _with_cache_policy(
        request,
        error_response(ErrorHandler.to_public(error, context), headers=_headers_for_application_error(error)),
    )


async def request_validation_error_handler(request: Request, error: RequestValidationError) -> Response:
    context = _http_context(request)
    errors = error.errors()
    code = ErrorCode.REQUIRED_FIELD_MISSING if errors and all(_is_missing(item) for item in errors) else ErrorCode.INVALID_VALUE
    details = tuple(_validation_detail(item) for item in errors) or (
        ErrorDetail(None, None, "La solicitud no cumple el formato esperado."),
    )
    application_error = ApplicationError.with_code(code, details=details, correlation_id=context.correlation_id)
    return _with_cache_policy(request, error_response(ErrorHandler.to_public(application_error, context)))


async def malformed_json_handler(request: Request, error: json.JSONDecodeError) -> Response:
    context = _http_context(request)
    application_error = ApplicationError.invalid_value(
        None,
        "El cuerpo de la solicitud debe contener JSON válido.",
        correlation_id=context.correlation_id,
        cause=error,
    )
    return _with_cache_policy(request, error_response(ErrorHandler.to_public(application_error, context)))


async def transport_http_exception_handler(request: Request, error: StarletteHTTPException) -> Response:
    context = _http_context(request)
    if error.status_code == 404:
        application_error = ApplicationError.with_code(ErrorCode.HTTP_ROUTE_NOT_FOUND, correlation_id=context.correlation_id)
        return _with_cache_policy(request, error_response(ErrorHandler.to_public(application_error, context)))
    if error.status_code == 405:
        application_error = ApplicationError.with_code(ErrorCode.HTTP_METHOD_NOT_ALLOWED, correlation_id=context.correlation_id)
        headers = _allow_header(error.headers)
        return _with_cache_policy(request, error_response(ErrorHandler.to_public(application_error, context), headers=headers))

    application_error = ApplicationError.unexpected(correlation_id=context.correlation_id, cause=error)
    return _with_cache_policy(
        request,
        error_response(ErrorHandler.to_public(application_error, context), status_code=error.status_code),
    )


async def unexpected_exception_handler(request: Request, error: Exception) -> Response:
    context = _http_context(request)
    logger.error("http_unexpected_error", extra={"correlation_id": context.correlation_id})
    return _with_cache_policy(request, error_response(ErrorHandler.handle(error, context)))


def _http_context(request: Request) -> ExecutionContext:
    return ExecutionContext(operation="HTTP", correlation_id=correlation_id_for_request(request), actor=None)


def _with_cache_policy(request: Request, response: Response) -> Response:
    if request.url.path in _NO_STORE_PATHS:
        response.headers["Cache-Control"] = "no-store"
    return response


def _is_missing(error: Mapping[str, Any]) -> bool:
    return str(error.get("type", "")).endswith("missing")


def _validation_detail(error: Mapping[str, Any]) -> ErrorDetail:
    location = error.get("loc", ())
    parts = tuple(str(part) for part in location) if isinstance(location, (tuple, list)) else ()
    field_parts = parts[1:] if parts and parts[0] in {"body", "path", "query", "header"} else parts
    field = ".".join(field_parts) or None
    reason = "El dato obligatorio no fue enviado." if _is_missing(error) else "El valor no corresponde con el formato esperado."
    return ErrorDetail(field=field, entity=None, reason=reason)


def _headers_for_application_error(error: ApplicationError) -> dict[str, str] | None:
    if error.code is ErrorCode.API_AUTHENTICATION_REQUIRED:
        return {"WWW-Authenticate": "Basic"}
    return None


def _allow_header(headers: Any) -> dict[str, str] | None:
    if headers is None:
        return None
    for name, value in headers.items():
        if name.lower() == "allow":
            return {"Allow": value}
    return None
