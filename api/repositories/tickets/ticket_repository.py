from api.contracts import TicketCreateInput, TicketFilters, TicketUpdateInput, UNSET
from ..mapping import ticket
from ..persistence import RepositoryBase

_COLUMNS = "t.id, t.code, t.reported_by, t.failure_type_id, t.description, t.address_id, t.status_id, t.priority_id, t.contact_email, t.contact_phone, t.diagnosis, t.solution, t.crew_id, t.created_at"
_BASE = " FROM tickets t"

class TicketRepository(RepositoryBase):
    def get_by_id(self, ticket_id: int): return self.fetch_one(f"SELECT {_COLUMNS}{_BASE} WHERE t.id = %s", (ticket_id,), operation="tickets.get_by_id", entity="ticket", mapper=ticket)
    def get_by_code(self, code: str): return self.fetch_one(f"SELECT {_COLUMNS}{_BASE} WHERE t.code = %s", (code,), operation="tickets.get_by_code", entity="ticket", mapper=ticket)
    def list_by_filters(self, filters: TicketFilters | None = None):
        filters = filters or TicketFilters()
        clauses, params = [], []
        direct = ("reported_by", "failure_type_id", "address_id", "status_id", "priority_id", "crew_id")
        for name in direct:
            value = getattr(filters, name)
            if value is not None: clauses.append(f"t.{name} = %s"); params.append(value)
        joins = ""
        if filters.municipality_id is not None or filters.commune_id is not None or filters.neighborhood_id is not None:
            joins = " JOIN addresses a ON a.id = t.address_id JOIN neighborhoods n ON n.id = a.neighborhood_id"
            if filters.municipality_id is not None: clauses.append("n.municipality_id = %s"); params.append(filters.municipality_id)
            if filters.commune_id is not None: clauses.append("n.commune_id = %s"); params.append(filters.commune_id)
            if filters.neighborhood_id is not None: clauses.append("n.id = %s"); params.append(filters.neighborhood_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return self.fetch_all(f"SELECT {_COLUMNS}{_BASE}{joins}{where} ORDER BY t.id", tuple(params), operation="tickets.list_by_filters", entity="ticket", mapper=ticket)
    def create(self, data: TicketCreateInput):
        names = ("code", "reported_by", "failure_type_id", "description", "address_id", "contact_email", "contact_phone")
        values = tuple(getattr(data, name) for name in names)
        return self.execute_one(f"INSERT INTO tickets ({', '.join(names)}) VALUES ({', '.join(['%s'] * len(names))}) RETURNING id, code, reported_by, failure_type_id, description, address_id, status_id, priority_id, contact_email, contact_phone, diagnosis, solution, crew_id, created_at", values, operation="tickets.create", entity="ticket", mapper=ticket)
    def update(self, data: TicketUpdateInput):
        allowed = ("code", "reported_by", "failure_type_id", "description", "address_id", "status_id", "priority_id", "contact_email", "contact_phone", "diagnosis", "solution", "crew_id")
        changes = [(name, getattr(data, name)) for name in allowed if getattr(data, name) is not UNSET]
        if not changes: return self.get_by_id(data.ticket_id)
        values = [value for _, value in changes] + [data.ticket_id]
        set_clause = ", ".join(f"{name} = %s" for name, _ in changes)
        return self.execute_one(f"UPDATE tickets SET {set_clause} WHERE id = %s RETURNING id, code, reported_by, failure_type_id, description, address_id, status_id, priority_id, contact_email, contact_phone, diagnosis, solution, crew_id, created_at", tuple(values), operation="tickets.update", entity="ticket", mapper=ticket)
