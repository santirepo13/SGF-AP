"""Service-level transaction checks for citizen registration."""

from __future__ import annotations

from api.contracts import CitizenRegistrationInput, ExecutionContext
from api.models import Role, User
from api.services.users.user_service import UserService


class Users:
    def __init__(self) -> None:
        self.data = None

    def create(self, data):
        self.data = data
        return User(9, data.first_name, data.last_name, data.email, data.password_hash, data.role_id, data.active)


class Roles:
    def get_by_name(self, name: str):
        return Role(25, name)


class Hashes:
    def hash(self, password: str) -> str:
        return "$argon2id$fixed"


class Transaction:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_registration_service_commits_only_after_a_complete_public_result() -> None:
    users = Users()
    transaction = Transaction()
    service = UserService(users, Roles(), password_hasher=Hashes(), transaction=transaction)

    result = service.register_citizen(
        ExecutionContext("UserService.register_citizen", "corr-service"),
        CitizenRegistrationInput("Ana", "Gómez", "ana@example.test", " exact password "),
    )

    assert result.success is True
    assert result.data is not None
    assert not hasattr(result.data, "password_hash")
    assert users.data is not None
    assert users.data.role_id == 25
    assert users.data.active is True
    assert transaction.commits == 1
    assert transaction.rollbacks == 0
