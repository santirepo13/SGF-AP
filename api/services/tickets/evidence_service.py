from api.contracts import EvidenceCreateInput, EvidenceOutput, OperationResult
from api.interfaces.repositories import EvidenceRepositoryInterface, TicketRepositoryInterface, UserRepositoryInterface
from api.security import role_operation_authorizer

from ..base import ServiceBase


class EvidenceService(ServiceBase):
    def __init__(
        self,
        evidences: EvidenceRepositoryInterface,
        tickets: TicketRepositoryInterface,
        users: UserRepositoryInterface,
        **kwargs,
    ):
        if kwargs.get("authorizer") is None:
            kwargs["authorizer"] = role_operation_authorizer
        super().__init__(**kwargs)
        self.evidences = evidences
        self.tickets = tickets
        self.users = users

    @staticmethod
    def _out(value):
        return EvidenceOutput(
            id=value.id,
            ticket_id=value.ticket_id,
            file_path=value.file_path,
            captured_at=value.captured_at,
            uploaded_by=value.uploaded_by,
        )

    def get_by_id(self, context, evidence_id: int) -> OperationResult[EvidenceOutput]:
        def work():
            value = self.evidences.get_by_id(evidence_id)
            if value is None:
                raise self._missing("evidence", context)
            return self._out(value)

        return self._execute(context, "EvidenceService.get_by_id", work)

    def list_by_ticket(self, context, ticket_id: int) -> OperationResult[list[EvidenceOutput]]:
        return self._execute(
            context,
            "EvidenceService.list_by_ticket",
            lambda: [self._out(value) for value in self.evidences.list_by_ticket(ticket_id)],
        )

    def list_by_ticket_and_uploader(
        self,
        context,
        ticket_id: int,
        uploaded_by: int,
    ) -> OperationResult[list[EvidenceOutput]]:
        return self._execute(
            context,
            "EvidenceService.list_by_ticket_and_uploader",
            lambda: [
                self._out(value)
                for value in self.evidences.list_by_ticket_and_uploader(ticket_id, uploaded_by)
            ],
        )

    def create_metadata(self, context, data: EvidenceCreateInput) -> OperationResult[EvidenceOutput]:
        def work():
            if self.tickets.get_by_id(data.ticket_id) is None:
                raise self._missing("ticket", context)
            if self.users.get_by_id(data.uploaded_by) is None:
                raise self._missing("user", context)
            return self._out(self.evidences.create(data))

        return self._execute(
            context,
            "EvidenceService.create_metadata",
            work,
            write=True,
            actor_required=True,
        )
