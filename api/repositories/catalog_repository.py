"""Small reusable bases for read-only catalog repositories."""

from collections.abc import Callable
from typing import Generic, TypeVar

from .persistence import ConnectionProtocol, RepositoryBase

T = TypeVar("T")


class CodeCatalogRepository(RepositoryBase, Generic[T]):
    table: str
    model: Callable
    code_type: type

    def get_by_code(self, code):
        query = f"SELECT code, name FROM {self.table} WHERE code = %s"
        return self.fetch_one(query, (self.code_type(code),), operation=f"{self.table}.get_by_code", entity=self.table, mapper=type(self).model)

    def list_all(self):
        query = f"SELECT code, name FROM {self.table} ORDER BY code"
        return self.fetch_all(query, (), operation=f"{self.table}.list_all", entity=self.table, mapper=type(self).model)


class CodeOnlyCatalogRepository(RepositoryBase, Generic[T]):
    table: str
    model: Callable
    code_type: type

    def get_by_code(self, code):
        query = f"SELECT code FROM {self.table} WHERE code = %s"
        return self.fetch_one(query, (self.code_type(code),), operation=f"{self.table}.get_by_code", entity=self.table, mapper=type(self).model)

    def list_all(self):
        query = f"SELECT code FROM {self.table} ORDER BY code"
        return self.fetch_all(query, (), operation=f"{self.table}.list_all", entity=self.table, mapper=type(self).model)


class IdNameCatalogRepository(RepositoryBase, Generic[T]):
    table: str
    model: Callable
    name_type: type | None = None

    def get_by_id(self, record_id: int):
        query = f"SELECT id, name FROM {self.table} WHERE id = %s"
        return self.fetch_one(query, (record_id,), operation=f"{self.table}.get_by_id", entity=self.table, mapper=type(self).model)

    def get_by_name(self, name):
        value = self.name_type(name) if self.name_type is not None and not isinstance(name, self.name_type) else name
        query = f"SELECT id, name FROM {self.table} WHERE name = %s"
        return self.fetch_one(query, (value,), operation=f"{self.table}.get_by_name", entity=self.table, mapper=type(self).model)

    def list_all(self):
        query = f"SELECT id, name FROM {self.table} ORDER BY id"
        return self.fetch_all(query, (), operation=f"{self.table}.list_all", entity=self.table, mapper=type(self).model)
