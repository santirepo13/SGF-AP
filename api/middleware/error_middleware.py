"""Central exception boundary for middleware and service calls."""

from __future__ import annotations

from dataclasses import replace
from types import UnionType
from typing import Any, get_args, get_origin, get_type_hints

from api.contracts import ErrorOutput, OperationResult
from api.errors import ApplicationError, ErrorHandler

from .base import MiddlewareRequest, NextHandler


class ErrorMiddleware:
    def process(self, request: MiddlewareRequest, next_handler: NextHandler) -> OperationResult[Any]:
        try:
            result = next_handler(request)
            if not isinstance(result, OperationResult):
                raise ApplicationError.unexpected(correlation_id=self._correlation_id(request))
            if result.success:
                self._validate_success_data(request, result.data)
            if result.error is not None and result.error.correlation_id != self._correlation_id(request):
                correlation_id = self._correlation_id(request)
                if correlation_id is not None:
                    return OperationResult.fail(replace(result.error, correlation_id=correlation_id))
            return result
        except BaseException as exc:
            error = ErrorHandler.classify_exception(exc, request.context)
            return OperationResult.fail(ErrorHandler.to_public(error, request.context))

    @staticmethod
    def _correlation_id(request: MiddlewareRequest) -> str | None:
        return request.context.correlation_id if request.context else None

    def _validate_success_data(self, request: MiddlewareRequest, data: Any) -> None:
        """Reject a successful result whose payload contradicts the service contract.

        Concrete services carry the same return annotations as their Scrum 7
        interfaces. Test doubles may omit annotations, in which case the
        middleware preserves their runtime result and still validates the
        outer OperationResult envelope.
        """
        method = getattr(request.service, request.method_name, None)
        if method is None:
            raise ApplicationError.unexpected(correlation_id=self._correlation_id(request))
        try:
            annotation = get_type_hints(method).get("return")
        except (NameError, TypeError):
            annotation = None
        if annotation is None:
            return
        result_args = get_args(annotation)
        if not result_args:
            return
        expected = result_args[0]
        if not self._matches(data, expected):
            raise ApplicationError.unexpected(correlation_id=self._correlation_id(request))

    def _matches(self, value: Any, expected: Any) -> bool:
        if expected is Any:
            return True
        if expected is type(None):
            return value is None
        origin = get_origin(expected)
        args = get_args(expected)
        if origin in (UnionType,):
            return any(self._matches(value, option) for option in args)
        if origin is list:
            return isinstance(value, list) and all(self._matches(item, args[0]) for item in value)
        if origin is tuple:
            return isinstance(value, tuple)
        if origin is None:
            try:
                return isinstance(value, expected)
            except TypeError:
                return True
        return True
