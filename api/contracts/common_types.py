"""Common types and SQL-aligned validation helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Final, TypeAlias


class _UnsetType:
    """Sentinel used when a partial update did not supply a field."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = _UnsetType()
Unset: TypeAlias = _UnsetType
AwareDateTime: TypeAlias = datetime


def ensure_aware(value: datetime, field_name: str = "datetime") -> datetime:
    """Return an aware datetime or raise a contract validation error."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")
    return value


def ensure_length(value: str, maximum: int, field_name: str) -> str:
    if len(value) > maximum:
        raise ValueError(f"{field_name} must have at most {maximum} characters")
    return value


def ensure_range(value: int, minimum: int, maximum: int, field_name: str) -> int:
    if not minimum <= value <= maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
    return value


def ensure_uppercase_letter(value: str | None, field_name: str) -> str | None:
    if value is not None and (len(value) != 1 or not value.isupper() or not value.isalpha()):
        raise ValueError(f"{field_name} must be one uppercase letter")
    return value


def ensure_choice(value: str, choices: tuple[str, ...], field_name: str) -> str:
    if value not in choices:
        allowed = ", ".join(choices)
        raise ValueError(f"{field_name} must be one of: {allowed}")
    return value
