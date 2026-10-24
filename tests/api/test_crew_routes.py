"""Unit coverage for Scrum 6 crew and membership route adaptation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from fastapi import FastAPI

from api.contracts import CrewCreateInput, CrewMemberInput, CrewUpdateInput
from api.routes.users.crew_member_routes import router as crew_member_router
from api.routes.users.crew_routes import router as crew_router


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


_CREW_ROUTES = {route.name: route.endpoint for route in crew_router.routes}
_MEMBER_ROUTES = {route.name: route.endpoint for route in crew_member_router.routes}


def test_crew_query_routes_use_registered_service_operations() -> None:
    request = object()
    service = object()

    for route_name, values, operation_name, arguments in (
        ("list_all", {}, "CrewService.list_all", ()),
        ("get_by_id", {"crew_id": 3}, "CrewService.get_by_id", (3,)),
        ("list_members", {"crew_id": 3}, "CrewService.list_members", (3,)),
    ):
        adapter = RecordingAdapter()
        result = _CREW_ROUTES[route_name](
            request=request,
            crew_service=service,
            adapter=adapter,
            **values,
        )
        assert result == operation_name
        _, operation, recorded_service, recorded_arguments = adapter.calls[0]
        assert operation.name == operation_name
        assert recorded_service is service
        assert recorded_arguments == arguments

    membership_adapter = RecordingAdapter()
    membership_result = _MEMBER_ROUTES["get_membership"](
        user_id=15,
        request=request,
        crew_service=service,
        adapter=membership_adapter,
    )
    assert membership_result == "CrewService.get_membership"
    assert membership_adapter.calls[0][1].name == "CrewService.get_membership"
    assert membership_adapter.calls[0][3] == (15,)

    remove_adapter = RecordingAdapter()
    remove_result = _MEMBER_ROUTES["remove_member"](
        user_id=15,
        request=request,
        crew_service=service,
        adapter=remove_adapter,
    )
    assert remove_result == "CrewService.remove_member"
    assert remove_adapter.calls[0][1].name == "CrewService.remove_member"
    assert remove_adapter.calls[0][3] == (15,)


def test_crew_write_routes_build_their_contracts_from_json_and_path_ids() -> None:
    service = object()

    create_adapter = RecordingAdapter()
    create_result = asyncio.run(
        _CREW_ROUTES["create"](
            request=JsonRequest(b'{"name":"Cuadrilla Norte"}'),
            crew_service=service,
            adapter=create_adapter,
            correlation_id="corr-create-crew",
        )
    )
    assert create_result == "CrewService.create"
    _, create_operation, _, (create_data,) = create_adapter.calls[0]
    assert create_operation.name == "CrewService.create"
    assert isinstance(create_data, CrewCreateInput)
    assert create_data.name == "Cuadrilla Norte"

    update_adapter = RecordingAdapter()
    update_result = asyncio.run(
        _CREW_ROUTES["update"](
            crew_id=3,
            request=JsonRequest(b'{"name":"Cuadrilla Norte 2"}'),
            crew_service=service,
            adapter=update_adapter,
            correlation_id="corr-update-crew",
        )
    )
    assert update_result == "CrewService.update"
    _, update_operation, _, (update_data,) = update_adapter.calls[0]
    assert update_operation.name == "CrewService.update"
    assert isinstance(update_data, CrewUpdateInput)
    assert update_data == CrewUpdateInput(crew_id=3, name="Cuadrilla Norte 2")

    add_adapter = RecordingAdapter()
    add_result = asyncio.run(
        _CREW_ROUTES["add_member"](
            crew_id=3,
            request=JsonRequest(b'{"user_id":15}'),
            crew_service=service,
            adapter=add_adapter,
            correlation_id="corr-add-member",
        )
    )
    assert add_result == "CrewService.add_member"
    _, add_operation, _, (add_data,) = add_adapter.calls[0]
    assert add_operation.name == "CrewService.add_member"
    assert isinstance(add_data, CrewMemberInput)
    assert add_data == CrewMemberInput(user_id=15, crew_id=3)

    change_adapter = RecordingAdapter()
    change_result = asyncio.run(
        _MEMBER_ROUTES["change_crew"](
            user_id=15,
            request=JsonRequest(b'{"crew_id":5}'),
            crew_service=service,
            adapter=change_adapter,
            correlation_id="corr-change-crew",
        )
    )
    assert change_result == "CrewService.change_crew"
    _, change_operation, _, (change_data,) = change_adapter.calls[0]
    assert change_operation.name == "CrewService.change_crew"
    assert isinstance(change_data, CrewMemberInput)
    assert change_data == CrewMemberInput(user_id=15, crew_id=5)


def test_crew_routers_document_all_nine_operations_and_public_response_shapes() -> None:
    application = FastAPI()
    application.include_router(crew_router)
    application.include_router(crew_member_router)
    document = application.openapi()

    assert set(document["paths"]) == {
        "/crews",
        "/crews/{crew_id}",
        "/crews/{crew_id}/members",
        "/crew-members/{user_id}",
    }
    assert set(document["paths"]["/crews"]) == {"get", "post"}
    assert set(document["paths"]["/crews/{crew_id}"]) == {"get", "patch"}
    assert set(document["paths"]["/crews/{crew_id}/members"]) == {"get", "post"}
    assert set(document["paths"]["/crew-members/{user_id}"]) == {"get", "patch", "delete"}

    crew_update_body = document["paths"]["/crews/{crew_id}"]["patch"]["requestBody"]["content"]["application/json"]["schema"]
    add_member_body = document["paths"]["/crews/{crew_id}/members"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    change_member_body = document["paths"]["/crew-members/{user_id}"]["patch"]["requestBody"]["content"]["application/json"]["schema"]
    assert crew_update_body["required"] == ["name"]
    assert "crew_id" not in crew_update_body["properties"]
    assert add_member_body["required"] == ["user_id"]
    assert "crew_id" not in add_member_body["properties"]
    assert change_member_body["required"] == ["crew_id"]
    assert "user_id" not in change_member_body["properties"]

    assert "201" in document["paths"]["/crews"]["post"]["responses"]
    assert "201" in document["paths"]["/crews/{crew_id}/members"]["post"]["responses"]
    for path_item in document["paths"].values():
        for operation in path_item.values():
            assert set(("400", "403", "404", "405", "409", "422", "500")) <= set(operation["responses"])
