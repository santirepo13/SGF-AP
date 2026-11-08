"""Explicit maintenance command; never started from request handling."""

from __future__ import annotations


def cleanup_expired_uploads(*, batch_size: int = 100) -> int:
    # Claim expired receiving/ready rows with FOR UPDATE SKIP LOCKED.
    # Mark deletion requested and commit before filesystem deletion.
    # Delete idempotently outside SQL transaction.
    # Mark deleted only after physical deletion succeeds.
    # Retain retry work when deletion fails.
    # Never select consumed rows or storage keys referenced by evidences.
    ...


if __name__ == "__main__":
    raise SystemExit(main())
