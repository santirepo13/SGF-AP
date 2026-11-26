"""SQL contracts for citizen pagination and ownership projections."""

from datetime import datetime, timezone

from api.repositories.tickets.history_event_repository import HistoryEventRepository
from api.repositories.tickets.ticket_repository import TicketRepository
from api.contracts import CitizenHistoryPageInput, CitizenQueryPageInput


class Cursor:
    description = None

    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, tuple(params)))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return None

    def close(self):
        pass


class Connection:
    def __init__(self, rows=()):
        self.cursor_value = Cursor(rows)

    def cursor(self):
        return self.cursor_value


def test_citizen_ticket_list_binds_owner_cursor_and_limit_plus_one() -> None:
    connection = Connection()
    repository = TicketRepository(connection)
    repository.list_citizen_reports(29, CitizenQueryPageInput(20), (datetime(2026, 1, 1, tzinfo=timezone.utc), "SGF-20"))
    sql, params = connection.cursor_value.calls[-1]
    assert "WHERE t.reported_by = %s" in sql
    assert "ORDER BY t.created_at DESC, t.code DESC" in sql
    assert "OFFSET" not in sql.upper()
    assert params == (29, datetime(2026, 1, 1, tzinfo=timezone.utc), "SGF-20", 21)


def test_citizen_history_binds_ticket_and_orders_by_internal_tiebreaker() -> None:
    connection = Connection()
    repository = HistoryEventRepository(connection)
    repository.list_citizen_history(7, CitizenHistoryPageInput(50), (datetime(2026, 1, 1, tzinfo=timezone.utc), "81"))
    sql, params = connection.cursor_value.calls[-1]
    assert "WHERE h.ticket_id = %s" in sql
    assert "ORDER BY h.event_time ASC, h.id ASC" in sql
    assert "OFFSET" not in sql.upper()
    assert params == (7, datetime(2026, 1, 1, tzinfo=timezone.utc), 81, 51)


def test_private_report_query_enforces_owner_and_last_update_in_same_query() -> None:
    connection = Connection()
    TicketRepository(connection).get_citizen_report(29, "SGF-AAAAAAAAAAAAAAAAAAAA")
    sql, params = connection.cursor_value.calls[-1]
    assert "WHERE t.reported_by = %s AND t.code = %s" in sql
    assert "MAX(event_time)" in sql
    assert "road_types" in sql and "road_quadrants" in sql
    assert params == (29, "SGF-AAAAAAAAAAAAAAAAAAAA")
