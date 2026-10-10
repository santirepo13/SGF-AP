"""Ordered composition of context, validation, authorization, service and logging."""

from __future__ import annotations

from typing import Any

from api.contracts import ExecutionContext, OperationResult

from .authorization_middleware import AuthorizationMiddleware
from .base import MiddlewareRequest
from .context_middleware import ContextMiddleware
from .error_middleware import ErrorMiddleware
from .execution_logging_middleware import ExecutionLoggingMiddleware
from .validation_middleware import ValidationMiddleware


class MiddlewarePipeline:
    def __init__(self, context: ContextMiddleware, validation: ValidationMiddleware, authorization: AuthorizationMiddleware, errors: ErrorMiddleware, logging: ExecutionLoggingMiddleware) -> None:
        self.context, self.validation, self.authorization, self.errors, self.logging = context, validation, authorization, errors, logging

    def execute(self, service_name: str, method_name: str, service: object, *args: Any, context: ExecutionContext | None = None, **kwargs: Any) -> OperationResult[Any]:
        request = MiddlewareRequest(service_name, method_name, service, args, kwargs, context)

        def invoke(req: MiddlewareRequest):
            return getattr(req.service, req.method_name)(req.context, *req.args, **req.kwargs)

        def authorized(req): return self.authorization.process(req, invoke)
        def validated(req): return self.validation.process(req, authorized)
        def logged(req): return self.logging.process(req, validated)
        def contextual(req): return self.context.process(req, logged)

        return self.errors.process(request, contextual)
