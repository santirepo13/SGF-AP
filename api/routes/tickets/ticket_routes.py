"""HTTP ticket registration, lookup, and processing routes."""

from __future__ import annotations

import re
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
    CitizenHistoryPageInput,
    CitizenQueryPageInput,
    CitizenTicketCodeInput,
    CitizenTicketDetailOutput,
    CitizenTicketPageOutput,
    CitizenHistoryPageOutput,
    PublicTicketOutput,
    TicketAssignmentInput,
    TicketAttentionInput,
    TicketClosureReviewInput,
    TicketCreateInput,
    TicketFilters,
    TicketOperationInput,
    TicketOutput,
)
from api.dependencies import get_evidence_service, get_ticket_service
from api.errors import ApplicationError
from api.http import (
    HttpOperation,
    HttpOperationAdapter,
    build_contract,
    get_http_adapter,
    get_request_correlation_id,
    read_json_contract,
)
from api.interfaces.services import EvidenceServiceInterface, TicketServiceInterface
from api.routes.users._openapi import contract_schema, response_envelopes

router = APIRouter(prefix="/tickets", tags=["Tickets"])

TicketServiceDependency = Annotated[TicketServiceInterface, Depends(get_ticket_service)]
EvidenceServiceDependency = Annotated[EvidenceServiceInterface, Depends(get_evidence_service)]
HttpAdapterDependency = Annotated[HttpOperationAdapter, Depends(get_http_adapter)]
CorrelationIdDependency = Annotated[str, Depends(get_request_correlation_id)]

_CREATE = HttpOperation("TicketService", "create", success_status=201)
_REGISTER_CITIZEN = HttpOperation("TicketService", "register_citizen", no_store=True)
_FIND_CITIZEN_MATCHES = HttpOperation("TicketService", "find_citizen_matches", no_store=True)
_LIST_CITIZEN_TICKET_EVIDENCE = HttpOperation(
    "EvidenceService", "list_citizen_ticket_evidence", no_store=True
)
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
_LIST_CITIZEN_REPORTS = HttpOperation("TicketService", "list_citizen_reports", no_store=True)
_GET_CITIZEN_REPORT = HttpOperation("TicketService", "get_citizen_report", no_store=True)
_LIST_CITIZEN_HISTORY = HttpOperation("TicketService", "list_citizen_history", no_store=True)
_GET_PUBLIC_REPORT = HttpOperation("TicketService", "get_public_report", no_store=True)
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

