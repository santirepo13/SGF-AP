from api.contracts import EvidenceCreateInput
from ..mapping import evidence
from ..persistence import RepositoryBase


class EvidenceRepository(RepositoryBase):
    _columns = (
        "id, ticket_id, file_path, captured_at, uploaded_by, uploaded_at, "
        "capture_source, media_type, size_bytes, purpose"
    )

    def get_by_id(self, evidence_id: int):
        return self.fetch_one(
            f"SELECT {self._columns} FROM evidences WHERE id = %s",
            (evidence_id,),
            operation="evidences.get_by_id",
            entity="evidence",
            mapper=evidence,
        )

    def list_by_ticket(self, ticket_id: int):
        return self.fetch_all(
            f"SELECT {self._columns} FROM evidences WHERE ticket_id = %s ORDER BY id",
            (ticket_id,),
            operation="evidences.list_by_ticket",
            entity="evidence",
            mapper=evidence,
        )

    def list_by_ticket_and_uploader(self, ticket_id: int, uploaded_by: int):
        return self.fetch_all(
            f"SELECT {self._columns} FROM evidences "
            "WHERE ticket_id = %s AND uploaded_by = %s ORDER BY id",
            (ticket_id, uploaded_by),
            operation="evidences.list_by_ticket_and_uploader",
            entity="evidence",
            mapper=evidence,
        )

    def create(self, data: EvidenceCreateInput):
        return self.execute_one(
            "INSERT INTO evidences "
            "(ticket_id, file_path, captured_at, uploaded_by, uploaded_at, "
            "capture_source, media_type, size_bytes, purpose) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
            f"RETURNING {self._columns}",
            (
                data.ticket_id,
                data.file_path,
                data.captured_at,
                data.uploaded_by,
                data.uploaded_at,
                data.capture_source,
                data.media_type,
                data.size_bytes,
                data.purpose,
            ),
            operation="evidences.create",
            entity="evidence",
            mapper=evidence,
        )

    def count_report_evidence_for_actor_for_update(self, *, ticket_id, actor_user_id):
        rows = self.fetch_all(
            "SELECT id FROM evidences "
            "WHERE ticket_id = %s AND uploaded_by = %s AND purpose = 'report' "
            "FOR UPDATE",
            (ticket_id, actor_user_id),
            operation="evidences.count_report_evidence_for_actor_for_update",
            entity="evidence",
            mapper=lambda row: row["id"],
        )
        return len(rows)

    def create_from_upload(
        self,
        *,
        ticket_id: int,
        storage_key: str,
        captured_at,
        uploaded_by: int,
        uploaded_at,
        capture_source: str,
        media_type: str,
        size_bytes: int,
    ):
        return self.execute_one(
            "INSERT INTO evidences "
            "(ticket_id, file_path, captured_at, uploaded_by, uploaded_at, "
            "capture_source, media_type, size_bytes, purpose) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'report') "
            f"RETURNING {self._columns}",
            (
                ticket_id,
                storage_key,
                captured_at,
                uploaded_by,
                uploaded_at,
                capture_source,
                media_type,
                size_bytes,
            ),
            operation="evidences.create_from_upload",
            entity="evidence",
            mapper=evidence,
        )

    def list_citizen_ticket_evidence(self, *, ticket_code: str, actor_user_id: int):
        return self.fetch_all(
            f"SELECT e.{self._columns.replace(', ', ', e.')} "
            "FROM evidences e JOIN tickets t ON t.id = e.ticket_id "
            "WHERE t.code = %s AND t.reported_by = %s AND e.purpose = 'report' "
            "AND e.uploaded_by = t.reported_by "
            "AND NOT EXISTS (SELECT 1 FROM citizen_contribution_evidences ce "
            "WHERE ce.evidence_id = e.id) "
            "ORDER BY e.id",
            (ticket_code, actor_user_id),
            operation="evidences.list_citizen_ticket_evidence",
            entity="evidence",
            mapper=evidence,
        )

    def get_citizen_owned_evidence(self, *, evidence_id: int, actor_user_id: int):
        return self.fetch_one(
            f"SELECT e.{self._columns.replace(', ', ', e.')} "
            "FROM evidences e JOIN tickets t ON t.id = e.ticket_id "
            "WHERE e.id = %s AND ("
            "  (e.purpose = 'report' AND t.reported_by = %s "
            "   AND e.uploaded_by = t.reported_by "
            "   AND NOT EXISTS (SELECT 1 FROM citizen_contribution_evidences ce "
            "                   WHERE ce.evidence_id = e.id)) "
            "  OR (COALESCE(e.purpose, 'legacy') = 'legacy' AND e.uploaded_by = %s)"
            ")",
            (evidence_id, actor_user_id, actor_user_id),
            operation="evidences.get_citizen_owned_evidence",
            entity="evidence",
            mapper=evidence,
        )

    def get_citizen_contribution_evidence_by_id(
        self,
        *,
        evidence_id: int,
        actor_user_id: int,
    ):
        return self.fetch_one(
            f"SELECT e.{self._columns.replace(', ', ', e.')} "
            "FROM evidences e "
            "JOIN citizen_contribution_evidences ce ON ce.evidence_id = e.id "
            "JOIN citizen_contributions c ON c.id = ce.contribution_id "
            "WHERE e.id = %s AND c.actor_user_id = %s",
            (evidence_id, actor_user_id),
            operation="evidences.get_citizen_contribution_evidence_by_id",
            entity="evidence",
            mapper=evidence,
        )

    def get_citizen_contribution_evidence(
        self,
        *,
        contribution_id: str,
        actor_user_id: int,
    ):
        owned = self.fetch_one(
            "SELECT id FROM citizen_contributions "
            "WHERE id = %s AND actor_user_id = %s",
            (contribution_id, actor_user_id),
            operation="evidences.get_citizen_contribution_owner",
            entity="citizen_contribution",
            mapper=lambda row: row["id"],
        )
        if owned is None:
            return None
        return self.fetch_all(
            f"SELECT e.{self._columns.replace(', ', ', e.')} "
            "FROM evidences e "
            "JOIN citizen_contribution_evidences ce ON ce.evidence_id = e.id "
            "WHERE ce.contribution_id = %s ORDER BY e.id",
            (contribution_id,),
            operation="evidences.get_citizen_contribution_evidence",
            entity="evidence",
            mapper=evidence,
        )
