"""Ticket registration and order-of-work processing."""

from __future__ import annotations

import re
import secrets
from uuid import UUID

from api.contracts import (
    CitizenAttemptLookupInput,
    CitizenAttemptOutput,
    CitizenMatchInput,
    CitizenMatchesOutput,
    CitizenTicketConfirmation,
    CitizenTicketCreateInput,
    CitizenTicketRegistrationOutput,
    CitizenContributionAttemptOutput,
    CitizenContributionInput,
    CitizenContributionOutput,
    HistoryEventCreateInput,
    OperationResult,
    TicketAttentionInput,
    TicketAssignmentInput,
    TicketClosureReviewInput,
    TicketCreateInput,
    TicketFilters,
    TicketInsertInput,
    TicketOperationInput,
    TicketOutput,
    TicketUpdateInput,
    UNSET,
)
from api.enums import ActionName, StatusName
from api.errors import ApplicationError
from api.interfaces.repositories import (
    ActionRepositoryInterface,
    AddressRepositoryInterface,
    CrewRepositoryInterface,
    CitizenContributionRepositoryInterface,
    EvidenceRepositoryInterface,
    FailureTypeRepositoryInterface,
    HistoryEventRepositoryInterface,
    OperationAttemptRepositoryInterface,
    RoleRepositoryInterface,
    StatusRepositoryInterface,
    TicketRepositoryInterface,
    UserRepositoryInterface,
)
from api.security import CitizenAuthorizer, role_operation_authorizer
from api.services.operation_attempts import (
    citizen_registration_digest,
    citizen_contribution_digest,
    contribution_result_from_payload,
    contribution_result_payload,
    registration_result_from_payload,
    registration_result_payload,
)

from ..base import ServiceBase
from .citizen_ticket_validation import (
    validate_citizen_attempt_lookup,
    validate_citizen_match,
    validate_citizen_ticket_create,
)
from .evidence_attachment import EvidenceAttachment
from .ticket_matcher import TicketMatcher, _OPEN_STATUS_NAMES


