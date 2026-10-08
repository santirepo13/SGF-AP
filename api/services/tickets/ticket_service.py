"""Ticket registration and order-of-work processing."""
from api.contracts import TicketAttentionInput, TicketAssignmentInput, TicketClosureReviewInput, TicketCreateInput, TicketFilters, TicketOperationInput, TicketOutput, TicketUpdateInput, HistoryEventCreateInput
from api.enums import ActionName, StatusName
from api.interfaces.repositories import ActionRepositoryInterface, AddressRepositoryInterface, CrewRepositoryInterface, EvidenceRepositoryInterface, FailureTypeRepositoryInterface, HistoryEventRepositoryInterface, StatusRepositoryInterface, TicketRepositoryInterface, UserRepositoryInterface
from ..base import ServiceBase

class TicketService(ServiceBase):
    def __init__(self, tickets: TicketRepositoryInterface, users: UserRepositoryInterface, failure_types: FailureTypeRepositoryInterface, statuses: StatusRepositoryInterface, actions: ActionRepositoryInterface, addresses: AddressRepositoryInterface | None = None, crews: CrewRepositoryInterface | None = None, evidences: EvidenceRepositoryInterface | None = None, events: HistoryEventRepositoryInterface | None = None, **kwargs):
        super().__init__(**kwargs); self.tickets, self.users, self.failure_types, self.statuses, self.actions = tickets, users, failure_types, statuses, actions; self.addresses, self.crews, self.evidences, self.events = addresses, crews, evidences, events
    @staticmethod
    def _out(x): return TicketOutput(**vars(x))
    def _ticket(self, context, ticket_id):
        value = self.tickets.get_by_id(ticket_id)
        if value is None: raise self._missing("ticket", context)
        return value
    def registrar(self, context, data: TicketCreateInput):
        def work():
            if self.users.get_by_id(data.reported_by) is None: raise self._missing("user", context)
            if self.failure_types.get_by_id(data.failure_type_id) is None: raise self._missing("failure_type", context)
            if data.address_id is not None and (self.addresses is None or self.addresses.get_by_id(data.address_id) is None): raise self._missing("address", context)
            status = self.statuses.get_by_name(StatusName.REGISTERED.value); action = self.actions.get_by_name(ActionName.REGISTRATION.value)
            if status is None: raise self._missing("status", context)
            if action is None: raise self._missing("action", context)
            ticket = self.tickets.create(data)
            if self.events is not None: self.events.create(HistoryEventCreateInput(ticket.id, action.id, context.actor.user_id if context.actor else None))
            return self._out(ticket)
        return self._execute(context, context.operation, work, write=True, actor_required=True)
    def obtener_por_id(self, context, ticket_id: int): return self._execute(context, context.operation, lambda: self._out(self._ticket(context, ticket_id)))
    def obtener_por_codigo(self, context, code: str): return self._execute(context, context.operation, lambda: self._out(x) if (x := self.tickets.get_by_code(code)) else None)
    def listar_por_filtros(self, context, filters: TicketFilters | None = None): return self._execute(context, context.operation, lambda: [self._out(x) for x in self.tickets.list_by_filters(filters)])
    def _process(self, context, ticket_id, action_name, allowed, update):
        def work():
            current = self._ticket(context, ticket_id); status = self.statuses.get_by_id(current.status_id)
            if status is None: raise self._missing("status", context)
            if status.name.value not in allowed: raise __import__("api.errors", fromlist=["ApplicationError"]).ApplicationError.invalid_ticket_state(correlation_id=context.correlation_id)
            action = self.actions.get_by_name(action_name.value)
            if action is None: raise self._missing("action", context)
            changed = self.tickets.update(update(current))
            if changed is None: raise self._missing("ticket", context)
            if self.events is not None: self.events.create(HistoryEventCreateInput(changed.id, action.id, context.actor.user_id if context.actor else None))
            return self._out(changed)
        return self._execute(context, context.operation, work, write=True, actor_required=True)
    def validar(self, context, data: TicketOperationInput):
        return self._process(context, data.ticket_id, ActionName.VALIDATION, {StatusName.REGISTERED.value}, lambda x: TicketUpdateInput(x.id, status_id=self.statuses.get_by_name(StatusName.VALIDATED.value).id))
    def priorizar(self, context, data: TicketOperationInput):
        def update(x):
            failure = self.failure_types.get_by_id(x.failure_type_id)
            if failure is None: raise self._missing("failure_type", context)
            status = self.statuses.get_by_name(StatusName.PRIORITIZED.value)
            if status is None: raise self._missing("status", context)
            return TicketUpdateInput(x.id, status_id=status.id, priority_id=failure.priority_id)
        return self._process(context, data.ticket_id, ActionName.PRIORITIZATION, {StatusName.VALIDATED.value}, update)
    def asignar(self, context, data: TicketAssignmentInput):
        if self.crews is None: return self._execute(context, context.operation, lambda: (_ for _ in ()).throw(self._missing("crew", context)), actor_required=True)
        def update(x):
            if self.crews.get_by_id(data.crew_id) is None: raise self._missing("crew", context)
            status = self.statuses.get_by_name(StatusName.ASSIGNED.value)
            if status is None: raise self._missing("status", context)
            return TicketUpdateInput(x.id, status_id=status.id, crew_id=data.crew_id)
        return self._process(context, data.ticket_id, ActionName.ASSIGNMENT, {StatusName.PRIORITIZED.value}, update)
    def registrar_atencion(self, context, data: TicketAttentionInput):
        def update(x):
            status = self.statuses.get_by_name(StatusName.IN_PROGRESS.value)
            if status is None: raise self._missing("status", context)
            return TicketUpdateInput(x.id, status_id=status.id, diagnosis=data.diagnosis, solution=data.solution)
        return self._process(context, data.ticket_id, ActionName.ATTENTION, {StatusName.ASSIGNED.value, StatusName.IN_PROGRESS.value}, update)
    def bloquear(self, context, data: TicketOperationInput):
        return self._process(context, data.ticket_id, ActionName.BLOCKAGE, {StatusName.IN_PROGRESS.value}, lambda x: TicketUpdateInput(x.id, status_id=self.statuses.get_by_name(StatusName.BLOCKED.value).id))
    def solicitar_cierre(self, context, data: TicketOperationInput):
        def update(x):
            if not x.solution: raise __import__("api.errors", fromlist=["ApplicationError"]).ApplicationError.invalid_value("solution", "La solución es obligatoria para solicitar el cierre.", correlation_id=context.correlation_id)
            if self.evidences is not None and not self.evidences.list_by_ticket(x.id): raise __import__("api.errors", fromlist=["ApplicationError"]).ApplicationError.invalid_value("evidence", "Se requiere al menos una evidencia.", correlation_id=context.correlation_id)
            status = self.statuses.get_by_name(StatusName.PENDING_CLOSURE.value)
            if status is None: raise self._missing("status", context)
            return TicketUpdateInput(x.id, status_id=status.id)
        return self._process(context, data.ticket_id, ActionName.CLOSURE_REQUEST, {StatusName.IN_PROGRESS.value, StatusName.RESOLVED.value}, update)
    def revisar_cierre(self, context, data: TicketClosureReviewInput):
        decision = data.decision.lower()
        approved = decision == "approval"
        action = ActionName.APPROVAL if approved else ActionName.REJECTION
        target = StatusName.RESOLVED if approved else StatusName.IN_PROGRESS
        return self._process(context, data.ticket_id, action, {StatusName.PENDING_CLOSURE.value}, lambda x: TicketUpdateInput(x.id, status_id=self.statuses.get_by_name(target.value).id))
