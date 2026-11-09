from __future__ import annotations

from uuid import UUID, uuid4

from api.models import CitizenContribution

from ..mapping import citizen_contribution
from ..persistence import RepositoryBase


class CitizenContributionRepository(RepositoryBase):
    _COLUMNS = "id, ticket_id, actor_user_id, request_key, created_at"

    def create(
        self,
        *,
        ticket_id: int,
        actor_user_id: int,
        request_key: str,
    ) -> CitizenContribution:
        return self.execute_one(
            "INSERT INTO citizen_contributions "
            "(id, ticket_id, actor_user_id, request_key) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (ticket_id, actor_user_id, request_key) "
            "DO UPDATE SET request_key = EXCLUDED.request_key "
            f"RETURNING {self._COLUMNS}",
            (uuid4(), ticket_id, actor_user_id, request_key),
            operation="citizen_contributions.create",
            entity="citizen_contribution",
            mapper=citizen_contribution,
        )

    def create_evidence_link(
        self,
        *,
        contribution_id: UUID,
        evidence_id: int,
    ) -> None:
        linked = self.execute_one(
            "INSERT INTO citizen_contribution_evidences "
            "(contribution_id, evidence_id) VALUES (%s, %s) "
            "ON CONFLICT (evidence_id) DO NOTHING RETURNING evidence_id",
            (contribution_id, evidence_id),
            operation="citizen_contributions.create_evidence_link",
            entity="citizen_contribution",
            mapper=lambda row: row["evidence_id"],
        )
        if linked is None:
            raise RuntimeError("evidence is already linked to a contribution")

    def list_evidence_ids_for_actor(
        self,
        *,
        contribution_id: UUID,
        actor_user_id: int,
    ) -> list[int] | None:
        owned = self.fetch_one(
            "SELECT id FROM citizen_contributions "
            "WHERE id = %s AND actor_user_id = %s",
            (contribution_id, actor_user_id),
            operation="citizen_contributions.get_owned",
            entity="citizen_contribution",
            mapper=lambda row: row["id"],
        )
        if owned is None:
            return None
        return self.fetch_all(
            "SELECT evidence_id FROM citizen_contribution_evidences "
            "WHERE contribution_id = %s ORDER BY evidence_id",
            (contribution_id,),
            operation="citizen_contributions.list_evidence_ids",
            entity="citizen_contribution",
            mapper=lambda row: int(row["evidence_id"]),
        )
