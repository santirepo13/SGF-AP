"""Private immutable evidence blob storage contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO, Protocol


@dataclass(frozen=True, slots=True)
class EvidenceStorageLimits:
    max_file_bytes: int


@dataclass(frozen=True, slots=True)
class StoredEvidenceObject:
    storage_key: str
    size_bytes: int
    content_sha256: str
    media_type: str


@dataclass(slots=True)
class EvidenceReadHandle:
    stream: BinaryIO
    size_bytes: int
    media_type: str

    def close(self) -> None:
        self.stream.close()


class EvidenceStorageInterface(Protocol):
    def write_staged(
        self,
        stream: BinaryIO,
        limits: EvidenceStorageLimits,
    ) -> StoredEvidenceObject: ...

    def open_read(self, storage_key: str) -> EvidenceReadHandle: ...

    def exists(self, storage_key: str) -> bool: ...

    def delete_if_present(self, storage_key: str) -> None: ...
    def list_storage_keys_older_than(self, older_than: datetime, limit: int) -> list[str]: ...
