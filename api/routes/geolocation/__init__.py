"""Geolocation HTTP route group."""

from .catalog_routes import router as catalog_router

__all__ = ["catalog_router"]
