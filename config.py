"""Configuration consumed by the local connector."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class ConnectorConfig:
    """Validated endpoint and HTTP Basic credentials for the SGF-AP connector."""

    url: str
    port: int
    user: str
    password: str = field(repr=False)

    @property
    def base_url(self) -> str:
        """Return the server URL with its separately configured port."""

        return f"{self.url}:{self.port}"


def load_connector_config(
    env_file: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> ConnectorConfig:
    """Load connector settings with process variables taking precedence over dotenv."""

    values = dict(os.environ if environ is None else environ)
    if env_file is None:
        env_file = Path(__file__).resolve().with_name(".env")
    _load_dotenv(env_file, values)

    url = values.get("API_URL", "").strip()
    port_value = values.get("API_PORT", "").strip()
    user = values.get("API_USER", "").strip()
    password = values.get("API_PASSWORD", "")
    if not url:
        raise ValueError("API_URL es obligatoria.")
    if not port_value:
        raise ValueError("API_PORT es obligatorio.")
    if not user:
        raise ValueError("API_USER es obligatorio.")
    if password == "":
        raise ValueError("API_PASSWORD es obligatoria.")

    _validate_http_url(url)
    try:
        port = int(port_value)
    except ValueError as exc:
        raise ValueError("API_PORT debe ser un número entero.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("API_PORT debe estar entre 1 y 65535.")

    return ConnectorConfig(url=url.rstrip("/"), port=port, user=user, password=password)


def _validate_http_url(value: str) -> None:
    """Accept only an HTTP authority without a port or request-specific components."""

    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("API_URL debe ser una dirección HTTP válida sin puerto.") from exc
    if (
        parsed.scheme != "http"
        or not parsed.hostname
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("API_URL debe ser una dirección HTTP válida sin puerto.")


def _load_dotenv(env_file: str | Path, values: dict[str, str]) -> None:
    """Load only absent values from dotenv so process variables remain authoritative."""

    path = Path(env_file)
    if not path.exists():
        return
    try:
        from dotenv import dotenv_values
    except ModuleNotFoundError as exc:
        raise ValueError("python-dotenv es necesaria para cargar el archivo .env.") from exc
    for key, value in dotenv_values(path).items():
        if key and value is not None and key not in values:
            values[key] = value
