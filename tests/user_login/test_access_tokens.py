"""JWT access-token issue and validation coverage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from api.errors import ApplicationError, ErrorCode
from api.security.access_tokens import AccessTokenProvider


def test_access_token_uses_the_same_expiry_for_response_and_validated_claims() -> None:
    pytest.importorskip("jwt")
    now = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    provider = AccessTokenProvider(bytes(range(32)), 3600, clock=lambda: now)

    issued = provider.issue(17)
    validated = provider.validate(issued.access_token)

    assert validated.user_id == 17
    assert validated.expires_at == issued.expires_at
    assert validated.issued_at == now
    assert "access_token" not in repr(issued)


def test_access_token_classifies_expired_and_malformed_credentials() -> None:
    pytest.importorskip("jwt")
    issued_at = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    issuer = AccessTokenProvider(bytes(range(32)), 10, clock=lambda: issued_at)
    token = issuer.issue(17)
    expired = AccessTokenProvider(bytes(range(32)), 10, clock=lambda: issued_at + timedelta(seconds=10))

    with pytest.raises(ApplicationError) as expired_error:
        expired.validate(token.access_token)
    with pytest.raises(ApplicationError) as invalid_error:
        issuer.validate("not-a-jwt")

    assert expired_error.value.code is ErrorCode.ACCESS_TOKEN_EXPIRED
    assert invalid_error.value.code is ErrorCode.INVALID_ACCESS_TOKEN
