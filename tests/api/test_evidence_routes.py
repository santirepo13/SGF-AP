"""Unit coverage for Scrum 8 evidence route adaptation and documentation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from fastapi import FastAPI
import pytest

from api.contracts import EvidenceCreateInput
from api.errors import ApplicationError
from api.routes.tickets.evidence_routes import router


@dataclass
class RecordingAdapter:
    calls: list[tuple[object, object, object, tuple[object, ...]]] = field(default_factory=list)

    def execute(self, request, operation, service, *arguments):
        self.calls.append((request, operation, service, arguments))
        return operation.name


class JsonRequest:
    def __init__(self, body: bytes) -> None:
        self._body = body

    async def body(self) -> bytes:
        return self._body


_ROUTES = {route.name: route.endpoint for route in router.routes}


def test_evidence_query_routes_select_registered_operations_from_path_and_query_values() -> None:
    request = object()
    service = object()

    get_adapter = RecordingAdapter()
    get_result = _ROUTES["get_by_id"](
        evidence_id=7,
        request=request,
        evidence_service=service,
        adapter=get_adapter,
    )
    assert get_result == "EvidenceService.get_by_id"
    _, get_operation, recorded_service, get_arguments = get_adapter.calls[0]
    assert get_operation.name == "EvidenceService.get_by_id"
    assert recorded_service is service
    assert get_arguments == (7,)

    ticket_adapter = RecordingAdapter()
    ticket_result = _ROUTES["list_by_ticket"](
        request=request,
        evidence_service=service,
        adapter=ticket_adapter,
        ticket_id=42,
    )
    assert ticket_result == "EvidenceService.list_by_ticket"
    assert ticket_adapter.calls[0][1].name == "EvidenceService.list_by_ticket"
    assert ticket_adapter.calls[0][3] == (42,)

    uploader_adapter = RecordingAdapter()
    uploader_result = _ROUTES["list_by_ticket"](
        request=request,
        evidence_service=service,
        adapter=uploader_adapter,
        ticket_id=42,
        uploaded_by=15,
    )
    assert uploader_result == "EvidenceService.list_by_ticket_and_uploader"
    assert uploader_adapter.calls[0][1].name == "EvidenceService.list_by_ticket_and_uploader"
    assert uploader_adapter.calls[0][3] == (42, 15)


def test_create_metadata_builds_an_aware_evidence_contract_from_iso_datetime() -> None:
    adapter = RecordingAdapter()
    result = asyncio.run(
        _ROUTES["create_metadata"](
            request=JsonRequest(
                b'{"ticket_id":42,"file_path":"evidences/ticket-42/evidence-01.jpg",'
                b'"captured_at":"2026-10-16T20:30:00-05:00","uploaded_by":15}'
            ),
            evidence_service=object(),
            adapter=adapter,
            correlation_id="corr-evidence-create",
        )
    )

    assert result == "EvidenceService.create_metadata"
    _, operation, _, (data,) = adapter.calls[0]
    assert operation.name == "EvidenceService.create_metadata"
    assert isinstance(data, EvidenceCreateInput)
    assert data.ticket_id == 42
    assert data.file_path == "evidences/ticket-42/evidence-01.jpg"
    assert data.captured_at.isoformat() == "2026-10-16T20:30:00-05:00"
    assert data.captured_at.tzinfo is not None
    assert data.uploaded_by == 15


def test_create_metadata_rejects_a_capture_datetime_without_timezone() -> None:
    with pytest.raises(ApplicationError) as raised:
        asyncio.run(
            _ROUTES["create_metadata"](
                request=JsonRequest(
                    b'{"ticket_id":42,"file_path":"evidences/ticket-42/evidence-01.jpg",'
                    b'"captured_at":"2026-10-16T20:30:00","uploaded_by":15}'
                ),
                evidence_service=object(),
                adapter=RecordingAdapter(),
                correlation_id="corr-evidence-naive-datetime",
            )
        )

    assert raised.value.code.value == "VAL-002"


def test_evidence_router_documents_collection_filtering_creation_and_response_contracts() -> None:
    application = FastAPI()
    application.include_router(router)
    document = application.openapi()

    assert set(document["paths"]) == {"/evidences", "/evidences/{evidence_id}"}
    assert set(document["paths"]["/evidences"]) == {"get", "post"}
    assert set(document["paths"]["/evidences/{evidence_id}"]) == {"get"}

    list_parameters = {
        parameter["name"]: parameter
        for parameter in document["paths"]["/evidences"]["get"]["parameters"]
    }
    assert set(list_parameters) == {"ticket_id", "uploaded_by"}
    assert list_parameters["ticket_id"]["required"] is True
    assert list_parameters["uploaded_by"]["required"] is False

    create_body = document["paths"]["/evidences"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert create_body["required"] == ["ticket_id", "file_path", "captured_at", "uploaded_by"]
    assert create_body["properties"]["captured_at"] == {"type": "string", "format": "date-time"}

    evidence_schema = document["paths"]["/evidences/{evidence_id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["data"]
    assert set(evidence_schema["properties"]) == {"id", "ticket_id", "file_path", "captured_at", "uploaded_by"}
    assert evidence_schema["properties"]["captured_at"] == {"type": "string", "format": "date-time"}
    assert "201" in document["paths"]["/evidences"]["post"]["responses"]
    for path_item in document["paths"].values():
        for operation in path_item.values():
            assert set(("400", "403", "404", "405", "409", "422", "500")) <= set(operation["responses"])
