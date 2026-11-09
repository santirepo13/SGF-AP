from uuid import UUID

from api.contracts import (
    CitizenEvidenceListOutput,
    CitizenEvidenceOutput,
    EvidenceContentDescriptor,
    EvidenceCreateInput,
    EvidenceOutput,
    OperationResult,
)
from api.interfaces.repositories import EvidenceRepositoryInterface, TicketRepositoryInterface, UserRepositoryInterface
from api.errors import ApplicationError, ErrorCode
from api.security import CitizenAuthorizer, role_operation_authorizer
from api.storage import EvidenceStorageUnavailable

from ..base import ServiceBase


class EvidenceService(ServiceBase):
    def __init__(
        self,
        evidences: EvidenceRepositoryInterface,
        tickets: TicketRepositoryInterface,
        users: UserRepositoryInterface,
        *,
        storage=None,
        roles=None,
        **kwargs,
    ):
        if kwargs.get("authorizer") is None:
            kwargs["authorizer"] = role_operation_authorizer
        super().__init__(**kwargs)
        self.evidences = evidences
        self.tickets = tickets
        self.users = users
        self.storage = storage
        self.roles = roles
        self.citizen_authorizer = CitizenAuthorizer()

    @staticmethod
    def _out(value):
        return EvidenceOutput(
            id=value.id,
            ticket_id=value.ticket_id,
            file_path="" if value.purpose == "report" else value.file_path,
            captured_at=value.captured_at,
            uploaded_by=value.uploaded_by,
            uploaded_at=value.uploaded_at,
            capture_source=value.capture_source,
            media_type=value.media_type,
            size_bytes=value.size_bytes,
            purpose=value.purpose,
        )

    def get_by_id(self, context, evidence_id: int) -> OperationResult[EvidenceOutput]:
        # Operational-only safe projection; never return file_path.
        def work():
            value = self.evidences.get_by_id(evidence_id)
            if value is None:
                raise self._missing("evidence", context)
            return self._out(value)

        return self._execute(context, "EvidenceService.get_by_id", work)

    def list_by_ticket(self, context, ticket_id: int) -> OperationResult[list[EvidenceOutput]]:
        # Operational-only safe projection; never return file_path.
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
        # Operational-only legacy entry; Citizens cannot provide file_path.
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

    def list_citizen_ticket_evidence(
        self,
        context,
        ticket_code: str,
    ) -> OperationResult[CitizenEvidenceListOutput]:
        def work():
            actor_id = self._citizen(context)
            ticket = self.tickets.get_by_code(ticket_code)
            if ticket is None or ticket.reported_by != actor_id:
                raise self._missing("ticket", context)
            values = self.evidences.list_citizen_ticket_evidence(ticket_code=ticket_code, actor_user_id=actor_id)
            return CitizenEvidenceListOutput(evidences=tuple(self._citizen_out(value) for value in values))

        return self._execute(context, "EvidenceService.list_citizen_ticket_evidence", work, actor_required=True)

    def list_citizen_contribution_evidence(
        self,
        context,
        contribution_id: str,
    ) -> OperationResult[CitizenEvidenceListOutput]:
        def work():
            actor_id = self._citizen(context)
            try:
                identifier = UUID(contribution_id)
            except (ValueError, TypeError, AttributeError) as error:
                raise ApplicationError.invalid_value("contribution_id", "El identificador no es válido.", correlation_id=context.correlation_id, cause=error) from error
            values = self.evidences.get_citizen_contribution_evidence(contribution_id=identifier, actor_user_id=actor_id)
            if values is None:
                raise self._missing("citizen_contribution", context)
            return CitizenEvidenceListOutput(evidences=tuple(self._citizen_out(value) for value in values))

        return self._execute(context, "EvidenceService.list_citizen_contribution_evidence", work, actor_required=True)

    def open_citizen_content(
        self,
        context,
        evidence_id: int,
    ) -> OperationResult[EvidenceContentDescriptor]:
        def work():
            actor_id = self._citizen(context)
            if type(evidence_id) is not int or evidence_id <= 0:
                raise ApplicationError.invalid_value("evidence_id", "El identificador no es válido.", correlation_id=context.correlation_id)
            value = self.evidences.get_citizen_owned_evidence(evidence_id=evidence_id, actor_user_id=actor_id)
            if value is None:
                value = self.evidences.get_citizen_contribution_evidence_by_id(evidence_id=evidence_id, actor_user_id=actor_id)
            if value is None:
                raise self._missing("evidence", context)
            extensions = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
            if self.storage is None or value.media_type not in extensions or value.size_bytes is None:
                raise ApplicationError.with_code(ErrorCode.EVIDENCE_STORAGE_UNAVAILABLE, correlation_id=context.correlation_id)
            try:
                handle = self.storage.open_read(value.file_path)
            except (OSError, EvidenceStorageUnavailable) as error:
                raise ApplicationError.with_code(ErrorCode.EVIDENCE_STORAGE_UNAVAILABLE, correlation_id=context.correlation_id, cause=error) from error
            if handle.size_bytes != value.size_bytes:
                handle.close()
                raise ApplicationError.with_code(ErrorCode.EVIDENCE_STORAGE_UNAVAILABLE, correlation_id=context.correlation_id)
            return EvidenceContentDescriptor(
                media_type=value.media_type, size_bytes=value.size_bytes,
                download_name=f"evidence-{value.id}.{extensions[value.media_type]}", stream=handle.stream,
            )

        return self._execute(context, "EvidenceService.open_citizen_content", work, actor_required=True)

    def _citizen(self, context):
        if context.actor is None:
            raise ApplicationError.access_token_required(correlation_id=context.correlation_id)
        if self.roles is None:
            raise ApplicationError.with_code(ErrorCode.EVIDENCE_STORAGE_UNAVAILABLE, correlation_id=context.correlation_id)
        user = self.users.get_by_id(context.actor.user_id)
        role = self.roles.get_by_id(user.role_id) if user is not None else None
        self.citizen_authorizer.require_citizen(context, user=user, role=role)
        return context.actor.user_id

    def _citizen_out(self, value):
        available = self.storage is not None and self.storage.exists(value.file_path)
        return CitizenEvidenceOutput(
            evidence_id=value.id, media_type=value.media_type, size_bytes=value.size_bytes,
            captured_at=value.captured_at, capture_source=value.capture_source,
            uploaded_at=value.uploaded_at, content_available=available,
        )
