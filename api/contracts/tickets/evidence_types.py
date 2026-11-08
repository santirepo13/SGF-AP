"""Evidence contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..common_types import ensure_aware


@dataclass(frozen=True)
class EvidenceCreateInput:
    """Operational-only legacy metadata input; never accepted from Citizen routes."""
    ticket_id: int
    file_path: str
    captured_at: datetime | None
    uploaded_by: int
    uploaded_at: datetime | None = None
    capture_source: str | None = None
    media_type: str | None = None
    size_bytes: int | None = None
    purpose: str | None = None

    def __post_init__(self) -> None:
        ensure_aware(self.captured_at, "captured_at")


@dataclass(frozen=True, kw_only=True)
class EvidenceOutput:
    id: int
    ticket_id: int
    file_path: str
    captured_at: datetime | None
    uploaded_by: int
    uploaded_at: datetime | None
    capture_source: str | None
    media_type: str | None
    size_bytes: int | None
    purpose: str | None


@dataclass(frozen=True)
class EvidenceLookupInput:
    ticket_id: int
