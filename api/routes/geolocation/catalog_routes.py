"""HTTP catalog and geolocation query routes."""

from __future__ import annotations

from dataclasses import fields
from types import UnionType
from typing import Annotated, Union, get_args, get_origin, get_type_hints

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from api.contracts import (
    ActionOutput,
    CommuneOutput,
    CrossBisCodeOutput,
    CrossQuadrantOutput,
    CrossSuffixLetterOutput,
    FailureTypeOutput,
    MunicipalityOutput,
    NeighborhoodOutput,
    PriorityOutput,
    RoadBisCodeOutput,
    RoadQuadrantOutput,
    RoadSuffixLetterOutput,
    RoadTypeOutput,
    RoleOutput,
    StatusOutput,
)
from api.dependencies import get_catalog_service
from api.http import HttpOperation, HttpOperationAdapter, get_http_adapter
from api.interfaces.services import CatalogServiceInterface

router = APIRouter(prefix="/catalogs", tags=["Catalogs and geolocation"])

CatalogServiceDependency = Annotated[CatalogServiceInterface, Depends(get_catalog_service)]
HttpAdapterDependency = Annotated[HttpOperationAdapter, Depends(get_http_adapter)]

_LIST_MUNICIPALITIES = HttpOperation("CatalogService", "list_municipalities")
_LIST_COMMUNES = HttpOperation("CatalogService", "list_communes")
_LIST_NEIGHBORHOODS_BY_MUNICIPALITY = HttpOperation("CatalogService", "list_neighborhoods_by_municipality")
_LIST_NEIGHBORHOODS_BY_COMMUNE = HttpOperation("CatalogService", "list_neighborhoods_by_commune")
_LIST_NEIGHBORHOODS_WITHOUT_COMMUNE = HttpOperation("CatalogService", "list_neighborhoods_without_commune")
_LIST_ROAD_TYPES = HttpOperation("CatalogService", "list_road_types")
_LIST_ROAD_SUFFIX_LETTERS = HttpOperation("CatalogService", "list_road_suffix_letters")
_LIST_ROAD_BIS_CODES = HttpOperation("CatalogService", "list_road_bis_codes")
_LIST_ROAD_QUADRANTS = HttpOperation("CatalogService", "list_road_quadrants")
_LIST_CROSS_SUFFIX_LETTERS = HttpOperation("CatalogService", "list_cross_suffix_letters")
_LIST_CROSS_BIS_CODES = HttpOperation("CatalogService", "list_cross_bis_codes")
_LIST_CROSS_QUADRANTS = HttpOperation("CatalogService", "list_cross_quadrants")
_LIST_ROLES = HttpOperation("CatalogService", "list_roles")
_LIST_PRIORITIES = HttpOperation("CatalogService", "list_priorities")
_LIST_FAILURE_TYPES = HttpOperation("CatalogService", "list_failure_types")
_LIST_FAILURE_TYPES_BY_PRIORITY = HttpOperation("CatalogService", "list_failure_types_by_priority")
_LIST_STATUSES = HttpOperation("CatalogService", "list_statuses")
_LIST_ACTIONS = HttpOperation("CatalogService", "list_actions")


def _execute(
    request: Request,
    adapter: HttpOperationAdapter,
    service: CatalogServiceInterface,
    operation: HttpOperation,
    *arguments: object,
) -> JSONResponse:
    """Execute a catalog operation through the shared HTTP adapter."""

    return adapter.execute(request, operation, service, *arguments)


def _catalog_responses(output_type: type[object]) -> dict[int, dict[str, object]]:
    """Build the common success and error envelope documentation for one route."""

    return {
        200: {
            "description": "Consulta realizada correctamente.",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["success", "data", "error"],
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {"type": "array", "items": _output_schema(output_type)},
                            "error": {"type": "null"},
                        },
                    }
                }
            },
        },
        400: _error_response("El identificador de ruta tiene un formato inválido."),
        403: _error_response("El actor autenticado está inactivo o no puede ejecutar la operación."),
        404: _error_response("La ruta solicitada no existe."),
        405: _error_response("El método HTTP no está permitido para esta ruta."),
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


