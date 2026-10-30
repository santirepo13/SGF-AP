"""Coverage for server and connector HTTP configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from api.config import APIConfig, AccessTokenConfig, ActorConfig, load_api_config
from api.errors import ApplicationError, ErrorCode
from config import ConnectorConfig, load_connector_config


_TEST_ACCESS_SECRET = "00" * 32


def test_connector_config_loads_dotenv_and_hides_password_from_representation(tmp_path: Path) -> None:
    pytest.importorskip("dotenv")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "API_URL=http://87.239.135.39\nAPI_PORT=8002\nAPI_USER=connector\nAPI_PASSWORD=connector-secret\n",
        encoding="utf-8",
    )

    config = load_connector_config(env_file, environ={})

    assert config.base_url == "http://87.239.135.39:8002"
    assert config.user == "connector"
    assert "connector-secret" not in repr(config)


def test_connector_environment_values_override_dotenv_and_preserve_password_exactly(tmp_path: Path) -> None:
    pytest.importorskip("dotenv")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "API_URL=http://file.example\nAPI_PORT=8002\nAPI_USER=file-user\nAPI_PASSWORD=file-password\n",
        encoding="utf-8",
    )

    config = load_connector_config(
        env_file,
        environ={
            "API_URL": "http://environment.example",
            "API_PORT": "9000",
            "API_USER": "environment-user",
            "API_PASSWORD": " exact password ",
        },
    )

    assert config == ConnectorConfig("http://environment.example", 9000, "environment-user", " exact password ")


@pytest.mark.parametrize(
    "values",
    (
        {"API_PORT": "8002", "API_USER": "user", "API_PASSWORD": "password"},
        {"API_URL": "https://host", "API_PORT": "8002", "API_USER": "user", "API_PASSWORD": "password"},
        {"API_URL": "http://host:8002", "API_PORT": "8002", "API_USER": "user", "API_PASSWORD": "password"},
        {"API_URL": "http://host", "API_PORT": "0", "API_USER": "user", "API_PASSWORD": "password"},
        {"API_URL": "http://host", "API_PORT": "8002", "API_USER": "", "API_PASSWORD": "password"},
        {"API_URL": "http://host", "API_PORT": "8002", "API_USER": "user", "API_PASSWORD": ""},
    ),
)
def test_connector_config_rejects_missing_or_invalid_values(values: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        load_connector_config("does-not-exist.env", environ=values)


def test_api_config_loads_and_prioritizes_environment_without_exposing_password(tmp_path: Path) -> None:
    pytest.importorskip("dotenv")
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"API_PORT=8002\nAPI_USER=file-user\nAPI_PASSWORD=file-password\nACCESS_TOKEN_SECRET={_TEST_ACCESS_SECRET}\n",
        encoding="utf-8",
    )

    config = load_api_config(
        env_file,
        environ={
            "API_PORT": "9000",
            "API_USER": "environment-user",
            "API_PASSWORD": "api-secret",
            "ACCESS_TOKEN_SECRET": _TEST_ACCESS_SECRET,
        },
    )

    assert config == APIConfig(
        port=9000,
        user="environment-user",
        password="api-secret",
        access_token=AccessTokenConfig(bytes(32), 3600),
    )
    assert "api-secret" not in repr(config)


def test_api_config_loads_a_business_actor_separate_from_basic_credentials() -> None:
    config = load_api_config(
        "does-not-exist.env",
        environ={
            "API_PORT": "8002",
            "API_USER": "http-user",
            "API_PASSWORD": "http-password",
            "ACCESS_TOKEN_SECRET": _TEST_ACCESS_SECRET,
            "SGFAP_ACTOR_USER_ID": "15",
            "SGFAP_ACTOR_ROLE_ID": "5",
            "SGFAP_ACTOR_ACTIVE": "true",
            "SGFAP_ACTOR_PERMISSIONS": "create_address, manage_users, *",
        },
    )

    assert config.user == "http-user"
    assert config.actor == ActorConfig(15, 5, True, frozenset({"create_address", "manage_users", "*"}))


@pytest.mark.parametrize(
    "values",
    (
        {"API_USER": "user", "API_PASSWORD": "password"},
        {"API_PORT": "invalid", "API_USER": "user", "API_PASSWORD": "password"},
        {"API_PORT": "65536", "API_USER": "user", "API_PASSWORD": "password"},
        {"API_PORT": "8002", "API_USER": "", "API_PASSWORD": "password"},
        {"API_PORT": "8002", "API_USER": "user", "API_PASSWORD": ""},
    ),
)
def test_api_config_rejects_missing_or_invalid_values(values: dict[str, str]) -> None:
    with pytest.raises(ApplicationError) as raised:
        load_api_config("does-not-exist.env", environ=values)

    assert raised.value.code is ErrorCode.INVALID_VALUE
