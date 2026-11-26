"""Citizen query controller response scope and pagination behavior."""

import asyncio
from types import SimpleNamespace

from client.citizen_queries import CitizenQueryController, QueryState


class Access:
    def __init__(self):
        self.generation = 1
        self.scope = SimpleNamespace(generation=1)

    def capture_request_scope(self):
        return self.scope

    def bind_connector_for_scope(self, scope, connector):
        return connector if scope is self.scope else None

    def is_current_request_scope(self, scope):
        return scope is self.scope and scope.generation == self.generation


class Connector:
    def __init__(self):
        self.calls = []
        self.responses = [
            {"success": True, "data": {"items": [{"code": "SGF-1"}], "next_cursor": "next"}, "error": None},
            {"success": True, "data": {"items": [{"code": "SGF-2"}], "next_cursor": None}, "error": None},
        ]

    def list_my_reports(self, limit, cursor):
        self.calls.append(cursor)
        return SimpleNamespace(status_code=200, payload=self.responses.pop(0))


def test_report_pages_append_in_order_and_duplicate_cursor_is_not_requested() -> None:
    async def run():
        access = Access()
        connector = Connector()
        controller = CitizenQueryController(connector, access)
        await controller.load_reports()
        await controller.load_reports(cursor="next")
        await controller.load_reports(cursor="next")
        assert controller.snapshot().items == [{"code": "SGF-1"}, {"code": "SGF-2"}]
        assert connector.calls == [None, "next"]
        assert controller.snapshot().state is QueryState.READY

    asyncio.run(run())


def test_refresh_failure_keeps_previous_items_marked_stale() -> None:
    class FailingConnector:
        def list_my_reports(self, limit, cursor):
            return SimpleNamespace(
                status_code=500,
                payload={"success": False, "data": None, "error": {"message": "Servidor no disponible"}},
            )

    async def run():
        controller = CitizenQueryController(FailingConnector(), Access())
        snapshot = controller.snapshot()
        snapshot.items = [{"code": "SGF-OLD"}]
        snapshot.list_state = QueryState.READY
        result = await controller.refresh_reports()
        assert result.items == [{"code": "SGF-OLD"}]
        assert result.list_state is QueryState.STALE

    asyncio.run(run())