class TicketService(ServiceBase):
    _REGISTER_CITIZEN_OPERATION = "TicketService.register_citizen"
    _FIND_CITIZEN_MATCHES_OPERATION = "TicketService.find_citizen_matches"
    _GET_CITIZEN_ATTEMPT_OPERATION = "TicketService.get_citizen_attempt"
    _CONTRIBUTE_CITIZEN_EVIDENCE_OPERATION = (
        "TicketService.contribute_citizen_evidence"
    )
    _GET_CITIZEN_CONTRIBUTION_ATTEMPT_OPERATION = (
        "TicketService.get_citizen_contribution_attempt"
    )

    def __init__(
        self,
        tickets: TicketRepositoryInterface,
        users: UserRepositoryInterface,
        failure_types: FailureTypeRepositoryInterface,
        statuses: StatusRepositoryInterface,
        actions: ActionRepositoryInterface,
        addresses: AddressRepositoryInterface | None = None,
        crews: CrewRepositoryInterface | None = None,
        evidences: EvidenceRepositoryInterface | None = None,
        events: HistoryEventRepositoryInterface | None = None,
        roles: RoleRepositoryInterface | None = None,
        operation_attempts: OperationAttemptRepositoryInterface | None = None,
        matcher: TicketMatcher | None = None,
        evidence_attachment: EvidenceAttachment | None = None,
        contributions: CitizenContributionRepositoryInterface | None = None,
        citizen_authorizer: CitizenAuthorizer | None = None,
        citizen_description_max_length: int = 4_000,
        **kwargs,
    ) -> None:
        if kwargs.get("authorizer") is None:
            kwargs["authorizer"] = role_operation_authorizer
        super().__init__(**kwargs)
        if type(citizen_description_max_length) is not int or citizen_description_max_length <= 0:
            raise ValueError("citizen_description_max_length must be a positive integer")
        self.tickets = tickets
        self.users = users
        self.failure_types = failure_types
        self.statuses = statuses
        self.actions = actions
        self.addresses = addresses
        self.crews = crews
        self.evidences = evidences
        self.events = events
        self.roles = roles
        self.operation_attempts = operation_attempts
        self.matcher = matcher
        self.evidence_attachment = evidence_attachment
        self.contributions = contributions
        self.citizen_authorizer = citizen_authorizer or CitizenAuthorizer()
        self.citizen_description_max_length = citizen_description_max_length

    @staticmethod
    def _out(value) -> TicketOutput:
        return TicketOutput(**vars(value))

    def _ticket(self, context, ticket_id: int):
        value = self.tickets.get_by_id(ticket_id)
        if value is None:
            raise self._missing("ticket", context)
        return value

    def create(self, context, data: TicketCreateInput) -> OperationResult[TicketOutput]:
        def work():
            if self.users.get_by_id(data.reported_by) is None:
                raise self._missing("user", context)
            if self.failure_types.get_by_id(data.failure_type_id) is None:
                raise self._missing("failure_type", context)
            if data.address_id is not None and (
                self.addresses is None or self.addresses.get_by_id(data.address_id) is None
            ):
                raise self._missing("address", context)
            status = self.statuses.get_by_name(StatusName.REGISTERED.value)
            action = self.actions.get_by_name(ActionName.REGISTRATION.value)
            if status is None:
                raise self._missing("status", context)
            if action is None:
                raise self._missing("action", context)
            if data.address_id is not None and self.matcher is not None:
                self.matcher.acquire_address_guard(
                    address_id=data.address_id,
                    failure_type_id=data.failure_type_id,
                )
                if self.matcher.find(
                    address_id=data.address_id,
                    failure_type_id=data.failure_type_id,
                    correlation_id=context.correlation_id,
                    lock=True,
                ).matches:
                    raise ApplicationError.unique_conflict(
                        "address_id",
                        entity="ticket",
                        correlation_id=context.correlation_id,
                    )
            ticket = self.tickets.create(
                TicketInsertInput(
                    code=data.code,
                    reported_by=data.reported_by,
                    failure_type_id=data.failure_type_id,
                    description=data.description,
                    status_id=status.id,
                    address_id=data.address_id,
                    contact_email=data.contact_email,
                    contact_phone=data.contact_phone,
                )
            )
            if self.events is not None:
                self.events.create(
                    HistoryEventCreateInput(
                        ticket.id,
                        action.id,
                        context.actor.user_id if context.actor else None,
                    )
                )
            return self._out(ticket)

        return self._run(context, "TicketService.create", work, write=True, actor_required=True)

    def register_citizen(
        self,
        context,
        data: CitizenTicketCreateInput,
    ) -> OperationResult[CitizenTicketRegistrationOutput]:
        def work():
            validate_citizen_ticket_create(
                data,
                description_max_length=self.citizen_description_max_length,
                correlation_id=context.correlation_id,
            )
            user = self._require_current_citizen(context, lock=True)
            attempts, matcher, events = self._citizen_registration_collaborators()
            digest = citizen_registration_digest(data)
            existing = attempts.get(
                actor_user_id=user.id,
                operation=self._REGISTER_CITIZEN_OPERATION,
                request_key=data.request_key,
            )
            if existing is not None:
                if existing.request_digest != digest:
                    raise ApplicationError.operation_key_reused(correlation_id=context.correlation_id)
                return self._registration_result_from_attempt(existing.result_payload, context)

            self._require_citizen_references(context, data.address_id, data.failure_type_id)
            matcher.acquire_address_guard(
                address_id=data.address_id,
                failure_type_id=data.failure_type_id,
            )
            prepared = self._attachment().prepare_attachment(
                context,
                request_key=data.request_key,
                upload_ids=_upload_ids(data.temporary_upload_ids),
            )
            matches = matcher.find(
                address_id=data.address_id,
                failure_type_id=data.failure_type_id,
                correlation_id=context.correlation_id,
                lock=True,
            )
            if matches.matches:
                result = CitizenTicketRegistrationOutput(
                    request_key=data.request_key,
                    outcome="matches",
                    ticket=None,
                    matches=matches.matches,
                )
            else:
                status = self._required_catalog(
                    self.statuses.get_by_name(StatusName.REGISTERED.value),
                    "status",
                    context,
                )
                action = self._required_catalog(
                    self.actions.get_by_name(ActionName.REGISTRATION.value),
                    "action",
                    context,
                )
                ticket = self._create_citizen_ticket(data, user.id, status.id, context)
                attached = self._attachment().attach_in_transaction(
                    context,
                    ticket_id=ticket.id,
                    request_key=data.request_key,
                    upload_ids=prepared.upload_ids,
                )
                events.create(HistoryEventCreateInput(ticket.id, action.id, user.id))
                result = CitizenTicketRegistrationOutput(
                    request_key=data.request_key,
                    outcome="created",
                    ticket=CitizenTicketConfirmation(
                        code=ticket.code,
                        created_at=ticket.created_at,
                        status=StatusName.REGISTERED.value,
                        evidence_count=len(attached.evidence_ids),
                        evidence_ids=attached.evidence_ids,
                    ),
                    matches=(),
                )
            attempts.create(
                actor_user_id=user.id,
                operation=self._REGISTER_CITIZEN_OPERATION,
                request_key=data.request_key,
                request_digest=digest,
                result_payload=registration_result_payload(result),
            )
            return result

        return self._run(
            context,
            self._REGISTER_CITIZEN_OPERATION,
            work,
            write=True,
            actor_required=True,
        )

    def find_citizen_matches(
        self,
        context,
        data: CitizenMatchInput,
    ) -> OperationResult[CitizenMatchesOutput]:
        def work():
            validate_citizen_match(data, correlation_id=context.correlation_id)
            self._require_current_citizen(context, lock=False)
            matcher = self._citizen_matcher()
            self._require_citizen_references(context, data.address_id, data.failure_type_id)
            return matcher.find(
                address_id=data.address_id,
                failure_type_id=data.failure_type_id,
                correlation_id=context.correlation_id,
            )

        return self._run(
            context,
            self._FIND_CITIZEN_MATCHES_OPERATION,
            work,
            actor_required=True,
        )

    def get_citizen_attempt(
        self,
        context,
        data: CitizenAttemptLookupInput,
    ) -> OperationResult[CitizenAttemptOutput]:
        def work():
            validate_citizen_attempt_lookup(data, correlation_id=context.correlation_id)
            user = self._require_current_citizen(context, lock=False)
            attempts = self._citizen_attempts()
            attempt = attempts.get(
                actor_user_id=user.id,
                operation=self._REGISTER_CITIZEN_OPERATION,
                request_key=data.request_key,
            )
            if attempt is None:
                return CitizenAttemptOutput(
                    request_key=data.request_key,
                    state="not_found",
                    result=None,
                )
            result = self._registration_result_from_attempt(attempt.result_payload, context)
            if result.request_key != data.request_key:
                raise ApplicationError.persistence_failure(correlation_id=context.correlation_id)
            return CitizenAttemptOutput(
                request_key=data.request_key,
                state="committed",
                result=result,
            )

        return self._run(
            context,
            self._GET_CITIZEN_ATTEMPT_OPERATION,
            work,
            actor_required=True,
        )

    def contribute_citizen_evidence(
        self,
        context,
        data: CitizenContributionInput,
    ) -> OperationResult[CitizenContributionOutput]:
        def work():
            if not isinstance(data, CitizenContributionInput):
                raise ApplicationError.invalid_value("data", "El aporte no es válido.", correlation_id=context.correlation_id)
            validate_citizen_attempt_lookup(CitizenAttemptLookupInput(data.request_key), correlation_id=context.correlation_id)
            validate_citizen_match(CitizenMatchInput(data.address_id, data.failure_type_id), correlation_id=context.correlation_id)
            if type(data.target_code) is not str or re.fullmatch(r"SGF-[0-9A-F]{20}", data.target_code) is None:
                raise ApplicationError.invalid_value("target_code", "El código no es válido.", correlation_id=context.correlation_id)
            if not isinstance(data.temporary_upload_ids, tuple) or not 1 <= len(data.temporary_upload_ids) <= 3 or any(not isinstance(value, UUID) for value in data.temporary_upload_ids) or len(set(data.temporary_upload_ids)) != len(data.temporary_upload_ids):
                raise ApplicationError.invalid_value("temporary_upload_ids", "Las fotografías no son válidas.", correlation_id=context.correlation_id)
            user = self._require_current_citizen(context, lock=True)
            attempts = self._citizen_attempts()
            digest = citizen_contribution_digest(data)
            attempt = attempts.get(actor_user_id=user.id, operation=self._CONTRIBUTE_CITIZEN_EVIDENCE_OPERATION, request_key=data.request_key)
            if attempt is not None:
                if attempt.request_digest != digest:
                    raise ApplicationError.operation_key_reused(correlation_id=context.correlation_id)
                return self._contribution_result_from_attempt(attempt.result_payload, data.request_key, context)
            if self.contributions is None:
                raise RuntimeError("contribution repository is required")
            self._require_citizen_references(context, data.address_id, data.failure_type_id)
            matcher = self._citizen_matcher()
            matcher.acquire_address_guard(address_id=data.address_id, failure_type_id=data.failure_type_id)
            ticket = self.tickets.get_by_code_for_update(data.target_code)
            if ticket is None or ticket.address_id != data.address_id or ticket.failure_type_id != data.failure_type_id:
                raise self._missing("ticket", context)
            status = self.statuses.get_by_id(ticket.status_id)
            if status is None or status.name.value not in _OPEN_STATUS_NAMES:
                raise ApplicationError.invalid_ticket_state(correlation_id=context.correlation_id)
            prepared = self._attachment().prepare_attachment(context, request_key=data.request_key, upload_ids=data.temporary_upload_ids)
            contribution = self.contributions.create(ticket_id=ticket.id, actor_user_id=user.id, request_key=data.request_key)
            attached = self._attachment().attach_in_transaction(
                context, ticket_id=ticket.id, request_key=data.request_key, upload_ids=prepared.upload_ids,
            )
            for evidence_id in attached.evidence_ids:
                self.contributions.create_evidence_link(contribution_id=contribution.id, evidence_id=evidence_id)
            result = CitizenContributionOutput(
                request_key=data.request_key, outcome="contributed", contribution_id=contribution.id,
                ticket_code=ticket.code, created_at=contribution.created_at,
                evidence_count=len(attached.evidence_ids), evidence_ids=attached.evidence_ids,
            )
            attempts.create(actor_user_id=user.id, operation=self._CONTRIBUTE_CITIZEN_EVIDENCE_OPERATION,
                            request_key=data.request_key, request_digest=digest, result_payload=contribution_result_payload(result))
            return result

        return self._run(context, self._CONTRIBUTE_CITIZEN_EVIDENCE_OPERATION, work, write=True, actor_required=True)

    def get_citizen_contribution_attempt(
        self,
        context,
        data: CitizenAttemptLookupInput,
    ) -> OperationResult[CitizenContributionAttemptOutput]:
        def work():
            validate_citizen_attempt_lookup(data, correlation_id=context.correlation_id)
            user = self._require_current_citizen(context, lock=False)
            attempt = self._citizen_attempts().get(
                actor_user_id=user.id, operation=self._CONTRIBUTE_CITIZEN_EVIDENCE_OPERATION, request_key=data.request_key,
            )
            if attempt is None:
                return CitizenContributionAttemptOutput(request_key=data.request_key, state="not_found", result=None)
            result = self._contribution_result_from_attempt(attempt.result_payload, data.request_key, context)
            return CitizenContributionAttemptOutput(request_key=data.request_key, state="committed", result=result)

        return self._run(context, self._GET_CITIZEN_CONTRIBUTION_ATTEMPT_OPERATION, work, actor_required=True)

    @staticmethod
    def _contribution_result_from_attempt(payload, request_key, context):
        try:
            result = contribution_result_from_payload(payload)
            if result.request_key != request_key:
                raise ValueError("stored request key does not match")
            return result
        except (TypeError, ValueError) as error:
            raise ApplicationError.persistence_failure(correlation_id=context.correlation_id, cause=error) from error

    def get_by_id(self, context, ticket_id: int) -> OperationResult[TicketOutput]:
        return self._run(
            context,
            "TicketService.get_by_id",
            lambda: self._out(self._ticket(context, ticket_id)),
        )

    def get_by_code(self, context, code: str) -> OperationResult[TicketOutput]:
        def work():
            value = self.tickets.get_by_code(code)
            if value is None:
                raise self._missing("ticket", context)
            return self._out(value)

        return self._run(context, "TicketService.get_by_code", work)

    def list_by_filters(
        self,
        context,
        filters: TicketFilters | None = None,
    ) -> OperationResult[list[TicketOutput]]:
        return self._run(
            context,
            "TicketService.list_by_filters",
            lambda: [self._out(value) for value in self.tickets.list_by_filters(filters)],
        )

    def _process(self, context, operation: str, ticket_id, action_name, allowed, update):
        def work():
            current = self._ticket(context, ticket_id)
            status = self.statuses.get_by_id(current.status_id)
            if status is None:
                raise self._missing("status", context)
            if status.name.value not in allowed:
                raise ApplicationError.invalid_ticket_state(correlation_id=context.correlation_id)
            action = self.actions.get_by_name(action_name.value)
            if action is None:
                raise self._missing("action", context)
            changed = self.tickets.update(update(current))
            if changed is None:
                raise self._missing("ticket", context)
            if self.events is not None:
                self.events.create(
                    HistoryEventCreateInput(
                        changed.id,
                        action.id,
                        context.actor.user_id if context.actor else None,
                    )
                )
            return self._out(changed)

        return self._run(context, operation, work, write=True, actor_required=True)

    def validate(self, context, data: TicketOperationInput) -> OperationResult[TicketOutput]:
        return self._process(
            context,
            "TicketService.validate",
            data.ticket_id,
            ActionName.VALIDATION,
            {StatusName.REGISTERED.value},
            lambda value: TicketUpdateInput(
                value.id,
                status_id=self.statuses.get_by_name(StatusName.VALIDATED.value).id,
            ),
        )

    def prioritize(self, context, data: TicketOperationInput) -> OperationResult[TicketOutput]:
        def update(value):
            failure = self.failure_types.get_by_id(value.failure_type_id)
            if failure is None:
                raise self._missing("failure_type", context)
            status = self.statuses.get_by_name(StatusName.PRIORITIZED.value)
            if status is None:
                raise self._missing("status", context)
            return TicketUpdateInput(value.id, status_id=status.id, priority_id=failure.priority_id)

        return self._process(
            context,
            "TicketService.prioritize",
            data.ticket_id,
            ActionName.PRIORITIZATION,
            {StatusName.VALIDATED.value},
            update,
        )

    def assign(self, context, data: TicketAssignmentInput) -> OperationResult[TicketOutput]:
        if self.crews is None:
            return self._run(
                context,
                "TicketService.assign",
                lambda: (_ for _ in ()).throw(self._missing("crew", context)),
                actor_required=True,
            )

        def update(value):
            if self.crews.get_by_id(data.crew_id) is None:
                raise self._missing("crew", context)
            status = self.statuses.get_by_name(StatusName.ASSIGNED.value)
            if status is None:
                raise self._missing("status", context)
            return TicketUpdateInput(value.id, status_id=status.id, crew_id=data.crew_id)

        return self._process(
            context,
            "TicketService.assign",
            data.ticket_id,
            ActionName.ASSIGNMENT,
            {StatusName.PRIORITIZED.value},
            update,
        )

    def record_attention(self, context, data: TicketAttentionInput) -> OperationResult[TicketOutput]:
        def update(value):
            status = self.statuses.get_by_name(StatusName.IN_PROGRESS.value)
            if status is None:
                raise self._missing("status", context)
            return TicketUpdateInput(
                value.id,
                status_id=status.id,
                diagnosis=data.diagnosis,
                solution=data.solution,
            )

        return self._process(
            context,
            "TicketService.record_attention",
            data.ticket_id,
            ActionName.ATTENTION,
            {StatusName.ASSIGNED.value, StatusName.IN_PROGRESS.value},
            update,
        )

    def block(self, context, data: TicketOperationInput) -> OperationResult[TicketOutput]:
        return self._process(
            context,
            "TicketService.block",
            data.ticket_id,
            ActionName.BLOCKAGE,
            {StatusName.IN_PROGRESS.value},
            lambda value: TicketUpdateInput(
                value.id,
                status_id=self.statuses.get_by_name(StatusName.BLOCKED.value).id,
            ),
        )

    def unblock(self, context, data: TicketOperationInput) -> OperationResult[TicketOutput]:
        def update(value):
            status = self.statuses.get_by_name(StatusName.IN_PROGRESS.value)
            if status is None:
                raise self._missing("status", context)
            return TicketUpdateInput(value.id, status_id=status.id)

        return self._process(
            context,
            "TicketService.unblock",
            data.ticket_id,
            ActionName.UNBLOCK,
            {StatusName.BLOCKED.value},
            update,
        )

    def request_closure(self, context, data: TicketOperationInput) -> OperationResult[TicketOutput]:
        def update(value):
            if not value.solution:
                raise ApplicationError.invalid_value(
                    "solution",
                    "La solución es obligatoria para solicitar el cierre.",
                    correlation_id=context.correlation_id,
                )
            if self.evidences is not None and not self.evidences.list_by_ticket(value.id):
                raise ApplicationError.invalid_value(
                    "evidence",
                    "Se requiere al menos una evidencia.",
                    correlation_id=context.correlation_id,
                )
            status = self.statuses.get_by_name(StatusName.PENDING_CLOSURE.value)
            if status is None:
                raise self._missing("status", context)
            return TicketUpdateInput(value.id, status_id=status.id)

        return self._process(
            context,
            "TicketService.request_closure",
            data.ticket_id,
            ActionName.CLOSURE_REQUEST,
            {StatusName.IN_PROGRESS.value},
            update,
        )

    def review_closure(
        self,
        context,
        data: TicketClosureReviewInput,
    ) -> OperationResult[TicketOutput]:
        decision = data.decision.lower()
        approved = decision == "approval"
        action = ActionName.APPROVAL if approved else ActionName.REJECTION
        target = StatusName.RESOLVED if approved else StatusName.IN_PROGRESS
        return self._process(
            context,
            "TicketService.review_closure",
            data.ticket_id,
            action,
            {StatusName.PENDING_CLOSURE.value},
            lambda value: TicketUpdateInput(
                value.id,
                status_id=self.statuses.get_by_name(target.value).id,
            ),
        )

    def _run(self, context, operation: str, work, *, write: bool = False, actor_required: bool = False):
        return self._execute(
            context,
            operation,
            work,
            write=write,
            actor_required=actor_required,
        )

    def _require_current_citizen(self, context, *, lock: bool):
        if context.actor is None:
            raise ApplicationError.access_token_required(correlation_id=context.correlation_id)
        if self.roles is None:
            raise RuntimeError("role repository is required for citizen ticket operations")
        user = (
            self.users.get_by_id_for_update(context.actor.user_id)
            if lock
            else self.users.get_by_id(context.actor.user_id)
        )
        role = self.roles.get_by_id(user.role_id) if user is not None else None
        self.citizen_authorizer.require_citizen(context, user=user, role=role)
        return user

    def _require_citizen_references(
        self,
        context,
        address_id: int,
        failure_type_id: int,
    ) -> None:
        if self.addresses is None or self.addresses.get_by_id(address_id) is None:
            raise ApplicationError.invalid_reference(
                "address_id",
                "La dirección indicada no existe.",
                entity="address",
                correlation_id=context.correlation_id,
            )
        if self.failure_types.get_by_id(failure_type_id) is None:
            raise ApplicationError.invalid_reference(
                "failure_type_id",
                "El tipo de falla indicado no existe.",
                entity="failure_type",
                correlation_id=context.correlation_id,
            )

    def _citizen_registration_collaborators(self):
        attempts = self._citizen_attempts()
        matcher = self._citizen_matcher()
        if self.events is None:
            raise RuntimeError("history-event repository is required for citizen ticket registration")
        return attempts, matcher, self.events

    def _attachment(self) -> EvidenceAttachment:
        if self.evidence_attachment is None:
            return EvidenceAttachment()
        return self.evidence_attachment

    def _citizen_attempts(self) -> OperationAttemptRepositoryInterface:
        if self.operation_attempts is None:
            raise RuntimeError("operation-attempt repository is required for citizen ticket operations")
        return self.operation_attempts

    def _citizen_matcher(self) -> TicketMatcher:
        if self.matcher is None:
            raise RuntimeError("ticket matcher is required for citizen ticket operations")
        return self.matcher

    @staticmethod
    def _required_catalog(value, entity: str, context):
        if value is None:
            raise ApplicationError.catalog_unavailable(entity, correlation_id=context.correlation_id)
        return value

    def _create_citizen_ticket(
        self,
        data: CitizenTicketCreateInput,
        reported_by: int,
        status_id: int,
        context,
    ):
        contact_email = None if data.contact_email is UNSET else data.contact_email
        contact_phone = None if data.contact_phone is UNSET else data.contact_phone
        for _ in range(5):
            ticket = self.tickets.create_if_code_available(
                TicketInsertInput(
                    code=f"SGF-{secrets.token_hex(10).upper()}",
                    reported_by=reported_by,
                    failure_type_id=data.failure_type_id,
                    description=data.description,
                    status_id=status_id,
                    address_id=data.address_id,
                    contact_email=contact_email,
                    contact_phone=contact_phone,
                )
            )
            if ticket is not None:
                return ticket
        raise ApplicationError.persistence_failure(correlation_id=context.correlation_id)

    @staticmethod
    def _registration_result_from_attempt(payload, context) -> CitizenTicketRegistrationOutput:
        try:
            return registration_result_from_payload(payload)
        except (TypeError, ValueError) as error:
            raise ApplicationError.persistence_failure(
                correlation_id=context.correlation_id,
                 cause=error,
             ) from error


def _upload_ids(value):
    return () if value is UNSET else value
