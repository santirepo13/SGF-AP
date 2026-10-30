"""User persistence model."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class User:
    id: int
    first_name: str
    last_name: str
    email: str
    password_hash: str = field(repr=False)
    role_id: int
    active: bool
    auth_version: int = 1
