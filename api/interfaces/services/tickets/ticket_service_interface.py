from typing import Protocol

from api.contracts import (
    CitizenAttemptLookupInput,
    CitizenAttemptOutput,
    CitizenContributionAttemptOutput,
    CitizenContributionInput,
    CitizenContributionOutput,
    CitizenMatchInput,
    CitizenMatchesOutput,
    CitizenTicketCreateInput,
    CitizenTicketRegistrationOutput,
    ExecutionContext,
    OperationResult,
    TicketAssignmentInput,
    TicketAttentionInput,
    TicketClosureReviewInput,
    TicketCreateInput,
    TicketFilters,
    TicketOperationInput,
    TicketOutput,
)


class TicketServiceInterface(Protocol):
    def create(self, context: ExecutionContext, data: TicketCreateInput) -> OperationResult[TicketOutput]: ...
    def register_citizen(self, context: ExecutionContext, data: CitizenTicketCreateInput) -> OperationResult[CitizenTicketRegistrationOutput]: ...
    def find_citizen_matches(self, context: ExecutionContext, data: CitizenMatchInput) -> OperationResult[CitizenMatchesOutput]: ...
    def get_citizen_attempt(self, context: ExecutionContext, data: CitizenAttemptLookupInput) -> OperationResult[CitizenAttemptOutput]: ...
    def contribute_citizen_evidence(
        self,
        context: ExecutionContext,
        data: CitizenContributionInput,
    ) -> OperationResult[CitizenContributionOutput]:
        pass

    def get_citizen_contribution_attempt(
        self,
        context: ExecutionContext,
        data: CitizenAttemptLookupInput,
    ) -> OperationResult[CitizenContributionAttemptOutput]:
        pass
    def get_by_id(self, context: ExecutionContext, ticket_id: int) -> OperationResult[TicketOutput]: ...
    def get_by_code(self, context: ExecutionContext, code: str) -> OperationResult[TicketOutput]: ...
    def list_by_filters(self, context: ExecutionContext, filters: TicketFilters | None = None) -> OperationResult[list[TicketOutput]]: ...
    def validate(self, context: ExecutionContext, data: TicketOperationInput) -> OperationResult[TicketOutput]: ...
    def prioritize(self, context: ExecutionContext, data: TicketOperationInput) -> OperationResult[TicketOutput]: ...
    def assign(self, context: ExecutionContext, data: TicketAssignmentInput) -> OperationResult[TicketOutput]: ...
    def record_attention(self, context: ExecutionContext, data: TicketAttentionInput) -> OperationResult[TicketOutput]: ...
    def block(self, context: ExecutionContext, data: TicketOperationInput) -> OperationResult[TicketOutput]: ...
    def unblock(self, context: ExecutionContext, data: TicketOperationInput) -> OperationResult[TicketOutput]: ...
    def request_closure(self, context: ExecutionContext, data: TicketOperationInput) -> OperationResult[TicketOutput]: ...
    def review_closure(self, context: ExecutionContext, data: TicketClosureReviewInput) -> OperationResult[TicketOutput]: ...