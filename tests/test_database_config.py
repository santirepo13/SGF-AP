from pathlib import Path

import pytest

from api.config import DatabaseConfig, PostgresConnectionProvider, load_database_config
from api.errors import ApplicationError, ErrorCode
from api.models import Municipality
from api.repositories import MunicipalityRepository


def test_load_database_config_from_dotenv_file(tmp_path: Path):
    pytest.importorskip("dotenv")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DB_HOST=db.example\nDB_PORT=5432\nDB_NAME=SGFAP\n"
        "DB_USER=Postgres\nDB_PASSWORD=secret\n",
        encoding="utf-8",
    )

    config = load_database_config(env_file, environ={})

    assert config == DatabaseConfig("db.example", 5432, "SGFAP", "Postgres", "secret")
    assert config.connection_kwargs["dbname"] == "SGFAP"


def test_environment_values_override_dotenv_file(tmp_path: Path):
    pytest.importorskip("dotenv")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DB_HOST=file-host\nDB_PORT=5432\nDB_NAME=file-db\n"
        "DB_USER=file-user\nDB_PASSWORD=file-password\n",
        encoding="utf-8",
    )

    config = load_database_config(
        env_file,
        environ={
            "DB_HOST": "environment-host",
            "DB_PORT": "5433",
            "DB_NAME": "environment-db",
            "DB_USER": "environment-user",
            "DB_PASSWORD": "environment-password",
        },
    )

    assert config.host == "environment-host"
    assert config.port == 5433
    assert config.name == "environment-db"


@pytest.mark.parametrize(
    "missing",
    ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"],
)
def test_missing_database_parameter_is_invalid(missing: str):
    values = {
        "DB_HOST": "host", "DB_PORT": "5432", "DB_NAME": "db",
        "DB_USER": "user", "DB_PASSWORD": "password",
    }
    values.pop(missing)

    with pytest.raises(ApplicationError) as caught:
        load_database_config("does-not-exist.env", environ=values)

    assert caught.value.code is ErrorCode.INVALID_VALUE


@pytest.mark.parametrize("port", ["not-a-number", "0", "65536"])
def test_invalid_port_is_rejected(port: str):
    values = {
        "DB_HOST": "host", "DB_PORT": port, "DB_NAME": "db",
        "DB_USER": "user", "DB_PASSWORD": "password",
    }

    with pytest.raises(ApplicationError) as caught:
        load_database_config("does-not-exist.env", environ=values)

    assert caught.value.code is ErrorCode.INVALID_VALUE


def test_connection_provider_passes_config_and_closes_connection():
    config = DatabaseConfig("host", 5432, "db", "user", "password")
    calls = []

    class FakeConnection:
        closed = False

        def close(self):
            self.closed = True

    connection = FakeConnection()

    def connector(**kwargs):
        calls.append(kwargs)
        return connection

    provider = PostgresConnectionProvider(config, connector)
    with provider.connection() as received:
        assert received is connection

    assert calls == [config.connection_kwargs]
    assert connection.closed is True


def test_connection_failure_is_centralized_and_keeps_cause():
    config = DatabaseConfig("host", 5432, "db", "user", "password")
    failure = OSError("connection refused")
    provider = PostgresConnectionProvider(config, lambda **kwargs: (_ for _ in ()).throw(failure))

    with pytest.raises(ApplicationError) as caught:
        provider.connect()

    assert caught.value.code is ErrorCode.PERSISTENCE_FAILURE
    assert caught.value.cause is failure


def test_provider_connection_can_be_injected_into_repository():
    config = DatabaseConfig("host", 5432, "db", "user", "password")

    class Cursor:
        description = None
        closed = False

        def execute(self, query, params=()):
            self.query, self.params = query, tuple(params)

        def fetchone(self):
            return {"id": 4, "name": "Cali"}

        def close(self):
            self.closed = True

    class Connection:
        def __init__(self):
            self.cursor_instance = Cursor()
            self.closed = False

        def cursor(self):
            return self.cursor_instance

        def close(self):
            self.closed = True

    connection = Connection()
    provider = PostgresConnectionProvider(config, lambda **kwargs: connection)

    with provider.connection() as shared_connection:
        result = MunicipalityRepository(shared_connection).get_by_id(4)

    assert result == Municipality(4, "Cali")
    assert connection.cursor_instance.params == (4,)
    assert connection.cursor_instance.closed is True
    assert connection.closed is True
