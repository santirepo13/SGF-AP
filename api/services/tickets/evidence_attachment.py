"""Transactional temporary-upload consumption for reports and contributions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from api.errors import ApplicationError, ErrorCode
from api.storage import EvidenceStorageUnavailable


@dataclass(frozen=True, slots=True)
class PreparedAttachment:
    upload_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class AttachedEvidence:
    evidence_ids: tuple[int, ...]


class EvidenceAttachment:
    def __init__(self, *, uploads=None, evidences=None, storage=None, max_report_photos=3):
        if type(max_report_photos) is not int or max_report_photos <= 0:
            raise ValueError("max_report_photos must be positive")
        self.uploads = uploads
        self.evidences = evidences
        self.storage = storage
        self.max_report_photos = max_report_photos

    def prepare_attachment(self, context, *, request_key: str, upload_ids: tuple[UUID, ...]) -> PreparedAttachment:
        if (
            not isinstance(upload_ids, tuple)
            or len(upload_ids) > self.max_report_photos
            or any(not isinstance(value, UUID) for value in upload_ids)
            or len(set(upload_ids)) != len(upload_ids)
        ):
            raise ApplicationError.invalid_value(
                "temporary_upload_ids", "Las referencias temporales no son válidas.",
                correlation_id=context.correlation_id,
            )
        return PreparedAttachment(upload_ids=upload_ids)

    def attach_in_transaction(
        self, context, *, ticket_id: int, request_key: str, upload_ids: tuple[UUID, ...],
    ) -> AttachedEvidence:
        prepared = self.prepare_attachment(context, request_key=request_key, upload_ids=upload_ids)
        if not prepared.upload_ids:
            return AttachedEvidence(evidence_ids=())
        if context.actor is None:
            raise ApplicationError.access_token_required(correlation_id=context.correlation_id)
        if self.uploads is None or self.evidences is None or self.storage is None:
            raise ApplicationError.with_code(ErrorCode.EVIDENCE_STORAGE_UNAVAILABLE, correlation_id=context.correlation_id)

        now = datetime.now(timezone.utc)
        rows = self.uploads.lock_ready_for_attachment(
            actor_user_id=context.actor.user_id, purpose="report", request_key=request_key,
            upload_ids=prepared.upload_ids, now=now,
        )
        by_id = {row.id: row for row in rows}
        if len(by_id) != len(prepared.upload_ids) or any(value not in by_id for value in prepared.upload_ids):
            raise ApplicationError.with_code(ErrorCode.EVIDENCE_UPLOAD_STATE, correlation_id=context.correlation_id)
        count = self.evidences.count_report_evidence_for_actor_for_update(
            ticket_id=ticket_id, actor_user_id=context.actor.user_id,
        )
        if count + len(prepared.upload_ids) > self.max_report_photos:
            raise ApplicationError.invalid_value(
                "temporary_upload_ids", "Se excedió el límite de fotografías.",
                correlation_id=context.correlation_id,
            )
        evidence_ids = []
        for upload_id in prepared.upload_ids:
            upload = by_id[upload_id]
            if not upload.storage_key or not upload.media_type or upload.size_bytes is None or not upload.content_sha256:
                raise ApplicationError.with_code(ErrorCode.EVIDENCE_UPLOAD_STATE, correlation_id=context.correlation_id)
            try:
                handle = self.storage.open_read(upload.storage_key)
                try:
                    digest = sha256()
                    size = 0
                    while chunk := handle.stream.read(256 * 1024):
                        size += len(chunk)
                        if size > upload.size_bytes:
                            raise EvidenceStorageUnavailable("evidence size mismatch")
                        digest.update(chunk)
                    if size != upload.size_bytes or digest.hexdigest() != upload.content_sha256:
                        raise EvidenceStorageUnavailable("evidence metadata mismatch")
                finally:
                    handle.close()
            except (OSError, EvidenceStorageUnavailable) as error:
                raise ApplicationError.with_code(
                    ErrorCode.EVIDENCE_STORAGE_UNAVAILABLE, correlation_id=context.correlation_id, cause=error,
                ) from error
            evidence = self.evidences.create_from_upload(
                ticket_id=ticket_id, storage_key=upload.storage_key, captured_at=upload.captured_at,
                uploaded_by=context.actor.user_id, uploaded_at=now, capture_source=upload.capture_source,
                media_type=upload.media_type, size_bytes=upload.size_bytes,
            )
            self.uploads.mark_consumed(upload_id=upload_id, evidence_id=evidence.id)
            evidence_ids.append(evidence.id)
        return AttachedEvidence(evidence_ids=tuple(evidence_ids))
