from datetime import datetime, timezone
from types import SimpleNamespace

from api.contracts import ActorContext, ExecutionContext, UserFilters
from api.models import User
from api.services.users.user_service import UserService


class Users:
    def __init__(self, value): self.value = value
    def get_by_id(self, user_id): return self.value
    def get_by_email(self, email): return self.value
    def list_by_filters(self, filters=None): return [self.value]


class Roles:
    def get_by_id(self, role_id): return SimpleNamespace(id=role_id, name="Citizen")


def test_user_service_uses_injected_repository_and_excludes_password_hash():
    user = User(1, "Ada", "Lovelace", "ada@example.com", "secret-hash", 2, False)
    service = UserService(Users(user), Roles())
    result = service.get_by_id(ExecutionContext("get_user", "corr-1"), 1)

    assert result.success
    assert result.data.email == "ada@example.com"
    assert result.data.active is False
    assert not hasattr(result.data, "password_hash")
