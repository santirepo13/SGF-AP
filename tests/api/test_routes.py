"""Unit coverage for central HTTP route registration."""

from __future__ import annotations

from api.routes import register_routers


class RouterCollector:
    def __init__(self) -> None:
        self.routers = []

    def include_router(self, router) -> None:
        self.routers.append(router)


def test_register_routers_includes_every_domain_group_once() -> None:
    application = RouterCollector()

    register_routers(application)  # type: ignore[arg-type]

    assert [router.prefix for router in application.routers] == [
        "/catalogs",
        "/addresses",
        "/users",
        "/crews",
        "/crew-members",
        "/tickets",
        "/evidences",
        "/tickets",
    ]
    assert [router.tags[0] for router in application.routers] == [
        "Catalogs and geolocation",
        "Addresses",
        "Users",
        "Crews",
        "Crew members",
        "Tickets",
        "Evidence",
        "History",
    ]
