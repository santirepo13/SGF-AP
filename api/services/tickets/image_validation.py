"""Bounded image inspection without trusting filename or declared MIME type."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO
import warnings

from PIL import Image


@dataclass(frozen=True, slots=True)
class ValidatedImage:
    media_type: str
    size_bytes: int
    content_sha256: str


class ImageValidationError(ValueError):
    pass


class ImageValidator:
    _FORMAT_MEDIA_TYPES = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
    }

    def __init__(self, *, max_pixels: int, allowed_media_types: frozenset[str]) -> None:
        self._max_pixels = max_pixels
        self._allowed_media_types = allowed_media_types

    def validate_stream(
        self,
        stream: BinaryIO,
        *,
        size_bytes: int,
        content_sha256: str,
    ) -> ValidatedImage:
        try:
            if type(size_bytes) is not int or size_bytes <= 0:
                raise ImageValidationError("invalid image size")
            if not isinstance(content_sha256, str):
                raise ImageValidationError("invalid image digest")
            stream.seek(0)
            digest = sha256()
            actual_size = 0
            while chunk := stream.read(256 * 1024):
                actual_size += len(chunk)
                if actual_size > size_bytes:
                    raise ImageValidationError("image size does not match metadata")
                digest.update(chunk)
            if actual_size != size_bytes or digest.hexdigest() != content_sha256:
                raise ImageValidationError("image bytes do not match metadata")
            stream.seek(0)
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(stream) as image:
                    media_type = self._FORMAT_MEDIA_TYPES.get(image.format or "")
                    if media_type is None or media_type not in self._allowed_media_types:
                        raise ImageValidationError("unsupported image format")
                    if getattr(image, "n_frames", 1) != 1:
                        raise ImageValidationError("animated images are not accepted")
                    width, height = image.size
                    if width <= 0 or height <= 0 or width * height > self._max_pixels:
                        raise ImageValidationError("image dimensions exceed the pixel limit")
                    image.verify()
                stream.seek(0)
                with Image.open(stream) as image:
                    if getattr(image, "n_frames", 1) != 1:
                        raise ImageValidationError("animated images are not accepted")
                    image.load()
        except ImageValidationError:
            raise
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError,
                Image.DecompressionBombWarning) as error:
            raise ImageValidationError("invalid image bytes") from error
        finally:
            stream.seek(0)
        return ValidatedImage(
            media_type=media_type,
            size_bytes=size_bytes,
            content_sha256=content_sha256,
        )

    def validate_file(
        self,
        path: Path,
        *,
        size_bytes: int,
        content_sha256: str,
    ) -> ValidatedImage:
        with path.open("rb") as stream:
            return self.validate_stream(
                stream,
                size_bytes=size_bytes,
                content_sha256=content_sha256,
            )
