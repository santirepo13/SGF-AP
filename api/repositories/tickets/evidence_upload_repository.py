class EvidenceUploadRepository(RepositoryBase):
    _COLUMNS = (
        "id, actor_user_id, request_key, upload_key, purpose, state, storage_key, "
        "content_sha256, size_bytes, media_type, captured_at, capture_source, "
        "received_at, expires_at, lease_expires_at, evidence_id, "
        "delete_requested_at, delete_attempts"
    )

    # SELECT pg_advisory_xact_lock(actor_user_id) before counting/reserving.
    # SELECT ... FOR UPDATE rows by (actor_user_id, purpose, request_key, upload_key).
    # All attachment locks use ORDER BY id FOR UPDATE.
    # Cleanup uses FOR UPDATE SKIP LOCKED and excludes consumed rows.
