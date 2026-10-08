"""Safe execution logging around the complete pipeline."""

from __future__ import annotations

from time import monotonic
from typing import Any

from api.errors import ErrorHandler

from .base import ExecutionLogger, MiddlewareRequest, NextHandler


class ExecutionLoggingMiddleware:
    def __init__(self, logger: ExecutionLogger, clock=monotonic) -> None:
        self.logger = logger
        self.clock = clock

    def process(self, request: MiddlewareRequest, next_handler: NextHandler):
        started = self.clock()
        context = request.context
        base = {"correlation_id": context.correlation_id if context else None, "operation": request.operation_name, "actor_user_id": context.actor.user_id if context and context.actor else None}
        try:
            self.logger.start({**base, "event": "started"})
        except BaseException:
            pass
        result = None
        failure = None
        try:
            result = next_handler(request)
            return result
        except BaseException as exc:
            failure = exc
            raise
        finally:
            current_context = request.context
            error_code = getattr(getattr(result, "error", None), "code", None)
            if error_code is None and failure is not None:
                error_code = ErrorHandler.classify_exception(failure, current_context).code.value
            record = {
                **base,
                "correlation_id": current_context.correlation_id if current_context else base["correlation_id"],
                "actor_user_id": current_context.actor.user_id if current_context and current_context.actor else base["actor_user_id"],
                "event": "finished",
                "duration_seconds": self.clock() - started,
                "success": getattr(result, "success", False),
                "error_code": error_code,
            }
            try:
                self.logger.finish(record)
            except BaseException:
                pass
