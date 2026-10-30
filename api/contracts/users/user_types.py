"""User contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..common_types import UNSET, Unset, ensure_aware


@dataclass(frozen=True)
class CitizenRegistrationInput:
    """Structurally typed public input used to create a citizen account.

    Semantic checks are centralized in ``services.users.registration_validation``
    so the same rules are also applied when the service is called directly.
    The password intentionally has ``repr=False`` so accidental diagnostic
    output cannot include the clear-text value.
    """

    first_name: str
    last_name: str
    email: str
    password: str = field(repr=False)

    def __post_init__(self) -> None:
        for field_name, value in (
            ("first_name", self.first_name),
            ("last_name", self.last_name),
            ("email", self.email),
            ("password", self.password),
        ):
            if type(value) is not str:
                raise ValueError(f"{field_name} must be a string")


@dataclass(frozen=True)
class UserLoginInput:
    """Credentials submitted by a person who wants to enter the application."""

    email: str
    password: str = field(repr=False)

    def __post_init__(self) -> None:
        for field_name, value in (("email", self.email), ("password", self.password)):
            if type(value) is not str:
                raise ValueError(f"{field_name} must be a string")


@dataclass(frozen=True)
class UserCreateInput:
    first_name: str
    last_name: str
    email: str
    password_hash: str = field(repr=False)
    role_id: int
    active: bool = True


@dataclass(frozen=True)
class UserFilters:
    email: str | None = None
    role_id: int | None = None
    active: bool | None = None


@dataclass(frozen=True)
class UserUpdateInput:
    user_id: int
    first_name: str | Unset = UNSET
    last_name: str | Unset = UNSET
    email: str | Unset = UNSET
    password_hash: str | Unset = field(default=UNSET, repr=False)
    role_id: int | Unset = UNSET
    active: bool | Unset = UNSET


@dataclass(frozen=True)
class UserActivationInput:
    user_id: int
    active: bool


@dataclass(frozen=True)
class UserOutput:
    """Public user information.

    ``role_name`` is supplied for authenticated responses so a client can route
    an accepted login without inferring a role from an internal identifier. It
    remains optional for older user lookup and registration operations whose
    repositories do not resolve the role record.
    """

    id: int
    first_name: str
    last_name: str
    email: str
    role_id: int
    active: bool
    role_name: str | None = None


@dataclass(frozen=True)
class UserLoginOutput:
    """Complete, public result of a confirmed login attempt."""

    user: UserOutput
    access_token: str = field(repr=False)
    expires_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.user, UserOutput):
            raise ValueError("user must be a UserOutput")
        if type(self.access_token) is not str or not self.access_token:
            raise ValueError("access_token must be a non-empty string")
        if not isinstance(self.expires_at, datetime):
            raise ValueError("expires_at must be a datetime")
        ensure_aware(self.expires_at, "expires_at")
