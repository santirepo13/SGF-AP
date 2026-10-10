"""Input/output contracts and meaningful value-preservation checks."""

if __name__ == "__main__":
    # Direct execution hands this file to pytest so its fixtures and assertions run.
    import sys
    from pathlib import Path
    import pytest

    project_root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pytest.ini").is_file())
    sys.path.insert(0, str(project_root))
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))

from datetime import datetime, timezone
from dataclasses import fields

import pytest

from api.contracts import (
    ACTOR_REQUIRED_OPERATIONS,
    AddressCreateInput,
    AddressOutput,
    ActionOutput,
    ActorContext,
    ExecutionContext,
    ErrorOutput,
    HistoryEventOutput,
    TicketClosureReviewInput,
    PriorityOutput,
    RoleLookupInput,
    RoleOutput,
    OperationResult,
    TicketAttentionInput,
    TicketCreateInput,
    UNSET,
    UserCreateInput,
    UserOutput,
    UserUpdateInput,
    requires_actor,
    validate_actor_context,
)


def test_user_create_applies_sql_default_for_active() -> None:
    """Creating a user without an active flag keeps the database's active default."""
    user = UserCreateInput("Ana", "Gómez", "ana@example.test", "hash", 1)
    assert user.active is True

def test_user_output_excludes_password_hash() -> None:
    """Public user output must not contain the stored password hash."""
    assert "password_hash" not in {field.name for field in fields(UserOutput)}

def test_partial_updates_distinguish_unset_from_none() -> None:
    """An omitted update field differs from an explicitly cleared field."""
    update = UserUpdateInput(user_id=4, email=None)
    assert update.first_name is UNSET
    assert update.email is None

def test_nullable_address_components_default_to_none() -> None:
    """Optional address pieces remain absent when the caller omits them."""
    address = AddressCreateInput("CL", 10, 20, 30)
    assert address.neighborhood_id is None
    assert address.road_bis_code is None

def test_address_sql_ranges_are_enforced() -> None:
    """Reject address numbers outside the allowed database ranges."""
    with pytest.raises(ValueError):
        AddressCreateInput("CL", 0, 20, 30)
    with pytest.raises(ValueError):
        AddressCreateInput("CL", 10, 20, 10000)

def test_persisted_datetime_requires_timezone() -> None:
    """Reject timezone-free stored dates while accepting timezone-aware ones."""
    kwargs = dict(id=1, road_type_code="CL", road_number=10, cross_road_number=20, door_plate_number=30)
    with pytest.raises(ValueError):
        AddressOutput(created_at=datetime.now(), **kwargs)
    AddressOutput(created_at=datetime.now(timezone.utc), **kwargs)

def test_ticket_attention_supports_unset_and_none() -> None:
    """Distinguish an unchanged diagnosis from a diagnosis explicitly cleared."""
    assert TicketAttentionInput(1).diagnosis is UNSET
    assert TicketAttentionInput(1, diagnosis=None).diagnosis is None

def test_ticket_code_sql_length_is_enforced() -> None:
    """Reject a ticket code longer than its database column permits."""
    with pytest.raises(ValueError):
        TicketCreateInput("x" * 25, 1, 1, "description")

def test_operation_result_invariants() -> None:
    """Keep success data and failure errors consistent across result objects."""
    assert OperationResult.ok([]).success is True
    assert OperationResult.ok().data is None
    error = ErrorOutput("NOT_FOUND", "No existe", correlation_id="corr-1")
    failed = OperationResult.fail(error)
    assert failed.success is False
    assert failed.error is error
    with pytest.raises(ValueError):
        OperationResult(success=False)

def test_catalog_sql_checks_are_represented() -> None:
    """Accept known catalogue names and reject names absent from the catalogue."""
    assert RoleOutput(1, "Citizen").name == "Citizen"
    assert PriorityOutput(1, "High").name == "High"
    with pytest.raises(ValueError):
        RoleOutput(1, "Unknown")
    with pytest.raises(ValueError):
        ActionOutput(1, "Unknown")

def test_actor_policy_is_explicit() -> None:
    """Require an actor for ticket registration but not for public lookup."""
    assert "register_ticket" in ACTOR_REQUIRED_OPERATIONS
    assert requires_actor("register_ticket") is True
    assert requires_actor("lookup_ticket") is False
    with pytest.raises(ValueError):
        validate_actor_context(ExecutionContext("register_ticket", "corr-1"))
    context = ExecutionContext("register_ticket", "corr-1", ActorContext(1, 2, True))
    assert validate_actor_context(context) is context

def test_catalog_lookup_uses_typed_identifier() -> None:
    """Keep the requested role identifier in the catalogue lookup input."""
    assert RoleLookupInput(7).role_id == 7


def test_contract_edge_cases_are_preserved():
    """Preserve explicit false, cleared values, closure decisions, and large IDs."""
    assert UserCreateInput("A", "B", "a@example.test", "hash", 1, False).active is False
    assert UserUpdateInput(1).email is UNSET
    assert UserUpdateInput(1, email=None).email is None
    assert TicketClosureReviewInput(1, "Approval").decision == "Approval"
    assert TicketClosureReviewInput(1, "Rejection").decision == "Rejection"
    assert HistoryEventOutput(2**40, 1, None, 1, datetime.now(timezone.utc)).id == 2**40
