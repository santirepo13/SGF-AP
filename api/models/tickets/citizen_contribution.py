from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CitizenContribution:
    id: UUID
    ticket_id: int
    actor_user_id: int
    request_key: str
    created_at: datetime
