"""Scrum 2 unit coverage for public HTTP response serialization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json

from api.contracts import ErrorOutput, OperationResult
from api.http.responses import operation_response, to_json_value


class State(str, Enum):
    ACTIVE = "Active"


@dataclass(frozen=True)
class PublicValue:
    state: State
    observed_at: datetime
    enabled: bool


def response_payload(response) -> dict:
    return json.loads(response.body)


def test_serializer_preserves_dataclasses_enums_dates_false_none_and_empty_lists() -> None:
    value = PublicValue(State.ACTIVE, datetime(2026, 10, 24, tzinfo=timezone.utc), False)

    assert to_json_value({"value": value, "none": None, "items": []}) == {
        "value": {"state": "Active", "observed_at": "2026-10-24T00:00:00+00:00", "enabled": False},
        "none": None,
        "items": [],
    }


def test_success_response_uses_explicit_status_and_preserves_false_data() -> None:
    response = operation_response(OperationResult.ok(False), success_status=201)

    assert response.status_code == 201
    assert response_payload(response) == {"success": True, "data": False, "error": None}


def test_failure_response_uses_mapped_status_and_public_error_only() -> None:
    response = operation_response(
        OperationResult.fail(ErrorOutput("REL-001", "Referencia inválida", "corr-http")),
    )

    assert response.status_code == 422
    assert response_payload(response) == {
        "success": False,
        "data": None,
        "error": {
            "code": "REL-001",
            "message": "Referencia inválida",
            "correlation_id": "corr-http",
            "details": [],
        },
    }
