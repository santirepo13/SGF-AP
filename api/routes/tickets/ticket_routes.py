"""HTTP ticket registration, lookup, and processing routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from api.contracts import (
    CitizenAttemptLookupInput,
    CitizenAttemptOutput,
    CitizenMatchInput,
    CitizenMatchesOutput,
    CitizenTicketCreateInput,
    CitizenTicketRegistrationOutput,
    CitizenContributionInput,
    CitizenContributionOutput,
    TicketAssignmentInput,
    TicketAttentionInput,
    TicketClosureReviewInput,
    TicketCreateInput,
    TicketFilters,
    TicketOperationInput,
    TicketOutput,
)
from api.dependencies import get_ticket_service
from api.errors import ApplicationError
from api.http import (
    HttpOperation,
    HttpOperationAdapter,
    build_contract,
    get_http_adapter,
    get_request_correlation_id,
    read_json_contract,
)
from api.interfaces.services import TicketServiceInterface
from api.routes.users._openapi import contract_schema, response_envelopes

router = APIRouter(prefix="/tickets", tags=["Tickets"])

TicketServiceDependency = Annotated[TicketServiceInterface, Depends(get_ticket_service)]
HttpAdapterDependency = Annotated[HttpOperationAdapter, Depends(get_http_adapter)]
CorrelationIdDependency = Annotated[str, Depends(get_request_correlation_id)]

_CREATE = HttpOperation("TicketService", "create", success_status=201)
_REGISTER_CITIZEN = HttpOperation("TicketService", "register_citizen", no_store=True)
_FIND_CITIZEN_MATCHES = HttpOperation("TicketService", "find_citizen_matches", no_store=True)
_GET_CITIZEN_ATTEMPT = HttpOperation("TicketService", "get_citizen_attempt", no_store=True)
_CONTRIBUTE_CITIZEN_EVIDENCE = HttpOperation(
    "TicketService",
    "contribute_citizen_evidence",
    no_store=True,
)
_GET_CITIZEN_CONTRIBUTION_ATTEMPT = HttpOperation(
    "TicketService",
    "get_citizen_contribution_attempt",
    no_store=True,
)
_GET_BY_ID = HttpOperation("TicketService", "get_by_id")
_GET_BY_CODE = HttpOperation("TicketService", "get_by_code")
_LIST_BY_FILTERS = HttpOperation("TicketService", "list_by_filters")
_VALIDATE = HttpOperation("TicketService", "validate")
_PRIORITIZE = HttpOperation("TicketService", "prioritize")
_ASSIGN = HttpOperation("TicketService", "assign")
_RECORD_ATTENTION = HttpOperation("TicketService", "record_attention")
_BLOCK = HttpOperation("TicketService", "block")
_UNBLOCK = HttpOperation("TicketService", "unblock")
_REQUEST_CLOSURE = HttpOperation("TicketService", "request_closure")
_REVIEW_CLOSURE = HttpOperation("TicketService", "review_closure")

_TICKET_OUTPUT_SCHEMA = contract_schema(TicketOutput)
_TICKET_CREATE_SCHEMA = contract_schema(TicketCreateInput)
_TICKET_CREATE_SCHEMA["properties"]["code"]["maxLength"] = 24
_ASSIGNMENT_SCHEMA = contract_schema(TicketAssignmentInput, excluded_fields=frozenset({"ticket_id"}))
_ATTENTION_SCHEMA = contract_schema(TicketAttentionInput, excluded_fields=frozenset({"ticket_id"}))
_CLOSURE_REVIEW_SCHEMA = contract_schema(TicketClosureReviewInput, excluded_fields=frozenset({"ticket_id"}))
_CLOSURE_REVIEW_SCHEMA["properties"]["decision"] = {
    "type": "string",
    "enum": ["Approval", "Rejection"],
}

_CITIZEN_MATCH_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["code", "status", "created_at", "progress_label"],
    "additionalProperties": False,
    "properties": {
        "code": {"type": "string"},
        "status": {"type": "string"},
        "created_at": {"type": "string", "format": "date-time"},
        "progress_label": {"type": "string"},
    },
}
_CITIZEN_CONFIRMATION_SCHEMA = {
    "type": "object",
    "required": ["code", "created_at", "status", "evidence_count"],
    "additionalProperties": False,
    "properties": {
        "code": {"type": "string", "pattern": "^SGF-[0-9A-F]{20}$"},
        "created_at": {"type": "string", "format": "date-time"},
        "status": {"type": "string", "enum": ["Registered"]},
        "evidence_count": {"type": "integer", "minimum": 0, "maximum": 3},
        "evidence_ids": {
            "type": "array",
            "maxItems": 3,
            "items": {"type": "integer", "minimum": 1},
        },
    },
}
_CITIZEN_REGISTRATION_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["request_key", "outcome", "ticket", "matches"],
    "additionalProperties": False,
    "properties": {
        "request_key": {"type": "string", "minLength": 1, "maxLength": 128},
        "outcome": {"type": "string", "enum": ["created", "matches"]},
        "ticket": {**_CITIZEN_CONFIRMATION_SCHEMA, "nullable": True},
        "matches": {"type": "array", "maxItems": 20, "items": _CITIZEN_MATCH_OUTPUT_SCHEMA},
    },
}
_CITIZEN_MATCHES_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["matches", "has_more"],
    "additionalProperties": False,
    "properties": {
        "matches": {"type": "array", "maxItems": 20, "items": _CITIZEN_MATCH_OUTPUT_SCHEMA},
        "has_more": {"type": "boolean"},
    },
}
_CITIZEN_ATTEMPT_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["request_key", "state", "result"],
    "additionalProperties": False,
    "properties": {
        "request_key": {"type": "string", "minLength": 1, "maxLength": 128},
        "state": {"type": "string", "enum": ["committed", "not_found"]},
        "result": {**_CITIZEN_REGISTRATION_OUTPUT_SCHEMA, "nullable": True},
    },
}
_CITIZEN_TICKET_CREATE_SCHEMA = {
    "type": "object",
    "required": ["request_key", "failure_type_id", "address_id", "description"],
    "additionalProperties": False,
    "properties": {
        "request_key": {"type": "string", "minLength": 1, "maxLength": 128},
        "failure_type_id": {"type": "integer", "minimum": 1},
        "address_id": {"type": "integer", "minimum": 1},
        "description": {"type": "string", "minLength": 1},
        "contact_email": {"type": "string", "format": "email", "nullable": True},
        "contact_phone": {"type": "string", "maxLength": 32, "nullable": True},
        "temporary_upload_ids": {
            "type": "array",
            "maxItems": 3,
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 1},
        },
        "email_notifications": {"type": "boolean"},
    },
}
_CITIZEN_MATCH_INPUT_SCHEMA = {
    "type": "object",
    "required": ["address_id", "failure_type_id"],
    "additionalProperties": False,
    "properties": {
        "address_id": {"type": "integer", "minimum": 1},
        "failure_type_id": {"type": "integer", "minimum": 1},
    },
}

_CITIZEN_CONTRIBUTION_SCHEMA = {
    "type": "object",
    "required": [
        "request_key",
        "target_code",
        "address_id",
        "failure_type_id",
        "temporary_upload_ids",
    ],
    "additionalProperties": False,
    "properties": {
        "request_key": {"type": "string", "minLength": 1, "maxLength": 128},
        "target_code": {"type": "string", "pattern": "^SGF-[0-9A-F]{20}$"},
        "address_id": {"type": "integer", "minimum": 1},
        "failure_type_id": {"type": "integer", "minimum": 1},
        "temporary_upload_ids": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "uniqueItems": True,
            "items": {"type": "string", "format": "uuid"},
        },
    },
}

@router.get(
    "/citizen/mine/{code}/evidences",
    status_code=200,
    response_class=JSONResponse,
)
def list_citizen_ticket_evidences(
    code: str,
    request: Request,
    evidence_service: EvidenceServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(
        request,
        adapter,
        evidence_service,
        _LIST_CITIZEN_TICKET_EVIDENCE,
        code,
    )


@router.post(
    "/citizen/contributions",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_CITIZEN_CONTRIBUTION_OUTPUT_SCHEMA),
)
async def contribute_citizen_evidence(
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(
        request,
        CitizenContributionInput,
        correlation_id=correlation_id,
    )
    return _execute(
        request,
        adapter,
        ticket_service,
        _CONTRIBUTE_CITIZEN_EVIDENCE,
        data,
    )


@router.get(
    "/citizen/contributions/attempts/{request_key}",
    status_code=200,
    response_class=JSONResponse,
)
def get_citizen_contribution_attempt(
    request_key: str,
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = build_contract(
        CitizenAttemptLookupInput,
        path_values={"request_key": request_key},
        correlation_id=correlation_id,
    )
    return _execute(
        request,
        adapter,
        ticket_service,
        _GET_CITIZEN_CONTRIBUTION_ATTEMPT,
        data,
    )


def _execute(
    request: Request,
    adapter: HttpOperationAdapter,
    service: TicketServiceInterface,
    operation: HttpOperation,
    *arguments: object,
) -> JSONResponse:
    """Execute one ticket operation through the shared HTTP adapter."""

    return adapter.execute(request, operation, service, *arguments)


def _validate_closure_decision(
    data: TicketClosureReviewInput,
    correlation_id: str,
) -> TicketClosureReviewInput:
    """Restrict review decisions to the public closure-review contract."""

    if data.decision not in {"Approval", "Rejection"}:
        raise ApplicationError.invalid_value(
            "decision",
            "La decisión debe ser Approval o Rejection.",
            correlation_id=correlation_id,
        )
    return data


@router.post(
    "",
    status_code=201,
    response_class=JSONResponse,
    responses=response_envelopes(_TICKET_OUTPUT_SCHEMA, success_status=201),
    summary="Registrar un ticket",
    description=(
        "Registra un ticket y su evento Registration. Requiere un actor activo con el permiso "
        "create_ticket. Los campos opcionales omitidos y los enviados como null se conservan como null."
    ),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _TICKET_CREATE_SCHEMA}},
        }
    },
)
async def create(
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(request, TicketCreateInput, correlation_id=correlation_id)
    return _execute(request, adapter, ticket_service, _CREATE, data)


@router.post(
    "/citizen",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_CITIZEN_REGISTRATION_OUTPUT_SCHEMA),
    summary="Registrar una falla de alumbrado como ciudadano",
    description=(
        "Registra una intención ciudadana confirmada o devuelve reportes abiertos coincidentes. "
        "La ubicación se identifica únicamente por address_id."
    ),
    openapi_extra={
        "security": [{"HTTPBasic": [], "UserAccessToken": []}],
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _CITIZEN_TICKET_CREATE_SCHEMA}},
        },
    },
)
async def register_citizen(
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(
        request,
        CitizenTicketCreateInput,
        correlation_id=correlation_id,
    )
    return await run_in_threadpool(
        _execute,
        request,
        adapter,
        ticket_service,
        _REGISTER_CITIZEN,
        data,
    )


@router.post(
    "/citizen/matches",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_CITIZEN_MATCHES_OUTPUT_SCHEMA),
    summary="Buscar reportes abiertos coincidentes",
    description="Busca coincidencias por la misma dirección estructurada y tipo de falla sin crear un reporte.",
    openapi_extra={
        "security": [{"HTTPBasic": [], "UserAccessToken": []}],
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _CITIZEN_MATCH_INPUT_SCHEMA}},
        },
    },
)
async def find_citizen_matches(
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(request, CitizenMatchInput, correlation_id=correlation_id)
    return await run_in_threadpool(
        _execute,
        request,
        adapter,
        ticket_service,
        _FIND_CITIZEN_MATCHES,
        data,
    )


@router.get(
    "/citizen/attempts/{request_key}",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_CITIZEN_ATTEMPT_OUTPUT_SCHEMA),
    summary="Recuperar un intento ciudadano confirmado",
    description=(
        "Devuelve un resultado confirmado del mismo ciudadano o not_found. "
        "not_found no confirma que el envío anterior haya fallado."
    ),
    openapi_extra={"security": [{"HTTPBasic": [], "UserAccessToken": []}]},
)
async def get_citizen_attempt(
    request_key: str,
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = build_contract(
        CitizenAttemptLookupInput,
        path_values={"request_key": request_key},
        correlation_id=correlation_id,
    )
    return await run_in_threadpool(
        _execute,
        request,
        adapter,
        ticket_service,
        _GET_CITIZEN_ATTEMPT,
        data,
    )


@router.get(
    "",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes({"type": "array", "items": _TICKET_OUTPUT_SCHEMA}),
    summary="Consultar tickets mediante filtros",
    description=(
        "Combina opcionalmente los filtros por reportante, tipo de falla, dirección, estado, prioridad, "
        "cuadrilla y ubicación. Una lista vacía es un resultado exitoso."
    ),
)
def list_by_filters(
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
    reported_by: Annotated[int | None, Query(description="Identificador del reportante.")] = None,
    failure_type_id: Annotated[int | None, Query(description="Identificador del tipo de falla.")] = None,
    address_id: Annotated[int | None, Query(description="Identificador de la dirección.")] = None,
    status_id: Annotated[int | None, Query(description="Identificador del estado.")] = None,
    priority_id: Annotated[int | None, Query(description="Identificador de la prioridad.")] = None,
    crew_id: Annotated[int | None, Query(description="Identificador de la cuadrilla asignada.")] = None,
    municipality_id: Annotated[int | None, Query(description="Identificador del municipio.")] = None,
    commune_id: Annotated[int | None, Query(description="Identificador de la comuna.")] = None,
    neighborhood_id: Annotated[int | None, Query(description="Identificador del barrio.")] = None,
) -> JSONResponse:
    filters = build_contract(
        TicketFilters,
        {
            "reported_by": reported_by,
            "failure_type_id": failure_type_id,
            "address_id": address_id,
            "status_id": status_id,
            "priority_id": priority_id,
            "crew_id": crew_id,
            "municipality_id": municipality_id,
            "commune_id": commune_id,
            "neighborhood_id": neighborhood_id,
        },
        correlation_id=correlation_id,
    )
    return _execute(request, adapter, ticket_service, _LIST_BY_FILTERS, filters)


@router.get(
    "/by-code/{code}",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_TICKET_OUTPUT_SCHEMA),
    summary="Consultar un ticket por código",
    description="Devuelve el ticket asociado al código recibido.",
)
def get_by_code(
    code: str,
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, ticket_service, _GET_BY_CODE, code)


@router.get(
    "/{ticket_id}",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_TICKET_OUTPUT_SCHEMA),
    summary="Consultar un ticket por identificador",
    description="Devuelve la información pública completa del ticket indicado.",
)
def get_by_id(
    ticket_id: int,
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, ticket_service, _GET_BY_ID, ticket_id)


@router.post(
    "/{ticket_id}/validate",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_TICKET_OUTPUT_SCHEMA),
    summary="Validar un ticket registrado",
    description=(
        "Cambia un ticket Registered a Validated y registra Validation. Requiere un actor activo "
        "con el permiso process_tickets. No recibe campos adicionales."
    ),
)
async def validate(
    ticket_id: int,
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(
        request,
        TicketOperationInput,
        path_values={"ticket_id": ticket_id},
        correlation_id=correlation_id,
    )
    return _execute(request, adapter, ticket_service, _VALIDATE, data)


@router.post(
    "/{ticket_id}/prioritize",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_TICKET_OUTPUT_SCHEMA),
    summary="Priorizar un ticket validado",
    description=(
        "Obtiene la prioridad del tipo de falla, cambia Validated a Prioritized y registra Prioritization. "
        "Requiere un actor activo con el permiso process_tickets. No recibe campos adicionales."
    ),
)
async def prioritize(
    ticket_id: int,
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(
        request,
        TicketOperationInput,
        path_values={"ticket_id": ticket_id},
        correlation_id=correlation_id,
    )
    return _execute(request, adapter, ticket_service, _PRIORITIZE, data)


@router.post(
    "/{ticket_id}/assign",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_TICKET_OUTPUT_SCHEMA),
    summary="Asignar una cuadrilla a un ticket",
    description=(
        "Asigna una cuadrilla existente y cambia Prioritized a Assigned. Requiere un actor activo "
        "con el permiso process_tickets."
    ),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _ASSIGNMENT_SCHEMA}},
        }
    },
)
async def assign(
    ticket_id: int,
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(
        request,
        TicketAssignmentInput,
        path_values={"ticket_id": ticket_id},
        correlation_id=correlation_id,
    )
    return _execute(request, adapter, ticket_service, _ASSIGN, data)


@router.post(
    "/{ticket_id}/attention",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_TICKET_OUTPUT_SCHEMA),
    summary="Registrar la atención de un ticket",
    description=(
        "Actualiza diagnosis y/o solution, y cambia Assigned o InProgress a InProgress. Requiere un actor "
        "activo con el permiso process_tickets. Los campos omitidos se conservan como UNSET; null los limpia."
    ),
    openapi_extra={
        "requestBody": {
            "required": False,
            "content": {"application/json": {"schema": _ATTENTION_SCHEMA}},
        }
    },
)
async def record_attention(
    ticket_id: int,
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(
        request,
        TicketAttentionInput,
        path_values={"ticket_id": ticket_id},
        correlation_id=correlation_id,
    )
    return _execute(request, adapter, ticket_service, _RECORD_ATTENTION, data)


@router.post(
    "/{ticket_id}/block",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_TICKET_OUTPUT_SCHEMA),
    summary="Bloquear un ticket en atención",
    description=(
        "Cambia un ticket InProgress a Blocked y registra Blockage. Requiere un actor activo con el permiso "
        "process_tickets. No recibe campos adicionales."
    ),
)
async def block(
    ticket_id: int,
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(
        request,
        TicketOperationInput,
        path_values={"ticket_id": ticket_id},
        correlation_id=correlation_id,
    )
    return _execute(request, adapter, ticket_service, _BLOCK, data)


@router.post(
    "/{ticket_id}/unblock",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_TICKET_OUTPUT_SCHEMA),
    summary="Reanudar un ticket bloqueado",
    description=(
        "Cambia un ticket Blocked a InProgress y registra Unblock. Requiere un actor activo con el permiso "
        "process_tickets. No recibe campos adicionales."
    ),
)
async def unblock(
    ticket_id: int,
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(
        request,
        TicketOperationInput,
        path_values={"ticket_id": ticket_id},
        correlation_id=correlation_id,
    )
    return _execute(request, adapter, ticket_service, _UNBLOCK, data)


@router.post(
    "/{ticket_id}/request-closure",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_TICKET_OUTPUT_SCHEMA),
    summary="Solicitar el cierre de un ticket",
    description=(
        "Con solución y evidencias, cambia InProgress a PendingClosure y registra ClosureRequest. "
        "Requiere un actor activo con el permiso process_tickets. No recibe campos adicionales."
    ),
)
async def request_closure(
    ticket_id: int,
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(
        request,
        TicketOperationInput,
        path_values={"ticket_id": ticket_id},
        correlation_id=correlation_id,
    )
    return _execute(request, adapter, ticket_service, _REQUEST_CLOSURE, data)


@router.post(
    "/{ticket_id}/review-closure",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_TICKET_OUTPUT_SCHEMA),
    summary="Revisar una solicitud de cierre",
    description=(
        "Approval cambia PendingClosure a Resolved; Rejection lo devuelve a InProgress. Requiere un actor activo "
        "con el permiso process_tickets."
    ),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _CLOSURE_REVIEW_SCHEMA}},
        }
    },
)
async def review_closure(
    ticket_id: int,
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(
        request,
        TicketClosureReviewInput,
        path_values={"ticket_id": ticket_id},
        correlation_id=correlation_id,
    )
    return _execute(
        request,
        adapter,
        ticket_service,
        _REVIEW_CLOSURE,
        _validate_closure_decision(data, correlation_id),
    )
