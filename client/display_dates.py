"""Centralized timezone-aware date presentation for the client."""

from __future__ import annotations

from datetime import datetime
import re
from zoneinfo import ZoneInfo

_COLOMBIA = ZoneInfo("America/Bogota")
_ISO_WITH_ZONE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$"
)


def parse_display_date(value: object) -> datetime:
    if not isinstance(value, str) or _ISO_WITH_ZONE.fullmatch(value) is None:
        raise ValueError("date must be an ISO 8601 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("date must include timezone information")
    return parsed.astimezone(_COLOMBIA)


def format_display_date(value: object) -> str:
    return parse_display_date(value).strftime("%d/%m/%Y %H:%M")


__all__ = ["format_display_date", "parse_display_date"]
