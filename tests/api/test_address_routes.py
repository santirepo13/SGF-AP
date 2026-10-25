"""Unit coverage for Scrum 4 address route adaptation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from fastapi import FastAPI

from api.contracts import AddressComponentsInput
from api.routes.address.address_routes import router


@dataclass
class RecordingAdapter:
    calls: list[tuple[object, object, object, tuple[object, ...]]] = field(default_factory=list)

    def execute(self, request, operation, service, *arguments):
        self.calls.append((request, operation, service, arguments))
        return operation.name


class JsonRequest:
    async def body(self) -> bytes:
        return (
            b'{"road_type_code":"CL","road_number":12,"cross_road_number":34,'
            b'"door_plate_number":56,"road_bis_suffix":null}'
        )


_ROUTES = {route.name: route.endpoint for route in router.routes}


def test_address_routes_build_contracts_and_use_the_registered_service_operations() -> None:
    request = object()
    service = object()

    search_adapter = RecordingAdapter()
    search_result = _ROUTES["find_by_components"](
        request=request,
        road_type_code="CL",
        road_number=12,
        cross_road_number=34,
        door_plate_number=56,
        address_service=service,
        adapter=search_adapter,
        correlation_id="corr-search",
    )
    assert search_result == "AddressService.find_by_components"
    assert len(search_adapter.calls) == 1
    _, search_operation, search_service, (components,) = search_adapter.calls[0]
    assert search_operation.name == "AddressService.find_by_components"
    assert search_service is service
    assert isinstance(components, AddressComponentsInput)
    assert components.road_type_code == "CL"
    assert components.road_bis_suffix is None
    assert components.neighborhood_id is None

    for route_name, address_id, operation_name in (
        ("get_by_id", 15, "AddressService.get_by_id"),
        ("format_address", 15, "AddressService.format_address"),
    ):
        adapter = RecordingAdapter()
        result = _ROUTES[route_name](
            address_id=address_id,
            request=request,
            address_service=service,
            adapter=adapter,
        )
        assert result == operation_name
        _, operation, recorded_service, arguments = adapter.calls[0]
        assert operation.name == operation_name
        assert recorded_service is service
        assert arguments == (address_id,)


def test_create_or_reuse_reads_the_json_contract_and_uses_the_create_operation() -> None:
    adapter = RecordingAdapter()
    service = object()

    result = asyncio.run(
        _ROUTES["create_or_reuse"](
            request=JsonRequest(),
            address_service=service,
            adapter=adapter,
            correlation_id="corr-create",
        )
    )

    assert result == "AddressService.create_or_reuse"
    _, operation, recorded_service, (data,) = adapter.calls[0]
    assert operation.name == "AddressService.create_or_reuse"
    assert recorded_service is service
    assert data.road_type_code == "CL"
    assert data.road_bis_suffix is None


def test_address_router_documents_the_four_routes_inputs_and_common_responses() -> None:
    application = FastAPI()
    application.include_router(router)
    document = application.openapi()

    assert set(document["paths"]) == {
        "/addresses/search",
        "/addresses/{address_id}/formatted",
        "/addresses/{address_id}",
        "/addresses",
    }
    assert "requestBody" in document["paths"]["/addresses"]["post"]

    search_operation = document["paths"]["/addresses/search"]["get"]
    parameters = {parameter["name"]: parameter for parameter in search_operation["parameters"]}
    assert {"road_type_code", "road_number", "cross_road_number", "door_plate_number"} <= set(parameters)
    assert parameters["road_type_code"]["required"] is True
    assert parameters["road_number"]["schema"]["type"] == "integer"
    assert parameters["road_suffix_letter_code"]["required"] is False

    for path_item in document["paths"].values():
        for operation in path_item.values():
            assert set(("200", "400", "403", "404", "405", "409", "422", "500")) <= set(operation["responses"])
