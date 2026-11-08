"""Transactional temporary-upload consumption for reports and contributions."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PreparedAttachment:
    upload_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class AttachedEvidence:
    evidence_ids: tuple[int, ...]


class EvidenceAttachment:
    def prepare_attachment(
        self,
        context,
        *,
        request_key: str,
        upload_ids: tuple[UUID, ...],
    ) -> PreparedAttachment:
        # 0..3 ordered, unique IDs; actor identity derives from context.
        # No state transition occurs here.
        ...

    def attach_in_transaction(
        self,
        context,
        *,
        ticket_id: int,
        request_key: str,
        upload_ids: tuple[UUID, ...],
    ) -> AttachedEvidence:
        # Lock ready uploads by UUID in stable order.
        # Require actor + request_key + report purpose + unexpired ready state.
        # Verify private objects still exist and match recorded immutable metadata.
        # Enforce <= 3 report evidences per actor/ticket under ticket lock.
        # Insert evidence metadata and mark each upload consumed in this transaction.
        # Rollback leaves ready uploads reusable until expiry.
        ...
