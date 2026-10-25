"""HTTP user lookup and administration routes."""

from __future__ import annotations

from dataclasses import MISSING, fields
from types import UnionType
from typing import Annotated, Union, get_args, get_origin, get_type_hints

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from api.contracts import (
    Unset,
    UserActivationInput,
    UserCreateInput,
    UserFilters,
    UserOutput,
    UserUpdateInput,
)
from api.dependencies import get_user_service
from api.http import (
    HttpOperation,
    HttpOperationAdapter,
    build_contract,
    get_http_adapter,
    get_request_correlation_id,
    read_json_contract,
)
from api.interfaces.services import UserServiceInterface

router = APIRouter(prefix="/users", tags=["Users"])

UserServiceDependency = Annotated[UserServiceInterface, Depends(get_user_service)]
HttpAdapterDependency = Annotated[HttpOperationAdapter, Depends(get_http_adapter)]
CorrelationIdDependency = Annotated[str, Depends(get_request_correlation_id)]

_GET_BY_ID = HttpOperation("UserService", "get_by_id")
_GET_BY_EMAIL = HttpOperation("UserService", "get_by_email")
_LIST_BY_FILTERS = HttpOperation("UserService", "list_by_filters")
_CREATE = HttpOperation("UserService", "create", success_status=201)
_UPDATE = HttpOperation("UserService", "update")
_SET_ACTIVE = HttpOperation("UserService", "set_active")


def _execute(
    request: Request,
    adapter: HttpOperationAdapter,
    service: UserServiceInterface,
    operation: HttpOperation,
    *arguments: object,
) -> JSONResponse:
    """Execute one user operation through the shared HTTP adapter."""

    return adapter.execute(request, operation, service, *arguments)


def _user_responses(
    data_schema: dict[str, object],
    *,
    success_status: int = 200,
) -> dict[int, dict[str, object]]:
    """Build common success and error envelope documentation for user operations."""

    return {
        success_status: {
            "description": "Usuario creado correctamente." if success_status == 201 else "Operación realizada correctamente.",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["success", "data", "error"],
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": data_schema,
                            "error": {"type": "null"},
                        },
                    }
                }
            },
        },
        400: _error_response("Falta un dato obligatorio o un valor tiene formato inválido."),
        403: _error_response("El actor está inactivo, no fue suministrado o no tiene permiso."),
        404: _error_response("El usuario o la ruta solicitada no existe."),
        405: _error_response("El método HTTP no está permitido para esta ruta."),
        409: _error_response("La aplicación informó un conflicto de unicidad."),
        422: _error_response("La aplicación informó una referencia inválida."),
        500: _error_response("Ocurrió un fallo de persistencia o un error interno."),
    }


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


def _contract_schema(
    contract_type: type[object],
    *,
    excluded_fields: frozenset[str] = frozenset(),
) -> dict[str, object]:
    annotations = get_type_hints(contract_type)
    contract_fields = tuple(field for field in fields(contract_type) if field.name not in excluded_fields)
    return {
        "type": "object",
        "required": [field.name for field in contract_fields if field.default is MISSING and field.default_factory is MISSING],
        "properties": {field.name: _value_schema(annotations[field.name]) for field in contract_fields},
    }


def _value_schema(annotation: object) -> dict[str, object]:
    if annotation is int:
        return {"type": "integer"}
    if annotation is str:
        return {"type": "string"}
    if annotation is bool:
        return {"type": "boolean"}

    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        options = get_args(annotation)
        public_options = [option for option in options if option not in (type(None), Unset)]
        if len(public_options) == 1:
            schema = _value_schema(public_options[0])
            if type(None) in options:
                return {**schema, "nullable": True}
            return schema
    return {"type": "string"}


_USER_OUTPUT_SCHEMA = _contract_schema(UserOutput)
_USER_CREATE_SCHEMA = _contract_schema(UserCreateInput)
_USER_UPDATE_SCHEMA = _contract_schema(UserUpdateInput, excluded_fields=frozenset({"user_id"}))
_USER_ACTIVATION_SCHEMA = _contract_schema(UserActivationInput, excluded_fields=frozenset({"user_id"}))


