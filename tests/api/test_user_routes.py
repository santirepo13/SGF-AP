"""Unit coverage for Scrum 5 user route adaptation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from fastapi import FastAPI

from api.contracts import UNSET, UserActivationInput, UserCreateInput, UserFilters, UserUpdateInput
from api.routes.users.user_routes import router


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


def test_user_query_routes_use_registered_operations_and_preserve_false_filters() -> None:
    request = object()
    service = object()

    email_adapter = RecordingAdapter()
    email_result = _ROUTES["get_by_email"](
        email="ada@example.test",
        request=request,
        user_service=service,
        adapter=email_adapter,
    )
    assert email_result == "UserService.get_by_email"
    assert email_adapter.calls[0][1].name == "UserService.get_by_email"
    assert email_adapter.calls[0][3] == ("ada@example.test",)

    list_adapter = RecordingAdapter()
    list_result = _ROUTES["list_by_filters"](
        request=request,
        user_service=service,
        adapter=list_adapter,
        correlation_id="corr-list",
        email="ada@example.test",
        role_id=2,
        active=False,
    )
    assert list_result == "UserService.list_by_filters"
    _, list_operation, _, (filters,) = list_adapter.calls[0]
    assert list_operation.name == "UserService.list_by_filters"
    assert isinstance(filters, UserFilters)
    assert filters == UserFilters(email="ada@example.test", role_id=2, active=False)

    id_adapter = RecordingAdapter()
    id_result = _ROUTES["get_by_id"](
        user_id=7,
        request=request,
        user_service=service,
        adapter=id_adapter,
    )
    assert id_result == "UserService.get_by_id"
    assert id_adapter.calls[0][1].name == "UserService.get_by_id"
    assert id_adapter.calls[0][3] == (7,)


def test_user_write_routes_build_create_update_and_activation_contracts() -> None:
    service = object()

    create_adapter = RecordingAdapter()
    create_result = asyncio.run(
        _ROUTES["create"](
            request=JsonRequest(
                b'{"first_name":"Ada","last_name":"Lovelace","email":"ada@example.test",'
                b'"password_hash":"stored-hash","role_id":2}'
            ),
            user_service=service,
            adapter=create_adapter,
            correlation_id="corr-create",
        )
    )
    assert create_result == "UserService.create"
    _, create_operation, _, (create_data,) = create_adapter.calls[0]
    assert create_operation.name == "UserService.create"
    assert isinstance(create_data, UserCreateInput)
    assert create_data.active is True

    update_adapter = RecordingAdapter()
    update_result = asyncio.run(
        _ROUTES["update"](
            user_id=7,
            request=JsonRequest(b'{"active":false}'),
            user_service=service,
            adapter=update_adapter,
            correlation_id="corr-update",
        )
    )
    assert update_result == "UserService.update"
    _, update_operation, _, (update_data,) = update_adapter.calls[0]
    assert update_operation.name == "UserService.update"
    assert isinstance(update_data, UserUpdateInput)
    assert update_data.user_id == 7
    assert update_data.active is False

    empty_update_adapter = RecordingAdapter()
    empty_update_result = asyncio.run(
        _ROUTES["update"](
            user_id=7,
            request=JsonRequest(b"{}"),
            user_service=service,
            adapter=empty_update_adapter,
            correlation_id="corr-empty-update",
        )
    )
    assert empty_update_result == "UserService.update"
    empty_update_data = empty_update_adapter.calls[0][3][0]
    assert empty_update_data.user_id == 7
    assert empty_update_data.first_name is UNSET
    assert empty_update_data.active is UNSET

    activation_adapter = RecordingAdapter()
    activation_result = asyncio.run(
        _ROUTES["set_active"](
            user_id=7,
            request=JsonRequest(b'{"active":false}'),
            user_service=service,
            adapter=activation_adapter,
            correlation_id="corr-activation",
        )
    )
    assert activation_result == "UserService.set_active"
    _, activation_operation, _, (activation_data,) = activation_adapter.calls[0]
    assert activation_operation.name == "UserService.set_active"
    assert isinstance(activation_data, UserActivationInput)
    assert activation_data == UserActivationInput(user_id=7, active=False)


def test_user_router_documents_six_operations_and_public_contracts() -> None:
    application = FastAPI()
    application.include_router(router)
    document = application.openapi()

    assert set(document["paths"]) == {
        "/users/by-email",
        "/users",
        "/users/{user_id}",
        "/users/{user_id}/activation",
    }
    assert set(document["paths"]["/users"]) == {"get", "post"}
    assert set(document["paths"]["/users/{user_id}"]) == {"get", "patch"}
    assert "patch" in document["paths"]["/users/{user_id}/activation"]
    assert "requestBody" in document["paths"]["/users"]["post"]
    assert "password_hash" not in document["paths"]["/users"]["post"]["responses"]["201"]["content"]["application/json"]["schema"]["properties"]["data"]["properties"]
    update_body = document["paths"]["/users/{user_id}"]["patch"]["requestBody"]["content"]["application/json"]["schema"]
    activation_body = document["paths"]["/users/{user_id}/activation"]["patch"]["requestBody"]["content"]["application/json"]["schema"]
    assert "user_id" not in update_body["properties"]
    assert activation_body["required"] == ["active"]

    list_parameters = {
        parameter["name"]: parameter
        for parameter in document["paths"]["/users"]["get"]["parameters"]
    }
    assert list_parameters["active"]["required"] is False
    active_schema = list_parameters["active"]["schema"]
    assert any(option.get("type") == "boolean" for option in active_schema.get("anyOf", [active_schema]))

    assert "201" in document["paths"]["/users"]["post"]["responses"]
    for path_item in document["paths"].values():
        for operation in path_item.values():
            assert set(("400", "403", "404", "405", "409", "422", "500")) <= set(operation["responses"])
