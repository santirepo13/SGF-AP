from typing import Protocol

from api.contracts import (
    EvidenceUploadDeleteOutput,
    EvidenceUploadInput,
    EvidenceUploadListOutput,
    EvidenceUploadLookupInput,
    EvidenceUploadOutput,
    ExecutionContext,
    OperationResult,
)


class EvidenceUploadServiceInterface(Protocol):
    def upload(
        self,
        context: ExecutionContext,
        data: EvidenceUploadInput,
    ) -> OperationResult[EvidenceUploadOutput]:
        pass

    def list_own(
        self,
        context: ExecutionContext,
        data: EvidenceUploadLookupInput,
    ) -> OperationResult[EvidenceUploadListOutput]:
        pass

    def delete_own(
        self,
        context: ExecutionContext,
        upload_id: str,
    ) -> OperationResult[EvidenceUploadDeleteOutput]:
        pass