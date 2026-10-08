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
    captured_at: datetime
    uploaded_by: int

    def __post_init__(self) -> None:
        ensure_aware(self.captured_at, "captured_at")
