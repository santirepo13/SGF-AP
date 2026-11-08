"""Single-file multipart parser with explicit text/file cardinality limits."""

from __future__ import annotations


async def read_single_evidence_multipart(
    request,
    *,
    correlation_id: str,
):
    # Enforce:
    # - Content-Type multipart/form-data with boundary
    # - exactly file + request_key + upload_key + capture_source
    # - optional captured_at
    # - no duplicate fields, no unknown fields, no additional file parts
    # - total non-file envelope <= configured 64 KiB
    # - no full arbitrary file body held in application memory
    # - parser/proxy/spool limits sourced from EvidenceStorageConfig
    ...
