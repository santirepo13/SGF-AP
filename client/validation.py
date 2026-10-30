"""Shared local validators for client account forms."""

from __future__ import annotations

import re


EMAIL_PATTERN = re.compile(
    r"^[^\s@]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$"
)


__all__ = ["EMAIL_PATTERN"]
