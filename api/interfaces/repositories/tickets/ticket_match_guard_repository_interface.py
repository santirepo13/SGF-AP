from typing import Protocol


class TicketMatchGuardRepositoryInterface(Protocol):
    def acquire_address_guard(self, *, address_id: int, failure_type_id: int) -> None: ...
