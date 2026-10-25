"""Ticket HTTP route groups."""

from .evidence_routes import router as evidence_router
from .history_routes import router as history_router
from .ticket_routes import router as ticket_router

__all__ = ["evidence_router", "history_router", "ticket_router"]
