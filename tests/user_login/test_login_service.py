"""Authentication sequence and safe rejection behavior for UserService.login."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from api.contracts import ExecutionContext, IssuedAccessToken, UserLoginInput
from api.errors import ErrorCode
from api.models import Role, User
from api.services.users.user_service import UserService


class Users:
    def __init__(self, user: User | None) -> None:
        self.user = user
        self.queries: list[str] = []

    def get_by_email(self, email: str) -> User | None:
        self.queries.append(email)
        return self.user


class Roles:
    def __init__(self, role: Role | None) -> None:
        self.role = role

    def get_by_id(self, role_id: int) -> Role | None:
        return self.role


class Verifier:
    def __init__(self, matches: bool) -> None:
        self.matches = matches
        self.calls: list[tuple[str, str]] = []

    def verify_password(self, password_hash: str, password: str) -> bool:
        self.calls.append((password_hash, password))
        return self.matches


class Tokens:
    def __init__(self) -> None:
        self.issued: list[int] = []

    def issue(self, user_id: int) -> IssuedAccessToken:
        self.issued.append(user_id)
        return IssuedAccessToken("opaque-token", datetime.now(timezone.utc) + timedelta(hours=1))


def _context() -> ExecutionContext:
    return ExecutionContext("UserService.login", "login-service")


def _user(*, active: bool = True) -> User:
    return User(9, "Ana", "Gómez", "ana@example.test", "$argon2id$hash", 4, active)


@pytest.mark.parametrize("role_name", ("Citizen", "Operator", "Coordinator", "Crew", "Admin"))
def test_login_issues_complete_output_for_each_supported_role(role_name: str) -> None:
    tokens = Tokens()
    service = UserService(Users(_user()), Roles(Role(4, role_name)), Verifier(True), tokens)

    result = service.login(_context(), UserLoginInput("ana@example.test", " exact Password "))

    assert result.success is True
    assert result.data is not None
    assert result.data.user.role_name == role_name
    assert result.data.access_token == "opaque-token"
    assert tokens.issued == [9]


def test_login_uses_the_same_generic_error_for_absent_user_and_wrong_password() -> None:
    absent = UserService(Users(None), Roles(Role(4, "Citizen")), Verifier(True), Tokens())
    wrong = UserService(Users(_user()), Roles(Role(4, "Citizen")), Verifier(False), Tokens())

    absent_result = absent.login(_context(), UserLoginInput("ana@example.test", "wrong"))
    wrong_result = wrong.login(_context(), UserLoginInput("ana@example.test", "wrong"))

    assert absent_result.error is not None and absent_result.error.code == ErrorCode.INVALID_CREDENTIALS.value
    assert wrong_result.error is not None and wrong_result.error.code == ErrorCode.INVALID_CREDENTIALS.value
    assert absent_result.error.message == wrong_result.error.message


def test_login_checks_password_before_reporting_an_inactive_account() -> None:
    inactive_user = _user(active=False)
    wrong = UserService(Users(inactive_user), Roles(Role(4, "Citizen")), Verifier(False), Tokens())
    correct = UserService(Users(inactive_user), Roles(Role(4, "Citizen")), Verifier(True), Tokens())

    wrong_result = wrong.login(_context(), UserLoginInput("ana@example.test", "wrong"))
    correct_result = correct.login(_context(), UserLoginInput("ana@example.test", "right"))

    assert wrong_result.error is not None and wrong_result.error.code == ErrorCode.INVALID_CREDENTIALS.value
    assert correct_result.error is not None and correct_result.error.code == ErrorCode.INACTIVE_USER.value
