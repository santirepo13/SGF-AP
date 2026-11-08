"""Explicit execution policies for the service operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from api.contracts import (
    AddressComponentsInput, AddressCreateInput, CitizenAttemptLookupInput,
    CitizenRegistrationInput, CitizenMatchInput, CitizenTicketCreateInput,
    CrewCreateInput, CrewMemberInput, CrewUpdateInput, EvidenceCreateInput,
    EvidenceUploadInput, EvidenceUploadLookupInput, CitizenContributionInput,
    HistoryEventCreateInput,
    TicketAssignmentInput, TicketAttentionInput, TicketClosureReviewInput,
    TicketCreateInput, TicketOperationInput, UserActivationInput,
    UserCreateInput, UserLoginInput, UserUpdateInput,
    PasswordRecoveryRequestInput, PasswordRecoveryVerifyInput, PasswordResetInput,
)


@dataclass(frozen=True)
class OperationPolicy:
    actor_required: bool = False
    permission: str | None = None
    input_types: tuple[type[Any], ...] = ()
    resolve_actor: bool = True


def _policies() -> dict[str, OperationPolicy]:
    public = OperationPolicy()
    actor = OperationPolicy(actor_required=True, permission="execute")
    return {
        **{f"CatalogService.{name}": public for name in (
            "list_municipalities", "list_communes", "list_neighborhoods_by_municipality",
            "list_neighborhoods_by_commune", "list_neighborhoods_without_commune",
            "list_road_types", "list_road_suffix_letters", "list_road_bis_codes",
            "list_road_quadrants", "list_cross_suffix_letters", "list_cross_bis_codes",
            "list_cross_quadrants", "list_roles", "list_priorities", "list_failure_types",
            "list_failure_types_by_priority", "list_statuses", "list_actions",
        )},
        "AddressService.get_by_id": public,
        "AddressService.find_by_components": OperationPolicy(input_types=(AddressComponentsInput,)),
        "AddressService.create_or_reuse": OperationPolicy(actor_required=True, permission="create_address", input_types=(AddressCreateInput,)),
        "AddressService.format_address": public,
        "UserService.get_by_id": public,
        "UserService.get_by_email": public,
        "UserService.list_by_filters": public,
        "UserService.register_citizen": OperationPolicy(actor_required=False, permission=None, input_types=(CitizenRegistrationInput,), resolve_actor=False),
        "UserService.login": OperationPolicy(actor_required=False, permission=None, input_types=(UserLoginInput,), resolve_actor=False),
        "UserService.request_password_recovery": OperationPolicy(actor_required=False, permission=None, input_types=(PasswordRecoveryRequestInput,), resolve_actor=False),
        "UserService.verify_password_recovery": OperationPolicy(actor_required=False, permission=None, input_types=(PasswordRecoveryVerifyInput,), resolve_actor=False),
        "UserService.complete_password_recovery": OperationPolicy(actor_required=False, permission=None, input_types=(PasswordResetInput,), resolve_actor=False),
        "UserService.get_current_user": OperationPolicy(actor_required=True, permission=None),
        "UserService.create": OperationPolicy(actor_required=True, permission="manage_users", input_types=(UserCreateInput,)),
        "UserService.update": OperationPolicy(actor_required=True, permission="manage_users", input_types=(UserUpdateInput,)),
        "UserService.set_active": OperationPolicy(actor_required=True, permission="manage_users", input_types=(UserActivationInput,)),
        "CrewService.get_by_id": public,
        "CrewService.list_all": public,
        "CrewService.create": OperationPolicy(actor_required=True, permission="manage_crews", input_types=(CrewCreateInput,)),
        "CrewService.update": OperationPolicy(actor_required=True, permission="manage_crews", input_types=(CrewUpdateInput,)),
        "CrewService.get_membership": public,
        "CrewService.list_members": public,
        "CrewService.add_member": OperationPolicy(actor_required=True, permission="manage_crews", input_types=(CrewMemberInput,)),
        "CrewService.change_crew": OperationPolicy(actor_required=True, permission="manage_crews", input_types=(CrewMemberInput,)),
        "CrewService.remove_member": OperationPolicy(actor_required=True, permission="manage_crews"),
        "TicketService.create": OperationPolicy(actor_required=True, permission="create_ticket", input_types=(TicketCreateInput,)),
        "TicketService.register_citizen": OperationPolicy(actor_required=True, permission="citizen_report_create", input_types=(CitizenTicketCreateInput,)),
        "TicketService.find_citizen_matches": OperationPolicy(actor_required=True, permission="citizen_report_read", input_types=(CitizenMatchInput,)),
        "TicketService.get_citizen_attempt": OperationPolicy(actor_required=True, permission="citizen_report_read", input_types=(CitizenAttemptLookupInput,)),
        "TicketService.contribute_citizen_evidence": OperationPolicy(
            actor_required=True,
            permission="citizen_evidence_contribute",
            input_types=(CitizenContributionInput,),
        ),
        "TicketService.get_citizen_contribution_attempt": OperationPolicy(
            actor_required=True,
            permission="citizen_evidence_read",
            input_types=(CitizenAttemptLookupInput,),
        ),
        "TicketService.get_by_id": public,
        "TicketService.get_by_code": public,
        "TicketService.list_by_filters": public,
        **{f"TicketService.{name}": OperationPolicy(actor_required=True, permission="process_tickets", input_types=(input_type,)) for name, input_type in (
            ("validate", TicketOperationInput), ("prioritize", TicketOperationInput),
            ("assign", TicketAssignmentInput), ("record_attention", TicketAttentionInput),
            ("block", TicketOperationInput), ("unblock", TicketOperationInput),
            ("request_closure", TicketOperationInput),
            ("review_closure", TicketClosureReviewInput),
        )},
        "EvidenceService.get_by_id": OperationPolicy(
            actor_required=True,
            permission="operational_ticket_read",
        ),
        "EvidenceService.list_by_ticket": OperationPolicy(
            actor_required=True,
            permission="operational_ticket_read",
        ),
        "EvidenceService.list_by_ticket_and_uploader": OperationPolicy(
            actor_required=True,
            permission="operational_ticket_read",
        ),
        "EvidenceService.create_metadata": OperationPolicy(actor_required=True, permission="create_evidence", input_types=(EvidenceCreateInput,)),
        "EvidenceService.list_citizen_ticket_evidence": OperationPolicy(
            actor_required=True,
            permission="citizen_evidence_read",
        ),
        "EvidenceService.list_citizen_contribution_evidence": OperationPolicy(
            actor_required=True,
            permission="citizen_evidence_read",
        ),
        "EvidenceService.open_citizen_content": OperationPolicy(
            actor_required=True,
            permission="citizen_evidence_read",
        ),
        "EvidenceUploadService.upload": OperationPolicy(
            actor_required=True,
            permission="citizen_evidence_upload",
            input_types=(EvidenceUploadInput,),
        ),
        "EvidenceUploadService.list_own": OperationPolicy(
            actor_required=True,
            permission="citizen_evidence_read",
            input_types=(EvidenceUploadLookupInput,),
        ),
        "EvidenceUploadService.delete_own": OperationPolicy(
            actor_required=True,
            permission="citizen_evidence_upload",
        ),
        "HistoryService.get_event": public,
        "HistoryService.list_by_ticket": public,
        "HistoryService.create_event": OperationPolicy(actor_required=True, permission="create_history_event", input_types=(HistoryEventCreateInput,)),
    }


OPERATION_POLICIES = _policies()
