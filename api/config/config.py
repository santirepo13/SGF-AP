"""Validated HTTP API configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from api.errors import ApplicationError


@dataclass(frozen=True, slots=True)
class APIConfig:
    """Server port and credentials used to protect the HTTP API."""

    port: int
    user: str
    password: str = field(repr=False)


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

    return APIConfig(port=port, user=user, password=password)


def _load_dotenv(env_file: str | Path, values: dict[str, str]) -> None:
    """Load missing values from a dotenv file without replacing process variables."""

    path = Path(env_file)
    if not path.exists():
        return
    try:
        from dotenv import dotenv_values
    except ModuleNotFoundError as exc:
        raise ApplicationError.invalid_value(
            "env_file",
            "La dependencia python-dotenv es necesaria para cargar el archivo de entorno.",
            cause=exc,
        ) from exc
    for key, value in dotenv_values(path).items():
        if key and value is not None and key not in values:
            values[key] = value
