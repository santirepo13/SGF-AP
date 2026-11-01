"""Shared service execution, authorization, error and transaction handling."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Generic, TypeVar

from api.contracts import ExecutionContext, OperationResult
from api.errors import ApplicationError, ErrorHandler

T = TypeVar("T")


class TransactionCoordinator:
    """Small injected transaction boundary; it never opens a connection."""

    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class ServiceBase:
    def __init__(
        self,
        *,
        transaction: TransactionCoordinator | None = None,
        authorizer: Callable[[ExecutionContext, str], bool] | None = None,
    ) -> None:
        self.transaction = transaction
        self.authorizer = authorizer

    def _execute(
        self,
        context: ExecutionContext,
        operation: str,
        action: Callable[[], T],
        *,
        write: bool = False,
        actor_required: bool = False,
    ) -> OperationResult[T]:
        try:
            if actor_required and context.actor is None:
                raise ApplicationError.access_token_required(correlation_id=context.correlation_id)
            if context.actor is not None and not context.actor.active:
                raise ApplicationError.inactive_user(correlation_id=context.correlation_id)
            if self.authorizer is not None and not self.authorizer(context, operation):
                raise ApplicationError.forbidden(operation, correlation_id=context.correlation_id)
            value = action()
        except BaseException as exc:
            if write:
                self._rollback()
            return self._failure(exc, context)

        if write and self.transaction is not None:
            try:
                self.transaction.commit()
            except BaseException as exc:
                self._rollback()
                error = ApplicationError.result_unknown(
                    correlation_id=context.correlation_id,
                    cause=exc,
                )
                return OperationResult.fail(ErrorHandler.to_public(error, context))
        return OperationResult.ok(value)

    def _rollback(self) -> None:
        if self.transaction is None:
            return
        try:
            self.transaction.rollback()
        except BaseException:
            pass

    @staticmethod
    def _failure(exc: BaseException, context: ExecutionContext) -> OperationResult:
        error = ErrorHandler.classify_exception(exc, context)
        return OperationResult.fail(ErrorHandler.to_public(error, context))

    @staticmethod
    def _require(value: Any, field: str, context: ExecutionContext) -> None:
        if value is None or value == "":
            raise ApplicationError.required_field(field, correlation_id=context.correlation_id)

    @staticmethod
    def _missing(entity: str, context: ExecutionContext) -> ApplicationError:
        return ApplicationError.resource_not_found(entity, correlation_id=context.correlation_id)
