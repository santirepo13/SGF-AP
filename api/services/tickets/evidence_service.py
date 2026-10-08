from api.contracts import EvidenceCreateInput, EvidenceOutput
from api.interfaces.repositories import EvidenceRepositoryInterface, TicketRepositoryInterface, UserRepositoryInterface
from ..base import ServiceBase

class EvidenceService(ServiceBase):
    def __init__(self, evidences: EvidenceRepositoryInterface, tickets: TicketRepositoryInterface, users: UserRepositoryInterface, **kwargs): super().__init__(**kwargs); self.evidences, self.tickets, self.users = evidences, tickets, users
    @staticmethod
    def _out(x): return EvidenceOutput(id=x.id, ticket_id=x.ticket_id, file_path=x.file_path, captured_at=x.captured_at, uploaded_by=x.uploaded_by)
    def obtener_por_id(self, context, evidence_id: int): return self._execute(context, context.operation, lambda: self._out(x) if (x := self.evidences.get_by_id(evidence_id)) else None)
    def listar_por_ticket(self, context, ticket_id: int): return self._execute(context, context.operation, lambda: [self._out(x) for x in self.evidences.list_by_ticket(ticket_id)])
    def listar_por_ticket_y_usuario(self, context, ticket_id: int, uploaded_by: int): return self._execute(context, context.operation, lambda: [self._out(x) for x in self.evidences.list_by_ticket_and_uploader(ticket_id, uploaded_by)])
    def registrar_metadatos(self, context, data: EvidenceCreateInput):
        def work():
            if self.tickets.get_by_id(data.ticket_id) is None: raise self._missing("ticket", context)
            if self.users.get_by_id(data.uploaded_by) is None: raise self._missing("user", context)
            return self._out(self.evidences.create(data))
        return self._execute(context, context.operation, work, write=True, actor_required=True)
