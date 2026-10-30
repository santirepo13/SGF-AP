"""Registration authorization policy checks."""

from __future__ import annotations

from api.contracts import CitizenRegistrationInput
from api.middleware.operation_policies import OPERATION_POLICIES


def test_registration_policy_allows_no_actor_and_requires_the_public_contract() -> None:
    policy = OPERATION_POLICIES["UserService.register_citizen"]

    assert policy.actor_required is False
    assert policy.permission is None
    assert policy.input_types == (CitizenRegistrationInput,)


def test_administrative_user_creation_remains_protected() -> None:
    policy = OPERATION_POLICIES["UserService.create"]

    assert policy.actor_required is True
    assert policy.permission == "manage_users"
