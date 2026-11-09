from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from api.errors import ApplicationError, ErrorCode
from api.models import EvidenceUpload

from ..mapping import evidence_upload
from ..persistence import RepositoryBase


class EvidenceUploadRepository(RepositoryBase):
    _COLUMNS = (
        "id, actor_user_id, request_key, upload_key, purpose, state, storage_key, "
        "content_sha256, size_bytes, media_type, captured_at, capture_source, "
        "received_at, expires_at, lease_expires_at, evidence_id, "
        "delete_requested_at, delete_attempts"
    )

    def lock_actor(self, actor_user_id: int) -> None:
        self.fetch_one(
            "SELECT pg_advisory_xact_lock(%s) AS locked",
            (actor_user_id,),
            operation="evidence_uploads.lock_actor",
            entity="evidence_upload",
            mapper=lambda _: None,
        )

    def get_by_upload_key_for_update(
        self,
        *,
        actor_user_id: int,
        purpose: str,
        request_key: str,
        upload_key: str,
    ) -> EvidenceUpload | None:
        return self.fetch_one(
            f"SELECT {self._COLUMNS} FROM evidence_uploads "
            "WHERE actor_user_id = %s AND purpose = %s "
            "AND request_key = %s AND upload_key = %s FOR UPDATE",
            (actor_user_id, purpose, request_key, upload_key),
            operation="evidence_uploads.get_for_update",
            entity="evidence_upload",
            mapper=evidence_upload,
        )

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
    ) -> EvidenceUpload:
        if type(maximum_active) is not int or maximum_active <= 0:
            raise ValueError("maximum_active must be positive")
        self.lock_actor(actor_user_id)
        active = self.fetch_one(
            "SELECT COUNT(*) AS count FROM evidence_uploads "
            "WHERE actor_user_id = %s AND purpose = %s "
            "AND state IN ('receiving', 'ready') AND expires_at > CURRENT_TIMESTAMP",
            (actor_user_id, purpose),
            operation="evidence_uploads.count_active",
            entity="evidence_upload",
            mapper=lambda row: int(row["count"]),
        )
        if active is None or active >= maximum_active:
            raise ApplicationError.with_code(ErrorCode.EVIDENCE_UPLOAD_STATE)
        return self.execute_one(
            "INSERT INTO evidence_uploads "
            "(id, actor_user_id, request_key, upload_key, purpose, state, "
            "capture_source, expires_at, lease_expires_at) "
            "VALUES (%s, %s, %s, %s, %s, 'receiving', 'unknown', %s, %s) "
            f"RETURNING {self._COLUMNS}",
            (
                uuid4(),
                actor_user_id,
                request_key,
                upload_key,
                purpose,
                expires_at,
                lease_expires_at,
            ),
            operation="evidence_uploads.reserve_receiving",
            entity="evidence_upload",
            mapper=evidence_upload,
        )

    def renew_receiving_lease(
        self,
        upload_id: UUID,
        lease_expires_at: datetime,
    ) -> EvidenceUpload | None:
        return self.execute_one(
            "UPDATE evidence_uploads SET lease_expires_at = %s "
            "WHERE id = %s AND state = 'receiving' "
            f"RETURNING {self._COLUMNS}",
            (lease_expires_at, upload_id),
            operation="evidence_uploads.renew_receiving_lease",
            entity="evidence_upload",
            mapper=evidence_upload,
        )

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
    ) -> EvidenceUpload:
        value = self.execute_one(
            "UPDATE evidence_uploads SET "
            "state = 'ready', storage_key = %s, content_sha256 = %s, "
            "size_bytes = %s, media_type = %s, captured_at = %s, "
            "capture_source = %s, received_at = %s, expires_at = %s, "
            "lease_expires_at = NULL "
            "WHERE id = %s AND state = 'receiving' "
            f"RETURNING {self._COLUMNS}",
            (
                storage_key,
                content_sha256,
                size_bytes,
                media_type,
                captured_at,
                capture_source,
                received_at,
                expires_at,
                upload_id,
            ),
            operation="evidence_uploads.mark_ready",
            entity="evidence_upload",
            mapper=evidence_upload,
        )
        if value is None:
            raise RuntimeError("receiving evidence upload disappeared before publication")
        return value

    def list_by_actor_and_request(
        self,
        *,
        actor_user_id: int,
        purpose: str,
        request_key: str,
    ) -> list[EvidenceUpload]:
        return self.fetch_all(
            f"SELECT {self._COLUMNS} FROM evidence_uploads "
            "WHERE actor_user_id = %s AND purpose = %s AND request_key = %s "
            "ORDER BY received_at NULLS LAST, id",
            (actor_user_id, purpose, request_key),
            operation="evidence_uploads.list_by_actor_and_request",
            entity="evidence_upload",
            mapper=evidence_upload,
        )

    def lock_ready_for_attachment(
        self,
        *,
        actor_user_id: int,
        purpose: str,
        request_key: str,
        upload_ids: tuple[UUID, ...],
        now: datetime,
    ) -> list[EvidenceUpload]:
        if not upload_ids:
            return []
        placeholders = ", ".join("%s" for _ in upload_ids)
        return self.fetch_all(
            f"SELECT {self._COLUMNS} FROM evidence_uploads "
            f"WHERE id IN ({placeholders}) AND actor_user_id = %s "
            "AND purpose = %s AND request_key = %s AND state = 'ready' "
            "AND expires_at > %s ORDER BY id FOR UPDATE",
            (*upload_ids, actor_user_id, purpose, request_key, now),
            operation="evidence_uploads.lock_ready_for_attachment",
            entity="evidence_upload",
            mapper=evidence_upload,
        )

    def mark_consumed(self, *, upload_id: UUID, evidence_id: int) -> None:
        value = self.execute_one(
            "UPDATE evidence_uploads SET state = 'consumed', evidence_id = %s "
            "WHERE id = %s AND state = 'ready' RETURNING id",
            (evidence_id, upload_id),
            operation="evidence_uploads.mark_consumed",
            entity="evidence_upload",
            mapper=lambda row: row["id"],
        )
        if value is None:
            raise RuntimeError("ready evidence upload disappeared before consumption")

    def request_delete(
        self,
        *,
        actor_user_id: int,
        upload_id: UUID,
        now: datetime,
    ) -> EvidenceUpload | None:
        return self.execute_one(
            "UPDATE evidence_uploads SET "
            "state = CASE WHEN state = 'consumed' THEN state ELSE 'deleted' END, "
            "delete_requested_at = CASE "
            "WHEN state = 'consumed' THEN delete_requested_at "
            "ELSE COALESCE(delete_requested_at, %s) END "
            "WHERE id = %s AND actor_user_id = %s "
            f"RETURNING {self._COLUMNS}",
            (now, upload_id, actor_user_id),
            operation="evidence_uploads.request_delete",
            entity="evidence_upload",
            mapper=evidence_upload,
        )

    def claim_expired_for_cleanup(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[EvidenceUpload]:
        return self.fetch_all(
            "WITH candidates AS ("
            "  SELECT id FROM evidence_uploads "
            "  WHERE (state = 'receiving' AND lease_expires_at IS NOT NULL "
            "         AND lease_expires_at <= %s) "
            "     OR (state = 'ready' AND expires_at <= %s) "
            "     OR (state = 'expired' AND delete_requested_at IS NOT NULL "
            "         AND delete_requested_at <= %s) "
            "  ORDER BY expires_at, id FOR UPDATE SKIP LOCKED LIMIT %s"
            ") "
            "UPDATE evidence_uploads u SET "
            "state = 'expired', "
            "delete_requested_at = COALESCE(u.delete_requested_at, %s), "
            "delete_attempts = u.delete_attempts + 1 "
            "FROM candidates c WHERE c.id = u.id "
            "RETURNING u.id, u.actor_user_id, u.request_key, u.upload_key, "
            "u.purpose, u.state, u.storage_key, u.content_sha256, u.size_bytes, "
            "u.media_type, u.captured_at, u.capture_source, u.received_at, "
            "u.expires_at, u.lease_expires_at, u.evidence_id, "
            "u.delete_requested_at, u.delete_attempts",
            (now, now, now, limit, now),
            operation="evidence_uploads.claim_expired_for_cleanup",
            entity="evidence_upload",
            mapper=evidence_upload,
        )

    def mark_deleted(self, upload_id: UUID, now: datetime) -> None:
        self.execute_one(
            "UPDATE evidence_uploads SET state = 'deleted', "
            "delete_requested_at = COALESCE(delete_requested_at, %s) "
            "WHERE id = %s AND state IN ('expired', 'deleted') RETURNING id",
            (now, upload_id),
            operation="evidence_uploads.mark_deleted",
            entity="evidence_upload",
            mapper=lambda row: row["id"],
        )

    def retain_delete_work(self, upload_id: UUID, now: datetime) -> None:
        self.execute_one(
            "UPDATE evidence_uploads SET delete_requested_at = %s, "
            "delete_attempts = delete_attempts + 1 "
            "WHERE id = %s AND state IN ('expired', 'deleted') RETURNING id",
            (now, upload_id),
            operation="evidence_uploads.retain_delete_work",
            entity="evidence_upload",
            mapper=lambda row: row["id"],
        )

    def list_unreferenced_storage_keys_older_than(
        self,
        *,
        older_than: datetime,
        limit: int,
    ) -> list[str]:
        return self.fetch_all(
            "SELECT u.storage_key FROM evidence_uploads u "
            "WHERE u.storage_key IS NOT NULL "
            "AND u.state IN ('deleted', 'expired') "
            "AND COALESCE(u.delete_requested_at, u.expires_at) <= %s "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM evidences e WHERE e.file_path = u.storage_key"
            ") ORDER BY u.id LIMIT %s",
            (older_than, limit),
            operation="evidence_uploads.list_unreferenced_storage_keys",
            entity="evidence_upload",
            mapper=lambda row: str(row["storage_key"]),
        )

    def storage_key_is_referenced(self, storage_key: str) -> bool:
        if type(storage_key) is not str or not storage_key:
            raise ValueError("storage_key must be non-empty")
        value = self.fetch_one(
            "SELECT EXISTS("
            "  SELECT 1 FROM evidences WHERE file_path = %s "
            "  UNION ALL "
            "  SELECT 1 FROM evidence_uploads "
            "  WHERE storage_key = %s AND state IN ('receiving', 'ready', 'consumed')"
            ") AS referenced",
            (storage_key, storage_key),
            operation="evidence_uploads.storage_key_is_referenced",
            entity="evidence_upload",
            mapper=lambda row: bool(row["referenced"]),
        )
        return value is True
