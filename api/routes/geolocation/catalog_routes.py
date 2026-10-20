"""Catalog and geolocation routes registered for future HTTP operations."""

from fastapi import APIRouter

router = APIRouter(prefix="/catalogs", tags=["Catalogs and geolocation"])
