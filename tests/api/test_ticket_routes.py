"""Unit coverage for Scrum 7 ticket route adaptation and documentation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from fastapi import FastAPI
import pytest

from api.contracts import (
    UNSET,
    TicketAssignmentInput,
    TicketAttentionInput,
    TicketClosureReviewInput,
    TicketCreateInput,
    TicketFilters,
    TicketOperationInput,
)
from api.errors import ApplicationError
from api.routes.tickets.ticket_routes import router


@dataclass
class RecordingAdapter:
    calls: list[tuple[object, object, object, tuple[object, ...]]] = field(default_factory=list)

    def execute(self, request, operation, service, *arguments):
        self.calls.append((request, operation, service, arguments))
        return operation.name


class JsonRequest:
    def __init__(self, body: bytes = b"") -> None:
        self._body = body

    async def body(self) -> bytes:
        return self._body


_ROUTES = {route.name: route.endpoint for route in router.routes}


def test_ticket_query_routes_use_registered_operations_and_preserve_all_filters() -> None:
    request = object()
    service = object()

    for route_name, values, operation_name, arguments in (
        ("get_by_id", {"ticket_id": 7}, "TicketService.get_by_id", (7,)),
        ("get_by_code", {"code": "TCK-007"}, "TicketService.get_by_code", ("TCK-007",)),
    ):
        adapter = RecordingAdapter()
        result = _ROUTES[route_name](
            request=request,
            ticket_service=service,
            adapter=adapter,
            **values,
        )
        assert result == operation_name
        _, operation, recorded_service, recorded_arguments = adapter.calls[0]
        assert operation.name == operation_name
        assert recorded_service is service
        assert recorded_arguments == arguments

    adapter = RecordingAdapter()
    result = _ROUTES["list_by_filters"](
        request=request,
        ticket_service=service,
        adapter=adapter,
        correlation_id="corr-ticket-filters",
        reported_by=1,
        failure_type_id=2,
        address_id=3,
        status_id=4,
        priority_id=5,
        crew_id=6,
        municipality_id=7,
        commune_id=8,
        neighborhood_id=9,
    )
    assert result == "TicketService.list_by_filters"
    _, operation, recorded_service, (filters,) = adapter.calls[0]
    assert operation.name == "TicketService.list_by_filters"
    assert recorded_service is service
    assert filters == TicketFilters(
        reported_by=1,
        failure_type_id=2,
        address_id=3,
        status_id=4,
        priority_id=5,
        crew_id=6,
        municipality_id=7,
        commune_id=8,
        neighborhood_id=9,
    )


def test_ticket_write_routes_build_create_and_processing_contracts() -> None:
    service = object()

    create_adapter = RecordingAdapter()
    create_result = asyncio.run(
        _ROUTES["create"](
            request=JsonRequest(
                b'{"code":"TCK-007","reported_by":15,"failure_type_id":3,'
                b'"description":"Luminaria apagada","address_id":null,'
                b'"contact_email":"citizen@example.com","contact_phone":null}'
            ),
            ticket_service=service,
            adapter=create_adapter,
            correlation_id="corr-ticket-create",
        )
    )
    assert create_result == "TicketService.create"
    _, operation, _, (created,) = create_adapter.calls[0]
    assert operation.name == "TicketService.create"
    assert created == TicketCreateInput(
        code="TCK-007",
        reported_by=15,
        failure_type_id=3,
        description="Luminaria apagada",
        address_id=None,
        contact_email="citizen@example.com",
        contact_phone=None,
    )

    for route_name, operation_name in (
        ("validate", "TicketService.validate"),
        ("prioritize", "TicketService.prioritize"),
        ("block", "TicketService.block"),
        ("request_closure", "TicketService.request_closure"),
    ):
        adapter = RecordingAdapter()
        result = asyncio.run(
            _ROUTES[route_name](
                ticket_id=7,
                request=JsonRequest(),
                ticket_service=service,
                adapter=adapter,
                correlation_id=f"corr-{route_name}",
            )
        )
        assert result == operation_name
        _, operation, _, (data,) = adapter.calls[0]
        assert operation.name == operation_name
        assert data == TicketOperationInput(ticket_id=7)

    assign_adapter = RecordingAdapter()
    assign_result = asyncio.run(
        _ROUTES["assign"](
            ticket_id=7,
            request=JsonRequest(b'{"crew_id":3}'),
            ticket_service=service,
            adapter=assign_adapter,
            correlation_id="corr-ticket-assign",
        )
    )
    assert assign_result == "TicketService.assign"
    _, assign_operation, _, (assignment,) = assign_adapter.calls[0]
    assert assign_operation.name == "TicketService.assign"
    assert assignment == TicketAssignmentInput(ticket_id=7, crew_id=3)

    attention_adapter = RecordingAdapter()
    attention_result = asyncio.run(
        _ROUTES["record_attention"](
            ticket_id=7,
            request=JsonRequest(b'{"diagnosis":null,"solution":"Fotocelda reemplazada"}'),
            ticket_service=service,
            adapter=attention_adapter,
            correlation_id="corr-ticket-attention",
        )
    )
    assert attention_result == "TicketService.record_attention"
    _, attention_operation, _, (attention,) = attention_adapter.calls[0]
    assert attention_operation.name == "TicketService.record_attention"
    assert attention == TicketAttentionInput(ticket_id=7, diagnosis=None, solution="Fotocelda reemplazada")

    omitted_attention_adapter = RecordingAdapter()
    asyncio.run(
        _ROUTES["record_attention"](
            ticket_id=7,
            request=JsonRequest(),
            ticket_service=service,
            adapter=omitted_attention_adapter,
            correlation_id="corr-ticket-attention-omitted",
        )
    )
    omitted_attention = omitted_attention_adapter.calls[0][3][0]
    assert omitted_attention.diagnosis is UNSET
    assert omitted_attention.solution is UNSET

    review_adapter = RecordingAdapter()
    review_result = asyncio.run(
        _ROUTES["review_closure"](
            ticket_id=7,
            request=JsonRequest(b'{"decision":"Approval"}'),
            ticket_service=service,
            adapter=review_adapter,
            correlation_id="corr-ticket-review",
        )
    )
    assert review_result == "TicketService.review_closure"
    _, review_operation, _, (review,) = review_adapter.calls[0]
    assert review_operation.name == "TicketService.review_closure"
    assert review == TicketClosureReviewInput(ticket_id=7, decision="Approval")


def test_ticket_review_rejects_an_unsupported_decision_during_input_adaptation() -> None:
    with pytest.raises(ApplicationError) as raised:
        asyncio.run(
            _ROUTES["review_closure"](
                ticket_id=7,
                request=JsonRequest(b'{"decision":"Deferred"}'),
                ticket_service=object(),
                adapter=RecordingAdapter(),
                correlation_id="corr-invalid-decision",
            )
        )

    assert raised.value.code.value == "VAL-002"
    assert raised.value.details[0].field == "decision"


def test_ticket_router_documents_eleven_operations_inputs_filters_and_output_contract() -> None:
    application = FastAPI()
    application.include_router(router)
    document = application.openapi()

    assert set(document["paths"]) == {
        "/tickets",
        "/tickets/by-code/{code}",
        "/tickets/{ticket_id}",
        "/tickets/{ticket_id}/validate",
        "/tickets/{ticket_id}/prioritize",
        "/tickets/{ticket_id}/assign",
        "/tickets/{ticket_id}/attention",
        "/tickets/{ticket_id}/block",
        "/tickets/{ticket_id}/request-closure",
        "/tickets/{ticket_id}/review-closure",
    }
    assert set(document["paths"]["/tickets"]) == {"get", "post"}
    assert set(document["paths"]["/tickets/by-code/{code}"]) == {"get"}
    assert set(document["paths"]["/tickets/{ticket_id}"]) == {"get"}
    for suffix in ("validate", "prioritize", "assign", "attention", "block", "request-closure", "review-closure"):
        assert set(document["paths"][f"/tickets/{{ticket_id}}/{suffix}"]) == {"post"}

    list_parameters = {
        parameter["name"]: parameter
        for parameter in document["paths"]["/tickets"]["get"]["parameters"]
    }
    assert set(list_parameters) == {
        "reported_by",
        "failure_type_id",
        "address_id",
        "status_id",
        "priority_id",
        "crew_id",
        "municipality_id",
        "commune_id",
        "neighborhood_id",
    }
    assert all(parameter["required"] is False for parameter in list_parameters.values())

    create_body = document["paths"]["/tickets"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assignment_body = document["paths"]["/tickets/{ticket_id}/assign"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    attention_body = document["paths"]["/tickets/{ticket_id}/attention"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    review_body = document["paths"]["/tickets/{ticket_id}/review-closure"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert create_body["required"] == ["code", "reported_by", "failure_type_id", "description"]
    assert create_body["properties"]["code"]["maxLength"] == 24
    assert assignment_body["required"] == ["crew_id"]
    assert "ticket_id" not in assignment_body["properties"]
    assert attention_body.get("required", []) == []
    assert attention_body["properties"]["diagnosis"]["nullable"] is True
    assert attention_body["properties"]["solution"]["nullable"] is True
    assert review_body["required"] == ["decision"]
    assert review_body["properties"]["decision"]["enum"] == ["Approval", "Rejection"]

    no_body_operations = ("validate", "prioritize", "block", "request-closure")
    for suffix in no_body_operations:
        operation = document["paths"][f"/tickets/{{ticket_id}}/{suffix}"]["post"]
        assert "requestBody" not in operation

    ticket_schema = document["paths"]["/tickets/{ticket_id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["data"]
    assert set(ticket_schema["properties"]) == {
        "id",
        "code",
        "reported_by",
        "failure_type_id",
        "description",
        "address_id",
        "status_id",
        "priority_id",
        "contact_email",
        "contact_phone",
        "diagnosis",
        "solution",
        "crew_id",
        "created_at",
    }
    assert ticket_schema["properties"]["created_at"] == {"type": "string", "format": "date-time"}
    assert "201" in document["paths"]["/tickets"]["post"]["responses"]
    for path_item in document["paths"].values():
        for operation in path_item.values():
            assert set(("400", "403", "404", "405", "409", "422", "500")) <= set(operation["responses"])
