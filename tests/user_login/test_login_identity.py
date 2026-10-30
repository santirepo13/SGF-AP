"""Request identity and login-policy coverage."""

from __future__ import annotations

from datetime import datetime, timezone

from api.contracts import ValidatedAccessToken
from api.errors import ApplicationError, ErrorCode
from api.middleware import AuthorizationMiddleware
from api.middleware.base import MiddlewareRequest
from api.middleware.operation_policies import OPERATION_POLICIES
from api.models import Role, User
from api.security.identity_provider import TokenIdentityProvider


class Tokens:
    def validate(self, token: str) -> ValidatedAccessToken:
        return ValidatedAccessToken(8, "token-id", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, 1, tzinfo=timezone.utc))


class Users:
    def get_by_id(self, user_id: int):
        return User(user_id, "Ana", "Gómez", "ana@example.test", "$argon2id$hash", 2, True)


class Roles:
    def get_by_id(self, role_id: int):
        return Role(role_id, "Operator")


def test_login_policy_ignores_an_existing_access_token() -> None:
    policy = OPERATION_POLICIES["UserService.login"]

    assert policy.actor_required is False
    assert policy.resolve_actor is False


def test_token_identity_provider_uses_current_user_and_role_records() -> None:
    actor = TokenIdentityProvider("opaque", Tokens(), Users(), Roles(), correlation_id="identity").resolve()

    assert actor is not None
    assert actor.user_id == 8
    assert actor.role_id == 2
    assert actor.active is True


def test_authorization_requires_an_access_token_for_protected_operations() -> None:
    from api.contracts import ExecutionContext

    request = MiddlewareRequest(
        "UserService",
        "create",
        object(),
        context=ExecutionContext("UserService.create", "auth", None),
        operation="UserService.create",
    )
    middleware = AuthorizationMiddleware()

    try:
        middleware.process(request, lambda value: value)
    except ApplicationError as error:
        assert error.code is ErrorCode.ACCESS_TOKEN_REQUIRED
    else:
        raise AssertionError("the protected operation unexpectedly continued")
