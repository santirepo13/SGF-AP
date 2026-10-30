"""HTTP-input and route-order checks for citizen registration."""

from __future__ import annotations

import pytest

from api.contracts import CitizenRegistrationInput
from api.errors import ApplicationError, ErrorCode
from api.http.inputs import build_contract
from api.routes.users.user_routes import router


def test_registration_http_contract_rejects_additional_properties() -> None:
    with pytest.raises(ApplicationError) as raised:
        build_contract(
            CitizenRegistrationInput,
            {
                "first_name": "Ana",
                "last_name": "Gómez",
                "email": "ana@example.test",
                "password": "password",
                "role_id": 1,
            },
            correlation_id="corr-extra",
        )

    assert raised.value.code is ErrorCode.INVALID_VALUE
    assert raised.value.details[0].field == "role_id"


def test_registration_http_contract_reports_null_required_fields() -> None:
    with pytest.raises(ApplicationError) as raised:
        build_contract(
            CitizenRegistrationInput,
            {
                "first_name": None,
                "last_name": "Gómez",
                "email": "ana@example.test",
                "password": "password",
            },
            correlation_id="corr-null",
        )

    assert raised.value.code is ErrorCode.REQUIRED_FIELD_MISSING
    assert raised.value.details[0].field == "first_name"


def test_registration_static_route_precedes_the_dynamic_user_identifier_route() -> None:
    paths = [route.path for route in router.routes]

    assert paths.index("/users/register") < paths.index("/users/{user_id}")
