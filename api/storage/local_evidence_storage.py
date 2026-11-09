"""Filesystem-backed private evidence storage rooted outside application assets."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import os
import secrets
import tempfile

from api.interfaces.storage import (
    EvidenceReadHandle,
    EvidenceStorageInterface,
    EvidenceStorageLimits,
    StoredEvidenceObject,
)


class EvidenceStorageUnavailable(RuntimeError):
    pass


class EvidenceStorageTooLarge(RuntimeError):
    pass


class LocalEvidenceStorage(EvidenceStorageInterface):
    _CHUNK_SIZE = 256 * 1024

    def __init__(self, root: Path) -> None:
        if root.is_symlink():
            raise EvidenceStorageUnavailable("private evidence root must not be a symbolic link")
        self._root = root.resolve(strict=True)
        self._staging = self._root / ".staging"
        self._validate_root()

    def write_staged(
        self,
        stream,
        limits: EvidenceStorageLimits,
    ) -> StoredEvidenceObject:
        descriptor, temporary_path = self._create_private_temporary_file()
        digest = sha256()
        size_bytes = 0
        try:
            with os.fdopen(descriptor, "wb") as destination:
                while chunk := stream.read(self._CHUNK_SIZE):
                    size_bytes += len(chunk)
                    if size_bytes > limits.max_file_bytes:
                        raise EvidenceStorageTooLarge("evidence size exceeds storage limit")
                    digest.update(chunk)
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())

            storage_key = self._new_storage_key()
            destination_path = self._resolve_storage_key(storage_key)
            destination_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.replace(temporary_path, destination_path)
            self._sync_directory(destination_path.parent)
            return StoredEvidenceObject(
                storage_key=storage_key,
                size_bytes=size_bytes,
                content_sha256=digest.hexdigest(),
                media_type="application/octet-stream",
            )
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise

    def open_read(self, storage_key: str) -> EvidenceReadHandle:
        path = self._resolve_storage_key(storage_key, require_existing=True)
        return EvidenceReadHandle(
            stream=path.open("rb"),
            size_bytes=path.stat().st_size,
            media_type="application/octet-stream",
        )

    def exists(self, storage_key: str) -> bool:
        try:
            return self._resolve_storage_key(storage_key, require_existing=True).is_file()
        except (EvidenceStorageUnavailable, FileNotFoundError):
            return False

    def delete_if_present(self, storage_key: str) -> None:
        try:
            self._resolve_storage_key(storage_key, require_existing=True).unlink()
        except FileNotFoundError:
            return

    def list_storage_keys_older_than(self, older_than, limit: int) -> list[str]:
        if type(limit) is not int or limit <= 0:
            raise ValueError("limit must be positive")
        if getattr(older_than, "tzinfo", None) is None or older_than.utcoffset() is None:
            raise ValueError("older_than must include timezone information")
        objects = self._root / "objects"
        if not objects.exists():
            return []
        if objects.is_symlink():
            raise EvidenceStorageUnavailable("private evidence objects must not be a symbolic link")
        cutoff = older_than.timestamp()
        result: list[str] = []
        for directory, directories, names in os.walk(objects, followlinks=False):
            directories[:] = [name for name in directories if not (Path(directory) / name).is_symlink()]
            for name in names:
                path = Path(directory) / name
                if path.is_symlink():
                    continue
                try:
                    resolved = path.resolve(strict=True)
                    resolved.relative_to(self._root)
                    if not resolved.is_file() or resolved.stat().st_mtime > cutoff:
                        continue
                except (FileNotFoundError, OSError, ValueError):
                    continue
                result.append(resolved.relative_to(self._root).as_posix())
                if len(result) >= limit:
                    return result
        return result

    def _validate_root(self) -> None:
        if not self._root.is_dir():
            raise EvidenceStorageUnavailable("private evidence root is unavailable")
        if self._staging.is_symlink():
            raise EvidenceStorageUnavailable("private evidence staging must not be a symbolic link")
        self._staging.mkdir(mode=0o700, exist_ok=True)
        probe = self._staging / f".probe-{secrets.token_hex(12)}"
        try:
            probe.touch(mode=0o600, exist_ok=False)
        finally:
            probe.unlink(missing_ok=True)

    def _create_private_temporary_file(self) -> tuple[int, Path]:
        descriptor, raw_path = tempfile.mkstemp(
            prefix=".upload-",
            dir=self._staging,
        )
        return descriptor, Path(raw_path)

    def _new_storage_key(self) -> str:
        return f"objects/{secrets.token_urlsafe(32)}"

    def _resolve_storage_key(
        self,
        storage_key: str,
        *,
        require_existing: bool = False,
    ) -> Path:
        if (
            not storage_key
            or Path(storage_key).is_absolute()
            or ".." in Path(storage_key).parts
        ):
            raise EvidenceStorageUnavailable("invalid private evidence key")
        candidate = (self._root / storage_key).resolve(strict=require_existing)
        try:
            candidate.relative_to(self._root)
        except ValueError as error:
            raise EvidenceStorageUnavailable("evidence key escapes storage root") from error
        return candidate

    @staticmethod
    def _sync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


class UnavailableEvidenceStorage(EvidenceStorageInterface):
    def write_staged(self, stream, limits: EvidenceStorageLimits) -> StoredEvidenceObject:
        raise EvidenceStorageUnavailable("private evidence storage is unavailable")

    def open_read(self, storage_key: str) -> EvidenceReadHandle:
        raise EvidenceStorageUnavailable("private evidence storage is unavailable")

    def exists(self, storage_key: str) -> bool:
        return False

    def delete_if_present(self, storage_key: str) -> None:
        raise EvidenceStorageUnavailable("private evidence storage is unavailable")

    def list_storage_keys_older_than(self, older_than, limit: int) -> list[str]:
        raise EvidenceStorageUnavailable("private evidence storage is unavailable")
