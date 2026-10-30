"""Runtime configuration selection for development and packaged clients."""

from __future__ import annotations

from collections.abc import Mapping
from importlib import import_module
from pathlib import Path

from config import ConnectorConfig, load_connector_config


def load_client_config(
    env_file: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> ConnectorConfig:
    """Prefer generated APK constants, then fall back to dotenv development config."""

    if env_file is None and environ is None:
        try:
            packaged_config = import_module(f"{__package__}.packaged_config")
        except ModuleNotFoundError as error:
            if error.name != f"{__package__}.packaged_config":
                raise
        else:
            return load_connector_config(
                "__no_packaged_env_file__.env",
                environ={
                    "API_URL": packaged_config.API_URL,
                    "API_PORT": str(packaged_config.API_PORT),
                    "API_USER": packaged_config.API_USER,
                    "API_PASSWORD": packaged_config.API_PASSWORD,
                },
            )
    return load_connector_config(env_file, environ=environ)


__all__ = ["load_client_config"]
