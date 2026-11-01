"""Role and ownership checks shared by citizen-facing service operations."""

from __future__ import annotations

from collections.abc import Callable

from api.contracts import ExecutionContext
from api.enums import RoleName
from api.errors import ApplicationError

from .identity_provider import role_name_for

CITIZEN_REPORT_OPERATIONS = frozenset(
    {
        "TicketService.register_citizen",
        "TicketService.find_citizen_matches",
        "TicketService.get_citizen_attempt",
    }
)

_CITIZEN_PERMISSIONS = frozenset(
    {
        "create_address",
        "citizen_report_create",
        "citizen_report_read",
        "citizen_evidence_manage",
        "citizen_preferences_manage",
    }
)

_OPERATIONAL_PERMISSIONS = frozenset(
    {
        "create_address",
        "create_ticket",
        "process_tickets",
        "manage_users",
        "manage_crews",
        "create_evidence",
        "create_history_event",
        "operational_ticket_read",
    }
)


class RolePermissionChecker:
    """Resolve citizen permissions from the token role and retain explicit internal fallback."""

    def __init__(self, fallback: object | None = None) -> None:
        self._fallback = fallback

    def is_allowed(self, actor: object, permission: str, operation: str) -> bool:
        role_name = _actor_role_name(actor)
        if role_name == RoleName.CITIZEN.value:
            return permission in _CITIZEN_PERMISSIONS
        if role_name in {RoleName.OPERATOR.value, RoleName.COORDINATOR.value, RoleName.CREW.value}:
            return permission in _OPERATIONAL_PERMISSIONS
        if role_name == RoleName.ADMIN.value:
            return permission in _OPERATIONAL_PERMISSIONS
        fallback = getattr(self._fallback, "is_allowed", None)
        return bool(fallback(actor, permission, operation)) if callable(fallback) else False


class CitizenAuthorizer:
    """Require a current active Citizen independently of HTTP middleware."""

    def require_citizen(
        self,
        context: ExecutionContext,
        *,
        user: object,
        role: object,
    ) -> None:
        actor = context.actor
        if actor is None:
            raise ApplicationError.access_token_required(correlation_id=context.correlation_id)
        if not actor.active or not getattr(user, "active", False):
            raise ApplicationError.inactive_user(correlation_id=context.correlation_id)
        if getattr(user, "id", None) != actor.user_id or getattr(user, "role_id", None) != actor.role_id:
            raise ApplicationError.invalid_access_token(correlation_id=context.correlation_id)
        if role_name_for(role) != RoleName.CITIZEN.value:
            raise ApplicationError.forbidden(context.operation, correlation_id=context.correlation_id)


def role_operation_authorizer(context: ExecutionContext, operation: str) -> bool:
    """Prevent a Citizen from reaching a legacy internal service operation directly."""

    actor = context.actor
    if actor is None:
        return True
    role_name = _actor_role_name(actor)
    if role_name == RoleName.CITIZEN.value:
        return operation in CITIZEN_REPORT_OPERATIONS or operation == "AddressService.create_or_reuse"
    return True


def _actor_role_name(actor: object) -> str | None:
    public_user = getattr(actor, "public_user", None)
    value = getattr(public_user, "role_name", None)
    return value if type(value) is str else None


__all__ = [
    "CITIZEN_REPORT_OPERATIONS",
    "CitizenAuthorizer",
    "RolePermissionChecker",
    "role_operation_authorizer",
]
