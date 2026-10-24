"""Unit coverage for Scrum 3 catalog and geolocation route adaptation."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import FastAPI

from api.routes.geolocation.catalog_routes import router


@dataclass
class RecordingAdapter:
    calls: list[tuple[object, object, object, tuple[object, ...]]] = field(default_factory=list)

    def execute(self, request, operation, service, *arguments):
        self.calls.append((request, operation, service, arguments))
        return operation.name


_ROUTES = {route.name: route.endpoint for route in router.routes}
_ROUTE_CASES = (
    ("list_municipalities", {}, "CatalogService.list_municipalities", ()),
    ("list_communes", {"municipality_id": 7}, "CatalogService.list_communes", (7,)),
    (
        "list_neighborhoods_by_municipality",
        {"municipality_id": 7},
        "CatalogService.list_neighborhoods_by_municipality",
        (7,),
    ),
    ("list_neighborhoods_by_commune", {"commune_id": 8}, "CatalogService.list_neighborhoods_by_commune", (8,)),
    (
        "list_neighborhoods_without_commune",
        {"municipality_id": 7},
        "CatalogService.list_neighborhoods_without_commune",
        (7,),
    ),
    ("list_road_types", {}, "CatalogService.list_road_types", ()),
    ("list_road_suffix_letters", {}, "CatalogService.list_road_suffix_letters", ()),
    ("list_road_bis_codes", {}, "CatalogService.list_road_bis_codes", ()),
    ("list_road_quadrants", {}, "CatalogService.list_road_quadrants", ()),
    ("list_cross_suffix_letters", {}, "CatalogService.list_cross_suffix_letters", ()),
    ("list_cross_bis_codes", {}, "CatalogService.list_cross_bis_codes", ()),
    ("list_cross_quadrants", {}, "CatalogService.list_cross_quadrants", ()),
    ("list_roles", {}, "CatalogService.list_roles", ()),
    ("list_priorities", {}, "CatalogService.list_priorities", ()),
    ("list_failure_types", {}, "CatalogService.list_failure_types", ()),
    (
        "list_failure_types_by_priority",
        {"priority_id": 2},
        "CatalogService.list_failure_types_by_priority",
        (2,),
    ),
    ("list_statuses", {}, "CatalogService.list_statuses", ()),
    ("list_actions", {}, "CatalogService.list_actions", ()),
)


def test_catalog_routes_use_the_registered_catalog_service_operations() -> None:
    for route_name, path_arguments, operation_name, arguments in _ROUTE_CASES:
        request = object()
        service = object()
        adapter = RecordingAdapter()

        result = _ROUTES[route_name](
            request=request,
            catalog_service=service,
            adapter=adapter,
            **path_arguments,
        )

        assert result == operation_name
        assert len(adapter.calls) == 1
        recorded_request, operation, recorded_service, recorded_arguments = adapter.calls[0]
        assert recorded_request is request
        assert recorded_service is service
        assert recorded_arguments == arguments
        assert operation.name == operation_name


def test_catalog_router_documents_all_eighteen_get_routes_and_common_responses() -> None:
    application = FastAPI()
    application.include_router(router)
    document = application.openapi()

    assert len(document["paths"]) == 18
    for path_item in document["paths"].values():
        operation = path_item["get"]
        assert set(("200", "400", "403", "404", "405", "500")) <= set(operation["responses"])

    parameters = document["paths"]["/catalogs/municipalities/{municipality_id}/communes"]["get"]["parameters"]
    assert len(parameters) == 1
    assert parameters[0]["name"] == "municipality_id"
    assert parameters[0]["in"] == "path"
    assert parameters[0]["required"] is True
    assert parameters[0]["schema"]["type"] == "integer"
