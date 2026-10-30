"""HS256 access-token issuance and validation for authenticated users."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from api.config import AccessTokenConfig
from api.contracts import IssuedAccessToken, ValidatedAccessToken
from api.errors import ApplicationError

try:  # Avoid making package imports fail before runtime dependencies are installed.
    import jwt
    from jwt import ExpiredSignatureError, InvalidTokenError
except ModuleNotFoundError:  # pragma: no cover - only applicable to an uninstalled deployment.
    jwt = None  # type: ignore[assignment]
    ExpiredSignatureError = InvalidTokenError = ()  # type: ignore[assignment,misc]


_TOKEN_ISSUER = "sgf-ap"
_TOKEN_AUDIENCE = "sgf-ap-api"
_TOKEN_USE = "access"
_REQUIRED_CLAIMS = ("sub", "iat", "exp", "jti", "iss", "aud", "token_use", "ver")


class AccessTokenProvider:
    """Issue and validate opaque JWT access credentials with a server-owned key."""

    def __init__(
        self,
        secret: bytes | AccessTokenConfig,
        ttl_seconds: int | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if isinstance(secret, AccessTokenConfig):
            if ttl_seconds is not None:
                raise ValueError("ttl_seconds must not be supplied with AccessTokenConfig")
            config = secret
        else:
            config = AccessTokenConfig(secret=secret, ttl_seconds=3600 if ttl_seconds is None else ttl_seconds)
        if jwt is None:
            raise RuntimeError("PyJWT is required to issue access tokens")
        self._secret = config.secret
        self._ttl_seconds = config.ttl_seconds
        self._clock = clock or _utc_now

    def issue(self, user_id: int, auth_version: int = 1) -> IssuedAccessToken:
        """Return a newly signed credential for a server-verified account revision."""

        if type(user_id) is not int or user_id <= 0:
            raise ApplicationError.unexpected(cause=ValueError("user_id must be a positive integer"))
        if type(auth_version) is not int or auth_version <= 0:
            raise ApplicationError.unexpected(cause=ValueError("auth_version must be a positive integer"))
        try:
            issued_at = _as_utc(self._clock())
            issued_seconds = int(issued_at.timestamp())
            expires_seconds = issued_seconds + self._ttl_seconds
            payload = {
                "sub": str(user_id),
                "iat": issued_seconds,
                "exp": expires_seconds,
                "jti": uuid4().hex,
                "iss": _TOKEN_ISSUER,
                "aud": _TOKEN_AUDIENCE,
                "token_use": _TOKEN_USE,
                "ver": auth_version,
            }
            encoded = jwt.encode(payload, self._secret, algorithm="HS256")
            token = encoded.decode("utf-8") if isinstance(encoded, bytes) else encoded
            if type(token) is not str or not token:
                raise RuntimeError("JWT component returned an invalid token")
            return IssuedAccessToken(
                access_token=token,
                expires_at=datetime.fromtimestamp(expires_seconds, timezone.utc),
            )
        except ApplicationError:
            raise
        except BaseException as error:
            raise ApplicationError.unexpected(cause=error) from error

    def validate(self, access_token: str) -> ValidatedAccessToken:
        """Validate signature, fixed claims, and time bounds without exposing a token."""

        if type(access_token) is not str or not access_token:
            raise ApplicationError.invalid_access_token()
        try:
            payload = jwt.decode(
                access_token,
                self._secret,
                algorithms=["HS256"],
                issuer=_TOKEN_ISSUER,
                audience=_TOKEN_AUDIENCE,
                options={
                    "require": list(_REQUIRED_CLAIMS),
                    # Time checks are performed below against the injected clock,
                    # which keeps issuance and validation deterministic in tests.
                    "verify_exp": False,
                    "verify_iat": False,
                },
            )
        except ExpiredSignatureError as error:
            raise ApplicationError.access_token_expired(cause=error) from error
        except InvalidTokenError as error:
            raise ApplicationError.invalid_access_token(cause=error) from error
        except BaseException as error:
            raise ApplicationError.unexpected(cause=error) from error

        try:
            return self._validated_payload(payload)
        except ApplicationError:
            raise
        except BaseException as error:
            raise ApplicationError.invalid_access_token(cause=error) from error

    def _validated_payload(self, payload: object) -> ValidatedAccessToken:
        if not isinstance(payload, dict):
            raise ApplicationError.invalid_access_token()
        if set(payload) != set(_REQUIRED_CLAIMS):
            raise ApplicationError.invalid_access_token()
        if payload.get("iss") != _TOKEN_ISSUER or payload.get("aud") != _TOKEN_AUDIENCE:
            raise ApplicationError.invalid_access_token()
        if payload.get("token_use") != _TOKEN_USE:
            raise ApplicationError.invalid_access_token()

        subject = payload.get("sub")
        if type(subject) is not str or not subject.isascii() or not subject.isdecimal():
            raise ApplicationError.invalid_access_token()
        user_id = int(subject)
        if user_id <= 0:
            raise ApplicationError.invalid_access_token()

        token_id = payload.get("jti")
        if type(token_id) is not str or not token_id:
            raise ApplicationError.invalid_access_token()

        auth_version = payload.get("ver")
        if type(auth_version) is not int or auth_version <= 0:
            raise ApplicationError.invalid_access_token()

        issued_seconds = payload.get("iat")
        expires_seconds = payload.get("exp")
        if type(issued_seconds) is not int or type(expires_seconds) is not int:
            raise ApplicationError.invalid_access_token()
        now_seconds = int(_as_utc(self._clock()).timestamp())
        if issued_seconds > now_seconds or expires_seconds <= issued_seconds:
            raise ApplicationError.invalid_access_token()
        if now_seconds >= expires_seconds:
            raise ApplicationError.access_token_expired()

        try:
            issued_at = datetime.fromtimestamp(issued_seconds, timezone.utc)
            expires_at = datetime.fromtimestamp(expires_seconds, timezone.utc)
        except (OverflowError, OSError, ValueError) as error:
            raise ApplicationError.invalid_access_token(cause=error) from error
        return ValidatedAccessToken(
            user_id=user_id,
            token_id=token_id,
            issued_at=issued_at,
            expires_at=expires_at,
            auth_version=auth_version,
        )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return an aware datetime")
    return value.astimezone(timezone.utc)


__all__ = [
    "AccessTokenProvider",
    "_TOKEN_AUDIENCE",
    "_TOKEN_ISSUER",
    "_TOKEN_USE",
]
