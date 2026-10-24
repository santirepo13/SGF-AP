"""HTTP crew query and maintenance routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from api.contracts import CrewCreateInput, CrewMemberInput, CrewMemberOutput, CrewOutput, CrewUpdateInput
from api.dependencies import get_crew_service
from api.http import (
    HttpOperation,
    HttpOperationAdapter,
    get_http_adapter,
    get_request_correlation_id,
    read_json_contract,
)
from api.interfaces.services import CrewServiceInterface

from ._openapi import contract_schema, response_envelopes

router = APIRouter(prefix="/crews", tags=["Crews"])

CrewServiceDependency = Annotated[CrewServiceInterface, Depends(get_crew_service)]
HttpAdapterDependency = Annotated[HttpOperationAdapter, Depends(get_http_adapter)]
CorrelationIdDependency = Annotated[str, Depends(get_request_correlation_id)]

_LIST_ALL = HttpOperation("CrewService", "list_all")
_GET_BY_ID = HttpOperation("CrewService", "get_by_id")
_CREATE = HttpOperation("CrewService", "create", success_status=201)
_UPDATE = HttpOperation("CrewService", "update")
_LIST_MEMBERS = HttpOperation("CrewService", "list_members")
_ADD_MEMBER = HttpOperation("CrewService", "add_member", success_status=201)

_CREW_OUTPUT_SCHEMA = contract_schema(CrewOutput)
_MEMBER_OUTPUT_SCHEMA = contract_schema(CrewMemberOutput)
_CREW_CREATE_SCHEMA = contract_schema(CrewCreateInput)
_CREW_UPDATE_SCHEMA = contract_schema(CrewUpdateInput, excluded_fields=frozenset({"crew_id"}))
_MEMBER_ADD_SCHEMA = contract_schema(CrewMemberInput, excluded_fields=frozenset({"crew_id"}))


def _execute(
    request: Request,
    adapter: HttpOperationAdapter,
    service: CrewServiceInterface,
    operation: HttpOperation,
    *arguments: object,
) -> JSONResponse:
    """Execute one crew operation through the shared HTTP adapter."""

    return adapter.execute(request, operation, service, *arguments)


@router.get(
    "",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes({"type": "array", "items": _CREW_OUTPUT_SCHEMA}),
    summary="Consultar las cuadrillas registradas",
    description="Devuelve las cuadrillas registradas; una lista vacía es un resultado exitoso.",
)
def list_all(
    request: Request,
    crew_service: CrewServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, crew_service, _LIST_ALL)


@router.get(
    "/{crew_id}/members",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes({"type": "array", "items": _MEMBER_OUTPUT_SCHEMA}),
    summary="Consultar los integrantes de una cuadrilla",
    description="Devuelve los integrantes de la cuadrilla indicada; una lista vacía es un resultado exitoso.",
)
def list_members(
    crew_id: int,
    request: Request,
    crew_service: CrewServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, crew_service, _LIST_MEMBERS, crew_id)


@router.get(
    "/{crew_id}",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_CREW_OUTPUT_SCHEMA),
    summary="Consultar una cuadrilla por identificador",
    description="Devuelve los datos públicos de la cuadrilla indicada.",
)
def get_by_id(
    crew_id: int,
    request: Request,
    crew_service: CrewServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, crew_service, _GET_BY_ID, crew_id)


@router.post(
    "/{crew_id}/members",
    status_code=201,
    response_class=JSONResponse,
    responses=response_envelopes(_MEMBER_OUTPUT_SCHEMA, success_status=201),
    summary="Incorporar un integrante a una cuadrilla",
    description="Crea la pertenencia del usuario enviado en el cuerpo para la cuadrilla indicada.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _MEMBER_ADD_SCHEMA}},
        }
    },
)
async def add_member(
    crew_id: int,
    request: Request,
    crew_service: CrewServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(
        request,
        CrewMemberInput,
        path_values={"crew_id": crew_id},
        correlation_id=correlation_id,
    )
    return _execute(request, adapter, crew_service, _ADD_MEMBER, data)


@router.post(
    "",
    status_code=201,
    response_class=JSONResponse,
    responses=response_envelopes(_CREW_OUTPUT_SCHEMA, success_status=201),
    summary="Registrar una cuadrilla",
    description="Crea una cuadrilla a partir de su nombre.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _CREW_CREATE_SCHEMA}},
        }
    },
)
async def create(
    request: Request,
    crew_service: CrewServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(request, CrewCreateInput, correlation_id=correlation_id)
    return _execute(request, adapter, crew_service, _CREATE, data)


@router.patch(
    "/{crew_id}",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_CREW_OUTPUT_SCHEMA),
    summary="Actualizar una cuadrilla",
    description="Actualiza el nombre obligatorio de la cuadrilla indicada.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _CREW_UPDATE_SCHEMA}},
        }
    },
)
async def update(
    crew_id: int,
    request: Request,
    crew_service: CrewServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(
        request,
        CrewUpdateInput,
        path_values={"crew_id": crew_id},
        correlation_id=correlation_id,
    )
    return _execute(request, adapter, crew_service, _UPDATE, data)
