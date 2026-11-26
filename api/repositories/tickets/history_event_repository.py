from datetime import datetime

from api.contracts import CitizenHistoryPageInput, HistoryEventCreateInput
from ..mapping import history_event
from ..persistence import RepositoryBase
class HistoryEventRepository(RepositoryBase):
    _columns = "id, ticket_id, user_id, action_id, event_time"
    def get_by_id(self, event_id: int): return self.fetch_one(f"SELECT {self._columns} FROM history_events WHERE id = %s", (event_id,), operation="history_events.get_by_id", entity="history_event", mapper=history_event)
    def list_by_ticket(self, ticket_id: int): return self.fetch_all(f"SELECT {self._columns} FROM history_events WHERE ticket_id = %s ORDER BY event_time, id", (ticket_id,), operation="history_events.list_by_ticket", entity="history_event", mapper=history_event)
    def list_citizen_history(self, ticket_id: int, page: CitizenHistoryPageInput, cursor_position=None):
        params: list[object] = [ticket_id]
        cursor_clause = ""
        if cursor_position is not None:
            cursor_clause = " AND (h.event_time, h.id) > (%s, %s)"
            timestamp, identifier = cursor_position
            if not isinstance(timestamp, datetime) or timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("history cursor timestamp must be timezone-aware")
            try:
                identifier = int(identifier)
            except (TypeError, ValueError) as error:
                raise ValueError("invalid history cursor tie breaker") from error
            params.extend((timestamp, identifier))
        params.append(page.limit + 1)
        return self.fetch_all(
            "SELECT h.id, h.ticket_id, h.action_id, h.event_time, a.name AS action "
            "FROM history_events h JOIN actions a ON a.id = h.action_id "
            f"WHERE h.ticket_id = %s{cursor_clause} ORDER BY h.event_time ASC, h.id ASC LIMIT %s",
            tuple(params),
            operation="history_events.list_citizen_history",
            entity="history_event",
            mapper=lambda row: row,
        )
    def create(self, data: HistoryEventCreateInput): return self.execute_one(f"INSERT INTO history_events (ticket_id, user_id, action_id) VALUES (%s, %s, %s) RETURNING {self._columns}", (data.ticket_id, data.user_id, data.action_id), operation="history_events.create", entity="history_event", mapper=history_event)
