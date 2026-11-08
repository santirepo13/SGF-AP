from typing import Protocol
from uuid import UUID

from api.models import CitizenContribution


class CitizenContributionRepositoryInterface(Protocol):
    def create(
        self,
        *,
        ticket_id: int,
        actor_user_id: int,
        request_key: str,
    ) -> CitizenContribution: ...
    def create_evidence_link(
        self,
        *,
        contribution_id: UUID,
        evidence_id: int,
    ) -> None: ...
    def list_evidence_ids_for_actor(
        self,
        *,
        contribution_id: UUID,
        actor_user_id: int,
    ) -> list[int] | None: ...
