"""Flet device-photo adapters that expose private bytes, never server paths."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO, Protocol


@dataclass(frozen=True, slots=True)
class DevicePhoto:
    source: str
    captured_at: datetime | None
    display_name: str
    size_bytes: int | None
    stream_factory: callable
    preview_bytes: bytes | None


class DevicePhotoPicker(Protocol):
    async def choose(self) -> DevicePhoto | None: ...
    async def capture(self) -> DevicePhoto | None: ...
    async def dispose(self) -> None: ...


class FletDevicePhotoPicker:
    # FilePicker and Camera are initialized only after permission paths are chosen.
    # Permission denial/cancellation/no camera returns None and leaves manual report usable.
    # Android URI data is copied/read through supported Flet APIs, never treated as Python paths.
    ...
