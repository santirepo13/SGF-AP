"""Address routes registered for future HTTP operations."""

from fastapi import APIRouter

router = APIRouter(prefix="/addresses", tags=["Addresses"])
