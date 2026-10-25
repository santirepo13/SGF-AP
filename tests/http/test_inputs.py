"""Scrum 2 unit coverage for HTTP input adaptation."""

from __future__ import annotations

from datetime import datetime

import pytest

from api.contracts import EvidenceCreateInput, TicketAttentionInput, UNSET, UserCreateInput, UserUpdateInput
from api.errors import ApplicationError, ErrorCode
from api.http.inputs import build_contract


def test_path_values_and_explicit_false_build_a_partial_update_without_losing_unset() -> None:
    data = build_contract(
        UserUpdateInput,
        {"active": False},
        path_values={"user_id": "7"},
        correlation_id="corr-input",
    )

    assert data.user_id == 7
    assert data.active is False
    assert data.first_name is UNSET
    assert data.email is UNSET


def test_explicit_null_is_preserved_while_an_omitted_ticket_field_remains_unset() -> None:
    data = build_contract(
        TicketAttentionInput,
        {"diagnosis": None},
        path_values={"ticket_id": "9"},
    )

    assert data.ticket_id == 9
    assert data.diagnosis is None
    assert data.solution is UNSET


def test_contract_defaults_apply_when_optional_json_field_is_omitted() -> None:
    data = build_contract(
        UserCreateInput,
        {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.test",
            "password_hash": "server-side-hash",
            "role_id": 2,
        },
    )

    assert data.active is True


def test_required_contract_field_is_a_central_required_field_error() -> None:
    with pytest.raises(ApplicationError) as raised:
        build_contract(UserCreateInput, {"first_name": "Ada"}, correlation_id="corr-required")

    assert raised.value.code is ErrorCode.REQUIRED_FIELD_MISSING
    assert raised.value.correlation_id == "corr-required"


@pytest.mark.parametrize("payload", [{"unexpected": "field"}, {"active": "false"}])
def test_unknown_or_json_type_incompatible_fields_are_central_invalid_value_errors(payload) -> None:
    with pytest.raises(ApplicationError) as raised:
        build_contract(UserUpdateInput, payload, path_values={"user_id": "1"})

    assert raised.value.code is ErrorCode.INVALID_VALUE


def test_aware_iso_datetime_is_converted_for_contracts_that_require_timezone() -> None:
    data = build_contract(
        EvidenceCreateInput,
        {
            "ticket_id": 1,
            "file_path": "remote/evidence.jpg",
            "captured_at": "2026-10-24T10:15:00-05:00",
            "uploaded_by": 3,
        },
    )

    assert isinstance(data.captured_at, datetime)
    assert data.captured_at.utcoffset() is not None


def test_naive_datetime_is_translated_to_invalid_value() -> None:
    with pytest.raises(ApplicationError) as raised:
        build_contract(
            EvidenceCreateInput,
            {
                "ticket_id": 1,
                "file_path": "remote/evidence.jpg",
                "captured_at": "2026-10-24T10:15:00",
                "uploaded_by": 3,
            },
        )

    assert raised.value.code is ErrorCode.INVALID_VALUE
