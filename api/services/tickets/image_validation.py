"""Bounded image inspection without trusting filename or declared MIME type."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from PIL import Image, UnidentifiedImageError


@dataclass(frozen=True, slots=True)
class ValidatedImage:
    media_type: str
    size_bytes: int
    content_sha256: str


class ImageValidator:
    _FORMAT_MEDIA_TYPES = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
    }

    def __init__(self, *, max_pixels: int, allowed_media_types: frozenset[str]) -> None:
        self._max_pixels = max_pixels
        self._allowed_media_types = allowed_media_types

    def validate_file(
        self,
        path: Path,
        *,
        size_bytes: int,
        content_sha256: str,
    ) -> ValidatedImage:
        # Open and verify once; reopen to inspect dimensions/frame count.
        # Reject truncated data, decompression bombs, animation, and multi-frame files.
        # Never transform, recompress, or alter accepted bytes.
        ...
