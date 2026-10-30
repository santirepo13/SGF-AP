"""Resolve one trusted actor from a validated user access credential."""

from __future__ import annotations

from api.contracts import ActorContext
from api.enums import RoleName
from api.errors import ApplicationError
from api.interfaces.repositories import RoleRepositoryInterface, UserRepositoryInterface
from api.interfaces.security import AccessTokenProviderInterface

_SUPPORTED_ROLE_NAMES = frozenset(role.value for role in RoleName)


class TokenIdentityProvider:
    """Request-scoped identity resolver backed by current server records."""

    def __init__(
        self,
        access_token: str | None,
        access_tokens: AccessTokenProviderInterface,
        users: UserRepositoryInterface,
        roles: RoleRepositoryInterface,
        *,
        correlation_id: str | None = None,
    ) -> None:
        self._access_token = access_token
        self._access_tokens = access_tokens
        self._users = users
        self._roles = roles
        self._correlation_id = correlation_id

    def resolve(self) -> ActorContext | None:
        if self._access_token is None:
            return None
        validated = self._access_tokens.validate(self._access_token)
        user = self._users.get_by_id(validated.user_id)
        if user is None or getattr(user, "id", None) != validated.user_id:
            raise ApplicationError.invalid_access_token(correlation_id=self._correlation_id)
        role = self._roles.get_by_id(user.role_id)
        role_name = _role_name(role)
        if role_name is None or getattr(role, "id", None) != user.role_id:
            raise ApplicationError.catalog_unavailable("role", correlation_id=self._correlation_id)
        return ActorContext(user_id=user.id, role_id=user.role_id, active=user.active)


def role_name_for(role: object) -> str | None:
    """Return one of the server-approved role names, or ``None`` otherwise."""

    return _role_name(role)


def _role_name(role: object) -> str | None:
    if role is None:
        return None
    value = getattr(role, "name", None)
    if isinstance(value, RoleName):
        value = value.value
    if type(value) is not str or value not in _SUPPORTED_ROLE_NAMES:
        return None
    return value


__all__ = ["TokenIdentityProvider", "role_name_for"]
