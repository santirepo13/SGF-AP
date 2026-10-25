"""HTTP ticket-history lookup routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from api.contracts import HistoryEventOutput
from api.dependencies import get_history_service
from api.http import HttpOperation, HttpOperationAdapter, get_http_adapter
from api.interfaces.services import HistoryServiceInterface
from api.routes.users._openapi import contract_schema, response_envelopes

router = APIRouter(prefix="/history-events", tags=["History"])

HistoryServiceDependency = Annotated[HistoryServiceInterface, Depends(get_history_service)]
HttpAdapterDependency = Annotated[HttpOperationAdapter, Depends(get_http_adapter)]

_GET_EVENT = HttpOperation("HistoryService", "get_event")
_LIST_BY_TICKET = HttpOperation("HistoryService", "list_by_ticket")

_HISTORY_EVENT_OUTPUT_SCHEMA = contract_schema(HistoryEventOutput)


def _execute(
    request: Request,
    adapter: HttpOperationAdapter,
    service: HistoryServiceInterface,
    operation: HttpOperation,
    *arguments: object,
) -> JSONResponse:
    """Execute one history lookup through the shared HTTP adapter."""

    return adapter.execute(request, operation, service, *arguments)


@router.get(
    "",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes({"type": "array", "items": _HISTORY_EVENT_OUTPUT_SCHEMA}),
    summary="Consultar el historial de un ticket",
    description=(
        "ticket_id es obligatorio. Devuelve los eventos en orden ascendente por event_time e id; "
        "una lista vacía es un resultado exitoso y no implica que el ticket no exista."
    ),
)
def list_by_ticket(
    request: Request,
    history_service: HistoryServiceDependency,
    adapter: HttpAdapterDependency,
    ticket_id: Annotated[int, Query(description="Identificador obligatorio del ticket.")],
) -> JSONResponse:
    return _execute(request, adapter, history_service, _LIST_BY_TICKET, ticket_id)


@router.get(
    "/{event_id}",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_HISTORY_EVENT_OUTPUT_SCHEMA),
    summary="Consultar un evento de historial por identificador",
    description="Devuelve el evento indicado o RES-001 cuando ese evento no existe.",
)
def get_event(
    event_id: int,
    request: Request,
    history_service: HistoryServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, history_service, _GET_EVENT, event_id)
