"""Per-selection citizen photo state, upload recovery, and attachment confirmation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4


class CitizenPhotoState(str, Enum):
    SELECTED = "selected"
    UPLOADING = "uploading"
    READY = "ready"
    FAILED = "failed"
    REMOVED = "removed"
    ATTACHED = "attached"
    LOCAL_UNAVAILABLE = "local_unavailable"


@dataclass(slots=True)
class CitizenPhotoSelection:
    selection_id: str
    upload_key: str
    source: str
    captured_at: datetime | None
    preview: bytes | None = field(repr=False)
    size_bytes: int | None = None
    state: CitizenPhotoState = CitizenPhotoState.SELECTED
    progress_bytes: int = 0
    upload_id: str | None = None
    error_message: str | None = None


class CitizenEvidenceController:
    MAX_PHOTOS = 3
    MAX_FILE_BYTES = 10_000_000

    def ensure_request_key(self) -> str:
        # Creates one request_key before first temporary upload and preserves it
        # through upload retries/recovery for the same report intent.
        ...

    async def select_photo(self, photo: DevicePhoto) -> CitizenPhotoSelection:
        # Enforce visible count/size locally; retain selection order.
        ...

    async def upload(self, selection_id: str) -> CitizenPhotoSelection:
        # Reuse upload_key and request_key; progress is actual sent bytes.
        # A late response cannot restore a removed selection.
        ...

    async def restore_server_uploads(self) -> None:
        # Reconcile only own upload IDs by request_key after process restart.
        # Missing local sources become LOCAL_UNAVAILABLE, not fabricated previews.
        ...

    async def remove(self, selection_id: str) -> None:
        # Mark removed before remote delete; late network success cannot reinsert it.
        ...

    def ready_upload_ids(self) -> tuple[str, ...]:
        ...

    def can_submit_report(self) -> bool:
        # All non-removed selections must be READY.
        ...

    def mark_attached(self, evidence_ids: tuple[int, ...]) -> None:
        # READY -> ATTACHED only after report/contribution confirmation.
        ...

    def clear_account_private_state(self) -> None:
        # Clears previews, local streams, remote references, and stale callbacks.
        ...
