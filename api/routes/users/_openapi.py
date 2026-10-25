"""OpenAPI schemas shared by user-management route groups."""

from __future__ import annotations

from dataclasses import MISSING, fields
from datetime import datetime
from types import UnionType
from typing import Union, get_args, get_origin, get_type_hints

from api.contracts import Unset


def response_envelopes(
    data_schema: dict[str, object],
    *,
    success_status: int = 200,
    nullable_data: bool = False,
) -> dict[int, dict[str, object]]:
    """Document the public success and centralized error envelopes."""

    success_data = {**data_schema, "nullable": True} if nullable_data else data_schema
    return {
        success_status: {
            "description": "Recurso creado correctamente." if success_status == 201 else "Operación realizada correctamente.",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["success", "data", "error"],
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": success_data,
                            "error": {"type": "null"},
                        },
                    }
                }
            },
        },
        400: _error_response("Falta un dato obligatorio o un valor tiene formato inválido."),
        403: _error_response("El actor está inactivo, no fue suministrado o no tiene permiso."),
        404: _error_response("El recurso o la ruta solicitada no existe."),
        405: _error_response("El método HTTP no está permitido para esta ruta."),
        409: _error_response("La aplicación informó un conflicto de unicidad."),
        422: _error_response("La aplicación informó una referencia inválida."),
        500: _error_response("Ocurrió un fallo de persistencia o un error interno."),
    }


def contract_schema(
    contract_type: type[object],
    *,
    excluded_fields: frozenset[str] = frozenset(),
) -> dict[str, object]:
    """Create an inline OpenAPI object schema from a public dataclass contract."""

    annotations = get_type_hints(contract_type)
    contract_fields = tuple(field for field in fields(contract_type) if field.name not in excluded_fields)
    return {
        "type": "object",
        "required": [field.name for field in contract_fields if field.default is MISSING and field.default_factory is MISSING],
        "properties": {field.name: value_schema(annotations[field.name]) for field in contract_fields},
    }


def value_schema(annotation: object) -> dict[str, object]:
    """Describe the primitive public types used by these route contracts."""

    if annotation is int:
        return {"type": "integer"}
    if annotation is str:
        return {"type": "string"}
    if annotation is bool:
        return {"type": "boolean"}
    if annotation is datetime:
        return {"type": "string", "format": "date-time"}

    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        options = get_args(annotation)
        public_options = [option for option in options if option not in (type(None), Unset)]
        if len(public_options) == 1:
            schema = value_schema(public_options[0])
            if type(None) in options:
                return {**schema, "nullable": True}
            return schema
    return {"type": "string"}


def _error_response(description: str) -> dict[str, object]:
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["success", "data", "error"],
                    "properties": {
                        "success": {"type": "boolean", "example": False},
                        "data": {"type": "null"},
                        "error": {
                            "type": "object",
                            "required": ["code", "message", "correlation_id", "details"],
                            "properties": {
                                "code": {"type": "string"},
                                "message": {"type": "string"},
                                "correlation_id": {"type": "string"},
                                "details": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "field": {"type": "string", "nullable": True},
                                            "entity": {"type": "string", "nullable": True},
                                            "reason": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                }
            }
        },
    }
