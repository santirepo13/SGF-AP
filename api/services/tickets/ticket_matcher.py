"""Single open-ticket matching rule and its database serialization guard."""

from __future__ import annotations

from api.contracts import CitizenMatchOutput, CitizenMatchesOutput
from api.errors import ApplicationError
from api.interfaces.repositories import StatusRepositoryInterface, TicketMatchGuardRepositoryInterface, TicketRepositoryInterface

_OPEN_STATUS_NAMES = (
    "Registered",
    "Validated",
    "Prioritized",
    "Assigned",
    "InProgress",
    "Blocked",
    "PendingClosure",
)

_PROGRESS_LABELS = {
    "Registered": "Reporte registrado",
    "Validated": "Reporte validado",
    "Prioritized": "Reporte priorizado",
    "Assigned": "Atención asignada",
    "InProgress": "Atención en curso",
    "Blocked": "Atención bloqueada",
    "PendingClosure": "Cierre pendiente de revisión",
}


class TicketMatcher:
    """Encapsulate match visibility, catalog checks, and lock ordering."""

    def __init__(
        self,
        tickets: TicketRepositoryInterface,
        statuses: StatusRepositoryInterface,
        guards: TicketMatchGuardRepositoryInterface,
    ) -> None:
        self._tickets = tickets
        self._statuses = statuses
        self._guards = guards

    def acquire_address_guard(self, *, address_id: int, failure_type_id: int) -> None:
        self._guards.acquire_address_guard(
            address_id=address_id,
            failure_type_id=failure_type_id,
        )

    def find(
        self,
        *,
        address_id: int,
        failure_type_id: int,
        correlation_id: str | None,
        lock: bool = False,
    ) -> CitizenMatchesOutput:
        self._require_open_status_catalog(correlation_id=correlation_id)
        candidates = self._tickets.list_open_matches(
            address_id=address_id,
            failure_type_id=failure_type_id,
            status_names=_OPEN_STATUS_NAMES,
            limit=21,
            lock=lock,
        )
        return CitizenMatchesOutput(
            matches=tuple(
                CitizenMatchOutput(
                    code=candidate.code,
                    status=candidate.status,
                    created_at=candidate.created_at,
                    progress_label=_PROGRESS_LABELS[candidate.status],
                )
                for candidate in candidates[:20]
            ),
            has_more=len(candidates) > 20,
        )

    def _require_open_status_catalog(self, *, correlation_id: str | None) -> None:
        for name in _OPEN_STATUS_NAMES:
            if self._statuses.get_by_name(name) is None:
                raise ApplicationError.catalog_unavailable("status", correlation_id=correlation_id)


__all__ = ["TicketMatcher"]
