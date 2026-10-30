"""Contracts and shared validation specific to user login."""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone

import pytest

from api.contracts import UserLoginInput, UserLoginOutput, UserOutput
from api.errors import ApplicationError, ErrorCode
from api.http.inputs import build_contract
from api.services.users.user_validation import validate_login


def test_login_contract_keeps_password_out_of_repr_and_is_frozen() -> None:
    data = UserLoginInput(email="Persona@example.test", password=" exact Á ")

    assert {field.name for field in fields(UserLoginInput)} == {"email", "password"}
    assert "exact Á" not in repr(data)
    with pytest.raises(Exception):
        data.email = "other@example.test"  # type: ignore[misc]


def test_login_contract_rejects_missing_null_type_and_extra_values() -> None:
    for body, expected in (
        ({"password": "secret"}, ErrorCode.REQUIRED_FIELD_MISSING),
        ({"email": None, "password": "secret"}, ErrorCode.REQUIRED_FIELD_MISSING),
        ({"email": "person@example.test", "password": 1}, ErrorCode.INVALID_VALUE),
        ({"email": "person@example.test", "password": "secret", "role_id": 1}, ErrorCode.INVALID_VALUE),
    ):
        with pytest.raises(ApplicationError) as raised:
            build_contract(UserLoginInput, body, correlation_id="login-contract")
        assert raised.value.code is expected
        assert "secret" not in str(raised.value.details)


def test_login_validator_preserves_password_without_new_composition_rules() -> None:
    data = UserLoginInput(email="Person@example.test", password=" exact Á ")

    assert validate_login(data, correlation_id="login-validation") is data


def test_login_output_hides_opaque_access_token_and_requires_aware_expiry() -> None:
    user = UserOutput(4, "Ana", "Gómez", "ana@example.test", 3, True, "Citizen")
    result = UserLoginOutput(user, "opaque-access-token", datetime.now(timezone.utc))

    assert "opaque-access-token" not in repr(result)
    with pytest.raises(ValueError):
        UserLoginOutput(user, "opaque-access-token", datetime.now())
