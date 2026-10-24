"""HTTP crew-membership query and maintenance routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from api.contracts import CrewMemberInput, CrewMemberOutput
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

router = APIRouter(prefix="/crew-members", tags=["Crew members"])

CrewServiceDependency = Annotated[CrewServiceInterface, Depends(get_crew_service)]
HttpAdapterDependency = Annotated[HttpOperationAdapter, Depends(get_http_adapter)]
CorrelationIdDependency = Annotated[str, Depends(get_request_correlation_id)]

_GET_MEMBERSHIP = HttpOperation("CrewService", "get_membership")
_CHANGE_CREW = HttpOperation("CrewService", "change_crew")
_REMOVE_MEMBER = HttpOperation("CrewService", "remove_member")

_MEMBER_OUTPUT_SCHEMA = contract_schema(CrewMemberOutput)
_MEMBER_CHANGE_SCHEMA = contract_schema(CrewMemberInput, excluded_fields=frozenset({"user_id"}))


def _execute(
    request: Request,
    adapter: HttpOperationAdapter,
    service: CrewServiceInterface,
    operation: HttpOperation,
    *arguments: object,
) -> JSONResponse:
    """Execute one crew-membership operation through the shared HTTP adapter."""

    return adapter.execute(request, operation, service, *arguments)


@router.get(
    "/{user_id}",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_MEMBER_OUTPUT_SCHEMA, nullable_data=True),
    summary="Consultar la pertenencia de un usuario",
    description="Devuelve la pertenencia del usuario o data=null cuando no tiene una registrada.",
)
def get_membership(
    user_id: int,
    request: Request,
    crew_service: CrewServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, crew_service, _GET_MEMBERSHIP, user_id)


@router.patch(
    "/{user_id}",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_MEMBER_OUTPUT_SCHEMA),
    summary="Cambiar un integrante de cuadrilla",
    description="Traslada la pertenencia existente del usuario a la cuadrilla recibida en el cuerpo.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _MEMBER_CHANGE_SCHEMA}},
        }
    },
)
async def change_crew(
    user_id: int,
    request: Request,
    crew_service: CrewServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(
        request,
        CrewMemberInput,
        path_values={"user_id": user_id},
        correlation_id=correlation_id,
    )
    return _execute(request, adapter, crew_service, _CHANGE_CREW, data)


@router.delete(
    "/{user_id}",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes({"type": "boolean"}),
    summary="Retirar la pertenencia de un usuario",
    description="Devuelve true si retiró una pertenencia y false si no existía una para el usuario.",
)
def remove_member(
    user_id: int,
    request: Request,
    crew_service: CrewServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, crew_service, _REMOVE_MEMBER, user_id)
