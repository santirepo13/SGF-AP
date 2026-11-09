"""Flet device-photo adapters that expose private bytes, never server paths."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from zoneinfo import ZoneInfo, Protocol


class DevicePhotoError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DevicePhoto:
    source: str
    captured_at: datetime | None
    display_name: str
    size_bytes: int | None
    stream_factory: Callable[[], BinaryIO] = field(repr=False)
    preview_bytes: bytes | None = field(repr=False)


class DevicePhotoPicker(Protocol):
    async def choose(self) -> DevicePhoto | None: ...
    async def capture(self) -> DevicePhoto | None: ...
    async def dispose(self) -> None: ...


class FletDevicePhotoPicker:
    MAX_FILE_BYTES = 10_000_000

    def __init__(self, page, *, camera_capture: Callable[[], Awaitable[bytes | None]] | None = None):
        self._page = page
        self._camera_capture = camera_capture
        self._picker = None

    async def choose(self) -> DevicePhoto | None:
        import flet as ft

        if self._picker is None:
            self._picker = ft.FilePicker()
        try:
            files = await self._picker.pick_files(
                allow_multiple=False, with_data=False, file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["jpg", "jpeg", "png", "webp"],
            )
        except Exception as error:
            raise DevicePhotoError("No fue posible seleccionar una fotografía.") from error
        if not files:
            return None
        item = files[0]
        size = getattr(item, "size", None)
        path = getattr(item, "path", None)
        if type(size) is not int or not 0 < size <= self.MAX_FILE_BYTES:
            raise DevicePhotoError("La fotografía debe tener un tamaño máximo de 10 MB.")
        if type(path) is not str or not Path(path).is_absolute():
            raise DevicePhotoError("No se puede leer esta selección sin una ruta local; selecciona otro archivo.")
        try:
            content = await asyncio.to_thread(self._read_bounded, Path(path))
        except OSError as error:
            raise DevicePhotoError("No fue posible leer la fotografía seleccionada.") from error
        return self._photo(content, source="unknown", captured_at=None, name=str(item.name))

    @classmethod
    def _read_bounded(cls, path: Path) -> bytes:
        with path.open("rb") as stream:
            content = stream.read(cls.MAX_FILE_BYTES + 1)
        if not content or len(content) > cls.MAX_FILE_BYTES:
            raise DevicePhotoError("La fotografía debe tener un tamaño máximo de 10 MB.")
        return content

    async def capture(self) -> DevicePhoto | None:
        if self._camera_capture is None:
            raise DevicePhotoError("La cámara no está disponible en esta pantalla.")
        try:
            content = await self._camera_capture()
        except Exception as error:
            raise DevicePhotoError("No fue posible tomar la fotografía.") from error
        if content is None:
            return None
        if not isinstance(content, bytes):
            raise DevicePhotoError("No fue posible leer la fotografía tomada.")
        return self._photo(content, source="camera", captured_at=datetime.now(ZoneInfo("America/Bogota")), name="camera.jpg")

    @classmethod
    def _photo(cls, content: bytes, *, source: str, captured_at: datetime | None, name: str) -> DevicePhoto:
        if not content or len(content) > cls.MAX_FILE_BYTES:
            raise DevicePhotoError("La fotografía debe tener un tamaño máximo de 10 MB.")
        return DevicePhoto(
            source=source, captured_at=captured_at, display_name=name,
            size_bytes=len(content), stream_factory=lambda: BytesIO(content), preview_bytes=content,
        )

    async def dispose(self) -> None:
        self._picker = None