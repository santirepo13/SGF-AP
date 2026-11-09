"""Citizen-owned resumable temporary-upload lifecycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from api.contracts import (
    EvidenceUploadDeleteOutput,
    EvidenceUploadInput,
    EvidenceUploadListOutput,
    EvidenceUploadLookupInput,
    EvidenceUploadOutput,
    ExecutionContext,
    OperationResult,
)
from api.config import EvidenceStorageConfig
from api.errors import ApplicationError, ErrorCode
from api.security import CitizenAuthorizer
from api.storage import EvidenceStorageTooLarge, EvidenceStorageUnavailable
from api.interfaces.repositories import (
    EvidenceUploadRepositoryInterface,
    RoleRepositoryInterface,
    UserRepositoryInterface,
)
from api.interfaces.storage import EvidenceStorageInterface, EvidenceStorageLimits

from ..base import ServiceBase
from .image_validation import ImageValidationError, ImageValidator


class EvidenceUploadService(ServiceBase):
    _PURPOSE = "report"

    def __init__(self, *, uploads, users, roles, storage, image_validator, config=None, **kwargs):
        super().__init__(**kwargs)
        self.uploads = uploads
        self.users = users
        self.roles = roles
        self.storage = storage
        self.image_validator = image_validator
        self.config = config or EvidenceStorageConfig()
        self.citizen_authorizer = CitizenAuthorizer()

    def upload(
        self,
        context: ExecutionContext,
        data: EvidenceUploadInput,
    ) -> OperationResult[EvidenceUploadOutput]:
        def work():
            if not self.config.enabled or self.transaction is None:
                raise ApplicationError.with_code(ErrorCode.EVIDENCE_STORAGE_UNAVAILABLE, correlation_id=context.correlation_id)
            if not isinstance(data, EvidenceUploadInput):
                raise ApplicationError.invalid_value("data", "La carga no es válida.", correlation_id=context.correlation_id)
            for name in ("request_key", "upload_key"):
                value = getattr(data, name)
                if type(value) is not str or not 1 <= len(value) <= 128:
                    raise ApplicationError.invalid_value(name, "La clave no es válida.", correlation_id=context.correlation_id)
            if data.capture_source not in {"camera", "device_metadata", "user_declared", "unknown"}:
                raise ApplicationError.invalid_value("capture_source", "La fuente no es válida.", correlation_id=context.correlation_id)
            if data.captured_at is not None and (
                not isinstance(data.captured_at, datetime)
                or data.captured_at.tzinfo is None
                or data.captured_at.utcoffset() is None
                or data.capture_source == "unknown"
            ):
                raise ApplicationError.invalid_value("captured_at", "La fecha no es válida.", correlation_id=context.correlation_id)
            if not callable(getattr(data.content, "read", None)):
                raise ApplicationError.invalid_value("file", "El archivo no es válido.", correlation_id=context.correlation_id)

            actor_id = self._citizen(context, lock=True)
            self.uploads.lock_actor(actor_id)
            current = self.uploads.get_by_upload_key_for_update(
                actor_user_id=actor_id, purpose=self._PURPOSE,
                request_key=data.request_key, upload_key=data.upload_key,
            )
            now = datetime.now(timezone.utc)
            if current is None:
                current = self.uploads.reserve_receiving(
                    actor_user_id=actor_id, purpose=self._PURPOSE,
                    request_key=data.request_key, upload_key=data.upload_key,
                    expires_at=now + timedelta(seconds=self.config.ready_ttl_seconds),
                    lease_expires_at=now + timedelta(seconds=self.config.receiving_max_seconds),
                    maximum_active=self.config.max_report_photos,
                )
                receiving = True
            elif current.state == "receiving" and current.lease_expires_at is not None and current.lease_expires_at <= now:
                current = self.uploads.renew_receiving_lease(
                    current.id,
                    now + timedelta(seconds=self.config.receiving_max_seconds),
                )
                if current is None:
                    raise ApplicationError.with_code(ErrorCode.EVIDENCE_UPLOAD_STATE, correlation_id=context.correlation_id)
                receiving = True
            elif current.state == "ready" and current.expires_at > now:
                receiving = False
            else:
                raise ApplicationError.with_code(ErrorCode.EVIDENCE_UPLOAD_STATE, correlation_id=context.correlation_id)
            try:
                self.transaction.commit()
            except Exception as error:
                raise ApplicationError.result_unknown(correlation_id=context.correlation_id, cause=error) from error

            stored = None
            try:
                stored = self.storage.write_staged(data.content, EvidenceStorageLimits(self.config.max_file_bytes))
                handle = self.storage.open_read(stored.storage_key)
                try:
                    image = self.image_validator.validate_stream(
                        handle.stream, size_bytes=stored.size_bytes, content_sha256=stored.content_sha256,
                    )
                finally:
                    handle.close()
                self._citizen(context, lock=True)
                self.uploads.lock_actor(actor_id)
                current = self.uploads.get_by_upload_key_for_update(
                    actor_user_id=actor_id, purpose=self._PURPOSE,
                    request_key=data.request_key, upload_key=data.upload_key,
                )
                now = datetime.now(timezone.utc)
                if receiving:
                    if current is None or current.state != "receiving" or current.lease_expires_at is None or current.lease_expires_at <= now:
                        raise ApplicationError.with_code(ErrorCode.EVIDENCE_UPLOAD_STATE, correlation_id=context.correlation_id)
                    current = self.uploads.mark_ready(
                        upload_id=current.id, storage_key=stored.storage_key, content_sha256=image.content_sha256,
                        size_bytes=image.size_bytes, media_type=image.media_type, captured_at=data.captured_at,
                        capture_source=data.capture_source, received_at=now,
                        expires_at=now + timedelta(seconds=self.config.ready_ttl_seconds),
                    )
                else:
                    if current is None or current.state != "ready" or current.expires_at <= now or (
                        current.content_sha256 != image.content_sha256
                        or current.size_bytes != image.size_bytes
                        or current.media_type != image.media_type
                        or current.capture_source != data.capture_source
                        or current.captured_at != data.captured_at
                    ):
                        raise ApplicationError.with_code(ErrorCode.EVIDENCE_UPLOAD_STATE, correlation_id=context.correlation_id)
                    self.storage.delete_if_present(stored.storage_key)
                    stored = None
                return EvidenceUploadOutput(
                    upload_id=current.id, upload_key=current.upload_key,
                    state="ready", size_bytes=current.size_bytes,
                    media_type=current.media_type, captured_at=current.captured_at,
                    capture_source=current.capture_source, expires_at=current.expires_at,
                )
            except Exception as error:
                if stored is not None:
                    try:
                        self.storage.delete_if_present(stored.storage_key)
                    except (OSError, EvidenceStorageUnavailable):
                        pass
                if isinstance(error, EvidenceStorageTooLarge):
                    raise ApplicationError.with_code(ErrorCode.EVIDENCE_TOO_LARGE, correlation_id=context.correlation_id, cause=error) from error
                if isinstance(error, ImageValidationError):
                    raise ApplicationError.with_code(ErrorCode.EVIDENCE_FORMAT_INVALID, correlation_id=context.correlation_id, cause=error) from error
                if isinstance(error, (OSError, EvidenceStorageUnavailable)):
                    raise ApplicationError.with_code(ErrorCode.EVIDENCE_STORAGE_UNAVAILABLE, correlation_id=context.correlation_id, cause=error) from error
                raise

        return self._execute(context, "EvidenceUploadService.upload", work, write=True, actor_required=True)

    def list_own(
        self,
        context: ExecutionContext,
        data: EvidenceUploadLookupInput,
    ) -> OperationResult[EvidenceUploadListOutput]:
        def work():
            actor_id = self._citizen(context, lock=False)
            if not isinstance(data, EvidenceUploadLookupInput) or type(data.request_key) is not str or not 1 <= len(data.request_key) <= 128:
                raise ApplicationError.invalid_value("request_key", "La clave del intento no es válida.", correlation_id=context.correlation_id)
            now = datetime.now(timezone.utc)
            rows = self.uploads.list_by_actor_and_request(
                actor_user_id=actor_id, purpose=self._PURPOSE, request_key=data.request_key,
            )
            ready = []
            for row in rows:
                if row.state != "ready" or row.expires_at <= now:
                    continue
                if row.size_bytes is None or row.media_type is None:
                    raise ApplicationError.persistence_failure(correlation_id=context.correlation_id)
                ready.append(EvidenceUploadOutput(
                    upload_id=row.id, upload_key=row.upload_key,
                    state="ready", size_bytes=row.size_bytes,
                    media_type=row.media_type, captured_at=row.captured_at,
                    capture_source=row.capture_source, expires_at=row.expires_at,
                ))
            return EvidenceUploadListOutput(uploads=tuple(ready))

        return self._execute(context, "EvidenceUploadService.list_own", work, actor_required=True)

    def delete_own(
        self,
        context: ExecutionContext,
        upload_id: str,
    ) -> OperationResult[EvidenceUploadDeleteOutput]:
        def work():
            actor_id = self._citizen(context, lock=True)
            try:
                identifier = UUID(upload_id)
            except (ValueError, TypeError, AttributeError) as error:
                raise ApplicationError.invalid_value("upload_id", "El identificador no es válido.", correlation_id=context.correlation_id, cause=error) from error
            row = self.uploads.request_delete(
                actor_user_id=actor_id, upload_id=identifier, now=datetime.now(timezone.utc),
            )
            if row is None:
                raise self._missing("evidence_upload", context)
            return EvidenceUploadDeleteOutput(upload_id=row.id, state=row.state)

        return self._execute(context, "EvidenceUploadService.delete_own", work, write=True, actor_required=True)

    def _citizen(self, context: ExecutionContext, *, lock: bool) -> int:
        if context.actor is None:
            raise ApplicationError.access_token_required(correlation_id=context.correlation_id)
        user = (
            self.users.get_by_id_for_update(context.actor.user_id)
            if lock else self.users.get_by_id(context.actor.user_id)
        )
        role = self.roles.get_by_id(user.role_id) if user is not None else None
        self.citizen_authorizer.require_citizen(context, user=user, role=role)
        return context.actor.user_id

    def _unavailable(self, context: ExecutionContext, operation: str) -> OperationResult:
        def work():
            raise ApplicationError.with_code(
                ErrorCode.EVIDENCE_STORAGE_UNAVAILABLE,
                correlation_id=context.correlation_id,
            )

        return self._execute(context, operation, work, actor_required=True)
