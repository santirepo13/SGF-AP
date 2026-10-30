"""Automated unit coverage for the citizen-registration API components."""

from __future__ import annotations

from dataclasses import fields

import pytest

from api.contracts import CitizenRegistrationInput, ExecutionContext
from api.errors import ErrorCode
from api.models import Role, User
from api.services.base import TransactionCoordinator
from api.services.users.user_service import UserService
from api.services.users.user_validation import validate_email, validate_name, validate_password


class RecordingUsers:
    def __init__(self) -> None:
        self.records = []

    def create(self, data):
        self.records.append(data)
        return User(19, data.first_name, data.last_name, data.email, data.password_hash, data.role_id, data.active)


class CitizenRoles:
    def __init__(self, role: Role | None = None) -> None:
        self.role = role or Role(7, "Citizen")
        self.names: list[str] = []

    def get_by_name(self, name: str):
        self.names.append(name)
        return self.role


class RecordingTransaction(TransactionCoordinator):
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FixedHasher:
    def __init__(self, value: str = "$argon2id$test") -> None:
        self.value = value
        self.passwords: list[str] = []

    def hash(self, password: str) -> str:
        self.passwords.append(password)
        return self.value


def _valid_input(**overrides: str) -> CitizenRegistrationInput:
    values = {
        "first_name": "José María",
        "last_name": "O’Neill-Suárez",
        "email": "Citizen@example.test",
        "password": " exact Password ",
    }
    values.update(overrides)
    return CitizenRegistrationInput(**values)


def test_registration_input_is_frozen_and_hides_password() -> None:
    data = _valid_input()

    assert {item.name for item in fields(CitizenRegistrationInput)} == {"first_name", "last_name", "email", "password"}
    assert "exact Password" not in repr(data)
    with pytest.raises(Exception):
        data.email = "other@example.test"  # type: ignore[misc]


def test_registration_validation_rejects_whitespace_only_names_as_required() -> None:
    with pytest.raises(Exception) as raised:
        validate_name("   ", "first_name", correlation_id="corr-validation")

    assert raised.value.code is ErrorCode.REQUIRED_FIELD_MISSING
    assert raised.value.correlation_id == "corr-validation"


def test_registration_validation_rejects_invalid_name_characters() -> None:
    with pytest.raises(Exception) as raised:
        validate_name("A1", "first_name", correlation_id="corr-validation")

    assert raised.value.code is ErrorCode.INVALID_VALUE
    assert raised.value.correlation_id == "corr-validation"


def test_registration_validation_rejects_invalid_email_format() -> None:
    with pytest.raises(Exception) as raised:
        validate_email("not-an-email", correlation_id="corr-validation")

    assert raised.value.code is ErrorCode.INVALID_VALUE
    assert raised.value.correlation_id == "corr-validation"


def test_registration_validation_rejects_an_empty_password() -> None:
    with pytest.raises(Exception) as raised:
        validate_password("", correlation_id="corr-validation")

    assert raised.value.code is ErrorCode.REQUIRED_FIELD_MISSING
    assert raised.value.correlation_id == "corr-validation"


def test_register_citizen_creates_an_active_citizen_after_hashing() -> None:
    users = RecordingUsers()
    roles = CitizenRoles(Role(31, "Citizen"))
    transaction = RecordingTransaction()
    hasher = FixedHasher()
    service = UserService(users, roles, password_hasher=hasher, transaction=transaction)

    result = service.register_citizen(
        ExecutionContext("UserService.register_citizen", "corr-register"),
        _valid_input(),
    )

    assert result.success is True
    assert result.data is not None and result.data.role_id == 31 and result.data.active is True
    assert roles.names == ["Citizen"]
    assert hasher.passwords == [" exact Password "]
    assert users.records[0].password_hash == "$argon2id$test"
    assert users.records[0].active is True
    assert transaction.commits == 1
    assert transaction.rollbacks == 0


def test_register_citizen_without_the_catalogue_role_does_not_write() -> None:
    users = RecordingUsers()
    roles = CitizenRoles(None)
    roles.role = None
    transaction = RecordingTransaction()
    service = UserService(users, roles, password_hasher=FixedHasher(), transaction=transaction)

    result = service.register_citizen(
        ExecutionContext("UserService.register_citizen", "corr-role"),
        _valid_input(),
    )

    assert result.success is False
    assert result.error is not None and result.error.code == ErrorCode.CATALOG_VALUE_UNAVAILABLE.value
    assert users.records == []
    assert transaction.commits == 0
    assert transaction.rollbacks == 1


def test_registration_policy_accepts_an_anonymous_actor() -> None:
    from api.middleware.operation_policies import OPERATION_POLICIES

    policy = OPERATION_POLICIES["UserService.register_citizen"]
    assert policy.actor_required is False
    assert policy.permission is None
    assert policy.input_types == (CitizenRegistrationInput,)
