"""Per-selection citizen photo state, upload recovery, and attachment confirmation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import BinaryIO
from uuid import UUID, uuid4

from .device_photos import DevicePhoto
from .transport import MultipartFile


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
    display_name: str = "Fotografía"
    size_bytes: int | None = None
    state: CitizenPhotoState = CitizenPhotoState.SELECTED
    progress_bytes: int = 0
    upload_id: str | None = None
    error_message: str | None = None
    stream_factory: Callable[[], BinaryIO] | None = field(default=None, repr=False)


class CitizenEvidenceController:
    MAX_PHOTOS = 3
    MAX_FILE_BYTES = 10_000_000
    _SOURCES = frozenset({"camera", "device_metadata", "user_declared", "unknown"})

    def __init__(self, *, connector, request_key_provider, access_scope):
        self.connector = connector
        self.request_key_provider = request_key_provider
        self.access_scope = access_scope
        self._selections: list[CitizenPhotoSelection] = []
        self._request_key: str | None = None
        self._generation = 0
        self._last_protected_response: tuple[object, object] | None = None
        self._on_change: Callable[[], None] | None = None

    def set_on_change(self, callback: Callable[[], None] | None) -> None:
        self._on_change = callback

    @property
    def selections(self) -> tuple[CitizenPhotoSelection, ...]:
        return tuple(
            replace(selection)
            for selection in self._selections
            if selection.state is not CitizenPhotoState.REMOVED
        )

    async def dispose(self) -> None:
        self.clear_account_private_state()

    def ensure_request_key(self) -> str:
        request_key = self.request_key_provider.ensure_evidence_request_key()
        if self._request_key is not None and self._request_key != request_key:
            raise RuntimeError("Las fotografías pertenecen a otro intento. Inicia un reporte nuevo.")
        self._request_key = request_key
        return request_key

    async def select_photo(self, photo: DevicePhoto) -> CitizenPhotoSelection:
        self._capture_bound_connector()
        if len(self.selections) >= self.MAX_PHOTOS:
            raise ValueError("Puedes agregar hasta tres fotografías.")
        self._validate_device_photo(photo)
        self.ensure_request_key()
        selection = CitizenPhotoSelection(
            selection_id=uuid4().hex,
            upload_key=uuid4().hex,
            source=photo.source,
            captured_at=photo.captured_at,
            preview=photo.preview_bytes,
            display_name=photo.display_name or "Fotografía",
            size_bytes=photo.size_bytes,
            stream_factory=photo.stream_factory,
        )
        self._selections.append(selection)
        self._notify()
        return replace(selection)

    async def upload(self, selection_id: str) -> CitizenPhotoSelection:
        selection = self._selection(selection_id)
        if selection.state not in {CitizenPhotoState.SELECTED, CitizenPhotoState.FAILED}:
            return replace(selection)
        if selection.stream_factory is None or selection.size_bytes is None:
            selection.state = CitizenPhotoState.LOCAL_UNAVAILABLE
            selection.error_message = "El archivo local ya no está disponible."
            self._notify()
            return replace(selection)

        scope, connector, generation = self._capture_bound_connector()
        request_key = self.ensure_request_key()
        selection.state = CitizenPhotoState.UPLOADING
        selection.progress_bytes = 0
        selection.error_message = None
        self._notify()
        loop = asyncio.get_running_loop()

        def progress(sent: int, total: int) -> None:
            loop.call_soon_threadsafe(
                self._apply_progress,
                scope,
                generation,
                selection_id,
                selection.upload_key,
                sent,
                total,
            )

        file = MultipartFile(
            field_name="file",
            filename="evidence",
            media_type=_media_type(selection.preview),
            stream_factory=selection.stream_factory,
            size_bytes=selection.size_bytes,
        )
        try:
            response = await asyncio.to_thread(
                connector.upload_photo,
                request_key=request_key,
                upload_key=selection.upload_key,
                capture_source=selection.source,
                captured_at=selection.captured_at.isoformat() if selection.captured_at else None,
                file=file,
                progress=progress,
            )
        except BaseException as error:
            if self._is_current(scope, generation) and selection.state is CitizenPhotoState.UPLOADING:
                selection.state = CitizenPhotoState.FAILED
                selection.error_message = _transport_message(error)
                self._notify()
            return replace(selection)

        if not self._is_current(scope, generation):
            return replace(selection)
        self._last_protected_response = (scope, response)
        upload = _ready_upload(_response_data(response), expected_upload_key=selection.upload_key)
        if selection.state is CitizenPhotoState.REMOVED:
            if upload is not None:
                try:
                    await asyncio.to_thread(connector.delete_upload, upload_id=upload["upload_id"])
                except BaseException:
                    pass
            return replace(selection)
        if upload is None:
            selection.state = CitizenPhotoState.FAILED
            selection.error_message = _response_message(response)
            self._notify()
            return replace(selection)

        selection.upload_id = upload["upload_id"]
        selection.size_bytes = upload["size_bytes"]
        selection.progress_bytes = upload["size_bytes"]
        selection.state = CitizenPhotoState.READY
        selection.error_message = None
        self._sync_upload_ids()
        self._notify()
        return replace(selection)

    async def restore_server_uploads(self) -> None:
        request_key = self._provider_request_key()
        if request_key is None:
            return
        if self._request_key is not None and self._request_key != request_key:
            raise RuntimeError("Las fotografías pertenecen a otro intento. Inicia un reporte nuevo.")
        scope, connector, generation = self._capture_bound_connector()
        try:
            response = await asyncio.to_thread(connector.list_uploads, request_key=request_key)
        except BaseException:
            return
        if not self._is_current(scope, generation):
            return
        self._last_protected_response = (scope, response)
        data = _response_data(response)
        raw_uploads = data.get("uploads") if isinstance(data, Mapping) else None
        if not isinstance(raw_uploads, list) or len(raw_uploads) > self.MAX_PHOTOS:
            return

        uploads: dict[str, dict[str, object]] = {}
        for raw in raw_uploads:
            upload = _ready_upload(raw, expected_upload_key=None)
            if upload is None or upload["upload_key"] in uploads:
                return
            uploads[upload["upload_key"]] = upload

        self._request_key = request_key
        existing = {selection.upload_key: selection for selection in self._selections}
        for upload_key, upload in uploads.items():
            selection = existing.get(upload_key)
            if selection is None:
                selection = CitizenPhotoSelection(
                    selection_id=uuid4().hex,
                    upload_key=upload_key,
                    source=upload["capture_source"],
                    captured_at=upload["captured_at"],
                    preview=None,
                    display_name="Fotografía recuperada",
                    size_bytes=upload["size_bytes"],
                    state=CitizenPhotoState.LOCAL_UNAVAILABLE,
                    upload_id=upload["upload_id"],
                    error_message="Disponible en el servidor; la copia local ya no está en este dispositivo.",
                )
                self._selections.append(selection)
                continue
            if selection.state is CitizenPhotoState.REMOVED:
                continue
            selection.upload_id = upload["upload_id"]
            selection.size_bytes = upload["size_bytes"]
            selection.progress_bytes = upload["size_bytes"]
            selection.state = CitizenPhotoState.READY
            selection.error_message = None

        returned_keys = set(uploads)
        for selection in self._selections:
            if (
                selection.state in {CitizenPhotoState.READY, CitizenPhotoState.LOCAL_UNAVAILABLE}
                and selection.upload_key not in returned_keys
            ):
                selection.upload_id = None
                selection.state = CitizenPhotoState.FAILED
                selection.error_message = "La fotografía temporal ya no está disponible."
        self._sync_upload_ids()
        self._notify()

    async def remove(self, selection_id: str) -> None:
        selection = self._selection(selection_id)
        if selection.state in {CitizenPhotoState.REMOVED, CitizenPhotoState.ATTACHED}:
            return
        upload_id = selection.upload_id
        selection.state = CitizenPhotoState.REMOVED
        selection.preview = None
        selection.stream_factory = None
        selection.upload_id = None
        selection.error_message = None
        self._sync_upload_ids()
        self._notify()
        if upload_id is None:
            return
        try:
            scope, connector, generation = self._capture_bound_connector()
        except RuntimeError:
            return
        try:
            response = await asyncio.to_thread(connector.delete_upload, upload_id=upload_id)
        except BaseException:
            return
        if self._is_current(scope, generation):
            self._last_protected_response = (scope, response)

    def ready_upload_ids(self) -> tuple[str, ...]:
        return tuple(
            selection.upload_id
            for selection in self._selections
            if selection.state in {CitizenPhotoState.READY, CitizenPhotoState.LOCAL_UNAVAILABLE}
            and selection.upload_id is not None
        )

    def can_submit_report(self) -> bool:
        return all(
            selection.state in {
                CitizenPhotoState.READY,
                CitizenPhotoState.LOCAL_UNAVAILABLE,
                CitizenPhotoState.REMOVED,
                CitizenPhotoState.ATTACHED,
            }
            and (
                selection.state not in {CitizenPhotoState.READY, CitizenPhotoState.LOCAL_UNAVAILABLE}
                or selection.upload_id is not None
            )
            for selection in self._selections
        )

    def mark_attached(self, evidence_ids: tuple[int, ...]) -> None:
        pending = [
            selection
            for selection in self._selections
            if selection.state in {CitizenPhotoState.READY, CitizenPhotoState.LOCAL_UNAVAILABLE}
        ]
        if (
            len(evidence_ids) != len(pending)
            or any(type(evidence_id) is not int or evidence_id <= 0 for evidence_id in evidence_ids)
        ):
            raise ValueError("La confirmación de fotografías no es válida.")
        for selection in pending:
            selection.state = CitizenPhotoState.ATTACHED
            selection.preview = None
            selection.stream_factory = None
            selection.error_message = None
        self._sync_upload_ids()
        self._notify()

    def take_last_protected_response(self) -> tuple[object, object] | None:
        response = self._last_protected_response
        self._last_protected_response = None
        return response

    def clear_account_private_state(self) -> None:
        self._generation += 1
        for selection in self._selections:
            selection.preview = None
            selection.stream_factory = None
            selection.upload_id = None
            selection.state = CitizenPhotoState.REMOVED
        self._selections.clear()
        self._request_key = None
        self._last_protected_response = None
        self._notify()

    def _capture_bound_connector(self):
        scope = self.access_scope.capture_request_scope()
        if scope is None or not self.access_scope.is_current_request_scope(scope):
            raise RuntimeError("La sesión ya no está disponible.")
        bind_for_scope = getattr(self.access_scope, "bind_connector_for_scope", None)
        if not callable(bind_for_scope):
            raise RuntimeError("El cliente de fotografías no admite una sesión fijada.")
        connector = bind_for_scope(scope, self.connector)
        if connector is None:
            raise RuntimeError("La sesión ya no está disponible.")
        return scope, connector, self._generation

    def _is_current(self, scope: object, generation: int) -> bool:
        return generation == self._generation and self.access_scope.is_current_request_scope(scope)

    def _selection(self, selection_id: str) -> CitizenPhotoSelection:
        if type(selection_id) is not str:
            raise ValueError("La fotografía no es válida.")
        for selection in self._selections:
            if selection.selection_id == selection_id:
                return selection
        raise ValueError("La fotografía ya no está disponible.")

    def _provider_request_key(self) -> str | None:
        getter = getattr(self.request_key_provider, "evidence_request_key", None)
        if callable(getter):
            value = getter()
            return value if type(value) is str and value else None
        snapshot = getattr(self.request_key_provider, "snapshot", None)
        if not callable(snapshot):
            return None
        state = snapshot()
        value = getattr(state, "evidence_request_key", None) or getattr(state, "request_key", None)
        return value if type(value) is str and value else None

    def _sync_upload_ids(self) -> None:
        if self._request_key is None:
            return
        setter = getattr(self.request_key_provider, "set_evidence_upload_ids", None)
        if callable(setter):
            setter(self._request_key, self.ready_upload_ids())

    def _apply_progress(
        self,
        scope: object,
        generation: int,
        selection_id: str,
        upload_key: str,
        sent: int,
        total: int,
    ) -> None:
        if not self._is_current(scope, generation):
            return
        try:
            selection = self._selection(selection_id)
        except ValueError:
            return
        if (
            selection.upload_key != upload_key
            or selection.state is not CitizenPhotoState.UPLOADING
            or selection.size_bytes != total
        ):
            return
        selection.progress_bytes = min(max(sent, 0), total)
        self._notify()

    def _validate_device_photo(self, photo: DevicePhoto) -> None:
        if (
            not isinstance(photo, DevicePhoto)
            or type(photo.size_bytes) is not int
            or not 0 < photo.size_bytes <= self.MAX_FILE_BYTES
            or not callable(photo.stream_factory)
            or photo.source not in self._SOURCES
        ):
            raise ValueError("La fotografía seleccionada no es válida.")
        if photo.captured_at is not None and (
            not isinstance(photo.captured_at, datetime)
            or photo.captured_at.tzinfo is None
            or photo.captured_at.utcoffset() is None
            or photo.source == "unknown"
        ):
            raise ValueError("La fecha de captura no es válida.")

    def _notify(self) -> None:
        if self._on_change is not None:
            self._on_change()


def _response_parts(response: object) -> tuple[int, object]:
    if isinstance(response, Mapping):
        status = response.get("status_code", response.get("status"))
        payload = response.get("payload", response)
    else:
        status = getattr(response, "status_code", getattr(response, "status", None))
        payload = getattr(response, "payload", None)
    return (status if type(status) is int else 0, payload)


def _response_data(response: object) -> object:
    status, payload = _response_parts(response)
    if (
        status == 200
        and isinstance(payload, Mapping)
        and payload.get("success") is True
        and payload.get("error") is None
    ):
        return payload.get("data")
    return None


def _response_message(response: object) -> str:
    _, payload = _response_parts(response)
    if isinstance(payload, Mapping):
        error = payload.get("error")
        if isinstance(error, Mapping):
            code = error.get("code")
            if code == "EVD-001":
                return "La carga anterior todavía se está recuperando. Inténtalo nuevamente en unos momentos."
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
    return "No se confirmó la carga. Reintenta la misma fotografía."


def _transport_message(error: BaseException) -> str:
    message = str(error)
    return message if message else "No se confirmó la carga. Reintenta la misma fotografía."


def _ready_upload(value: object, *, expected_upload_key: str | None) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    required = {
        "upload_id",
        "upload_key",
        "state",
        "size_bytes",
        "media_type",
        "captured_at",
        "capture_source",
        "expires_at",
    }
    if set(value) != required or value.get("state") != "ready":
        return None
    upload_key = value.get("upload_key")
    upload_id = value.get("upload_id")
    size_bytes = value.get("size_bytes")
    source = value.get("capture_source")
    media_type = value.get("media_type")
    captured_at = _parse_timestamp(value.get("captured_at"))
    if (
        type(upload_key) is not str
        or not 1 <= len(upload_key) <= 128
        or (expected_upload_key is not None and upload_key != expected_upload_key)
        or type(upload_id) is not str
        or type(size_bytes) is not int
        or not 0 < size_bytes <= CitizenEvidenceController.MAX_FILE_BYTES
        or source not in CitizenEvidenceController._SOURCES
        or media_type not in {"image/jpeg", "image/png", "image/webp"}
        or (value.get("captured_at") is not None and captured_at is None)
        or (source == "unknown" and captured_at is not None)
        or _parse_timestamp(value.get("expires_at")) is None
    ):
        return None
    try:
        normalized_id = str(UUID(upload_id))
    except (TypeError, ValueError, AttributeError):
        return None
    return {
        "upload_id": normalized_id,
        "upload_key": upload_key,
        "size_bytes": size_bytes,
        "capture_source": source,
        "captured_at": captured_at,
    }


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def _media_type(content: bytes | None) -> str | None:
    if not isinstance(content, bytes):
        return None
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


__all__ = ["CitizenEvidenceController", "CitizenPhotoSelection", "CitizenPhotoState"]
