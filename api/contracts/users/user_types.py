"""User contracts."""

from __future__ import annotations

from dataclasses import dataclass

from ..common_types import UNSET, Unset


@dataclass(frozen=True)
class UserCreateInput:
    first_name: str
    last_name: str
    email: str
    password_hash: str
    role_id: int
    active: bool = True


@dataclass(frozen=True)
class UserUpdateInput:
    user_id: int
    first_name: str | Unset = UNSET
    last_name: str | Unset = UNSET
    email: str | Unset = UNSET
    password_hash: str | Unset = UNSET
    role_id: int | Unset = UNSET
    active: bool | Unset = UNSET


@dataclass(frozen=True)
class UserActivationInput:
    user_id: int
    active: bool


@dataclass(frozen=True)
class UserOutput:
    id: int
    first_name: str
    last_name: str
    email: str
    role_id: int
    active: bool