@router.get(
    "/by-email",
    status_code=200,
    response_class=JSONResponse,
    responses=_user_responses(_USER_OUTPUT_SCHEMA),
    summary="Consultar un usuario por correo electrónico",
    description="Devuelve los datos públicos del usuario asociado al correo indicado.",
)
def get_by_email(
    email: Annotated[str, Query(description="Correo electrónico del usuario.")],
    request: Request,
    user_service: UserServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, user_service, _GET_BY_EMAIL, email)


@router.get(
    "",
    status_code=200,
    response_class=JSONResponse,
    responses=_user_responses({"type": "array", "items": _USER_OUTPUT_SCHEMA}),
    summary="Listar usuarios mediante filtros",
    description="Lista usuarios. Los filtros de correo, rol y activación pueden combinarse; active=false se conserva como filtro.",
)
def list_by_filters(
    request: Request,
    user_service: UserServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
    email: Annotated[str | None, Query(description="Correo electrónico que se desea filtrar.")] = None,
    role_id: Annotated[int | None, Query(description="Identificador del rol que se desea filtrar.")] = None,
    active: Annotated[bool | None, Query(description="Estado de activación que se desea filtrar.")] = None,
) -> JSONResponse:
    filters = build_contract(
        UserFilters,
        {"email": email, "role_id": role_id, "active": active},
        correlation_id=correlation_id,
    )
    return _execute(request, adapter, user_service, _LIST_BY_FILTERS, filters)


@router.get(
    "/{user_id}",
    status_code=200,
    response_class=JSONResponse,
    responses=_user_responses(_USER_OUTPUT_SCHEMA),
    summary="Consultar un usuario por identificador",
    description="Devuelve los datos públicos y el estado de activación del usuario indicado.",
)
def get_by_id(
    user_id: int,
    request: Request,
    user_service: UserServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, user_service, _GET_BY_ID, user_id)


@router.post(
    "",
    status_code=201,
    response_class=JSONResponse,
    responses=_user_responses(_USER_OUTPUT_SCHEMA, success_status=201),
    summary="Crear un usuario",
    description="Crea una cuenta aplicando active=true cuando el campo se omite.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _USER_CREATE_SCHEMA}},
        }
    },
)
async def create(
    request: Request,
    user_service: UserServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(request, UserCreateInput, correlation_id=correlation_id)
    return _execute(request, adapter, user_service, _CREATE, data)


@router.patch(
    "/{user_id}",
    status_code=200,
    response_class=JSONResponse,
    responses=_user_responses(_USER_OUTPUT_SCHEMA),
    summary="Actualizar parcialmente un usuario",
    description="Actualiza solo los campos enviados; los omitidos se mantienen como UNSET y no modifican el registro.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _USER_UPDATE_SCHEMA}},
        }
    },
)
async def update(
    user_id: int,
    request: Request,
    user_service: UserServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(
        request,
        UserUpdateInput,
        path_values={"user_id": user_id},
        correlation_id=correlation_id,
    )
    return _execute(request, adapter, user_service, _UPDATE, data)


@router.patch(
    "/{user_id}/activation",
    status_code=200,
    response_class=JSONResponse,
    responses=_user_responses(_USER_OUTPUT_SCHEMA),
    summary="Activar o desactivar un usuario",
    description="Actualiza el estado active del usuario indicado sin alterar sus relaciones.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _USER_ACTIVATION_SCHEMA}},
        }
    },
)
async def set_active(
    user_id: int,
    request: Request,
    user_service: UserServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(
        request,
        UserActivationInput,
        path_values={"user_id": user_id},
        correlation_id=correlation_id,
    )
    return _execute(request, adapter, user_service, _SET_ACTIVE, data)
