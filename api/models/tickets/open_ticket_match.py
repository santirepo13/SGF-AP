"""Minimal internal projection used while detecting open ticket matches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from api.contracts.common_types import ensure_aware


@dataclass(frozen=True, slots=True)
class OpenTicketMatch:
    id: int
    code: str
    status: str
    created_at: datetime

    def __post_init__(self) -> None:
        if type(self.id) is not int or self.id <= 0:
            raise ValueError("id must be a positive integer")
        if type(self.code) is not str or not self.code:
            raise ValueError("code must be a non-empty string")
        if type(self.status) is not str or not self.status:
            raise ValueError("status must be a non-empty string")
        ensure_aware(self.created_at, "created_at")
