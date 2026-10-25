"""Unit coverage for Scrum 9 history-query route adaptation and documentation."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import FastAPI

from api.routes.tickets.history_routes import router


@dataclass
class RecordingAdapter:
    calls: list[tuple[object, object, object, tuple[object, ...]]] = field(default_factory=list)

    def execute(self, request, operation, service, *arguments):
        self.calls.append((request, operation, service, arguments))
        return operation.name


_ROUTES = {route.name: route.endpoint for route in router.routes}


def test_history_query_routes_use_registered_service_operations() -> None:
    request = object()
    service = object()

    event_adapter = RecordingAdapter()
    event_result = _ROUTES["get_event"](
        event_id=105,
        request=request,
        history_service=service,
        adapter=event_adapter,
    )
    assert event_result == "HistoryService.get_event"
    _, event_operation, recorded_service, event_arguments = event_adapter.calls[0]
    assert event_operation.name == "HistoryService.get_event"
    assert recorded_service is service
    assert event_arguments == (105,)

    ticket_adapter = RecordingAdapter()
    ticket_result = _ROUTES["list_by_ticket"](
        request=request,
        history_service=service,
        adapter=ticket_adapter,
        ticket_id=42,
    )
    assert ticket_result == "HistoryService.list_by_ticket"
    _, ticket_operation, recorded_service, ticket_arguments = ticket_adapter.calls[0]
    assert ticket_operation.name == "HistoryService.list_by_ticket"
    assert recorded_service is service
    assert ticket_arguments == (42,)


def test_history_router_documents_event_and_ticket_lookup_contracts() -> None:
    application = FastAPI()
    application.include_router(router)
    document = application.openapi()

    assert set(document["paths"]) == {"/history-events", "/history-events/{event_id}"}
    assert set(document["paths"]["/history-events"]) == {"get"}
    assert set(document["paths"]["/history-events/{event_id}"]) == {"get"}

    list_parameters = {
        parameter["name"]: parameter
        for parameter in document["paths"]["/history-events"]["get"]["parameters"]
    }
    assert set(list_parameters) == {"ticket_id"}
    assert list_parameters["ticket_id"]["required"] is True

    event_schema = document["paths"]["/history-events/{event_id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["data"]
    assert set(event_schema["properties"]) == {"id", "ticket_id", "user_id", "action_id", "event_time"}
    assert event_schema["properties"]["user_id"]["nullable"] is True
    assert event_schema["properties"]["event_time"] == {"type": "string", "format": "date-time"}

    for path_item in document["paths"].values():
        for operation in path_item.values():
            assert set(("400", "403", "404", "405", "409", "422", "500")) <= set(operation["responses"])
