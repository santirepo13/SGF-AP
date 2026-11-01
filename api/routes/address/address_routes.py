"""HTTP address lookup, search, creation, and formatting routes."""

from __future__ import annotations

from dataclasses import MISSING, fields
from datetime import datetime
from types import UnionType
from typing import Annotated, Union, get_args, get_origin, get_type_hints

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from api.contracts import AddressComponentsInput, AddressCreateInput, AddressOutput
from api.dependencies import get_address_service
from api.http import (
    HttpOperation,
    HttpOperationAdapter,
    build_contract,
    get_http_adapter,
    get_request_correlation_id,
    read_json_contract,
)
from api.interfaces.services import AddressServiceInterface

router = APIRouter(prefix="/addresses", tags=["Addresses"])

AddressServiceDependency = Annotated[AddressServiceInterface, Depends(get_address_service)]
HttpAdapterDependency = Annotated[HttpOperationAdapter, Depends(get_http_adapter)]
CorrelationIdDependency = Annotated[str, Depends(get_request_correlation_id)]

_FIND_BY_COMPONENTS = HttpOperation("AddressService", "find_by_components")
_GET_BY_ID = HttpOperation("AddressService", "get_by_id")
_CREATE_OR_REUSE = HttpOperation("AddressService", "create_or_reuse")
_FORMAT_ADDRESS = HttpOperation("AddressService", "format_address")


def _execute(
    request: Request,
    adapter: HttpOperationAdapter,
    service: AddressServiceInterface,
    operation: HttpOperation,
    *arguments: object,
) -> JSONResponse:
    """Execute one address operation through the shared HTTP adapter."""

    return adapter.execute(request, operation, service, *arguments)


def _address_responses(data_schema: dict[str, object], *, nullable_data: bool = False) -> dict[int, dict[str, object]]:
    """Build common success and error envelope documentation for address operations."""

    success_data = {**data_schema, "nullable": True} if nullable_data else data_schema
    return {
        200: {
            "description": "Operación realizada correctamente.",
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
        400: _error_response("Falta un componente obligatorio o un valor tiene formato inválido."),
        403: _error_response("El actor está inactivo, no fue suministrado o no tiene permiso."),
        404: _error_response("La dirección o la ruta solicitada no existe."),
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


def _contract_schema(contract_type: type[object]) -> dict[str, object]:
    annotations = get_type_hints(contract_type)
    contract_fields = fields(contract_type)
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
    if annotation is datetime:
        return {"type": "string", "format": "date-time"}

    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        options = get_args(annotation)
        non_null = [option for option in options if option is not type(None)]
        if len(non_null) == 1 and len(non_null) != len(options):
            return {**_value_schema(non_null[0]), "nullable": True}
    return {"type": "string"}


_ADDRESS_OUTPUT_SCHEMA = _contract_schema(AddressOutput)
_ADDRESS_CREATE_SCHEMA = _contract_schema(AddressCreateInput)


@router.get(
    "/search",
    status_code=200,
    response_class=JSONResponse,
    responses=_address_responses(_ADDRESS_OUTPUT_SCHEMA, nullable_data=True),
    summary="Buscar una dirección por componentes",
    description="Busca una dirección por sus componentes. Una búsqueda sin coincidencia devuelve data como null.",
)
def find_by_components(
    request: Request,
    road_type_code: Annotated[str, Query(description="Código del tipo de vía.")],
    road_number: Annotated[int, Query(description="Número de la vía principal.")],
    cross_road_number: Annotated[int, Query(description="Número de la vía de cruce.")],
    door_plate_number: Annotated[int, Query(description="Número de placa.")],
    address_service: AddressServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
    road_suffix_letter_code: Annotated[str | None, Query(description="Sufijo de la vía principal.")] = None,
    road_bis_code: Annotated[str | None, Query(description="Código BIS de la vía principal.")] = None,
    road_bis_suffix: Annotated[str | None, Query(description="Sufijo BIS de la vía principal.")] = None,
    road_quadrant_code: Annotated[int | None, Query(description="Cuadrante de la vía principal.")] = None,
    cross_suffix_letter_code: Annotated[str | None, Query(description="Sufijo de la vía de cruce.")] = None,
    cross_bis_code: Annotated[str | None, Query(description="Código BIS de la vía de cruce.")] = None,
    cross_bis_suffix: Annotated[str | None, Query(description="Sufijo BIS de la vía de cruce.")] = None,
    cross_quadrant_code: Annotated[int | None, Query(description="Cuadrante de la vía de cruce.")] = None,
    neighborhood_id: Annotated[int | None, Query(description="Identificador del barrio.")] = None,
) -> JSONResponse:
    components = build_contract(
        AddressComponentsInput,
        {
            "road_type_code": road_type_code,
            "road_number": road_number,
            "cross_road_number": cross_road_number,
            "door_plate_number": door_plate_number,
            "road_suffix_letter_code": road_suffix_letter_code,
            "road_bis_code": road_bis_code,
            "road_bis_suffix": road_bis_suffix,
            "road_quadrant_code": road_quadrant_code,
            "cross_suffix_letter_code": cross_suffix_letter_code,
            "cross_bis_code": cross_bis_code,
            "cross_bis_suffix": cross_bis_suffix,
            "cross_quadrant_code": cross_quadrant_code,
            "neighborhood_id": neighborhood_id,
        },
        correlation_id=correlation_id,
    )
    return _execute(request, adapter, address_service, _FIND_BY_COMPONENTS, components)


@router.get(
    "/{address_id}/formatted",
    status_code=200,
    response_class=JSONResponse,
    responses=_address_responses({"type": "string"}),
    summary="Obtener la representación textual de una dirección",
    description="Devuelve la representación textual legible de la dirección indicada.",
)
def format_address(
    address_id: int,
    request: Request,
    address_service: AddressServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, address_service, _FORMAT_ADDRESS, address_id)


@router.get(
    "/{address_id}",
    status_code=200,
    response_class=JSONResponse,
    responses=_address_responses(_ADDRESS_OUTPUT_SCHEMA),
    summary="Consultar una dirección por identificador",
    description="Devuelve los componentes y metadatos públicos de la dirección indicada.",
)
def get_by_id(
    address_id: int,
    request: Request,
    address_service: AddressServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, address_service, _GET_BY_ID, address_id)


@router.post(
    "",
    status_code=200,
    response_class=JSONResponse,
    responses=_address_responses(_ADDRESS_OUTPUT_SCHEMA),
    summary="Crear o reutilizar una dirección",
    description="Crea una dirección o reutiliza una existente con los mismos componentes.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _ADDRESS_CREATE_SCHEMA}},
        }
    },
)
async def create_or_reuse(
    request: Request,
    address_service: AddressServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(request, AddressCreateInput, correlation_id=correlation_id)
    return _execute(request, adapter, address_service, _CREATE_OR_REUSE, data)
