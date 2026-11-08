from typing import Protocol
from api.contracts import EvidenceCreateInput
from api.models import Evidence

class EvidenceRepositoryInterface(Protocol):
    def get_by_id(self, evidence_id: int) -> Evidence | None: ...
    def list_by_ticket(self, ticket_id: int) -> list[Evidence]: ...
    def list_by_ticket_and_uploader(self, ticket_id: int, uploaded_by: int) -> list[Evidence]: ...
    def create(self, data: EvidenceCreateInput) -> Evidence: ...
    def count_report_evidence_for_actor_for_update(
        self,
        *,
        ticket_id: int,
        actor_user_id: int,
    ) -> int: ...
    def list_citizen_ticket_evidence(
        self,
        *,
        ticket_code: str,
        actor_user_id: int,
    ) -> list[Evidence]: ...
    def get_citizen_owned_evidence(
        self,
        *,
        evidence_id: int,
        actor_user_id: int,
    ) -> Evidence | None: ...
    def get_citizen_contribution_evidence(
        self,
        *,
        contribution_id: str,
        actor_user_id: int,
    ) -> list[Evidence] | None: ...
