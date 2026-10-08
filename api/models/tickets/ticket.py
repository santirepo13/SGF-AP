"""Ticket persistence model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from api.contracts.common_types import ensure_aware, ensure_length


@dataclass(frozen=True)
class Ticket:
    id: int
    code: str
    reported_by: int
    failure_type_id: int
    description: str
    address_id: int | None
    status_id: int
    priority_id: int | None
    contact_email: str | None
    contact_phone: str | None
    diagnosis: str | None
    solution: str | None
    crew_id: int | None
    created_at: datetime

    def __post_init__(self) -> None:
        ensure_length(self.code, 24, "code")
        ensure_aware(self.created_at, "created_at")
