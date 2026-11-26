from api.contracts import HistoryEventCreateInput, HistoryEventOutput, OperationResult
from api.enums import RoleName
from api.interfaces.repositories import ActionRepositoryInterface, HistoryEventRepositoryInterface, TicketRepositoryInterface
from api.security import role_operation_authorizer

from ..base import ServiceBase


class HistoryService(ServiceBase):
    def __init__(
        self,
        events: HistoryEventRepositoryInterface,
        tickets: TicketRepositoryInterface,
        actions: ActionRepositoryInterface,
        crew_members=None,
        **kwargs,
    ):
        if kwargs.get("authorizer") is None:
            kwargs["authorizer"] = role_operation_authorizer
        super().__init__(**kwargs)
        self.events = events
        self.tickets = tickets
        self.actions = actions
        self.crew_members = crew_members

    @staticmethod
    def _out(value):
        return HistoryEventOutput(
            value.id,
            value.ticket_id,
            value.user_id,
            value.action_id,
            value.event_time,
        )

    def get_event(self, context, event_id: int) -> OperationResult[HistoryEventOutput]:
        def work():
            value = self.events.get_by_id(event_id)
            if value is None:
                raise self._missing("history_event", context)
            ticket = self.tickets.get_by_id(value.ticket_id)
            self._require_ticket_resource(context, ticket)
            return self._out(value)

        return self._execute(context, "HistoryService.get_event", work, actor_required=True)

    def list_by_ticket(self, context, ticket_id: int) -> OperationResult[list[HistoryEventOutput]]:
        def work():
            ticket = self.tickets.get_by_id(ticket_id)
            if ticket is None:
                raise self._missing("ticket", context)
            self._require_ticket_resource(context, ticket)
            return [self._out(value) for value in self.events.list_by_ticket(ticket_id)]

        return self._execute(
            context,
            "HistoryService.list_by_ticket",
            work,
            actor_required=True,
        )

    def _require_ticket_resource(self, context, ticket) -> None:
        if ticket is None:
            raise self._missing("ticket", context)
        actor = context.actor
        if actor is None or getattr(getattr(actor, "public_user", None), "role_name", None) != RoleName.CREW.value:
            return
        membership = self.crew_members.get_by_user_id(actor.user_id) if self.crew_members is not None else None
        if ticket is None or membership is None or membership.crew_id != ticket.crew_id:
            raise self._missing("ticket", context)

    def create_event(self, context, data: HistoryEventCreateInput) -> OperationResult[HistoryEventOutput]:
        def work():
            if self.tickets.get_by_id(data.ticket_id) is None:
                raise self._missing("ticket", context)
            if self.actions.get_by_id(data.action_id) is None:
                raise self._missing("action", context)
            return self._out(self.events.create(data))

        return self._execute(
            context,
            "HistoryService.create_event",
            work,
            write=True,
            actor_required=True,
        )
