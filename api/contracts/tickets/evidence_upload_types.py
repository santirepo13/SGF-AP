"""Safe citizen evidence-upload, attachment, download, and contribution contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO, Literal
from uuid import UUID

from api.contracts.common_types import ensure_aware

CaptureSource = Literal["camera", "device_metadata", "user_declared", "unknown"]
EvidencePurpose = Literal["report", "legacy"]
EvidenceUploadState = Literal["receiving", "ready", "consumed", "expired", "deleted"]


@dataclass(frozen=True, slots=True)
class EvidenceUploadInput:
    request_key: str
    upload_key: str
    capture_source: CaptureSource
    captured_at: datetime | None
    content: BinaryIO


@dataclass(frozen=True, slots=True)
class EvidenceUploadOutput:
    upload_id: UUID
    upload_key: str
    state: Literal["ready"]
    size_bytes: int
    media_type: str
    captured_at: datetime | None
    capture_source: CaptureSource
    expires_at: datetime

    def __post_init__(self) -> None:
        if self.captured_at is not None:
            ensure_aware(self.captured_at, "captured_at")
        ensure_aware(self.expires_at, "expires_at")


@dataclass(frozen=True, slots=True)
class EvidenceUploadLookupInput:
    request_key: str


@dataclass(frozen=True, slots=True)
class EvidenceUploadListOutput:
    uploads: tuple[EvidenceUploadOutput, ...]


@dataclass(frozen=True, slots=True)
class EvidenceUploadDeleteOutput:
    upload_id: UUID
    state: Literal["deleted", "consumed"]


@dataclass(frozen=True, slots=True)
class CitizenEvidenceOutput:
    evidence_id: int
    media_type: str | None
    size_bytes: int | None
    captured_at: datetime | None
    capture_source: str | None
    uploaded_at: datetime | None
    content_available: bool


@dataclass(frozen=True, slots=True)
class CitizenEvidenceListOutput:
    evidences: tuple[CitizenEvidenceOutput, ...]


@dataclass(frozen=True, slots=True)
class CitizenContributionInput:
    request_key: str
    target_code: str
    address_id: int
    failure_type_id: int
    temporary_upload_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class CitizenContributionOutput:
    request_key: str
    outcome: Literal["contributed"]
    contribution_id: UUID
    ticket_code: str
    created_at: datetime
    evidence_count: int
    evidence_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CitizenContributionAttemptOutput:
    request_key: str
    state: Literal["committed", "not_found"]
    result: CitizenContributionOutput | None


@dataclass(frozen=True, slots=True)
class EvidenceContentDescriptor:
    media_type: str
    size_bytes: int
    download_name: str
    stream: BinaryIO

    def close(self) -> None:
        self.stream.close()
