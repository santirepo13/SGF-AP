"""User persistence model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    first_name: str
    last_name: str
    email: str
    password_hash: str
    role_id: int
    active: bool
