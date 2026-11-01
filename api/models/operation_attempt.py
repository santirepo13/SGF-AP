"""Persisted idempotency result for a completed application operation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from api.contracts.common_types import ensure_aware


@dataclass(frozen=True, slots=True)
class OperationAttempt:
    actor_user_id: int
    operation: str
    request_key: str = field(repr=False)
    request_digest: str = field(repr=False)
    result_payload: Mapping[str, object] = field(repr=False)
    committed_at: datetime

    def __post_init__(self) -> None:
        if type(self.actor_user_id) is not int or self.actor_user_id <= 0:
            raise ValueError("actor_user_id must be a positive integer")
        if type(self.operation) is not str or not self.operation:
            raise ValueError("operation must be a non-empty string")
        if type(self.request_key) is not str or not self.request_key:
            raise ValueError("request_key must be a non-empty string")
        if type(self.request_digest) is not str or len(self.request_digest) != 64:
            raise ValueError("request_digest must be a SHA-256 hexadecimal digest")
        ensure_aware(self.committed_at, "committed_at")
