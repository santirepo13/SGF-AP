"""Citizen-owned resumable temporary-upload lifecycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from api.contracts import (
    EvidenceUploadDeleteOutput,
    EvidenceUploadInput,
    EvidenceUploadListOutput,
    EvidenceUploadLookupInput,
    EvidenceUploadOutput,
    ExecutionContext,
    OperationResult,
)
from api.errors import ApplicationError, ErrorCode
from api.interfaces.repositories import (
    EvidenceUploadRepositoryInterface,
    RoleRepositoryInterface,
    UserRepositoryInterface,
)
from api.interfaces.storage import EvidenceStorageInterface, EvidenceStorageLimits

from ..base import ServiceBase
from .image_validation import ImageValidator


class EvidenceUploadService(ServiceBase):
    _PURPOSE = "report"

    def upload(
        self,
        context: ExecutionContext,
        data: EvidenceUploadInput,
    ) -> OperationResult[EvidenceUploadOutput]:
        # 1. Validate exact metadata and one stream.
        # 2. Lock current Citizen + reserve receiving row in a short transaction.
        # 3. Commit reservation before filesystem transfer.
        # 4. Stream to private storage with byte cap.
        # 5. Validate immutable staged bytes with Pillow.
        # 6. Lock row, compare ready replays by digest + capture metadata.
        # 7. Publish ready metadata with 24-hour expiry.
        ...

    def list_own(
        self,
        context: ExecutionContext,
        data: EvidenceUploadLookupInput,
    ) -> OperationResult[EvidenceUploadListOutput]:
        ...

    def delete_own(
        self,
        context: ExecutionContext,
        upload_id: str,
    ) -> OperationResult[EvidenceUploadDeleteOutput]:
        # ready/receiving -> deleted idempotently; consumed remains consumed.
        # Never disclose another actor's record.
        ...

    def _state_error(self, reason: str, context: ExecutionContext) -> ApplicationError:
        return ApplicationError.with_code(
            ErrorCode.EVIDENCE_UPLOAD_STATE,
            details=(ErrorDetail("upload_id", "evidence_upload", reason),),
            correlation_id=context.correlation_id,
        )
