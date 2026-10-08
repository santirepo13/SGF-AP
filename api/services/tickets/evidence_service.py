from api.contracts import EvidenceCreateInput, EvidenceOutput, OperationResult
from api.interfaces.repositories import EvidenceRepositoryInterface, TicketRepositoryInterface, UserRepositoryInterface
from ..base import ServiceBase

class EvidenceService(ServiceBase):
    def __init__(self, evidences: EvidenceRepositoryInterface, tickets: TicketRepositoryInterface, users: UserRepositoryInterface, **kwargs): super().__init__(**kwargs); self.evidences, self.tickets, self.users = evidences, tickets, users
    @staticmethod
    def _out(x): return EvidenceOutput(id=x.id, ticket_id=x.ticket_id, file_path=x.file_path, captured_at=x.captured_at, uploaded_by=x.uploaded_by)
    def get_by_id(self, context, evidence_id: int) -> OperationResult[EvidenceOutput]:
        def work():
            value = self.evidences.get_by_id(evidence_id)
            if value is None: raise self._missing("evidence", context)
            return self._out(value)
        return self._execute(context, context.operation, work)
    def list_by_ticket(self, context, ticket_id: int) -> OperationResult[list[EvidenceOutput]]: return self._execute(context, context.operation, lambda: [self._out(x) for x in self.evidences.list_by_ticket(ticket_id)])
    def list_by_ticket_and_uploader(self, context, ticket_id: int, uploaded_by: int) -> OperationResult[list[EvidenceOutput]]: return self._execute(context, context.operation, lambda: [self._out(x) for x in self.evidences.list_by_ticket_and_uploader(ticket_id, uploaded_by)])
    def create_metadata(self, context, data: EvidenceCreateInput) -> OperationResult[EvidenceOutput]:
        def work():
            if self.tickets.get_by_id(data.ticket_id) is None: raise self._missing("ticket", context)
            if self.users.get_by_id(data.uploaded_by) is None: raise self._missing("user", context)
            return self._out(self.evidences.create(data))
        return self._execute(context, context.operation, work, write=True, actor_required=True)
