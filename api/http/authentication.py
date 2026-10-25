"""Central HTTP Basic authentication for the SGF-AP HTTP surface."""

from __future__ import annotations

import base64
import binascii
import hmac

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from api.config import APIConfig
from api.errors.http.exception_handlers import authentication_error_response


class BasicAuthenticator:
    """Validate an Authorization header against server-side API credentials."""

    def __init__(self, config: APIConfig) -> None:
        self._user = config.user.encode("utf-8")
        self._password = config.password.encode("utf-8")

    def is_authenticated(self, authorization: str | None) -> bool:
        """Return true only for a complete, valid HTTP Basic credential pair."""

        credentials = _parse_basic_credentials(authorization)
        if credentials is None:
            return False
        user, password = credentials
        user_matches = hmac.compare_digest(user.encode("utf-8"), self._user)
        password_matches = hmac.compare_digest(password.encode("utf-8"), self._password)
        return user_matches and password_matches


class BasicAuthenticationMiddleware(BaseHTTPMiddleware):
    """Reject unauthenticated requests before documentation or application routes run."""

    async def dispatch(self, request: Request, call_next) -> Response:
        config = getattr(request.app.state, "api_config", None)
        if not isinstance(config, APIConfig) or not BasicAuthenticator(config).is_authenticated(
            request.headers.get("Authorization")
        ):
            return authentication_error_response(request)
        return await call_next(request)


def _parse_basic_credentials(authorization: str | None) -> tuple[str, str] | None:
    """Parse Basic credentials without retaining invalid header content in diagnostics."""

    if authorization is None:
        return None
    scheme, separator, encoded = authorization.partition(" ")
    if scheme.lower() != "basic" or not separator or not encoded:
        return None
    try:
        decoded = base64.b64decode(encoded.strip(), validate=True).decode("utf-8")
    except (UnicodeDecodeError, binascii.Error, ValueError):
        return None
    user, separator, password = decoded.partition(":")
    if not separator:
        return None
    return user, password
