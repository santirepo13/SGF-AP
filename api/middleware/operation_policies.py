"""Explicit execution policies for the service operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from api.contracts import (
    AddressComponentsInput, AddressCreateInput, CrewCreateInput, CrewMemberInput,
    CrewUpdateInput, EvidenceCreateInput, HistoryEventCreateInput,
    TicketAssignmentInput, TicketAttentionInput, TicketClosureReviewInput,
    TicketCreateInput, TicketOperationInput, UserActivationInput,
    UserCreateInput, UserUpdateInput,
)


@dataclass(frozen=True)
class OperationPolicy:
    actor_required: bool = False
    permission: str | None = None
    input_types: tuple[type[Any], ...] = ()


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
        "TicketService.get_by_id": public,
        "TicketService.get_by_code": public,
        "TicketService.list_by_filters": public,
        **{f"TicketService.{name}": OperationPolicy(actor_required=True, permission="process_tickets", input_types=(input_type,)) for name, input_type in (
            ("validate", TicketOperationInput), ("prioritize", TicketOperationInput),
            ("assign", TicketAssignmentInput), ("record_attention", TicketAttentionInput),
            ("block", TicketOperationInput), ("request_closure", TicketOperationInput),
            ("review_closure", TicketClosureReviewInput),
        )},
        "EvidenceService.get_by_id": public,
        "EvidenceService.list_by_ticket": public,
        "EvidenceService.list_by_ticket_and_uploader": public,
        "EvidenceService.create_metadata": OperationPolicy(actor_required=True, permission="create_evidence", input_types=(EvidenceCreateInput,)),
        "HistoryService.get_event": public,
        "HistoryService.list_by_ticket": public,
        "HistoryService.create_event": OperationPolicy(actor_required=True, permission="create_history_event", input_types=(HistoryEventCreateInput,)),
    }


OPERATION_POLICIES = _policies()
