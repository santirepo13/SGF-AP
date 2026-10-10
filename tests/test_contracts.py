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
    user = UserCreateInput("Ana", "Gómez", "ana@example.test", "hash", 1)
    assert user.active is True

def test_user_output_excludes_password_hash() -> None:
    assert "password_hash" not in {field.name for field in fields(UserOutput)}

def test_partial_updates_distinguish_unset_from_none() -> None:
    update = UserUpdateInput(user_id=4, email=None)
    assert update.first_name is UNSET
    assert update.email is None

def test_nullable_address_components_default_to_none() -> None:
    address = AddressCreateInput("CL", 10, 20, 30)
    assert address.neighborhood_id is None
    assert address.road_bis_code is None

def test_address_sql_ranges_are_enforced() -> None:
    with pytest.raises(ValueError):
        AddressCreateInput("CL", 0, 20, 30)
    with pytest.raises(ValueError):
        AddressCreateInput("CL", 10, 20, 10000)

def test_persisted_datetime_requires_timezone() -> None:
    kwargs = dict(id=1, road_type_code="CL", road_number=10, cross_road_number=20, door_plate_number=30)
    with pytest.raises(ValueError):
        AddressOutput(created_at=datetime.now(), **kwargs)
    AddressOutput(created_at=datetime.now(timezone.utc), **kwargs)

def test_ticket_attention_supports_unset_and_none() -> None:
    assert TicketAttentionInput(1).diagnosis is UNSET
    assert TicketAttentionInput(1, diagnosis=None).diagnosis is None

def test_ticket_code_sql_length_is_enforced() -> None:
    with pytest.raises(ValueError):
        TicketCreateInput("x" * 25, 1, 1, "description")

def test_operation_result_invariants() -> None:
    assert OperationResult.ok([]).success is True
    assert OperationResult.ok().data is None
    error = ErrorOutput("NOT_FOUND", "No existe", correlation_id="corr-1")
    failed = OperationResult.fail(error)
    assert failed.success is False
    assert failed.error is error
    with pytest.raises(ValueError):
        OperationResult(success=False)

def test_catalog_sql_checks_are_represented() -> None:
    assert RoleOutput(1, "Citizen").name == "Citizen"
    assert PriorityOutput(1, "High").name == "High"
    with pytest.raises(ValueError):
        RoleOutput(1, "Unknown")
    with pytest.raises(ValueError):
        ActionOutput(1, "Unknown")

def test_actor_policy_is_explicit() -> None:
    assert "register_ticket" in ACTOR_REQUIRED_OPERATIONS
    assert requires_actor("register_ticket") is True
    assert requires_actor("lookup_ticket") is False
    with pytest.raises(ValueError):
        validate_actor_context(ExecutionContext("register_ticket", "corr-1"))
    context = ExecutionContext("register_ticket", "corr-1", ActorContext(1, 2, True))
    assert validate_actor_context(context) is context

def test_catalog_lookup_uses_typed_identifier() -> None:
    assert RoleLookupInput(7).role_id == 7
