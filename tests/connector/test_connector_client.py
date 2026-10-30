"""Unit coverage for the executable local SGF-AP connector."""

from __future__ import annotations

from dataclasses import dataclass
import io
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from config import ConnectorConfig
from test_local_connector import (
    OPERATIONS,
    ConnectorError,
    ConnectorResponseError,
    LocalConnector,
    _decode_response,
    _load_test_plan,
    main,
    parse_arguments,
)


@dataclass
class FakeResponse:
    status: int
    headers: dict[str, str]
    content: bytes

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self.content


class RecordingOpener:
    def __init__(self, response: FakeResponse | BaseException) -> None:
        self.response = response
        self.request = None
        self.timeout = None

    def open(self, request, *, timeout: int):
        self.request = request
        self.timeout = timeout
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


def _success_response(*, status: int = 200) -> FakeResponse:
    return FakeResponse(
        status=status,
        headers={"Content-Type": "application/json", "X-Correlation-ID": "corr-connector"},
        content=b'{"success":true,"data":[],"error":null}',
    )


def test_operations_cover_every_route_group_and_expected_operation_count() -> None:
    assert len(OPERATIONS) == 55
    assert {
        "catalogs.list_municipalities",
        "addresses.create_or_reuse",
        "users.set_active",
        "users.register_citizen",
        "crews.change_crew",
        "tickets.review_closure",
        "evidences.create_metadata",
        "history.list_by_ticket",
    } <= set(OPERATIONS)


def test_full_test_plan_covers_every_registered_operation_without_connecting() -> None:
    plan = _load_test_plan(Path("connector_full_test_plan.json"))

    assert set(step["operation"] for step in plan) == set(OPERATIONS)


def test_connector_encodes_paths_filters_body_and_managed_basic_authentication() -> None:
    opener = RecordingOpener(_success_response())
    connector = LocalConnector(ConnectorConfig("http://api.example", 8002, "connector", "secret"), opener=opener)

    response = connector.execute(
        "tickets.get_by_code",
        path_params={"code": "TCK / 1"},
        params={"active": False, "unused": None},
        headers={"X-Correlation-ID": "corr-request"},
    )

    assert response.status_code == 200
    assert opener.timeout == 10
    assert opener.request.full_url == "http://api.example:8002/tickets/by-code/TCK%20%2F%201?active=false"
    assert opener.request.get_header("Authorization") != "Basic ignored"
    assert opener.request.get_header("Accept") == "application/json"
    assert opener.request.get_header("X-correlation-id") == "corr-request"

    opener = RecordingOpener(_success_response())
    connector = LocalConnector(ConnectorConfig("http://api.example", 8002, "connector", "secret"), opener=opener)
    connector.execute(
        "tickets.attention",
        path_params={"ticket_id": 7},
        body={"diagnosis": None, "solution": "Reparada", "flags": [], "active": False},
    )
    assert json.loads(opener.request.data.decode("utf-8")) == {
        "diagnosis": None,
        "solution": "Reparada",
        "flags": [],
        "active": False,
    }
    assert opener.request.get_header("Content-type") == "application/json"


def test_connector_prevents_additional_headers_from_replacing_authorization() -> None:
    connector = LocalConnector(ConnectorConfig("http://api.example", 8002, "connector", "secret"), opener=RecordingOpener(_success_response()))

    with pytest.raises(ConnectorError, match="Authorization"):
        connector.execute("catalogs.list_roles", headers={"authorization": "Basic replacement"})


def test_connector_preserves_json_error_responses_including_authentication_challenges() -> None:
    error = HTTPError(
        "http://api.example:8002/catalogs/roles",
        401,
        "Unauthorized",
        {"Content-Type": "application/json", "WWW-Authenticate": "Basic"},
        io.BytesIO(
            b'{"success":false,"data":null,"error":{"code":"AUTH-001",'
            b'"message":"Autenticaci\\u00f3n de API requerida o credenciales inv\\u00e1lidas.",'
            b'"correlation_id":"corr-auth","details":[]}}'
        ),
    )
    connector = LocalConnector(ConnectorConfig("http://api.example", 8002, "connector", "secret"), opener=RecordingOpener(error))

    response = connector.execute("catalogs.list_roles")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Basic"
    assert response.payload["error"]["code"] == "AUTH-001"


def test_parse_and_main_report_local_argument_problems_without_loading_configuration(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        parse_arguments(["users.create", "--body", "[]"])
    assert raised.value.code == 2

    assert main(["--list-operations"]) == 0
    assert "catalogs.list_roles: GET /catalogs/roles" in capsys.readouterr().out
    assert main(["unknown.operation"]) == 2
    assert "unknown.operation" in capsys.readouterr().err


def test_connector_rejects_non_envelope_json_responses_with_available_status() -> None:
    with pytest.raises(ConnectorResponseError) as raised:
        _decode_response(200, {"Content-Type": "application/json"}, b'[]')

    assert getattr(raised.value, "status_code") == 200
