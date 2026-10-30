"""In-process, one-time proofs for the simple code-based recovery flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hmac
import secrets
from threading import RLock


class RecoveryProofRejected(Exception):
    pass


class RecoveryRateLimited(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("password recovery is temporarily rate limited")
        self.retry_after_seconds = retry_after_seconds


@dataclass(slots=True)
class RecoveryChallenge:
    request_id: str
    user_id: int | None
    email: str = field(repr=False)
    code_mac: bytes = field(repr=False)
    expires_at: datetime
    attempts: int = 0
    cancelled: bool = False
    code_used: bool = False
    grant_mac: bytes | None = field(default=None, repr=False)
    grant_expires_at: datetime | None = None
    grant_claimed: bool = False
    grant_consumed: bool = False


class PasswordRecoveryStore:
    """Keep short-lived proofs only in process memory and never log their values."""

    def __init__(
        self,
        secret: bytes,
        *,
        code_ttl_seconds: int = 600,
        grant_ttl_seconds: int = 300,
        max_verify_attempts: int = 5,
        resend_wait_seconds: int = 60,
    ) -> None:
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("password recovery secret must contain at least 32 bytes")
        self._secret = secret
        self._code_ttl = timedelta(seconds=code_ttl_seconds)
        self._grant_ttl = timedelta(seconds=grant_ttl_seconds)
        self._max_verify_attempts = max_verify_attempts
        self._resend_wait = timedelta(seconds=resend_wait_seconds)
        self._lock = RLock()
        self._challenges: dict[str, RecoveryChallenge] = {}
        self._grant_index: dict[bytes, str] = {}
        self._next_request_at: dict[str, datetime] = {}

    def begin(self, *, user_id: int | None, email: str) -> tuple[RecoveryChallenge, str]:
        now = _utc_now()
        key = email.casefold()
        with self._lock:
            self._discard_expired(now)
            next_allowed = self._next_request_at.get(key)
            if next_allowed is not None and now < next_allowed:
                seconds = max(1, int((next_allowed - now).total_seconds()))
                raise RecoveryRateLimited(seconds)
            for challenge in self._challenges.values():
                if challenge.email.casefold() == key and not challenge.code_used:
                    challenge.cancelled = True
            request_id = secrets.token_urlsafe(24)
            code = f"{secrets.randbelow(100_000_000):08d}"
            challenge = RecoveryChallenge(
                request_id=request_id,
                user_id=user_id,
                email=email,
                code_mac=self._mac(f"code:{request_id}:{code}"),
                expires_at=now + self._code_ttl,
            )
            self._challenges[request_id] = challenge
            self._next_request_at[key] = now + self._resend_wait
            return challenge, code

    def verify(self, *, request_id: str, code: str) -> tuple[str, datetime]:
        now = _utc_now()
        with self._lock:
            self._discard_expired(now)
            challenge = self._challenges.get(request_id)
            if (
                challenge is None
                or challenge.user_id is None
                or challenge.cancelled
                or challenge.code_used
                or now >= challenge.expires_at
                or challenge.attempts >= self._max_verify_attempts
            ):
                raise RecoveryProofRejected()
            supplied = self._mac(f"code:{request_id}:{code}")
            if not hmac.compare_digest(challenge.code_mac, supplied):
                challenge.attempts += 1
                raise RecoveryProofRejected()
            reset_token = secrets.token_urlsafe(32)
            grant_mac = self._mac(f"grant:{reset_token}")
            challenge.code_used = True
            challenge.grant_mac = grant_mac
            challenge.grant_expires_at = now + self._grant_ttl
            self._grant_index[grant_mac] = request_id
            return reset_token, challenge.grant_expires_at

    def claim_reset(self, reset_token: str) -> tuple[str, int]:
        now = _utc_now()
        with self._lock:
            self._discard_expired(now)
            grant_mac = self._mac(f"grant:{reset_token}")
            request_id = self._grant_index.get(grant_mac)
            challenge = self._challenges.get(request_id or "")
            if (
                challenge is None
                or challenge.user_id is None
                or challenge.grant_mac is None
                or not hmac.compare_digest(challenge.grant_mac, grant_mac)
                or challenge.grant_expires_at is None
                or now >= challenge.grant_expires_at
                or challenge.grant_consumed
                or challenge.grant_claimed
            ):
                raise RecoveryProofRejected()
            challenge.grant_claimed = True
            return challenge.request_id, challenge.user_id

    def finish_reset(self, request_id: str, *, completed: bool) -> None:
        with self._lock:
            challenge = self._challenges.get(request_id)
            if challenge is None:
                return
            challenge.grant_claimed = False
            if completed:
                challenge.grant_consumed = True
                challenge.cancelled = True
                if challenge.grant_mac is not None:
                    self._grant_index.pop(challenge.grant_mac, None)

    def _mac(self, value: str) -> bytes:
        return hmac.digest(self._secret, value.encode("utf-8"), "sha256")

    def _discard_expired(self, now: datetime) -> None:
        expired = [
            request_id
            for request_id, challenge in self._challenges.items()
            if (challenge.grant_expires_at or challenge.expires_at) < now
        ]
        for request_id in expired:
            challenge = self._challenges.pop(request_id)
            if challenge.grant_mac is not None:
                self._grant_index.pop(challenge.grant_mac, None)
        self._next_request_at = {key: value for key, value in self._next_request_at.items() if value >= now}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "PasswordRecoveryStore",
    "RecoveryProofRejected",
    "RecoveryRateLimited",
]
