from api.contracts import EvidenceCreateInput
from ..mapping import evidence
from ..persistence import RepositoryBase
class EvidenceRepository(RepositoryBase):
    _columns = "id, ticket_id, file_path, captured_at, uploaded_by"
    def get_by_id(self, evidence_id: int): return self.fetch_one(f"SELECT {self._columns} FROM evidences WHERE id = %s", (evidence_id,), operation="evidences.get_by_id", entity="evidence", mapper=evidence)
    def list_by_ticket(self, ticket_id: int): return self.fetch_all(f"SELECT {self._columns} FROM evidences WHERE ticket_id = %s ORDER BY id", (ticket_id,), operation="evidences.list_by_ticket", entity="evidence", mapper=evidence)
    def list_by_ticket_and_uploader(self, ticket_id: int, uploaded_by: int): return self.fetch_all(f"SELECT {self._columns} FROM evidences WHERE ticket_id = %s AND uploaded_by = %s ORDER BY id", (ticket_id, uploaded_by), operation="evidences.list_by_ticket_and_uploader", entity="evidence", mapper=evidence)
    def create(self, data: EvidenceCreateInput): return self.execute_one(f"INSERT INTO evidences (ticket_id, file_path, captured_at, uploaded_by) VALUES (%s, %s, %s, %s) RETURNING {self._columns}", (data.ticket_id, data.file_path, data.captured_at, data.uploaded_by), operation="evidences.create", entity="evidence", mapper=evidence)
