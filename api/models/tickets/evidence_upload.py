from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EvidenceUpload:
    id: UUID
    actor_user_id: int
    request_key: str
    upload_key: str
    purpose: str
    state: str
    storage_key: str | None
    content_sha256: str | None
    size_bytes: int | None
    media_type: str | None
    captured_at: datetime | None
    capture_source: str
    received_at: datetime | None
    expires_at: datetime
    lease_expires_at: datetime | None
    evidence_id: int | None
    delete_requested_at: datetime | None
    delete_attempts: int
