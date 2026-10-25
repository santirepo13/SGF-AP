"""Central registration for SGF-AP HTTP route groups."""

from fastapi import FastAPI

from .address import address_router
from .geolocation import catalog_router
from .tickets import evidence_router, ticket_router
from .tickets.history_routes import router as history_router
from .users import crew_member_router, crew_router, user_router


def register_routers(app: FastAPI) -> None:
    """Attach every domain group from one composition point."""

    for router in (
        catalog_router,
        address_router,
        user_router,
        crew_router,
        crew_member_router,
        ticket_router,
        evidence_router,
        history_router,
    ):
        app.include_router(router)
