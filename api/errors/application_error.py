"""Framework-independent application exception."""

from __future__ import annotations

from collections.abc import Iterable

from api.contracts.error_types import ErrorDetail

from .error_catalog import ErrorCatalog
from .error_codes import ErrorCode


class ApplicationError(Exception):
    """Known error that can safely cross application layers."""

    def __init__(
        self,
        code: ErrorCode,
        details: Iterable[ErrorDetail] = (),
        correlation_id: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        self.code = code
        self.details = tuple(details)
        self.correlation_id = correlation_id
        self.cause = cause
        super().__init__(ErrorCatalog.get(code).message)
        if cause is not None:
            self.__cause__ = cause

    @property
    def message(self) -> str:
        return ErrorCatalog.get(self.code).message

    @classmethod
    def with_code(
        cls,
        code: ErrorCode,
        *,
        details: Iterable[ErrorDetail] = (),
        correlation_id: str | None = None,
        cause: BaseException | None = None,
    ) -> "ApplicationError":
        return cls(code, details, correlation_id, cause)

    @classmethod
    def required_field(cls, field: str, *, entity: str | None = None, correlation_id: str | None = None) -> "ApplicationError":
        return cls(ErrorCode.REQUIRED_FIELD_MISSING, (ErrorDetail(field, entity, "El campo es obligatorio."),), correlation_id)

    @classmethod
    def invalid_value(cls, field: str | None, reason: str, *, entity: str | None = None, correlation_id: str | None = None, cause: BaseException | None = None) -> "ApplicationError":
        return cls(ErrorCode.INVALID_VALUE, (ErrorDetail(field, entity, reason),), correlation_id, cause)

    @classmethod
    def resource_not_found(cls, entity: str, *, correlation_id: str | None = None) -> "ApplicationError":
        return cls(ErrorCode.RESOURCE_NOT_FOUND, (ErrorDetail(None, entity, "El registro no existe."),), correlation_id)

    @classmethod
    def invalid_reference(cls, field: str | None, reason: str, *, entity: str | None = None, correlation_id: str | None = None, cause: BaseException | None = None) -> "ApplicationError":
        return cls(ErrorCode.INVALID_REFERENCE, (ErrorDetail(field, entity, reason),), correlation_id, cause)

    @classmethod
    def unique_conflict(cls, field: str | None = None, *, entity: str | None = None, correlation_id: str | None = None, cause: BaseException | None = None) -> "ApplicationError":
        details = () if field is None and entity is None else (ErrorDetail(field, entity, "El valor ya está registrado."),)
        return cls(ErrorCode.UNIQUE_CONFLICT, details, correlation_id, cause)

    @classmethod
    def inactive_user(cls, *, correlation_id: str | None = None) -> "ApplicationError":
        return cls(ErrorCode.INACTIVE_USER, correlation_id=correlation_id)

    @classmethod
    def forbidden(cls, operation: str | None = None, *, correlation_id: str | None = None) -> "ApplicationError":
        details = () if operation is None else (ErrorDetail(None, None, f"La operación {operation} no está autorizada."),)
        return cls(ErrorCode.FORBIDDEN_OPERATION, details, correlation_id)

    @classmethod
    def invalid_ticket_state(cls, *, correlation_id: str | None = None) -> "ApplicationError":
        return cls(ErrorCode.INVALID_TICKET_STATE, correlation_id=correlation_id)

    @classmethod
    def catalog_unavailable(cls, catalog: str, *, correlation_id: str | None = None) -> "ApplicationError":
        return cls(ErrorCode.CATALOG_VALUE_UNAVAILABLE, (ErrorDetail(None, catalog, "El valor requerido no está disponible."),), correlation_id)

    @classmethod
    def persistence_failure(cls, *, correlation_id: str | None = None, cause: BaseException | None = None) -> "ApplicationError":
        return cls(ErrorCode.PERSISTENCE_FAILURE, correlation_id=correlation_id, cause=cause)

    @classmethod
    def unexpected(cls, *, correlation_id: str | None = None, cause: BaseException | None = None) -> "ApplicationError":
        return cls(ErrorCode.UNEXPECTED_ERROR, correlation_id=correlation_id, cause=cause)
