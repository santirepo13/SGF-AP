"""Database-backed serialization guards for open-ticket matching."""

from __future__ import annotations

from ..persistence import RepositoryBase


class TicketMatchGuardRepository(RepositoryBase):
    def acquire_address_guard(self, *, address_id: int, failure_type_id: int) -> None:
        self.fetch_one(
            "INSERT INTO ticket_match_guards (scope_type, scope_id, failure_type_id) "
            "VALUES ('address', %s, %s) ON CONFLICT DO NOTHING RETURNING scope_type",
            (address_id, failure_type_id),
            operation="ticket_match_guards.create",
            entity="ticket_match_guard",
            mapper=lambda _: True,
        )
        locked = self.fetch_one(
            "SELECT scope_type FROM ticket_match_guards "
            "WHERE scope_type = 'address' AND scope_id = %s AND failure_type_id = %s FOR UPDATE",
            (address_id, failure_type_id),
            operation="ticket_match_guards.acquire",
            entity="ticket_match_guard",
            mapper=lambda _: True,
        )
        if locked is not True:
            raise RuntimeError("ticket match guard could not be acquired")
