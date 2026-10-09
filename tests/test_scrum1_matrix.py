"""Field-level Scrum 1 contract matrix."""

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from typing import get_type_hints

import pytest

from api.contracts import *
from api.enums import ActionName, PriorityName, RoleName, StatusName
from api.errors import ErrorCatalog, ErrorCode


CONTRACT_FIELDS = {
    UserCreateInput: ("first_name", "last_name", "email", "password_hash", "role_id", "active"),
    UserUpdateInput: ("user_id", "first_name", "last_name", "email", "password_hash", "role_id", "active"),
    UserActivationInput: ("user_id", "active"),
    CrewCreateInput: ("name",),
    CrewUpdateInput: ("crew_id", "name"),
    CrewMemberInput: ("user_id", "crew_id"),
    AddressCreateInput: (
        "road_type_code", "road_number", "cross_road_number", "door_plate_number",
        "road_suffix_letter_code", "road_bis_code", "road_bis_suffix", "road_quadrant_code",
        "cross_suffix_letter_code", "cross_bis_code", "cross_bis_suffix", "cross_quadrant_code",
        "neighborhood_id",
    ),
    AddressComponentsInput: (
        "road_type_code", "road_number", "cross_road_number", "door_plate_number",
        "road_suffix_letter_code", "road_bis_code", "road_bis_suffix", "road_quadrant_code",
        "cross_suffix_letter_code", "cross_bis_code", "cross_bis_suffix", "cross_quadrant_code",
        "neighborhood_id",
    ),
    TicketCreateInput: ("code", "reported_by", "failure_type_id", "description", "address_id", "contact_email", "contact_phone"),
    TicketOperationInput: ("ticket_id",),
    TicketAssignmentInput: ("ticket_id", "crew_id"),
    TicketAttentionInput: ("ticket_id", "diagnosis", "solution"),
    TicketClosureReviewInput: ("ticket_id", "decision"),
    EvidenceCreateInput: ("ticket_id", "file_path", "captured_at", "uploaded_by"),
    HistoryEventCreateInput: ("ticket_id", "action_id", "user_id"),
    ActorContext: ("user_id", "role_id", "active"),
    ExecutionContext: ("operation", "correlation_id", "actor"),
    ErrorDetail: ("field", "entity", "reason"),
    ErrorOutput: ("code", "message", "correlation_id", "details"),
}


FIELD_CASES = tuple(
    (f"S1.{contract.__name__}.{field_name}.VALID", contract, field_name)
    for contract, field_names in CONTRACT_FIELDS.items()
    for field_name in field_names
)


@pytest.mark.parametrize("case_id, contract, field_name", FIELD_CASES, ids=[case[0] for case in FIELD_CASES])
def test_each_contract_field_is_declared_with_a_type(case_id, contract, field_name):
    assert is_dataclass(contract), case_id
    assert field_name in {field.name for field in fields(contract)}, case_id
    assert field_name in get_type_hints(contract), case_id


@pytest.mark.parametrize(
    "enum_type, value",
    [(enum_type, member.value) for enum_type in (RoleName, PriorityName, StatusName, ActionName) for member in enum_type],
    ids=[f"{enum_type.__name__}.{value}" for enum_type, value in [(enum_type, member.value) for enum_type in (RoleName, PriorityName, StatusName, ActionName) for member in enum_type]],
)
def test_enum_sql_round_trip_is_individual(enum_type, value):
    assert enum_type.from_sql(value).to_sql() == value


@pytest.mark.parametrize("code", tuple(ErrorCode), ids=lambda code: f"S3-{code.name}")
def test_every_error_code_has_one_catalog_message(code):
    definition = ErrorCatalog.get(code)
    assert definition.code is code
    assert definition.message
    assert definition.category


def test_contract_edge_cases_are_preserved():
    assert UserCreateInput("A", "B", "a@example.test", "hash", 1, False).active is False
    assert UserUpdateInput(1).email is UNSET
    assert UserUpdateInput(1, email=None).email is None
    assert TicketClosureReviewInput(1, "Approval").decision == "Approval"
    assert TicketClosureReviewInput(1, "Rejection").decision == "Rejection"
    assert HistoryEventOutput(2**40, 1, None, 1, datetime.now(timezone.utc)).id == 2**40
