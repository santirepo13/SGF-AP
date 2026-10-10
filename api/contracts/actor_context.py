"""Authenticated actor contract."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ActorContext:
    user_id: int
    role_id: int
    active: bool
