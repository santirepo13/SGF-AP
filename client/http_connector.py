"""UI-facing adapter over the packaged HTTP transport."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from config import ConnectorConfig

from .config import load_client_config
from .transport import ConnectorResponse, RegistrationTransport


class RegistrationHttpConnector:
    """Expose registration, login, and future authenticated requests to UI flows."""

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        opener: Any | None = None,
        access_token_supplier: Callable[[], str | None] | None = None,
    ) -> None:
        self._connector = RegistrationTransport(
            config,
            opener=opener,
            access_token_supplier=access_token_supplier,
        )

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

    def login(self, *, email: str, password: str) -> ConnectorResponse:
        return self._connector.login(email=email, password=password)

    def post_json(
        self,
        path: str,
        body_values: Mapping[str, object],
        *,
        requires_identity: bool = False,
    ) -> ConnectorResponse:
        return self._connector.post_json(path, body_values, requires_identity=requires_identity)


LoginHttpConnector = RegistrationHttpConnector


def build_registration_connector(
    env_file: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    opener: Any | None = None,
    access_token_supplier: Callable[[], str | None] | None = None,
) -> RegistrationHttpConnector:
    """Build the connector from development or build-time configuration."""

    return RegistrationHttpConnector(
        load_client_config(env_file, environ=environ),
        opener=opener,
        access_token_supplier=access_token_supplier,
    )


def build_login_connector(
    env_file: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    opener: Any | None = None,
    access_token_supplier: Callable[[], str | None] | None = None,
) -> LoginHttpConnector:
    return build_registration_connector(
        env_file,
        environ=environ,
        opener=opener,
        access_token_supplier=access_token_supplier,
    )


__all__ = [
    "ConnectorResponse",
    "LoginHttpConnector",
    "RegistrationHttpConnector",
    "build_login_connector",
    "build_registration_connector",
]
