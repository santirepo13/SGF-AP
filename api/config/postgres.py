"""PostgreSQL connection lifecycle managed outside repositories."""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Callable, Iterator
from typing import Any

from api.errors import ApplicationError

from .database import DatabaseConfig


class PostgresConnectionProvider:
    """Create and close PostgreSQL connections without owning transactions."""

    def __init__(self, config: DatabaseConfig, connector: Callable[..., Any] | None = None) -> None:
        self.config = config
        self._connector = connector

    def connect(self) -> Any:
        connector = self._connector or _default_connector
        try:
            return connector(**self.config.connection_kwargs)
        except Exception as exc:
            raise ApplicationError.persistence_failure(cause=exc) from exc

    @contextmanager
    def connection(self) -> Iterator[Any]:
        connection = self.connect()
        try:
            yield connection
        finally:
            try:
                connection.close()
            except Exception:
                # Closing is best-effort after the original operation. The
                # connection provider must never hide the operation result.
                pass


def _default_connector(**kwargs: object) -> Any:
    try:
        import psycopg
    except ModuleNotFoundError as exc:
        raise RuntimeError("psycopg is not installed") from exc
    return psycopg.connect(**kwargs)
