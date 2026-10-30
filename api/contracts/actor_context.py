"""Authenticated actor contract."""

from __future__ import annotations

from dataclasses import dataclass, field

from .users.user_types import UserOutput


@dataclass(frozen=True)
class ActorContext:
    user_id: int
    role_id: int
    active: bool
    public_user: UserOutput | None = field(default=None, repr=False)
