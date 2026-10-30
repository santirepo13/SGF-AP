"""Argon2id verification behavior used by login."""

from __future__ import annotations

import pytest

from api.errors import ApplicationError, ErrorCode
from api.security import Argon2idPasswordHasher


def test_password_verification_returns_false_only_for_a_normal_mismatch() -> None:
    pytest.importorskip("argon2")
    hasher = Argon2idPasswordHasher()
    password_hash = hasher.hash(" exact Á ")

    assert hasher.verify_password(password_hash, " exact Á ") is True
    assert hasher.verify_password(password_hash, "exact Á") is False


def test_password_verification_treats_a_damaged_hash_as_internal() -> None:
    pytest.importorskip("argon2")
    hasher = Argon2idPasswordHasher()

    with pytest.raises(ApplicationError) as raised:
        hasher.verify_password("not-an-argon2-hash", "password")

    assert raised.value.code is ErrorCode.UNEXPECTED_ERROR
    assert "password" not in str(raised.value.details).casefold()
