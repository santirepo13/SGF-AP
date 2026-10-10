"""Base behavior for enums persisted as SQL text values."""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

E = TypeVar("E", bound="SqlEnum")


class SqlEnum(str, Enum):
    """String enum with explicit SQL conversion helpers."""

    @classmethod
    def from_sql(cls: type[E], value: str) -> E:
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"invalid {cls.__name__} SQL value: {value!r}") from exc

    def to_sql(self) -> str:
        return self.value
