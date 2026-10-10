from api.contracts import HistoryEventCreateInput
from ..mapping import history_event
from ..persistence import RepositoryBase
class HistoryEventRepository(RepositoryBase):
    _columns = "id, ticket_id, user_id, action_id, event_time"
    def get_by_id(self, event_id: int): return self.fetch_one(f"SELECT {self._columns} FROM history_events WHERE id = %s", (event_id,), operation="history_events.get_by_id", entity="history_event", mapper=history_event)
    def list_by_ticket(self, ticket_id: int): return self.fetch_all(f"SELECT {self._columns} FROM history_events WHERE ticket_id = %s ORDER BY event_time, id", (ticket_id,), operation="history_events.list_by_ticket", entity="history_event", mapper=history_event)
    def create(self, data: HistoryEventCreateInput): return self.execute_one(f"INSERT INTO history_events (ticket_id, user_id, action_id) VALUES (%s, %s, %s) RETURNING {self._columns}", (data.ticket_id, data.user_id, data.action_id), operation="history_events.create", entity="history_event", mapper=history_event)
