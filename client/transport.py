"""HTTP transport used by the packaged Flet client."""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from io import BytesIO
import re
import secrets
import json
import socket
from typing import Any, BinaryIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from config import ConnectorConfig

_TIMEOUT_SECONDS = 10


@dataclass(frozen=True, slots=True)
class ConnectorResponse:
    status_code: int
    headers: dict[str, str]
    payload: dict[str, Any] = field(repr=False)


@dataclass(frozen=True, slots=True)
class MultipartFile:
    field_name: str
    filename: str
    media_type: str | None
    stream_factory: Callable[[], BinaryIO] = field(repr=False)
    size_bytes: int


@dataclass(frozen=True, slots=True)
class BinaryConnectorResponse:
    status_code: int
    headers: dict[str, str]
    stream: BinaryIO = field(repr=False)


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


class _NoRedirectHandler(HTTPRedirectHandler):
    """Return redirects to the controller instead of replaying credentials."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class RegistrationTransport:
    """Send public access requests and authenticated account checks."""

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        opener: Any | None = None,
        access_token_supplier: Callable[[], str | None] | None = None,
    ) -> None:
        self._config = config
        self._opener = opener or build_opener(_NoRedirectHandler())
        self._access_token_supplier = access_token_supplier

    def for_access_token(self, access_token: str) -> RegistrationTransport:
        if (
            type(access_token) is not str
            or not access_token
            or "\r" in access_token
            or "\n" in access_token
        ):
            raise ValueError("access_token must be a valid non-empty string")
        return RegistrationTransport(
            self._config,
            opener=self._opener,
            access_token_supplier=lambda: access_token,
        )

    def register_citizen(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
    ) -> ConnectorResponse:
        return self.post_json(
            "/users/register",
            {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "password": password,
            },
        )

    def login(self, *, email: str, password: str) -> ConnectorResponse:
        """Submit exact credentials without attaching an earlier user token."""

        return self.post_json("/users/login", {"email": email, "password": password})

    def current_user(self, *, access_token: str) -> ConnectorResponse:
        """Confirm the current account using one candidate access credential."""

        return self._request("GET", "/users/me", access_token=access_token)

    def request_password_recovery(self, *, email: str) -> ConnectorResponse:
        return self.post_json("/users/password-recovery/request", {"email": email})

    def verify_password_recovery(self, *, request_id: str, code: str) -> ConnectorResponse:
        return self.post_json("/users/password-recovery/verify", {"request_id": request_id, "code": code})

    def complete_password_recovery(
        self,
        *,
        reset_token: str,
        new_password: str,
        password_confirmation: str,
    ) -> ConnectorResponse:
        return self.post_json(
            "/users/password-recovery/complete",
            {
                "reset_token": reset_token,
                "new_password": new_password,
                "password_confirmation": password_confirmation,
            },
        )

    get_current_user = current_user

    def post_json(
        self,
        path: str,
        body_values: Mapping[str, object],
        *,
        requires_identity: bool = False,
    ) -> ConnectorResponse:
        """Send one JSON request with Basic and, only when requested, user access."""

        access_token = self._supplied_access_token() if requires_identity else None
        return self._request("POST", path, body_values=body_values, access_token=access_token)

    def get_json(
        self,
        path: str,
        query_values: Mapping[str, object] | None = None,
        *,
        requires_identity: bool = False,
    ) -> ConnectorResponse:
        """Send one GET request without placing credentials in a query string."""

        if query_values:
            query = urlencode(
                {
                    name: value
                    for name, value in query_values.items()
                    if value is not None
                },
                doseq=True,
            )
            if query:
                separator = "&" if "?" in path else "?"
                path = f"{path}{separator}{query}"
        access_token = self._supplied_access_token() if requires_identity else None
        return self._request("GET", path, access_token=access_token)

    def post_multipart(
        self,
        path: str,
        *,
        fields: Mapping[str, str],
        file: MultipartFile,
        requires_identity: bool,
        progress: Callable[[int, int], None] | None = None,
    ) -> ConnectorResponse:
        if type(path) is not str or not path.startswith("/") or "\r" in path or "\n" in path:
            raise ValueError("path must be an absolute API path")
        if not isinstance(file, MultipartFile) or type(file.size_bytes) is not int or not 0 < file.size_bytes <= 10_000_000:
            raise ValueError("file size is invalid")
        if not re.fullmatch(r"[A-Za-z0-9_]+", file.field_name):
            raise ValueError("file field name is invalid")
        boundary = "sgfap-" + secrets.token_hex(24)
        parts = []
        for name, value in fields.items():
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]+", name) or not isinstance(value, str):
                raise ValueError("multipart fields must have valid text names and values")
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii") + value.encode("utf-8") + b"\r\n")
        media_type = file.media_type if file.media_type in {"image/jpeg", "image/png", "image/webp"} else "application/octet-stream"
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file.field_name}"; filename="evidence"\r\nContent-Type: {media_type}\r\n\r\n'.encode("ascii"))
        prefix = b"".join(parts)
        suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
        if len(prefix) + len(suffix) > 65_536:
            raise ValueError("multipart envelope exceeds limit")

        def body():
            yield prefix
            sent = 0
            with file.stream_factory() as stream:
                while sent < file.size_bytes:
                    chunk = stream.read(min(256 * 1024, file.size_bytes - sent))
                    if not isinstance(chunk, bytes) or not chunk:
                        raise ValueError("file ended before its declared size")
                    sent += len(chunk)
                    yield chunk
                    if progress is not None:
                        progress(sent, file.size_bytes)
                if stream.read(1):
                    raise ValueError("file exceeds its declared size")
            yield suffix

        headers = {
            "Accept": "application/json", "Authorization": self._basic_authorization(),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(prefix) + file.size_bytes + len(suffix)),
        }
        if requires_identity:
            headers["User-Access-Token"] = self._supplied_access_token()
        content = body()
        request = Request(f"{self._config.base_url}{path}", data=content, headers=headers, method="POST")
        try:
            try:
                with self._opener.open(request, timeout=_TIMEOUT_SECONDS) as response:
                    return _decode_response(response.status, response.headers, response.read(65_537))
            except HTTPError as error:
                with error:
                    return _decode_response(error.code, error.headers, error.read(65_537))
            except (socket.timeout, TimeoutError) as error:
                raise ConnectorTimeoutError("No se recibió una respuesta; el resultado remoto puede ser desconocido.", request_sent=None) from error
            except (URLError, OSError) as error:
                raise ConnectorTransportError("La conexión fue interrumpida; el resultado remoto puede ser desconocido.", request_sent=None) from error
        finally:
            content.close()

    def get_binary(
        self,
        path: str,
        *,
        requires_identity: bool,
        maximum_bytes: int,
    ) -> BinaryConnectorResponse | ConnectorResponse:
        if type(path) is not str or not path.startswith("/") or "\r" in path or "\n" in path:
            raise ValueError("path must be an absolute API path")
        if type(maximum_bytes) is not int or maximum_bytes <= 0:
            raise ValueError("maximum_bytes must be positive")
        headers = {"Accept": "image/jpeg, image/png, image/webp, application/json", "Authorization": self._basic_authorization()}
        if requires_identity:
            headers["User-Access-Token"] = self._supplied_access_token()
        request = Request(f"{self._config.base_url}{path}", headers=headers, method="GET")
        try:
            with self._opener.open(request, timeout=_TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    return _decode_response(response.status, response.headers, response.read(65_537))
                media_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if media_type == "application/json":
                    return _decode_response(response.status, response.headers, response.read(65_537))
                length = response.headers.get("Content-Length")
                if media_type not in {"image/jpeg", "image/png", "image/webp"} or not length or not length.isascii() or not length.isdigit():
                    raise ConnectorResponseError("El contenido de la evidencia no es válido.", status_code=response.status)
                size = int(length)
                if not 0 < size <= maximum_bytes:
                    raise ConnectorResponseError("La evidencia supera el tamaño permitido.", status_code=response.status)
                content = response.read(size + 1)
                if len(content) != size:
                    raise ConnectorResponseError("La evidencia recibida está incompleta.", status_code=response.status)
                return BinaryConnectorResponse(response.status, _safe_headers(response.headers), BytesIO(content))
        except HTTPError as error:
            with error:
                return _decode_response(error.code, error.headers, error.read(65_537))
        except (socket.timeout, TimeoutError) as error:
            raise ConnectorTimeoutError("No se recibió la evidencia.", request_sent=None) from error
        except (URLError, OSError) as error:
            raise ConnectorTransportError("No fue posible obtener la evidencia.", request_sent=None) from error

    def delete_json(self, path: str, *, requires_identity: bool = False) -> ConnectorResponse:
        access_token = self._supplied_access_token() if requires_identity else None
        return self._request("DELETE", path, access_token=access_token)

    def _supplied_access_token(self) -> str:
        access_token = self._access_token_supplier() if self._access_token_supplier is not None else None
        if type(access_token) is not str or not access_token:
            raise ConnectorTransportError(
                "No hay una credencial de acceso disponible para la operación.",
                request_sent=False,
            )
        return access_token

    def _request(
        self,
        method: str,
        path: str,
        *,
        body_values: Mapping[str, object] | None = None,
        access_token: str | None = None,
    ) -> ConnectorResponse:
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError("path must be an absolute API path")
        if access_token is not None and (type(access_token) is not str or not access_token):
            raise ValueError("access_token must be a non-empty string")

        body = None
        headers = {"Accept": "application/json", "Authorization": self._basic_authorization()}
        if body_values is not None:
            body = json.dumps(dict(body_values), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if access_token is not None:
            headers["User-Access-Token"] = access_token

        request = Request(
            f"{self._config.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
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

    def _basic_authorization(self) -> str:
        value = f"{self._config.user}:{self._config.password}".encode("utf-8")
        return "Basic " + base64.b64encode(value).decode("ascii")


ApiTransport = RegistrationTransport


def _decode_response(status_code: int, headers: Any, content: bytes) -> ConnectorResponse:
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConnectorResponseError(
            "El servicio devolvió una respuesta no válida.",
            status_code=status_code,
        ) from error
    if not isinstance(payload, dict) or set(payload) != {"success", "data", "error"}:
        raise ConnectorResponseError(
            "El servicio devolvió un formato de respuesta incompatible.",
            status_code=status_code,
        )
    return ConnectorResponse(status_code=status_code, headers=_safe_headers(headers), payload=payload)


def _safe_headers(headers: Any) -> dict[str, str]:
    if headers is None or not hasattr(headers, "items"):
        return {}
    allowed = {"content-type", "www-authenticate", "x-correlation-id", "cache-control"}
    return {
        str(name): str(value)
        for name, value in headers.items()
        if str(name).lower() in allowed
    }


__all__ = [
    "ApiTransport",
    "BinaryConnectorResponse",
    "ConnectorError",
    "ConnectorResponse",
    "ConnectorResponseError",
    "ConnectorTimeoutError",
    "ConnectorTransportError",
    "MultipartFile",
    "RegistrationTransport",
]