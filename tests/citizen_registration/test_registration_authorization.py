"""Registration authorization policy checks."""

from __future__ import annotations

from api.contracts import ActorContext, CitizenRegistrationInput, UserOutput
from api.enums import RoleName
from api.middleware.operation_policies import OPERATION_POLICIES
from api.security.citizen_authorization import RolePermissionChecker, role_operation_authorizer


def test_registration_policy_allows_no_actor_and_requires_the_public_contract() -> None:
    policy = OPERATION_POLICIES["UserService.register_citizen"]

    assert policy.actor_required is False
    assert policy.permission is None
    assert policy.input_types == (CitizenRegistrationInput,)


def test_administrative_user_creation_remains_protected() -> None:
    policy = OPERATION_POLICIES["UserService.create"]

    assert policy.actor_required is True
    assert policy.permission == "manage_users"


def _actor(role_name: str) -> ActorContext:
    return ActorContext(
        user_id=11,
        role_id=2,
        active=True,
        public_user=UserOutput(11, "Test", "User", "test@example.com", 2, True, role_name),
    )


def test_legacy_sensitive_reads_require_explicit_operational_permission_and_internal_role() -> None:
    checker = RolePermissionChecker()
    operation = "TicketService.get_by_code"
    for role in (RoleName.OPERATOR, RoleName.COORDINATOR, RoleName.CREW, RoleName.ADMIN):
        assert checker.is_allowed(_actor(role.value), "operational_ticket_read", operation)
    assert not checker.is_allowed(_actor(RoleName.CITIZEN.value), "operational_ticket_read", operation)
    assert not checker.is_allowed(_actor(RoleName.CITIZEN.value), "execute", operation)


def test_public_ticket_lookup_does_not_resolve_incidental_access_tokens() -> None:
    policy = OPERATION_POLICIES["TicketService.get_public_report"]
    assert policy.resolve_actor is False
    assert not role_operation_authorizer(
        type("Context", (), {"actor": _actor(RoleName.CITIZEN.value)})(),
        "TicketService.get_by_code",
    )
