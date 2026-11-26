from datetime import datetime

from api.contracts import (
    CitizenQueryPageInput,
    TicketFilters,
    TicketInsertInput,
    TicketUpdateInput,
    UNSET,
)

from ..mapping import open_ticket_match, ticket
from ..persistence import RepositoryBase

_TICKET_FIELDS = (
    "id, code, reported_by, failure_type_id, description, address_id, status_id, "
    "priority_id, contact_email, contact_phone, diagnosis, solution, crew_id, created_at, email_notifications"
)
_COLUMNS = f"t.{_TICKET_FIELDS.replace(', ', ', t.')}"
_BASE = " FROM tickets t"
_INSERT_FIELDS = (
    "code",
    "reported_by",
    "failure_type_id",
    "description",
    "address_id",
    "status_id",
    "priority_id",
    "contact_email",
    "contact_phone",
    "diagnosis",
    "solution",
    "crew_id",
    "email_notifications",
)


class TicketRepository(RepositoryBase):
    def get_by_id(self, ticket_id: int):
        return self.fetch_one(
            f"SELECT {_COLUMNS}{_BASE} WHERE t.id = %s",
            (ticket_id,),
            operation="tickets.get_by_id",
            entity="ticket",
            mapper=ticket,
        )

    def get_by_code(self, code: str):
        return self.fetch_one(
            f"SELECT {_COLUMNS}{_BASE} WHERE t.code = %s",
            (code,),
            operation="tickets.get_by_code",
            entity="ticket",
            mapper=ticket,
        )

    def get_by_code_for_update(self, code: str):
        return self.fetch_one(
            f"SELECT {_COLUMNS}{_BASE} WHERE t.code = %s FOR UPDATE OF t",
            (code,),
            operation="tickets.get_by_code_for_update",
            entity="ticket",
            mapper=ticket,
        )

    def list_by_filters(self, filters: TicketFilters | None = None):
        filters = filters or TicketFilters()
        clauses, params = [], []
        for name in ("reported_by", "failure_type_id", "address_id", "status_id", "priority_id", "crew_id"):
            value = getattr(filters, name)
            if value is not None:
                clauses.append(f"t.{name} = %s")
                params.append(value)
        joins = ""
        if filters.municipality_id is not None or filters.commune_id is not None or filters.neighborhood_id is not None:
            joins = " JOIN addresses a ON a.id = t.address_id JOIN neighborhoods n ON n.id = a.neighborhood_id"
            if filters.municipality_id is not None:
                clauses.append("n.municipality_id = %s")
                params.append(filters.municipality_id)
            if filters.commune_id is not None:
                clauses.append("n.commune_id = %s")
                params.append(filters.commune_id)
            if filters.neighborhood_id is not None:
                clauses.append("n.id = %s")
                params.append(filters.neighborhood_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return self.fetch_all(
            f"SELECT {_COLUMNS}{_BASE}{joins}{where} ORDER BY t.id",
            tuple(params),
            operation="tickets.list_by_filters",
            entity="ticket",
            mapper=ticket,
        )

    def create(self, data: TicketInsertInput):
        return self._insert(data, operation="tickets.create")

    def create_if_code_available(self, data: TicketInsertInput):
        return self._insert(
            data,
            operation="tickets.create_if_code_available",
            on_conflict=" ON CONFLICT (code) DO NOTHING",
        )

    def list_open_matches(
        self,
        *,
        address_id: int,
        failure_type_id: int,
        status_names: tuple[str, ...],
        limit: int,
        lock: bool = False,
    ):
        if not status_names:
            return []
        placeholders = ", ".join("%s" for _ in status_names)
        if lock:
            return self.fetch_all(
                "WITH locked_matches AS ("
                "SELECT t.id FROM tickets t JOIN statuses s ON s.id = t.status_id "
                f"WHERE t.address_id = %s AND t.failure_type_id = %s AND s.name IN ({placeholders}) "
                "ORDER BY t.id FOR UPDATE OF t"
                ") "
                "SELECT t.id, t.code, s.name AS status, t.created_at "
                "FROM tickets t JOIN locked_matches locked ON locked.id = t.id "
                "JOIN statuses s ON s.id = t.status_id "
                "ORDER BY t.created_at DESC, t.code ASC LIMIT %s",
                (address_id, failure_type_id, *status_names, limit),
                operation="tickets.list_open_matches_locked",
                entity="ticket",
                mapper=open_ticket_match,
            )
        return self.fetch_all(
            "SELECT t.id, t.code, s.name AS status, t.created_at "
            "FROM tickets t JOIN statuses s ON s.id = t.status_id "
            f"WHERE t.address_id = %s AND t.failure_type_id = %s AND s.name IN ({placeholders}) "
            "ORDER BY t.created_at DESC, t.code ASC LIMIT %s",
            (address_id, failure_type_id, *status_names, limit),
            operation="tickets.list_open_matches",
            entity="ticket",
            mapper=open_ticket_match,
        )

    def list_citizen_reports(self, reported_by: int, page: CitizenQueryPageInput, cursor_position=None):
        if cursor_position is not None:
            timestamp, code = cursor_position
            if not isinstance(timestamp, datetime) or timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("citizen cursor timestamp must be timezone-aware")
            if type(code) is not str or not code:
                raise ValueError("citizen cursor code is invalid")
        cursor_clause = ""
        params: list[object] = [reported_by]
        if cursor_position is not None:
            cursor_clause = " AND (t.created_at, t.code) < (%s, %s)"
            params.extend(cursor_position)
        params.append(page.limit + 1)
        return self.fetch_all(
            "SELECT t.code, t.created_at, s.name AS status, f.name AS failure_type_label, "
            "GREATEST(t.created_at, COALESCE(h.last_event_time, t.created_at)) AS last_updated_at "
            "FROM tickets t JOIN statuses s ON s.id = t.status_id "
            "JOIN failure_types f ON f.id = t.failure_type_id "
            "LEFT JOIN (SELECT ticket_id, MAX(event_time) AS last_event_time "
            "FROM history_events GROUP BY ticket_id) h ON h.ticket_id = t.id "
            f"WHERE t.reported_by = %s{cursor_clause} "
            "ORDER BY t.created_at DESC, t.code DESC LIMIT %s",
            tuple(params),
            operation="tickets.list_citizen_reports",
            entity="ticket",
            mapper=lambda row: row,
        )

    def get_citizen_report(self, reported_by: int, code: str):
        return self.fetch_one(
            "SELECT t.id, t.code, t.created_at, t.status_id, s.name AS status, "
            "f.name AS failure_type_label, t.description, t.contact_email, t.contact_phone, "
            "t.email_notifications, GREATEST(t.created_at, COALESCE(h.last_event_time, t.created_at)) AS last_updated_at, "
            "a.id AS address_id, rt.name AS road_type_name, a.road_number, rsl.code AS road_suffix_letter_code, "
            "rbc.code AS road_bis_code, a.road_bis_suffix, rq.name AS road_quadrant_name, a.cross_road_number, "
            "csl.code AS cross_suffix_letter_code, cbc.code AS cross_bis_code, a.cross_bis_suffix, cq.name AS cross_quadrant_name, "
            "a.door_plate_number, a.neighborhood_id, n.name AS neighborhood_name "
            "FROM tickets t JOIN statuses s ON s.id = t.status_id "
            "JOIN failure_types f ON f.id = t.failure_type_id "
            "LEFT JOIN (SELECT ticket_id, MAX(event_time) AS last_event_time FROM history_events GROUP BY ticket_id) h ON h.ticket_id = t.id "
            "LEFT JOIN addresses a ON a.id = t.address_id "
            "LEFT JOIN road_types rt ON rt.code = a.road_type_code "
            "LEFT JOIN road_suffix_letters rsl ON rsl.code = a.road_suffix_letter_code "
            "LEFT JOIN road_bis_codes rbc ON rbc.code = a.road_bis_code "
            "LEFT JOIN road_quadrants rq ON rq.code = a.road_quadrant_code "
            "LEFT JOIN cross_suffix_letters csl ON csl.code = a.cross_suffix_letter_code "
            "LEFT JOIN cross_bis_codes cbc ON cbc.code = a.cross_bis_code "
            "LEFT JOIN cross_quadrants cq ON cq.code = a.cross_quadrant_code "
            "LEFT JOIN neighborhoods n ON n.id = a.neighborhood_id "
            "WHERE t.reported_by = %s AND t.code = %s",
            (reported_by, code),
            operation="tickets.get_citizen_report",
            entity="ticket",
            mapper=lambda row: row,
        )

    def get_citizen_report_id(self, reported_by: int, code: str):
        return self.fetch_one(
            "SELECT t.id FROM tickets t WHERE t.reported_by = %s AND t.code = %s",
            (reported_by, code),
            operation="tickets.get_citizen_report_id",
            entity="ticket",
            mapper=lambda row: row["id"],
        )

    def get_public_report(self, code: str):
        return self.fetch_one(
            "SELECT t.code, t.created_at, s.name AS status, "
            "GREATEST(t.created_at, COALESCE(h.last_event_time, t.created_at)) AS last_updated_at "
            "FROM tickets t JOIN statuses s ON s.id = t.status_id "
            "LEFT JOIN (SELECT ticket_id, MAX(event_time) AS last_event_time FROM history_events GROUP BY ticket_id) h ON h.ticket_id = t.id "
            "WHERE t.code = %s",
            (code,),
            operation="tickets.get_public_report",
            entity="ticket",
            mapper=lambda row: row,
        )

    def update(self, data: TicketUpdateInput):
        allowed = (
            "code", "reported_by", "failure_type_id", "description", "address_id", "status_id",
            "priority_id", "contact_email", "contact_phone", "diagnosis", "solution", "crew_id",
            "email_notifications",
        )
        changes = [(name, getattr(data, name)) for name in allowed if getattr(data, name) is not UNSET]
        if not changes:
            return self.get_by_id(data.ticket_id)
        values = [value for _, value in changes] + [data.ticket_id]
        set_clause = ", ".join(f"{name} = %s" for name, _ in changes)
        return self.execute_one(
            f"UPDATE tickets SET {set_clause} WHERE id = %s RETURNING {_TICKET_FIELDS}",
            tuple(values),
            operation="tickets.update",
            entity="ticket",
            mapper=ticket,
        )

    def _insert(self, data: TicketInsertInput, *, operation: str, on_conflict: str = ""):
        values = tuple(getattr(data, name) for name in _INSERT_FIELDS)
        placeholders = ", ".join("%s" for _ in _INSERT_FIELDS)
        return self.execute_one(
            f"INSERT INTO tickets ({', '.join(_INSERT_FIELDS)}) VALUES ({placeholders}){on_conflict} RETURNING {_TICKET_FIELDS}",
            values,
            operation=operation,
            entity="ticket",
            mapper=ticket,
        )
