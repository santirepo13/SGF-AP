"""Explicit maintenance command; never started from request handling."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from typing import Sequence

from api.config import EvidenceStorageConfig, PostgresConnectionProvider, load_api_config, load_database_config
from api.interfaces.storage import EvidenceStorageInterface
from api.repositories.tickets.evidence_upload_repository import EvidenceUploadRepository
from api.storage import EvidenceStorageUnavailable, LocalEvidenceStorage


def cleanup_expired_uploads(
    *,
    batch_size: int = 100,
    connection_provider: PostgresConnectionProvider | None = None,
    storage: EvidenceStorageInterface | None = None,
    evidence_config: EvidenceStorageConfig | None = None,
    now: datetime | None = None,
) -> int:
    """Delete expired temporary objects after their rows are durably claimed."""

    if type(batch_size) is not int or not 1 <= batch_size <= 1_000:
        raise ValueError("batch_size must be between 1 and 1000")
    if now is not None and (now.tzinfo is None or now.utcoffset() is None):
        raise ValueError("now must include timezone information")

    if evidence_config is None:
        evidence_config = load_api_config().evidence_storage
    if not evidence_config.enabled or evidence_config.root is None:
        return 0
    if connection_provider is None:
        connection_provider = PostgresConnectionProvider(load_database_config())
    if storage is None:
        storage = LocalEvidenceStorage(evidence_config.root)

    current_time = now or datetime.now(timezone.utc)
    completed = 0
    with connection_provider.connection() as connection:
        uploads = EvidenceUploadRepository(connection)
        claimed = uploads.claim_expired_for_cleanup(now=current_time, limit=batch_size)
        connection.commit()

        for upload in claimed:
            try:
                if upload.storage_key is not None:
                    storage.delete_if_present(upload.storage_key)
                uploads.mark_deleted(upload.id, current_time)
                connection.commit()
                completed += 1
            except (OSError, EvidenceStorageUnavailable):
                connection.rollback()
                try:
                    uploads.retain_delete_work(upload.id, current_time)
                    connection.commit()
                except BaseException:
                    connection.rollback()
            except BaseException:
                connection.rollback()
                try:
                    uploads.retain_delete_work(upload.id, current_time)
                    connection.commit()
                except BaseException:
                    connection.rollback()

        orphan_cutoff = current_time - timedelta(seconds=evidence_config.orphan_safety_seconds)
        try:
            orphan_keys = storage.list_storage_keys_older_than(orphan_cutoff, batch_size)
        except (OSError, EvidenceStorageUnavailable):
            return completed
        for storage_key in orphan_keys:
            try:
                if uploads.storage_key_is_referenced(storage_key):
                    continue
                storage.delete_if_present(storage_key)
                completed += 1
            except (OSError, EvidenceStorageUnavailable):
                continue
        return completed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delete expired temporary evidence uploads.")
    parser.add_argument("--batch-size", type=int, default=100)
    arguments = parser.parse_args(argv)
    cleanup_expired_uploads(batch_size=arguments.batch_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
