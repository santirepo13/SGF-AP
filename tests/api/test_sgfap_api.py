"""Unit coverage for the SGF-AP FastAPI factory and lifecycle."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI

from api.config import APIConfig
from api.config.database import DatabaseConfig
from api.sgfap_api import create_app, lifespan


class ReadinessCursor:
    def __init__(self, *, result: int = 1, failure: BaseException | None = None) -> None:
        self.result = result
        self.failure = failure
        self.queries: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query: str) -> None:
        self.queries.append(query)
        if self.failure is not None:
            raise self.failure

    def fetchone(self):
        return (self.result,)


class ReadinessConnection:
    def __init__(self, cursor: ReadinessCursor) -> None:
        self._cursor = cursor
        self.closed = 0

    def cursor(self) -> ReadinessCursor:
        return self._cursor

    def close(self) -> None:
        self.closed += 1


class ReadinessProvider:
    def __init__(self, connection: ReadinessConnection) -> None:
        self.connection = connection

    def connect(self) -> ReadinessConnection:
        return self.connection


def test_create_app_builds_named_asgi_application_with_lifespan() -> None:
    application = create_app()

    assert application.title == "SGF-AP"
    assert callable(application.router.lifespan_context)


def test_lifespan_prepares_dependencies_and_releases_readiness_connection(monkeypatch) -> None:
    cursor = ReadinessCursor()
    connection = ReadinessConnection(cursor)
    provider = ReadinessProvider(connection)
    config = DatabaseConfig(host="db.remote", port=5432, name="sgfap", user="api", password="secret")
    application = FastAPI()

    monkeypatch.setattr("api.sgfap_api.load_api_config", lambda: APIConfig(8002, "connector", "secret"))
    monkeypatch.setattr("api.sgfap_api.load_database_config", lambda: config)
    monkeypatch.setattr("api.sgfap_api.PostgresConnectionProvider", lambda configured: provider)

    async def exercise_lifespan() -> None:
        async with lifespan(application):
            assert application.state.api_config == APIConfig(8002, "connector", "secret")
            assert application.state.db_config is config
            assert application.state.db_provider is provider
            assert application.state.dependencies.connection_provider is provider
            assert cursor.queries == ["SELECT 1"]
            assert connection.closed == 1

    asyncio.run(exercise_lifespan())

    assert not hasattr(application.state, "api_config")
    assert not hasattr(application.state, "db_config")
    assert not hasattr(application.state, "db_provider")
    assert not hasattr(application.state, "dependencies")


def test_lifespan_preserves_startup_cause_and_closes_partially_opened_connection(monkeypatch) -> None:
    cause = RuntimeError("remote database unavailable")
    connection = ReadinessConnection(ReadinessCursor(failure=cause))
    provider = ReadinessProvider(connection)
    config = DatabaseConfig(host="db.remote", port=5432, name="sgfap", user="api", password="secret")
    application = FastAPI()

    monkeypatch.setattr("api.sgfap_api.load_api_config", lambda: APIConfig(8002, "connector", "secret"))
    monkeypatch.setattr("api.sgfap_api.load_database_config", lambda: config)
    monkeypatch.setattr("api.sgfap_api.PostgresConnectionProvider", lambda configured: provider)

    async def exercise_lifespan() -> None:
        with pytest.raises(RuntimeError) as raised:
            async with lifespan(application):
                pytest.fail("the application must not yield after failed startup")
        assert raised.value is cause

    asyncio.run(exercise_lifespan())

    assert connection.closed == 1
    assert not hasattr(application.state, "api_config")
    assert not hasattr(application.state, "dependencies")
