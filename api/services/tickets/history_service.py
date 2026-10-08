from api.contracts import HistoryEventCreateInput, HistoryEventOutput, OperationResult
from api.interfaces.repositories import ActionRepositoryInterface, HistoryEventRepositoryInterface, TicketRepositoryInterface
from ..base import ServiceBase

class HistoryService(ServiceBase):
    def __init__(self, events: HistoryEventRepositoryInterface, tickets: TicketRepositoryInterface, actions: ActionRepositoryInterface, **kwargs): super().__init__(**kwargs); self.events, self.tickets, self.actions = events, tickets, actions
    @staticmethod
    def _out(x): return HistoryEventOutput(x.id, x.ticket_id, x.user_id, x.action_id, x.event_time)
    def get_event(self, context, event_id: int) -> OperationResult[HistoryEventOutput]:
        def work():
            value = self.events.get_by_id(event_id)
            if value is None: raise self._missing("history_event", context)
            return self._out(value)
        return self._execute(context, context.operation, work)
    def list_by_ticket(self, context, ticket_id: int) -> OperationResult[list[HistoryEventOutput]]: return self._execute(context, context.operation, lambda: [self._out(x) for x in self.events.list_by_ticket(ticket_id)])
    def create_event(self, context, data: HistoryEventCreateInput) -> OperationResult[HistoryEventOutput]:
        def work():
            if self.tickets.get_by_id(data.ticket_id) is None: raise self._missing("ticket", context)
            if self.actions.get_by_id(data.action_id) is None: raise self._missing("action", context)
            return self._out(self.events.create(data))
        return self._execute(context, context.operation, work, write=True, actor_required=True)
