"""Scrum 2 unit coverage for centralized HTTP error translation."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from fastapi import Request
from starlette.exceptions import HTTPException

from api.errors.http.exception_handlers import (
    application_error_handler,
    authentication_error_response,
    transport_http_exception_handler,
)
from api.errors.http.status_mapping import status_for_error_code
from api.errors import ApplicationError, ErrorCode


def request_for(*, correlation_id: str | None = None) -> Request:
    headers = [] if correlation_id is None else [(b"x-correlation-id", correlation_id.encode())]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers, "app": SimpleNamespace(state=SimpleNamespace())})


def payload(response) -> dict:
    return json.loads(response.body)


def test_error_status_mapping_covers_application_and_transport_codes() -> None:
    assert status_for_error_code(ErrorCode.REQUIRED_FIELD_MISSING) == 400
    assert status_for_error_code(ErrorCode.INVALID_REFERENCE) == 422
    assert status_for_error_code(ErrorCode.HTTP_ROUTE_NOT_FOUND) == 404
    assert status_for_error_code(ErrorCode.HTTP_METHOD_NOT_ALLOWED) == 405
    assert status_for_error_code(ErrorCode.API_AUTHENTICATION_REQUIRED) == 401
    assert status_for_error_code("unknown") == 500


def test_application_error_handler_returns_safe_envelope_with_request_correlation() -> None:
    response = asyncio.run(
        application_error_handler(
            request_for(correlation_id="corr-handler"),
            ApplicationError.invalid_value("password", "No permitido"),
        )
    )

    assert response.status_code == 400
    assert payload(response)["error"] == {
        "code": "VAL-002",
        "message": "Uno o más datos tienen un tipo, formato o valor inválido.",
        "correlation_id": "corr-handler",
        "details": [{"field": "password", "entity": None, "reason": "No permitido"}],
    }


def test_authentication_failure_uses_common_envelope_and_basic_challenge() -> None:
    response = authentication_error_response(request_for(correlation_id="corr-authentication"))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"
    assert payload(response)["error"] == {
        "code": "AUTH-001",
        "message": "Autenticación de API requerida o credenciales inválidas.",
        "correlation_id": "corr-authentication",
        "details": [],
    }


def test_missing_route_and_method_return_transport_catalog_errors_and_allow_header() -> None:
    not_found = asyncio.run(transport_http_exception_handler(request_for(), HTTPException(status_code=404)))
    method = asyncio.run(
        transport_http_exception_handler(
            request_for(),
            HTTPException(status_code=405, headers={"Allow": "GET, POST"}),
        )
    )

    assert payload(not_found)["error"]["code"] == "HTTP-001"
    assert method.status_code == 405
    assert payload(method)["error"]["code"] == "HTTP-002"
    assert method.headers["allow"] == "GET, POST"
