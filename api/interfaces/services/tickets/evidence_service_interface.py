from typing import Protocol
from api.contracts import (
    CitizenEvidenceListOutput,
    EvidenceContentDescriptor,
    EvidenceCreateInput,
    EvidenceOutput,
    ExecutionContext,
    OperationResult,
)


class EvidenceServiceInterface(Protocol):
    def get_by_id(
        self, context: ExecutionContext, evidence_id: int
    ) -> OperationResult[EvidenceOutput]:
        pass

    def list_by_ticket(
        self, context: ExecutionContext, ticket_id: int
    ) -> OperationResult[list[EvidenceOutput]]:
        pass

    def list_by_ticket_and_uploader(
        self,
        context: ExecutionContext,
        ticket_id: int,
        uploaded_by: int,
    ) -> OperationResult[list[EvidenceOutput]]:
        pass

    def create_metadata(
        self, context: ExecutionContext, data: EvidenceCreateInput
    ) -> OperationResult[EvidenceOutput]:
        pass

    def list_citizen_ticket_evidence(
        self,
        context: ExecutionContext,
        ticket_code: str,
    ) -> OperationResult[CitizenEvidenceListOutput]:
        pass

    def list_citizen_contribution_evidence(
        self,
        context: ExecutionContext,
        contribution_id: str,
    ) -> OperationResult[CitizenEvidenceListOutput]:
        pass

    def open_citizen_content(
        self,
        context: ExecutionContext,
        evidence_id: int,
    ) -> OperationResult[EvidenceContentDescriptor]:
        pass