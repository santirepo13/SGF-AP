"""Context and correlation preparation."""

from __future__ import annotations

from uuid import uuid4

from api.contracts import ExecutionContext
from api.errors import ApplicationError

from .base import CorrelationIdGenerator, IdentityProvider, MiddlewareRequest, NextHandler
from .operation_policies import OPERATION_POLICIES


class UuidCorrelationIdGenerator:
    def generate(self) -> str:
        return str(uuid4())


class ContextMiddleware:
    def __init__(self, identity_provider: IdentityProvider | None = None, correlation_ids: CorrelationIdGenerator | None = None) -> None:
        self.identity_provider = identity_provider
        self.correlation_ids = correlation_ids or UuidCorrelationIdGenerator()

    def process(self, request: MiddlewareRequest, next_handler: NextHandler):
        operation = request.operation_name
        if not operation or operation not in OPERATION_POLICIES:
            correlation_id = request.context.correlation_id if request.context and request.context.correlation_id else self.correlation_ids.generate()
            raise ApplicationError.invalid_value("operation", "La operación no está registrada.", correlation_id=correlation_id)
        correlation_id = request.context.correlation_id if request.context and request.context.correlation_id else self.correlation_ids.generate()
        actor = request.context.actor if request.context else None
        if self.identity_provider is not None:
            actor = self.identity_provider.resolve()
        request.operation = operation
        request.context = ExecutionContext(operation=operation, correlation_id=correlation_id, actor=actor)
        return next_handler(request)
