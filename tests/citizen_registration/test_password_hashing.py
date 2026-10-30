"""Unit coverage for Argon2id password hashing."""

from __future__ import annotations

import pytest

from api.security import Argon2idPasswordHasher


def test_argon2id_hashes_are_salted_and_verifiable() -> None:
    pytest.importorskip("argon2")
    hasher = Argon2idPasswordHasher()

    first = hasher.hash("Pass word Á")
    second = hasher.hash("Pass word Á")

    assert first.startswith("$argon2id$")
    assert second.startswith("$argon2id$")
    assert first != second
    assert hasher.verify(first, "Pass word Á") is True
    assert hasher.verify(second, "Pass word Á") is True
    assert hasher.verify(first, "Pass word á") is False
    assert hasher.verify(first, "Pass word Á ") is False


def test_argon2id_component_never_places_password_in_repr() -> None:
    pytest.importorskip("argon2")
    hasher = Argon2idPasswordHasher()

    assert "password" not in repr(hasher).lower()
