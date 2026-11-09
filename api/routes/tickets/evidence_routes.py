"""HTTP evidence metadata registration and lookup routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool

from api.contracts import EvidenceCreateInput, EvidenceOutput, EvidenceUploadLookupInput
from api.dependencies import get_evidence_service, get_evidence_upload_service
from api.http import (
    HttpOperation,
    HttpOperationAdapter,
    build_contract,
    get_http_adapter,
    get_request_correlation_id,
    read_json_contract,
)
from api.http.multipart import read_single_evidence_multipart
from api.interfaces.services import EvidenceServiceInterface, EvidenceUploadServiceInterface
from api.routes.users._openapi import contract_schema, response_envelopes

router = APIRouter(prefix="/evidences", tags=["Evidence"])

EvidenceServiceDependency = Annotated[EvidenceServiceInterface, Depends(get_evidence_service)]
EvidenceUploadServiceDependency = Annotated[EvidenceUploadServiceInterface, Depends(get_evidence_upload_service)]
HttpAdapterDependency = Annotated[HttpOperationAdapter, Depends(get_http_adapter)]
CorrelationIdDependency = Annotated[str, Depends(get_request_correlation_id)]

_GET_BY_ID = HttpOperation("EvidenceService", "get_by_id")
_LIST_BY_TICKET = HttpOperation("EvidenceService", "list_by_ticket")
_LIST_BY_TICKET_AND_UPLOADER = HttpOperation("EvidenceService", "list_by_ticket_and_uploader")
_CREATE_METADATA = HttpOperation("EvidenceService", "create_metadata", success_status=201)
_UPLOAD = HttpOperation("EvidenceUploadService", "upload", no_store=True)
_LIST_UPLOADS = HttpOperation("EvidenceUploadService", "list_own", no_store=True)
_DELETE_UPLOAD = HttpOperation("EvidenceUploadService", "delete_own", no_store=True)
_LIST_CONTRIBUTION = HttpOperation("EvidenceService", "list_citizen_contribution_evidence", no_store=True)
_OPEN_CONTENT = HttpOperation("EvidenceService", "open_citizen_content", no_store=True)

_EVIDENCE_OUTPUT_SCHEMA = contract_schema(EvidenceOutput)
_EVIDENCE_CREATE_SCHEMA = contract_schema(EvidenceCreateInput)


def _execute(
    request: Request,
    adapter: HttpOperationAdapter,
    service: EvidenceServiceInterface,
    operation: HttpOperation,
    *arguments: object,
) -> JSONResponse:
    """Execute one evidence operation through the shared HTTP adapter."""

    return adapter.execute(request, operation, service, *arguments)


@router.get(
    "",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes({"type": "array", "items": _EVIDENCE_OUTPUT_SCHEMA}),
    summary="Consultar evidencias de un ticket",
    description=(
        "ticket_id es obligatorio. Si se omite uploaded_by, consulta todas las evidencias del ticket; "
        "si se proporciona, consulta solo los aportes de ese usuario. Una lista vacía es un resultado exitoso."
    ),
)
def list_by_ticket(
    request: Request,
    evidence_service: EvidenceServiceDependency,
    adapter: HttpAdapterDependency,
    ticket_id: Annotated[int, Query(description="Identificador obligatorio del ticket.")],
    uploaded_by: Annotated[int | None, Query(description="Usuario que incorporó la evidencia.")] = None,
) -> JSONResponse:
    if uploaded_by is None:
        return _execute(request, adapter, evidence_service, _LIST_BY_TICKET, ticket_id)
    return _execute(
        request,
        adapter,
        evidence_service,
        _LIST_BY_TICKET_AND_UPLOADER,
        ticket_id,
        uploaded_by,
    )


@router.post("/uploads", status_code=200)
async def upload_evidence(
    request: Request,
    evidence_upload_service: EvidenceUploadServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
):
    data = await read_single_evidence_multipart(request, correlation_id=correlation_id)
    try:
        return await run_in_threadpool(adapter.execute, request, _UPLOAD, evidence_upload_service, data)
    finally:
        data.content.close()


@router.get("/uploads", status_code=200)
def list_uploads(
    request: Request,
    evidence_upload_service: EvidenceUploadServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
    request_key: str,
):
    data = build_contract(EvidenceUploadLookupInput, query_values={"request_key": request_key}, correlation_id=correlation_id)
    return adapter.execute(request, _LIST_UPLOADS, evidence_upload_service, data)


@router.delete("/uploads/{upload_id}", status_code=200)
def delete_upload(
    upload_id: str,
    request: Request,
    evidence_upload_service: EvidenceUploadServiceDependency,
    adapter: HttpAdapterDependency,
):
    return adapter.execute(request, _DELETE_UPLOAD, evidence_upload_service, upload_id)


@router.get("/citizen/contributions/{contribution_id}", status_code=200)
def list_contribution_evidence(
    contribution_id: str,
    request: Request,
    evidence_service: EvidenceServiceDependency,
    adapter: HttpAdapterDependency,
):
    return adapter.execute(request, _LIST_CONTRIBUTION, evidence_service, contribution_id)


@router.get("/{evidence_id}/content", status_code=200)
def open_evidence_content(
    evidence_id: int,
    request: Request,
    evidence_service: EvidenceServiceDependency,
    adapter: HttpAdapterDependency,
):
    response = adapter.execute_binary(request, _OPEN_CONTENT, evidence_service, evidence_id)
    response.headers["Cache-Control"] = "private, no-store"
    return response


@router.get(
    "/{evidence_id}",
    status_code=200,
    response_class=JSONResponse,
    responses=response_envelopes(_EVIDENCE_OUTPUT_SCHEMA),
    summary="Consultar una evidencia por identificador",
    description="Devuelve los metadatos públicos de la evidencia indicada.",
)
def get_by_id(
    evidence_id: int,
    request: Request,
    evidence_service: EvidenceServiceDependency,
    adapter: HttpAdapterDependency,
) -> JSONResponse:
    return _execute(request, adapter, evidence_service, _GET_BY_ID, evidence_id)


@router.post(
    "",
    status_code=201,
    response_class=JSONResponse,
    responses=response_envelopes(_EVIDENCE_OUTPUT_SCHEMA, success_status=201),
    summary="Registrar metadatos de una evidencia",
    description=(
        "Registra los metadatos de una evidencia asociada a un ticket. captured_at debe ser ISO 8601 con "
        "zona horaria. Requiere un actor activo con el permiso create_evidence."
    ),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _EVIDENCE_CREATE_SCHEMA}},
        }
    },
)
async def create_metadata(
    request: Request,
    evidence_service: EvidenceServiceDependency,
    adapter: HttpAdapterDependency,
    correlation_id: CorrelationIdDependency,
) -> JSONResponse:
    data = await read_json_contract(request, EvidenceCreateInput, correlation_id=correlation_id)
    return _execute(request, adapter, evidence_service, _CREATE_METADATA, data)
