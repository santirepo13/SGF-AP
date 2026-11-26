"""Explicit safe contracts for citizen ticket queries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from ..common_types import ensure_aware, ensure_length
from .evidence_upload_types import CitizenEvidenceOutput

_CITIZEN_CODE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,23}", re.ASCII)


def _text(value: str, name: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class PublicTicketOutput:
    code: str
    status: str
    status_label: str
    last_updated_at: datetime
    public_summary: str

    def __post_init__(self) -> None:
        _text(self.code, "code")
        _text(self.status, "status")
        _text(self.status_label, "status_label")
        _text(self.public_summary, "public_summary")
        ensure_length(self.code, 24, "code")
        ensure_aware(self.last_updated_at, "last_updated_at")


@dataclass(frozen=True, slots=True)
class CitizenTicketListItem:
    code: str
    created_at: datetime
    status: str
    status_label: str
    failure_type_label: str
    last_updated_at: datetime

    def __post_init__(self) -> None:
        _text(self.code, "code")
        _text(self.status, "status")
        _text(self.status_label, "status_label")
        _text(self.failure_type_label, "failure_type_label")
        ensure_length(self.code, 24, "code")
        ensure_aware(self.created_at, "created_at")
        ensure_aware(self.last_updated_at, "last_updated_at")


@dataclass(frozen=True, slots=True)
class CitizenTicketDetailOutput:
    code: str
    created_at: datetime
    status: str
    status_label: str
    failure_type_label: str
    last_updated_at: datetime
    public_summary: str
    description: str
    formatted_address: str | None
    contact_email: str | None
    contact_phone: str | None
    email_notifications: bool
    evidences: tuple[CitizenEvidenceOutput, ...] = ()

    def __post_init__(self) -> None:
        item = CitizenTicketListItem(
            self.code, self.created_at, self.status, self.status_label,
            self.failure_type_label, self.last_updated_at,
        )
        del item
        _text(self.public_summary, "public_summary")
        if type(self.description) is not str:
            raise ValueError("description must be a string")
        if self.formatted_address is not None and type(self.formatted_address) is not str:
            raise ValueError("formatted_address must be a string or None")
        if self.contact_email is not None and type(self.contact_email) is not str:
            raise ValueError("contact_email must be a string or None")
        if self.contact_phone is not None and type(self.contact_phone) is not str:
            raise ValueError("contact_phone must be a string or None")
        if type(self.email_notifications) is not bool:
            raise ValueError("email_notifications must be a boolean")
        if any(not isinstance(value, CitizenEvidenceOutput) for value in self.evidences):
            raise ValueError("evidences must contain CitizenEvidenceOutput values")


@dataclass(frozen=True, slots=True)
class CitizenHistoryItem:
    occurred_at: datetime
    action: str
    label: str

    def __post_init__(self) -> None:
        ensure_aware(self.occurred_at, "occurred_at")
        _text(self.action, "action")
        _text(self.label, "label")


@dataclass(frozen=True, slots=True)
class CitizenTicketPageOutput:
    items: tuple[CitizenTicketListItem, ...]
    next_cursor: str | None

    def __post_init__(self) -> None:
        if any(not isinstance(item, CitizenTicketListItem) for item in self.items):
            raise ValueError("items must contain CitizenTicketListItem values")
        if self.next_cursor is not None and (type(self.next_cursor) is not str or len(self.next_cursor) > 512):
            raise ValueError("next_cursor is invalid")


@dataclass(frozen=True, slots=True)
class CitizenHistoryPageOutput:
    items: tuple[CitizenHistoryItem, ...]
    next_cursor: str | None

    def __post_init__(self) -> None:
        if any(not isinstance(item, CitizenHistoryItem) for item in self.items):
            raise ValueError("items must contain CitizenHistoryItem values")
        if self.next_cursor is not None and (type(self.next_cursor) is not str or len(self.next_cursor) > 512):
            raise ValueError("next_cursor is invalid")


@dataclass(frozen=True, slots=True)
class CitizenQueryPageInput:
    limit: int = 20
    cursor: str | None = None

    def __post_init__(self) -> None:
        if type(self.limit) is not int or not 1 <= self.limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        if self.cursor is not None and (type(self.cursor) is not str or not self.cursor or len(self.cursor) > 512):
            raise ValueError("cursor is invalid")


@dataclass(frozen=True, slots=True)
class CitizenHistoryPageInput:
    limit: int = 50
    cursor: str | None = None

    def __post_init__(self) -> None:
        if type(self.limit) is not int or not 1 <= self.limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if self.cursor is not None and (type(self.cursor) is not str or not self.cursor or len(self.cursor) > 512):
            raise ValueError("cursor is invalid")


@dataclass(frozen=True, slots=True)
class CitizenTicketCodeInput:
    code: str

    def __post_init__(self) -> None:
        _text(self.code, "code")
        ensure_length(self.code, 24, "code")
        if _CITIZEN_CODE_PATTERN.fullmatch(self.code) is None:
            raise ValueError("code contains invalid characters")


__all__ = [
    "CitizenHistoryItem", "CitizenHistoryPageInput", "CitizenHistoryPageOutput",
    "CitizenQueryPageInput", "CitizenTicketCodeInput", "CitizenTicketDetailOutput",
    "CitizenTicketListItem", "CitizenTicketPageOutput", "PublicTicketOutput",
]