_CITIZEN_EVIDENCE_REFERENCE_SCHEMA = {
    "type": "object",
    "required": [
        "evidence_id", "media_type", "size_bytes", "captured_at", "capture_source",
        "uploaded_at", "content_available",
    ],
    "additionalProperties": False,
    "properties": {
        "evidence_id": {"type": "integer", "minimum": 1},
        "media_type": {"type": "string", "nullable": True},
        "size_bytes": {"type": "integer", "minimum": 0, "nullable": True},
        "captured_at": {"type": "string", "format": "date-time", "nullable": True},
        "capture_source": {"type": "string", "nullable": True},
        "uploaded_at": {"type": "string", "format": "date-time", "nullable": True},
        "content_available": {"type": "boolean"},
    },
}
_CITIZEN_TICKET_ITEM_SCHEMA = {
    "type": "object",
    "required": ["code", "created_at", "status", "status_label", "failure_type_label", "last_updated_at"],
    "additionalProperties": False,
    "properties": {
        "code": {"type": "string", "maxLength": 24},
        "created_at": {"type": "string", "format": "date-time"},
        "status": {"type": "string"},
        "status_label": {"type": "string"},
        "failure_type_label": {"type": "string"},
        "last_updated_at": {"type": "string", "format": "date-time"},
    },
}
_CITIZEN_TICKET_PAGE_SCHEMA = {
    "type": "object",
    "required": ["items", "next_cursor"],
    "additionalProperties": False,
    "properties": {
        "items": {"type": "array", "items": _CITIZEN_TICKET_ITEM_SCHEMA},
        "next_cursor": {"type": "string", "nullable": True},
    },
}
_CITIZEN_DETAIL_SCHEMA = {
    "type": "object",
    "required": [
        "code", "created_at", "status", "status_label", "failure_type_label", "last_updated_at",
        "public_summary", "description", "formatted_address", "contact_email", "contact_phone",
        "email_notifications", "evidences",
    ],
    "additionalProperties": False,
    "properties": {
        **_CITIZEN_TICKET_ITEM_SCHEMA["properties"],
        "public_summary": {"type": "string"},
        "description": {"type": "string"},
        "formatted_address": {"type": "string", "nullable": True},
        "contact_email": {"type": "string", "nullable": True},
        "contact_phone": {"type": "string", "nullable": True},
        "email_notifications": {"type": "boolean"},
        "evidences": {"type": "array", "items": _CITIZEN_EVIDENCE_REFERENCE_SCHEMA},
    },
}
_CITIZEN_HISTORY_ITEM_SCHEMA = {
    "type": "object",
    "required": ["occurred_at", "action", "label"],
    "additionalProperties": False,
    "properties": {
        "occurred_at": {"type": "string", "format": "date-time"},
        "action": {"type": "string"},
        "label": {"type": "string"},
    },
}
_CITIZEN_HISTORY_PAGE_SCHEMA = {
    "type": "object",
    "required": ["items", "next_cursor"],
    "additionalProperties": False,
    "properties": {
        "items": {"type": "array", "items": _CITIZEN_HISTORY_ITEM_SCHEMA},
        "next_cursor": {"type": "string", "nullable": True},
    },
}
_PUBLIC_TICKET_SCHEMA = {
    "type": "object",
    "required": ["code", "status", "status_label", "last_updated_at", "public_summary"],
    "additionalProperties": False,
    "properties": {
        "code": {"type": "string", "maxLength": 24},
        "status": {"type": "string"},
        "status_label": {"type": "string"},
        "last_updated_at": {"type": "string", "format": "date-time"},
        "public_summary": {"type": "string"},
    },
}


def _validated_code(code: str, correlation_id: str) -> CitizenTicketCodeInput:
    return build_contract(CitizenTicketCodeInput, {"code": code}, correlation_id=correlation_id)


def _page(contract_type, limit: int, cursor: str | None, correlation_id: str):
    return build_contract(
        contract_type,
        {"limit": limit, "cursor": cursor},
        correlation_id=correlation_id,
    )


def _page_from_request(request: Request, contract_type, default_limit: int, maximum: int, correlation_id: str):
    values: dict[str, str] = {}
    allowed = {"limit", "cursor"}
    for name, value in request.query_params.multi_items():
        if name not in allowed or name in values:
            raise ApplicationError.invalid_value(name, "El parámetro de consulta no es válido.", correlation_id=correlation_id)
        values[name] = value
    raw_limit = values.get("limit", str(default_limit))
    if re.fullmatch(r"[0-9]+", raw_limit, flags=re.ASCII) is None:
        raise ApplicationError.invalid_value("limit", "El límite no es válido.", correlation_id=correlation_id)
    try:
        parsed_limit = int(raw_limit)
    except (TypeError, ValueError) as error:
        raise ApplicationError.invalid_value("limit", "El límite no es válido.", correlation_id=correlation_id, cause=error) from error
    if not 1 <= parsed_limit <= maximum:
        raise ApplicationError.invalid_value("limit", "El límite no es válido.", correlation_id=correlation_id)
    return _page(contract_type, parsed_limit, values.get("cursor"), correlation_id)


def _reject_query_parameters(request: Request, correlation_id: str, *, allowed: set[str] | None = None) -> None:
    values = tuple(request.query_params.multi_items())
    seen: set[str] = set()
    for name, _value in values:
        if allowed is None or name not in allowed or name in seen:
            raise ApplicationError.invalid_value(name, "El parámetro de consulta no está permitido.", correlation_id=correlation_id)
        seen.add(name)


