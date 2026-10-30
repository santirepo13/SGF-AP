"""User contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..common_types import UNSET, Unset


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
    id: int
    first_name: str
    last_name: str
    email: str
    role_id: int
    active: bool
