"""Contract for issuing and validating opaque user access credentials."""

from __future__ import annotations

from typing import Protocol

from api.contracts import IssuedAccessToken, ValidatedAccessToken


class AccessTokenProviderInterface(Protocol):
    def issue(self, user_id: int, auth_version: int = 1) -> IssuedAccessToken: ...

    def validate(self, access_token: str) -> ValidatedAccessToken: ...
