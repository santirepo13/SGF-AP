"""Ticket operation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..common_types import UNSET, Unset, ensure_aware, ensure_length


@dataclass(frozen=True)
class TicketCreateInput:
    code: str
    reported_by: int
    failure_type_id: int
    description: str
    address_id: int | None = None
    contact_email: str | None = None
    contact_phone: str | None = None

    def __post_init__(self) -> None:
        ensure_length(self.code, 24, "code")


@dataclass(frozen=True)
class TicketFilters:
    reported_by: int | None = None
    failure_type_id: int | None = None
    address_id: int | None = None
    status_id: int | None = None
    priority_id: int | None = None
    crew_id: int | None = None
    municipality_id: int | None = None
    commune_id: int | None = None
    neighborhood_id: int | None = None


@dataclass(frozen=True)
class TicketUpdateInput:
    """Partial ticket update; UNSET preserves and None clears nullable fields."""

    ticket_id: int
    code: str | Unset = UNSET
    reported_by: int | Unset = UNSET
    failure_type_id: int | Unset = UNSET
    description: str | Unset = UNSET
    address_id: int | None | Unset = UNSET
    status_id: int | Unset = UNSET
    priority_id: int | None | Unset = UNSET
    contact_email: str | None | Unset = UNSET
    contact_phone: str | None | Unset = UNSET
    diagnosis: str | None | Unset = UNSET
    solution: str | None | Unset = UNSET
    crew_id: int | None | Unset = UNSET

    def __post_init__(self) -> None:
        if self.code is not UNSET:
            ensure_length(self.code, 24, "code")


@dataclass(frozen=True)
class TicketLookupInput:
    ticket_id: int


@dataclass(frozen=True)
class TicketCodeLookupInput:
    code: str


@dataclass(frozen=True)
class TicketOperationInput:
    ticket_id: int


@dataclass(frozen=True)
class TicketAssignmentInput:
    ticket_id: int
    crew_id: int


@dataclass(frozen=True)
class TicketAttentionInput:
    ticket_id: int
    diagnosis: str | None | Unset = UNSET
    solution: str | None | Unset = UNSET


@dataclass(frozen=True)
class TicketClosureReviewInput:
    ticket_id: int
    decision: str


@dataclass(frozen=True)
class TicketOutput:
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
