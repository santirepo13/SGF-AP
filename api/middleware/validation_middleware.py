"""Input and service-signature validation."""

from __future__ import annotations

import inspect
from dataclasses import is_dataclass

from api.contracts import ExecutionContext
from api.errors import ApplicationError

from .base import MiddlewareRequest, NextHandler
from .operation_policies import OPERATION_POLICIES


class ValidationMiddleware:
    def process(self, request: MiddlewareRequest, next_handler: NextHandler):
        policy = OPERATION_POLICIES[request.operation_name]
        method = getattr(request.service, request.method_name, None)
        if method is None or not callable(method):
            raise ApplicationError.invalid_value("method", "El método de servicio no existe.", correlation_id=request.context.correlation_id)
        signature = inspect.signature(method)
        try:
            bound = signature.bind(request.context, *request.args, **request.kwargs)
        except TypeError as exc:
            raise ApplicationError.invalid_value(None, "Los parámetros no corresponden con la operación.", correlation_id=request.context.correlation_id, cause=exc) from exc
        annotations = getattr(method, "__annotations__", {})
        for name, value in bound.arguments.items():
            if isinstance(value, ExecutionContext):
                continue
            if value is None:
                continue
            expected = annotations.get(name)
            if expected in (int, str, bool) and type(value) is not expected:
                raise ApplicationError.invalid_value(name, "El tipo del valor no corresponde al contrato.", correlation_id=request.context.correlation_id)
            if isinstance(value, (str, int, bool)):
                continue
            if is_dataclass(value) and policy.input_types and not isinstance(value, policy.input_types):
                raise ApplicationError.invalid_value("data", "La entrada no corresponde al contrato de la operación.", correlation_id=request.context.correlation_id)
        return next_handler(request)
