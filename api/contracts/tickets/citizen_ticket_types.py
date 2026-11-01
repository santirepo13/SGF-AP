"""Public citizen-report contracts separate from internal ticket records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..common_types import UNSET, Unset, ensure_aware


@dataclass(frozen=True, slots=True)
class CitizenTicketCreateInput:
    """A citizen report intent without identity, workflow, or internal ticket fields."""

    request_key: str = field(repr=False)
    failure_type_id: int
    address_id: int
    description: str
    contact_email: str | None | Unset = field(default=UNSET, repr=False)
    contact_phone: str | None | Unset = field(default=UNSET, repr=False)
    temporary_upload_ids: list[str] | None | Unset = field(default=UNSET, repr=False)
    email_notifications: bool | None | Unset = field(default=UNSET, repr=False)


@dataclass(frozen=True, slots=True)
class CitizenMatchInput:
    """The canonical references used to search for open matching reports."""

    address_id: int
    failure_type_id: int


@dataclass(frozen=True, slots=True)
class CitizenAttemptLookupInput:
    """The opaque key used to recover a previously submitted report intent."""

    request_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CitizenTicketConfirmation:
    """Minimal confirmation available only after a report commits."""

    code: str
    created_at: datetime
    status: str
    evidence_count: int

    def __post_init__(self) -> None:
        if type(self.code) is not str or not self.code:
            raise ValueError("code must be a non-empty string")
        if type(self.status) is not str or not self.status:
            raise ValueError("status must be a non-empty string")
        if type(self.evidence_count) is not int or self.evidence_count < 0:
            raise ValueError("evidence_count must be a non-negative integer")
        ensure_aware(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class CitizenMatchOutput:
    """Safe projection of an existing open report for duplicate guidance."""

    code: str
    status: str
    created_at: datetime
    progress_label: str

    def __post_init__(self) -> None:
        for field_name in ("code", "status", "progress_label"):
            value = getattr(self, field_name)
            if type(value) is not str or not value:
                raise ValueError(f"{field_name} must be a non-empty string")
        ensure_aware(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class CitizenMatchesOutput:
    """Bounded match result; has_more keeps the existence decision accurate."""

    matches: tuple[CitizenMatchOutput, ...]
    has_more: bool

    def __post_init__(self) -> None:
        if type(self.has_more) is not bool:
            raise ValueError("has_more must be a boolean")
        if len(self.matches) > 20:
            raise ValueError("matches may contain at most twenty items")
        if any(not isinstance(match, CitizenMatchOutput) for match in self.matches):
            raise ValueError("matches must contain CitizenMatchOutput values")


@dataclass(frozen=True, slots=True)
class CitizenTicketRegistrationOutput:
    """A committed decision: a created ticket or existing open matches."""

    request_key: str = field(repr=False)
    outcome: str
    ticket: CitizenTicketConfirmation | None
    matches: tuple[CitizenMatchOutput, ...]

    def __post_init__(self) -> None:
        if type(self.request_key) is not str or not self.request_key:
            raise ValueError("request_key must be a non-empty string")
        if self.outcome not in {"created", "matches"}:
            raise ValueError("outcome must be created or matches")
        if self.outcome == "created":
            if not isinstance(self.ticket, CitizenTicketConfirmation) or self.matches:
                raise ValueError("created output requires ticket and no matches")
        elif self.ticket is not None:
            raise ValueError("matches output must not include a ticket")
        if any(not isinstance(match, CitizenMatchOutput) for match in self.matches):
            raise ValueError("matches must contain CitizenMatchOutput values")


@dataclass(frozen=True, slots=True)
class CitizenAttemptOutput:
    """Recovery result for one actor-owned registration request key."""

    request_key: str = field(repr=False)
    state: str
    result: CitizenTicketRegistrationOutput | None

    def __post_init__(self) -> None:
        if type(self.request_key) is not str or not self.request_key:
            raise ValueError("request_key must be a non-empty string")
        if self.state not in {"committed", "not_found"}:
            raise ValueError("state must be committed or not_found")
        if self.state == "committed" and not isinstance(self.result, CitizenTicketRegistrationOutput):
            raise ValueError("committed output requires a result")
        if self.state == "not_found" and self.result is not None:
            raise ValueError("not_found output must not include a result")


__all__ = [
    "CitizenAttemptLookupInput",
    "CitizenAttemptOutput",
    "CitizenMatchInput",
    "CitizenMatchOutput",
    "CitizenMatchesOutput",
    "CitizenTicketConfirmation",
    "CitizenTicketCreateInput",
    "CitizenTicketRegistrationOutput",
]