@router.get(
    "/citizen/mine/{code}/evidences",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes({
        "type": "object",
        "additionalProperties": False,
        "required": ["evidences"],
        "properties": {"evidences": {"type": "array", "items": _CITIZEN_EVIDENCE_REFERENCE_SCHEMA}},
    }),
    openapi_extra={"security": [{"HTTPBasic": [], "UserAccessToken": []}]},
)
async def list_citizen_ticket_evidences(
    code: str,
    request: Request,
    evidence_service: EvidenceServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    _reject_query_parameters(request, correlation_id)
    _validated_code(code, correlation_id)
    return await run_in_threadpool(
        _execute,
        request,
        adapter,
        evidence_service,
        _LIST_CITIZEN_TICKET_EVIDENCE,
        code,
    )


@router.get(
    "/citizen/mine/{code}/history",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_CITIZEN_HISTORY_PAGE_SCHEMA),
    summary="Consultar el historial ciudadano paginado",
    description="Historial privado del titular, ordenado por fecha ascendente. Retorna items y next_cursor; el cursor es independiente del listado.",
    openapi_extra={"security": [{"HTTPBasic": [], "UserAccessToken": []}]},
)
async def list_citizen_history(
    code: str,
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    _reject_query_parameters(request, correlation_id, allowed={"limit", "cursor"})
    page = _page_from_request(request, CitizenHistoryPageInput, 50, 100, correlation_id)
    return await run_in_threadpool(
        _execute, request, adapter, ticket_service, _LIST_CITIZEN_HISTORY,
        _validated_code(code, correlation_id).code, page,
    )


@router.get(
    "/citizen/mine/{code}",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_CITIZEN_DETAIL_SCHEMA),
    summary="Consultar el detalle privado de un reporte propio",
    description="Solo devuelve el detalle del reporte perteneciente al actor autenticado. Un reporte ajeno o inexistente retorna RES-001.",
    openapi_extra={"parameters": [], "security": [{"HTTPBasic": [], "UserAccessToken": []}]},
)
async def get_citizen_report(
    code: str,
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    _reject_query_parameters(request, correlation_id)
    return await run_in_threadpool(
        _execute, request, adapter, ticket_service, _GET_CITIZEN_REPORT,
        _validated_code(code, correlation_id),
    )


@router.get(
    "/citizen/mine",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_CITIZEN_TICKET_PAGE_SCHEMA),
    summary="Listar reportes propios",
    description="Lista paginada del actor autenticado; una lista vacía es exitosa y devuelve items vacío y next_cursor nulo.",
    openapi_extra={"security": [{"HTTPBasic": [], "UserAccessToken": []}]},
)
async def list_my_citizen_reports(
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    _reject_query_parameters(request, correlation_id, allowed={"limit", "cursor"})
    page = _page_from_request(request, CitizenQueryPageInput, 20, 50, correlation_id)
    return await run_in_threadpool(
        _execute, request, adapter, ticket_service, _LIST_CITIZEN_REPORTS, page,
    )


@router.get(
    "/public/{code}",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_PUBLIC_TICKET_SCHEMA),
    summary="Consultar el avance público de un reporte",
    description="No requiere sesión ciudadana. Solo devuelve código, estado público, fecha de actualización y resumen. Código inexistente retorna RES-001.",
    openapi_extra={"parameters": [], "security": [{"HTTPBasic": []}]},
)
async def get_public_report(
    code: str,
    request: Request,
    ticket_service: TicketServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    _reject_query_parameters(request, correlation_id)
    _validated_code(code, correlation_id)
    return await run_in_threadpool(
        _execute, request, adapter, ticket_service, _GET_PUBLIC_REPORT, code,
    )

_CITIZEN_CONTRIBUTION_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["request_key", "outcome", "contribution_id", "ticket_code", "created_at", "evidence_count", "evidence_ids"],
    "properties": {
        "request_key": {"type": "string"},
        "outcome": {"type": "string", "enum": ["contributed"]},
        "contribution_id": {"type": "string", "format": "uuid"},
        "ticket_code": {"type": "string"},
        "created_at": {"type": "string", "format": "date-time"},
        "evidence_count": {"type": "integer", "minimum": 1, "maximum": 3},
        "evidence_ids": {"type": "array", "items": {"type": "integer", "minimum": 1}},
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
    description="Ruta operacional protegida. Requiere actor activo, operational_ticket_read y la regla de recurso correspondiente al rol interno. No es una proyección pública ni está disponible para Citizen.",
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
