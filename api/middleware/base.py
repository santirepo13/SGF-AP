"""Shared middleware contracts and safe helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from api.contracts import ActorContext, ExecutionContext, OperationResult


class CorrelationIdGenerator(Protocol):
    def generate(self) -> str: ...


class IdentityProvider(Protocol):
    def resolve(self) -> ActorContext | None: ...


class PermissionChecker(Protocol):
    def is_allowed(self, actor: ActorContext, permission: str, operation: str) -> bool: ...


class ExecutionLogger(Protocol):
    def start(self, record: dict[str, Any]) -> None: ...
    def finish(self, record: dict[str, Any]) -> None: ...


@dataclass
class MiddlewareRequest:
    service_name: str
    method_name: str
    service: object
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    context: ExecutionContext | None = None
    operation: str | None = None

    @property
    def operation_name(self) -> str:
        return self.operation or f"{self.service_name}.{self.method_name}"


NextHandler = Callable[[MiddlewareRequest], OperationResult[Any]]
