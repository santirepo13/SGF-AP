"""Central classification and public error translation."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from api.contracts.error_types import ErrorDetail, ErrorOutput
from api.contracts.execution_context import ExecutionContext

from .application_error import ApplicationError
from .error_codes import ErrorCode


@dataclass(frozen=True)
class PersistenceContext:
    """Safe context used to decide whether a SQL failure came from input."""

    operation: str
    entity: str | None = None
    field: str | None = None
    input_origin: bool = False


class ErrorHandler:
    """Translate known and technical failures without exposing diagnostics."""

    @classmethod
    def classify_exception(
        cls,
        exception: BaseException,
        context: ExecutionContext | None = None,
        *,
        persistence_context: PersistenceContext | None = None,
    ) -> ApplicationError:
        if isinstance(exception, ApplicationError):
            return exception

        sqlstate = cls._sqlstate(exception)
        if sqlstate is not None:
            return cls.translate_persistence(exception, context, persistence_context=persistence_context)

        if isinstance(exception, ValueError) and persistence_context and persistence_context.input_origin:
            return ApplicationError.invalid_value(
                persistence_context.field,
                "El valor recibido no cumple la regla esperada.",
                entity=persistence_context.entity,
                correlation_id=cls._context_correlation(context),
            )

        return ApplicationError.unexpected(
            correlation_id=cls._context_correlation(context),
            cause=exception,
        )

    @classmethod
    def translate_persistence(
        cls,
        exception: BaseException,
        context: ExecutionContext | None = None,
        *,
        persistence_context: PersistenceContext | None = None,
    ) -> ApplicationError:
        sqlstate = cls._sqlstate(exception)
        if sqlstate is None:
            return ApplicationError.persistence_failure(
                correlation_id=cls._context_correlation(context),
                cause=exception,
            )

        persistence_context = persistence_context or PersistenceContext("persistence")
        field = cls._diagnostic_value(exception, "column_name") or persistence_context.field
        entity = cls._diagnostic_value(exception, "table_name") or persistence_context.entity
        correlation_id = cls._context_correlation(context)
        input_origin = persistence_context.input_origin

        if sqlstate == "23502":
            if input_origin:
                return ApplicationError.required_field(field or "unknown", entity=entity, correlation_id=correlation_id)
            return ApplicationError.persistence_failure(correlation_id=correlation_id, cause=exception)
        if sqlstate == "23503":
            return ApplicationError.invalid_reference(field, "La referencia indicada no existe o no corresponde al registro relacionado.", entity=entity, correlation_id=correlation_id, cause=exception)
        if sqlstate == "23505":
            return ApplicationError.unique_conflict(field, entity=entity, correlation_id=correlation_id, cause=exception)
        if sqlstate in {"23514", "22001", "22P02", "22003"} and input_origin:
            return ApplicationError.invalid_value(field, "El valor recibido no cumple la regla esperada.", entity=entity, correlation_id=correlation_id)
        if sqlstate.startswith("08") or sqlstate in {"40001", "40P01"}:
            return ApplicationError.persistence_failure(correlation_id=correlation_id, cause=exception)
        return ApplicationError.persistence_failure(correlation_id=correlation_id, cause=exception)

    @classmethod
    def to_public(
        cls,
        error: ApplicationError,
        context: ExecutionContext | None = None,
    ) -> ErrorOutput:
        correlation_id = error.correlation_id or cls._context_correlation(context) or str(uuid4())
        return ErrorOutput(
            code=error.code.value,
            message=error.message,
            details=error.details,
            correlation_id=correlation_id,
        )

    @classmethod
    def handle(
        cls,
        exception: BaseException,
        context: ExecutionContext | None = None,
        *,
        persistence_context: PersistenceContext | None = None,
    ) -> ErrorOutput:
        error = cls.classify_exception(exception, context, persistence_context=persistence_context)
        return cls.to_public(error, context)

    @staticmethod
    def _context_correlation(context: ExecutionContext | None) -> str | None:
        return context.correlation_id if context and context.correlation_id else None

    @staticmethod
    def _diagnostic_value(exception: BaseException, name: str) -> str | None:
        diagnostic = getattr(exception, "diag", None)
        value = getattr(diagnostic, name, None) if diagnostic is not None else None
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _sqlstate(exception: BaseException) -> str | None:
        direct = getattr(exception, "sqlstate", None) or getattr(exception, "pgcode", None)
        if isinstance(direct, str) and direct:
            return direct
        diagnostic = getattr(exception, "diag", None)
        value = getattr(diagnostic, "sqlstate", None) if diagnostic is not None else None
        return value if isinstance(value, str) and value else None
