"""Validated HTTP API and access-token configuration loaded from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from api.errors import ApplicationError


@dataclass(frozen=True, slots=True)
class ActorConfig:
    """Server-owned SGF-AP actor kept separate from HTTP Basic credentials."""

    user_id: int
    role_id: int
    active: bool
    permissions: frozenset[str]


@dataclass(frozen=True, slots=True)
class AccessTokenConfig:
    """Validated server-only key material and expiry for HS256 credentials."""

    secret: bytes = field(repr=False)
    ttl_seconds: int = 3600

    def __post_init__(self) -> None:
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise ValueError("access-token secret must contain at least 32 bytes")
        if type(self.ttl_seconds) is not int or self.ttl_seconds <= 0:
            raise ValueError("access-token lifetime must be a positive integer")


@dataclass(frozen=True, slots=True)
class APIConfig:
    """Server port, HTTP Basic credentials, and user access-token settings."""

    port: int
    user: str
    password: str = field(repr=False)
    actor: ActorConfig | None = None
    access_token: AccessTokenConfig | None = field(default=None, repr=False)

    @property
    def access_token_secret(self) -> bytes:
        """Return key bytes only for server-side composition."""

        if self.access_token is None:
            raise RuntimeError("access-token configuration is not initialized")
        return self.access_token.secret

    @property
    def access_token_ttl_seconds(self) -> int:
        if self.access_token is None:
            raise RuntimeError("access-token configuration is not initialized")
        return self.access_token.ttl_seconds


def load_api_config(
    env_file: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> APIConfig:
    """Load API settings, giving explicit process variables precedence over dotenv."""

    values = dict(os.environ if environ is None else environ)
    if env_file is None:
        env_file = Path(__file__).resolve().parents[1] / ".env"
    _load_dotenv(env_file, values)

    port_value = values.get("API_PORT", "").strip()
    user = values.get("API_USER", "").strip()
    password = values.get("API_PASSWORD", "")
    if not port_value:
        raise ApplicationError.invalid_value("API_PORT", "El puerto de la API es obligatorio.")
    if not user:
        raise ApplicationError.invalid_value("API_USER", "El usuario de autenticación es obligatorio.")
    if password == "":
        raise ApplicationError.invalid_value("API_PASSWORD", "La contraseña de autenticación es obligatoria.")

    try:
        port = int(port_value)
    except ValueError as exc:
        raise ApplicationError.invalid_value("API_PORT", "El puerto de la API debe ser un número entero.", cause=exc) from exc
    if not 1 <= port <= 65535:
        raise ApplicationError.invalid_value("API_PORT", "El puerto de la API debe estar entre 1 y 65535.")

    return APIConfig(
        port=port,
        user=user,
        password=password,
        actor=_load_actor_config(values),
        access_token=_load_access_token_config(values),
    )


def _load_access_token_config(values: Mapping[str, str]) -> AccessTokenConfig:
    """Decode and validate the server-only hexadecimal JWT signing key."""

    encoded_secret = values.get("ACCESS_TOKEN_SECRET", "")
    if not encoded_secret:
        raise ApplicationError.invalid_value(
            "ACCESS_TOKEN_SECRET",
            "La clave de acceso del servidor es obligatoria.",
        )
    try:
        secret = bytes.fromhex(encoded_secret)
    except ValueError as exc:
        raise ApplicationError.invalid_value(
            "ACCESS_TOKEN_SECRET",
            "La clave de acceso del servidor debe estar codificada en hexadecimal.",
            cause=exc,
        ) from exc
    if len(secret) < 32:
        raise ApplicationError.invalid_value(
            "ACCESS_TOKEN_SECRET",
            "La clave de acceso del servidor debe tener al menos 32 bytes.",
        )

    ttl_value = values.get("ACCESS_TOKEN_TTL_SECONDS", "3600").strip()
    if not ttl_value:
        raise ApplicationError.invalid_value(
            "ACCESS_TOKEN_TTL_SECONDS",
            "La vigencia de la credencial es obligatoria.",
        )
    try:
        ttl_seconds = int(ttl_value)
    except ValueError as exc:
        raise ApplicationError.invalid_value(
            "ACCESS_TOKEN_TTL_SECONDS",
            "La vigencia de la credencial debe ser un número entero.",
            cause=exc,
        ) from exc
    if ttl_seconds <= 0:
        raise ApplicationError.invalid_value(
            "ACCESS_TOKEN_TTL_SECONDS",
            "La vigencia de la credencial debe ser positiva.",
        )
    return AccessTokenConfig(secret=secret, ttl_seconds=ttl_seconds)


def _load_actor_config(values: Mapping[str, str]) -> ActorConfig | None:
    """Load an optional server-side actor without deriving it from API credentials."""

    names = (
        "SGFAP_ACTOR_USER_ID",
        "SGFAP_ACTOR_ROLE_ID",
        "SGFAP_ACTOR_ACTIVE",
        "SGFAP_ACTOR_PERMISSIONS",
    )
    if not any(name in values for name in names):
        return None

    user_id_value = values.get("SGFAP_ACTOR_USER_ID", "").strip()
    role_id_value = values.get("SGFAP_ACTOR_ROLE_ID", "").strip()
    active_value = values.get("SGFAP_ACTOR_ACTIVE", "").strip().lower()
    permissions_value = values.get("SGFAP_ACTOR_PERMISSIONS", "")
    if not user_id_value:
        raise ApplicationError.invalid_value("SGFAP_ACTOR_USER_ID", "El identificador del actor es obligatorio.")
    if not role_id_value:
        raise ApplicationError.invalid_value("SGFAP_ACTOR_ROLE_ID", "El rol del actor es obligatorio.")
    if active_value not in {"true", "false"}:
        raise ApplicationError.invalid_value("SGFAP_ACTOR_ACTIVE", "El estado del actor debe ser true o false.")
    permissions = frozenset(permission.strip() for permission in permissions_value.split(",") if permission.strip())
    if not permissions:
        raise ApplicationError.invalid_value("SGFAP_ACTOR_PERMISSIONS", "Debe configurarse al menos un permiso del actor.")
    try:
        user_id = int(user_id_value)
        role_id = int(role_id_value)
    except ValueError as exc:
        raise ApplicationError.invalid_value("SGFAP_ACTOR_USER_ID", "Los identificadores del actor y su rol deben ser enteros.", cause=exc) from exc
    if user_id <= 0 or role_id <= 0:
        raise ApplicationError.invalid_value("SGFAP_ACTOR_USER_ID", "Los identificadores del actor y su rol deben ser positivos.")
    return ActorConfig(user_id=user_id, role_id=role_id, active=active_value == "true", permissions=permissions)


def _load_dotenv(env_file: str | Path, values: dict[str, str]) -> None:
    """Load missing dotenv values without replacing explicit process variables."""

    path = Path(env_file)
    if not path.exists():
        return
    try:
        from dotenv import dotenv_values
    except ModuleNotFoundError:
        loaded = _read_simple_dotenv(path)
    else:
        loaded = dotenv_values(path)
    for key, value in loaded.items():
        if key and value is not None and key not in values:
            values[key] = value


def _read_simple_dotenv(path: Path) -> dict[str, str]:
    """Minimal fallback for production images that omit python-dotenv."""

    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            result[key] = value
    return result
