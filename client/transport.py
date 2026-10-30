"""Small HTTP transport used by the packaged Flet client.

The server-side executable connector remains in ``test_local_connector.py`` for
full API plans.  The mobile app uses this isolated transport so packaging it
does not pull server tests, database tooling, or local test credentials into an
APK.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass
import json
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from config import ConnectorConfig

_TIMEOUT_SECONDS = 10


@dataclass(frozen=True, slots=True)
class ConnectorResponse:
    status_code: int
    headers: dict[str, str]
    payload: dict[str, Any]


class ConnectorError(Exception):
    """Safe client failure that never includes credentials or request bodies."""


class ConnectorTransportError(ConnectorError):
    """A transport failure whose remote outcome may be unknown."""

    def __init__(self, message: str, *, request_sent: bool | None = None) -> None:
        super().__init__(message)
        self.request_sent = request_sent


class ConnectorTimeoutError(ConnectorTransportError):
    """The remote endpoint did not respond before the timeout."""


class ConnectorResponseError(ConnectorError):
    """The endpoint returned a body outside the public response envelope."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_sent = True


class RegistrationTransport:
    """Send the one public registration operation used by the mobile UI."""

    def __init__(self, config: ConnectorConfig, *, opener: Any | None = None) -> None:
        self._config = config
        self._opener = opener or build_opener()

    def register_citizen(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
    ) -> ConnectorResponse:
        body = json.dumps(
            {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "password": password,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        token = base64.b64encode(
            f"{self._config.user}:{self._config.password}".encode("utf-8")
        ).decode("ascii")
        request = Request(
            f"{self._config.base_url}/users/register",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Basic {token}",
            },
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=_TIMEOUT_SECONDS) as response:
                return _decode_response(response.status, response.headers, response.read())
        except HTTPError as error:
            return _decode_response(error.code, error.headers, error.read())
        except socket.timeout as error:
            raise ConnectorTimeoutError(
                "No se recibió una respuesta; el resultado remoto puede ser desconocido.",
                request_sent=None,
            ) from error
        except URLError as error:
            if isinstance(error.reason, socket.timeout):
                raise ConnectorTimeoutError(
                    "No se recibió una respuesta; el resultado remoto puede ser desconocido.",
                    request_sent=None,
                ) from error
            raise ConnectorTransportError(
                "No fue posible conectar con el servicio; el resultado remoto puede ser desconocido.",
                request_sent=False,
            ) from error
        except OSError as error:
            raise ConnectorTransportError(
                "La conexión con el servicio fue interrumpida; el resultado remoto puede ser desconocido.",
                request_sent=None,
            ) from error


def _decode_response(status_code: int, headers: Any, content: bytes) -> ConnectorResponse:
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConnectorResponseError(
            "El servicio devolvió una respuesta no válida.",
            status_code=status_code,
        ) from error
    if not isinstance(payload, dict) or not {"success", "data", "error"}.issubset(payload):
        raise ConnectorResponseError(
            "El servicio devolvió un formato de respuesta incompatible.",
            status_code=status_code,
        )
    return ConnectorResponse(
        status_code=status_code,
        headers=_safe_headers(headers),
        payload=payload,
    )


def _safe_headers(headers: Any) -> dict[str, str]:
    if headers is None or not hasattr(headers, "items"):
        return {}
    allowed = {"content-type", "www-authenticate", "x-correlation-id"}
    return {
        str(name): str(value)
        for name, value in headers.items()
        if str(name).lower() in allowed
    }


__all__ = [
    "ConnectorError",
    "ConnectorResponse",
    "ConnectorResponseError",
    "ConnectorTimeoutError",
    "ConnectorTransportError",
    "RegistrationTransport",
]
