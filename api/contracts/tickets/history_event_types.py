"""Ticket history event contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..common_types import ensure_aware


@dataclass(frozen=True)
class HistoryEventCreateInput:
    ticket_id: int
    action_id: int
    user_id: int | None = None


@dataclass(frozen=True)
class HistoryEventOutput:
    id: int
    ticket_id: int
    user_id: int | None
    action_id: int
    event_time: datetime

    def __post_init__(self) -> None:
        ensure_aware(self.event_time, "event_time")


@dataclass(frozen=True)
class HistoryEventLookupInput:
    ticket_id: int
