"""Crew routes registered for future HTTP operations."""

from fastapi import APIRouter

router = APIRouter(prefix="/crews", tags=["Crews"])
