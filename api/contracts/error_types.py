"""Controlled error contracts."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ErrorDetail:
    field: str | None
    entity: str | None
    reason: str


@dataclass(frozen=True)
class ErrorOutput:
    code: str
    message: str
    correlation_id: str
    details: tuple[ErrorDetail, ...] = field(default_factory=tuple)
