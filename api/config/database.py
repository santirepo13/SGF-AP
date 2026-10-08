"""Validated PostgreSQL configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from api.errors import ApplicationError


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str

    @property
    def connection_kwargs(self) -> dict[str, object]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.name,
            "user": self.user,
            "password": self.password,
        }


def load_database_config(
    env_file: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> DatabaseConfig:
    """Load and validate database settings without exposing credentials.

    Values already present in ``environ`` take precedence over the dotenv file.
    The explicit mapping is useful for tests and deployment adapters.
    """
    values = dict(os.environ if environ is None else environ)
    if env_file is None:
        env_file = Path(__file__).resolve().parents[1] / ".env"
    _load_dotenv(env_file, values)

    raw = {name: values.get(name, "").strip() for name in _REQUIRED_NAMES}
    for name, value in raw.items():
        if not value:
            raise ApplicationError.invalid_value(name, "El parámetro de conexión es obligatorio.")

    try:
        port = int(raw["DB_PORT"])
    except ValueError as exc:
        raise ApplicationError.invalid_value("DB_PORT", "El puerto debe ser un número entero.", cause=exc) from exc
    if not 1 <= port <= 65535:
        raise ApplicationError.invalid_value("DB_PORT", "El puerto debe estar entre 1 y 65535.")

    return DatabaseConfig(
        host=raw["DB_HOST"],
        port=port,
        name=raw["DB_NAME"],
        user=raw["DB_USER"],
        password=raw["DB_PASSWORD"],
    )


_REQUIRED_NAMES = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")


def _load_dotenv(env_file: str | Path, values: dict[str, str]) -> None:
    """Load dotenv values while preserving explicitly supplied environment data."""
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
