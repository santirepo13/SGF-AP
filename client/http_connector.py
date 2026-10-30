"""Registration-specific adapter over the packaged HTTP transport."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from config import ConnectorConfig

from .config import load_client_config
from .transport import (
    ConnectorResponse,
    RegistrationTransport,
)


class RegistrationHttpConnector:
    """Expose only the citizen-registration request to the UI controller."""

    def __init__(self, config: ConnectorConfig, *, opener: Any | None = None) -> None:
        self._connector = RegistrationTransport(config, opener=opener)

    def register_citizen(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
    ) -> ConnectorResponse:
        return self._connector.register_citizen(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
        )


def build_registration_connector(
    env_file: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    opener: Any | None = None,
) -> RegistrationHttpConnector:
    """Build the connector from development or build-time configuration."""

    return RegistrationHttpConnector(
        load_client_config(env_file, environ=environ),
        opener=opener,
    )


__all__ = ["ConnectorResponse", "RegistrationHttpConnector", "build_registration_connector"]
