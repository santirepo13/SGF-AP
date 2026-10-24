"""Central registration for SGF-AP HTTP route groups."""

from fastapi import FastAPI

from .address import address_router
from .geolocation import catalog_router
from .tickets.evidence_routes import router as evidence_router
from .tickets.history_routes import router as history_router
from .tickets.ticket_routes import router as ticket_router
from .users.crew_routes import router as crew_router
from .users.user_routes import router as user_router


def register_routers(app: FastAPI) -> None:
    """Attach every domain group from one composition point."""

    for router in (
        catalog_router,
        address_router,
        user_router,
        crew_router,
        ticket_router,
        evidence_router,
        history_router,
    ):
        app.include_router(router)
