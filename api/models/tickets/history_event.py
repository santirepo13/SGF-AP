"""History event persistence model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from api.contracts.common_types import ensure_aware


@dataclass(frozen=True)
class HistoryEvent:
    id: int
    ticket_id: int
    user_id: int | None
    action_id: int
    event_time: datetime

    def __post_init__(self) -> None:
        ensure_aware(self.event_time, "event_time")
