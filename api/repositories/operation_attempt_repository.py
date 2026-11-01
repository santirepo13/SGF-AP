"""Transactional ledger for confirmed idempotent operation results."""

from __future__ import annotations

import json
from collections.abc import Mapping

from api.models import OperationAttempt

from .mapping import operation_attempt
from .persistence import RepositoryBase

_COLUMNS = "actor_user_id, operation, request_key, request_digest, result_payload, committed_at"


class OperationAttemptRepository(RepositoryBase):
    def get(
        self,
        *,
        actor_user_id: int,
        operation: str,
        request_key: str,
    ) -> OperationAttempt | None:
        return self.fetch_one(
            f"SELECT {_COLUMNS} FROM operation_attempts "
            "WHERE actor_user_id = %s AND operation = %s AND request_key = %s",
            (actor_user_id, operation, request_key),
            operation="operation_attempts.get",
            entity="operation_attempt",
            mapper=operation_attempt,
        )

    def create(
        self,
        *,
        actor_user_id: int,
        operation: str,
        request_key: str,
        request_digest: str,
        result_payload: Mapping[str, object],
    ) -> OperationAttempt:
        serialized_payload = json.dumps(
            dict(result_payload),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        )
        return self.execute_one(
            "INSERT INTO operation_attempts "
            "(actor_user_id, operation, request_key, request_digest, result_payload) "
            "VALUES (%s, %s, %s, %s, %s::jsonb) "
            f"RETURNING {_COLUMNS}",
            (actor_user_id, operation, request_key, request_digest, serialized_payload),
            operation="operation_attempts.create",
            entity="operation_attempt",
            mapper=operation_attempt,
        )
