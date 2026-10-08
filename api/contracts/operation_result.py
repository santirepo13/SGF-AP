"""Generic operation result contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from .error_types import ErrorOutput

T = TypeVar("T")


@dataclass(frozen=True)
class OperationResult(Generic[T]):
    success: bool
    data: T | None = None
    error: ErrorOutput | None = None

    def __post_init__(self) -> None:
        if self.success and self.error is not None:
            raise ValueError("a successful result cannot contain an error")
        if not self.success and self.error is None:
            raise ValueError("a failed result must contain an error")
        if not self.success and self.data is not None:
            raise ValueError("a failed result cannot contain completed data")

    @classmethod
    def ok(cls, data: T | None = None) -> "OperationResult[T]":
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: ErrorOutput) -> "OperationResult[T]":
        return cls(success=False, error=error)
