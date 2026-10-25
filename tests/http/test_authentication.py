"""Coverage for centralized HTTP Basic authentication."""

from __future__ import annotations

import asyncio
import base64
from types import SimpleNamespace

from fastapi import Request
from fastapi.responses import JSONResponse

from api.config import APIConfig
from api.http.authentication import BasicAuthenticationMiddleware, BasicAuthenticator


def _basic_header(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _request(config: APIConfig, authorization: str | None = None) -> Request:
    headers = [] if authorization is None else [(b"authorization", authorization.encode("ascii"))]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/docs",
            "headers": headers,
            "app": SimpleNamespace(state=SimpleNamespace(api_config=config)),
        }
    )


def test_basic_authenticator_requires_a_valid_basic_user_and_password_pair() -> None:
    authenticator = BasicAuthenticator(APIConfig(port=8002, user="connector", password="secret"))

    assert authenticator.is_authenticated(_basic_header("connector", "secret")) is True
    assert authenticator.is_authenticated(_basic_header("connector", "incorrect")) is False
    assert authenticator.is_authenticated(_basic_header("unknown", "secret")) is False
    assert authenticator.is_authenticated(None) is False
    assert authenticator.is_authenticated("Bearer token") is False
    assert authenticator.is_authenticated("Basic malformed") is False


def test_authentication_middleware_challenges_missing_credentials_and_allows_valid_ones() -> None:
    config = APIConfig(port=8002, user="connector", password="secret")
    middleware = BasicAuthenticationMiddleware(lambda scope, receive, send: None)

    async def accepted(request: Request) -> JSONResponse:
        return JSONResponse({"accepted": True})

    rejected = asyncio.run(middleware.dispatch(_request(config), accepted))
    allowed = asyncio.run(middleware.dispatch(_request(config, _basic_header("connector", "secret")), accepted))

    assert rejected.status_code == 401
    assert rejected.headers["www-authenticate"] == "Basic"
    assert b'"code":"AUTH-001"' in rejected.body
    assert allowed.status_code == 200
    assert allowed.body == b'{"accepted":true}'
