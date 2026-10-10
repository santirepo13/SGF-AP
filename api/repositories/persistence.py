"""DB-API-compatible persistence primitives used by repositories."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Callable
from typing import Any, Protocol

from api.errors import ErrorHandler, PersistenceContext


class CursorProtocol(Protocol):
    description: Sequence[Any] | None

    def execute(self, query: str, params: Sequence[object] = ()) -> object: ...
    def fetchone(self) -> object | None: ...
    def fetchall(self) -> Sequence[object]: ...
    def close(self) -> object: ...


class ConnectionProtocol(Protocol):
    def cursor(self) -> CursorProtocol: ...


def row_mapping(row: object, description: Sequence[Any] | None) -> Mapping[str, object]:
    if isinstance(row, Mapping):
        return row
    if row is None or description is None:
        raise ValueError("database row has no usable column description")
    columns = [item[0] if isinstance(item, Sequence) else getattr(item, "name", None) for item in description]
    if any(column is None for column in columns):
        raise ValueError("database description has no column names")
    return dict(zip(columns, row, strict=True))


class RepositoryBase:
    def __init__(self, connection: ConnectionProtocol) -> None:
        self.connection = connection

    def fetch_one(self, query: str, params: Sequence[object], *, operation: str, entity: str, input_origin: bool = False, mapper: Callable | None = None):
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, params)
            row = cursor.fetchone()
            mapped = None if row is None else row_mapping(row, cursor.description)
            return None if mapped is None or mapper is None else mapper(mapped)
        except Exception as exc:
            error = ErrorHandler.classify_exception(exc, persistence_context=PersistenceContext(operation, entity, input_origin=input_origin))
            raise error from exc
        finally:
            cursor.close()

    def fetch_all(self, query: str, params: Sequence[object], *, operation: str, entity: str, mapper: Callable | None = None):
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, params)
            rows = [row_mapping(row, cursor.description) for row in cursor.fetchall()]
            return rows if mapper is None else [mapper(row) for row in rows]
        except Exception as exc:
            error = ErrorHandler.classify_exception(exc, persistence_context=PersistenceContext(operation, entity))
            raise error from exc
        finally:
            cursor.close()

    def execute_one(self, query: str, params: Sequence[object], *, operation: str, entity: str, input_origin: bool = True, mapper: Callable | None = None):
        return self.fetch_one(query, params, operation=operation, entity=entity, input_origin=input_origin, mapper=mapper)
