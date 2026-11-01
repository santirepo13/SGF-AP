from collections.abc import Mapping
from typing import Protocol

from api.models import OperationAttempt


class OperationAttemptRepositoryInterface(Protocol):
    def get(
        self,
        *,
        actor_user_id: int,
        operation: str,
        request_key: str,
    ) -> OperationAttempt | None: ...

    def create(
        self,
        *,
        actor_user_id: int,
        operation: str,
        request_key: str,
        request_digest: str,
        result_payload: Mapping[str, object],
    ) -> OperationAttempt: ...
