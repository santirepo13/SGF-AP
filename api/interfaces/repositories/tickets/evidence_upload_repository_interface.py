from datetime import datetime
from typing import Protocol
from uuid import UUID

from api.models import EvidenceUpload


class EvidenceUploadRepositoryInterface(Protocol):
    def lock_actor(self, actor_user_id: int) -> None: ...
    def get_by_upload_key_for_update(
        self,
        *,
        actor_user_id: int,
        purpose: str,
        request_key: str,
        upload_key: str,
    ) -> EvidenceUpload | None: ...
    def reserve_receiving(
        self,
        *,
        actor_user_id: int,
        purpose: str,
        request_key: str,
        upload_key: str,
        expires_at: datetime,
        lease_expires_at: datetime,
        maximum_active: int,
    ) -> EvidenceUpload: ...
    def renew_receiving_lease(
        self,
        upload_id: UUID,
        lease_expires_at: datetime,
    ) -> EvidenceUpload | None: ...
    def mark_ready(
        self,
        *,
        upload_id: UUID,
        storage_key: str,
        content_sha256: str,
        size_bytes: int,
        media_type: str,
        captured_at: datetime | None,
        capture_source: str,
        received_at: datetime,
        expires_at: datetime,
    ) -> EvidenceUpload: ...
    def list_by_actor_and_request(
        self,
        *,
        actor_user_id: int,
        purpose: str,
        request_key: str,
    ) -> list[EvidenceUpload]: ...
    def lock_ready_for_attachment(
        self,
        *,
        actor_user_id: int,
        purpose: str,
        request_key: str,
        upload_ids: tuple[UUID, ...],
        now: datetime,
    ) -> list[EvidenceUpload]: ...
    def mark_consumed(
        self,
        *,
        upload_id: UUID,
        evidence_id: int,
    ) -> None: ...
    def request_delete(
        self,
        *,
        actor_user_id: int,
        upload_id: UUID,
        now: datetime,
    ) -> EvidenceUpload | None: ...
    def claim_expired_for_cleanup(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[EvidenceUpload]: ...
    def mark_deleted(self, upload_id: UUID, now: datetime) -> None: ...
    def retain_delete_work(self, upload_id: UUID, now: datetime) -> None: ...
    def list_unreferenced_storage_keys_older_than(
        self,
        *,
        older_than: datetime,
        limit: int,
    ) -> list[str]: ...
