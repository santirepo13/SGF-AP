"""Evidence persistence model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from api.contracts.common_types import ensure_aware


@dataclass(frozen=True)
class Evidence:
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

    def __post_init__(self) -> None:
        if self.captured_at is not None:
            ensure_aware(self.captured_at, "captured_at")
        if self.uploaded_at is not None:
            ensure_aware(self.uploaded_at, "uploaded_at")