def _output_schema(output_type: type[object]) -> dict[str, object]:
    annotations = get_type_hints(output_type)
    return {
        "type": "object",
        "required": [field.name for field in fields(output_type) if field.name in annotations],
        "properties": {name: _value_schema(annotation) for name, annotation in annotations.items()},
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
        non_null = [option for option in options if option is not type(None)]
        if len(non_null) == 1 and len(non_null) != len(options):
            return {**_value_schema(non_null[0]), "nullable": True}
    return {"type": "string"}


@router.get(
    "/municipalities",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(MunicipalityOutput),
    summary="Consultar municipios disponibles",
    description="Devuelve los municipios disponibles para ubicar un reporte.",
)
def list_municipalities(
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_MUNICIPALITIES)


@router.get(
    "/municipalities/{municipality_id}/communes",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(CommuneOutput),
    summary="Consultar comunas de un municipio",
    description="Devuelve las comunas asociadas al municipio indicado.",
)
def list_communes(
    municipality_id: int,
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_COMMUNES, municipality_id)


@router.get(
    "/municipalities/{municipality_id}/neighborhoods",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(NeighborhoodOutput),
    summary="Consultar barrios de un municipio",
    description="Devuelve los barrios asociados al municipio indicado.",
)
def list_neighborhoods_by_municipality(
    municipality_id: int,
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_NEIGHBORHOODS_BY_MUNICIPALITY, municipality_id)


@router.get(
    "/municipalities/{municipality_id}/neighborhoods/without-commune",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(NeighborhoodOutput),
    summary="Consultar barrios sin comuna de un municipio",
    description="Devuelve los barrios del municipio indicado que no tienen una comuna asignada.",
)
def list_neighborhoods_without_commune(
    municipality_id: int,
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_NEIGHBORHOODS_WITHOUT_COMMUNE, municipality_id)


@router.get(
    "/communes/{commune_id}/neighborhoods",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(NeighborhoodOutput),
    summary="Consultar barrios de una comuna",
    description="Devuelve los barrios asociados a la comuna indicada.",
)
def list_neighborhoods_by_commune(
    commune_id: int,
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_NEIGHBORHOODS_BY_COMMUNE, commune_id)


@router.get(
    "/road-types",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(RoadTypeOutput),
    summary="Consultar tipos de vía",
    description="Devuelve los tipos de vía permitidos para construir una dirección.",
)
def list_road_types(
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_ROAD_TYPES)


@router.get(
    "/road-suffix-letters",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(RoadSuffixLetterOutput),
    summary="Consultar sufijos de vía principal",
    description="Devuelve las letras de sufijo admitidas para la vía principal.",
)
def list_road_suffix_letters(
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_ROAD_SUFFIX_LETTERS)


@router.get(
    "/road-bis-codes",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(RoadBisCodeOutput),
    summary="Consultar códigos BIS de vía principal",
    description="Devuelve los códigos BIS admitidos para la vía principal.",
)
def list_road_bis_codes(
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_ROAD_BIS_CODES)


@router.get(
    "/road-quadrants",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(RoadQuadrantOutput),
    summary="Consultar cuadrantes de vía principal",
    description="Devuelve los cuadrantes admitidos para la vía principal.",
)
def list_road_quadrants(
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_ROAD_QUADRANTS)


@router.get(
    "/cross-suffix-letters",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(CrossSuffixLetterOutput),
    summary="Consultar sufijos de vía de cruce",
    description="Devuelve las letras de sufijo admitidas para la vía de cruce.",
)
def list_cross_suffix_letters(
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_CROSS_SUFFIX_LETTERS)


@router.get(
    "/cross-bis-codes",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(CrossBisCodeOutput),
    summary="Consultar códigos BIS de vía de cruce",
    description="Devuelve los códigos BIS admitidos para la vía de cruce.",
)
def list_cross_bis_codes(
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_CROSS_BIS_CODES)


@router.get(
    "/cross-quadrants",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(CrossQuadrantOutput),
    summary="Consultar cuadrantes de vía de cruce",
    description="Devuelve los cuadrantes admitidos para la vía de cruce.",
)
def list_cross_quadrants(
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_CROSS_QUADRANTS)


@router.get(
    "/roles",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(RoleOutput),
    summary="Consultar roles disponibles",
    description="Devuelve los roles disponibles para las cuentas de usuario.",
)
def list_roles(
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_ROLES)


@router.get(
    "/priorities",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(PriorityOutput),
    summary="Consultar prioridades disponibles",
    description="Devuelve las prioridades disponibles para los reportes.",
)
def list_priorities(
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_PRIORITIES)


@router.get(
    "/failure-types",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(FailureTypeOutput),
    summary="Consultar tipos de falla",
    description="Devuelve los tipos de falla de alumbrado público disponibles.",
)
def list_failure_types(
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_FAILURE_TYPES)


@router.get(
    "/priorities/{priority_id}/failure-types",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(FailureTypeOutput),
    summary="Consultar tipos de falla por prioridad",
    description="Devuelve los tipos de falla asociados a la prioridad indicada.",
)
def list_failure_types_by_priority(
    priority_id: int,
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_FAILURE_TYPES_BY_PRIORITY, priority_id)


@router.get(
    "/statuses",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(StatusOutput),
    summary="Consultar estados de tickets",
    description="Devuelve los estados disponibles para interpretar la situación de un ticket.",
)
def list_statuses(
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_STATUSES)


@router.get(
    "/actions",
    status_code=200,
    response_class=JSONResponse,
    responses=_catalog_responses(ActionOutput),
    summary="Consultar acciones de historial",
    description="Devuelve las acciones disponibles para los eventos del historial de tickets.",
)
def list_actions(
    request: Request,
    catalog_service: CatalogServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, catalog_service, _LIST_ACTIONS)
