"""Immutable public error catalog."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .error_codes import ErrorCode


@dataclass(frozen=True)
class ErrorDefinition:
    code: ErrorCode
    category: str
    message: str


_DEFINITIONS: dict[ErrorCode, ErrorDefinition] = {
    ErrorCode.REQUIRED_FIELD_MISSING: ErrorDefinition(ErrorCode.REQUIRED_FIELD_MISSING, "Validación", "Falta un dato obligatorio."),
    ErrorCode.INVALID_VALUE: ErrorDefinition(ErrorCode.INVALID_VALUE, "Validación", "Uno o más datos tienen un tipo, formato o valor inválido."),
    ErrorCode.RESOURCE_NOT_FOUND: ErrorDefinition(ErrorCode.RESOURCE_NOT_FOUND, "Recurso", "No se encontró el registro solicitado."),
    ErrorCode.INVALID_REFERENCE: ErrorDefinition(ErrorCode.INVALID_REFERENCE, "Relación", "Una referencia indicada no existe o no corresponde al registro relacionado."),
    ErrorCode.UNIQUE_CONFLICT: ErrorDefinition(ErrorCode.UNIQUE_CONFLICT, "Conflicto", "Ya existe un registro con los datos que deben ser únicos."),
    ErrorCode.INACTIVE_USER: ErrorDefinition(ErrorCode.INACTIVE_USER, "Usuario", "La cuenta no se encuentra habilitada."),
    ErrorCode.INVALID_CREDENTIALS: ErrorDefinition(ErrorCode.INVALID_CREDENTIALS, "Usuario", "El correo electrónico o la contraseña son incorrectos."),
    ErrorCode.INVALID_ACCESS_TOKEN: ErrorDefinition(ErrorCode.INVALID_ACCESS_TOKEN, "Usuario", "La credencial de acceso no es válida."),
    ErrorCode.ACCESS_TOKEN_EXPIRED: ErrorDefinition(ErrorCode.ACCESS_TOKEN_EXPIRED, "Usuario", "La credencial de acceso ha vencido."),
    ErrorCode.ACCESS_TOKEN_REQUIRED: ErrorDefinition(ErrorCode.ACCESS_TOKEN_REQUIRED, "Usuario", "Se requiere una credencial de acceso."),
    ErrorCode.FORBIDDEN_OPERATION: ErrorDefinition(ErrorCode.FORBIDDEN_OPERATION, "Permisos", "No tiene autorización para realizar esta operación."),
    ErrorCode.INVALID_TICKET_STATE: ErrorDefinition(ErrorCode.INVALID_TICKET_STATE, "Ticket", "La operación no está permitida en el estado actual del ticket."),
    ErrorCode.CATALOG_VALUE_UNAVAILABLE: ErrorDefinition(ErrorCode.CATALOG_VALUE_UNAVAILABLE, "Catálogo", "Un valor de catálogo requerido para la operación no está disponible."),
    ErrorCode.API_AUTHENTICATION_REQUIRED: ErrorDefinition(ErrorCode.API_AUTHENTICATION_REQUIRED, "Autenticación", "Autenticación de API requerida o credenciales inválidas."),
    ErrorCode.PERSISTENCE_FAILURE: ErrorDefinition(ErrorCode.PERSISTENCE_FAILURE, "Persistencia", "No fue posible completar la operación de persistencia."),
    ErrorCode.UNEXPECTED_ERROR: ErrorDefinition(ErrorCode.UNEXPECTED_ERROR, "Interno", "Ocurrió un error interno inesperado."),
    ErrorCode.HTTP_ROUTE_NOT_FOUND: ErrorDefinition(ErrorCode.HTTP_ROUTE_NOT_FOUND, "HTTP", "La ruta solicitada no existe."),
    ErrorCode.HTTP_METHOD_NOT_ALLOWED: ErrorDefinition(ErrorCode.HTTP_METHOD_NOT_ALLOWED, "HTTP", "El método HTTP no está permitido para esta ruta."),
}


if set(_DEFINITIONS) != set(ErrorCode):
    raise RuntimeError("error catalog must contain exactly one definition per ErrorCode")

_IMMUTABLE_DEFINITIONS: Mapping[ErrorCode, ErrorDefinition] = MappingProxyType(_DEFINITIONS)


class ErrorCatalog:
    """Read-only access to the application's public error definitions."""

    definitions = _IMMUTABLE_DEFINITIONS

    @classmethod
    def get(cls, code: ErrorCode) -> ErrorDefinition:
        return cls.definitions[code]

    @classmethod
    def all(cls) -> tuple[ErrorDefinition, ...]:
        return tuple(cls.definitions.values())
