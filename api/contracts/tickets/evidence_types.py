"""Evidence contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..common_types import ensure_aware


@dataclass(frozen=True)
class EvidenceCreateInput:
    ticket_id: int
    file_path: str
    captured_at: datetime
    uploaded_by: int

    def __post_init__(self) -> None:
        ensure_aware(self.captured_at, "captured_at")


@dataclass(frozen=True, kw_only=True)
class EvidenceOutput(EvidenceCreateInput):
    id: int


@dataclass(frozen=True)
class EvidenceLookupInput:
    ticket_id: int
