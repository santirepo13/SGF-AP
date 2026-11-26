"""Stateful citizen report queries with scope and generation protection."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

from .access_continuity import AccessCoordinator, RequestScope
from .citizen_connector import CitizenReportConnector
from .transport import BinaryConnectorResponse


class QueryState(str, Enum):
    LOADING = "loading"
    EMPTY = "empty"
    READY = "ready"
    ERROR = "error"
    STALE = "stale"
    LOADING_MORE = "loading_more"
    NOT_FOUND = "not_found"


@dataclass
class CitizenQuerySnapshot:
    state: QueryState = QueryState.EMPTY
    items: list[dict[str, Any]] = field(default_factory=list)
    detail: dict[str, Any] | None = None
    public_detail: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    next_cursor: str | None = None
    next_history_cursor: str | None = None
    evidence_previews: dict[int, bytes] = field(default_factory=dict)
    error: str | None = None
    list_state: QueryState = QueryState.EMPTY
    detail_state: QueryState = QueryState.EMPTY
    history_state: QueryState = QueryState.EMPTY
    public_state: QueryState = QueryState.EMPTY
    list_error: str | None = None
    detail_error: str | None = None
    history_error: str | None = None
    public_error: str | None = None
    requested_detail_code: str | None = None
    verified_report_code: str | None = None


class QueryResponseError(RuntimeError):
    pass


class CitizenQueryController:
    def __init__(
        self,
        connector: CitizenReportConnector,
        access: AccessCoordinator,
        handle_protected_response: Callable[[object | None, object], Awaitable[bool]] | None = None,
    ) -> None:
        self._connector = connector
        self._access = access
        self._handle_protected_response = handle_protected_response
        self._generation = 0
        self._loaded_cursors: set[str | None] = set()
        self._loading_cursors: set[tuple[int, str | None]] = set()
        self._history_cursors: set[str | None] = set()
        self._history_loading_cursors: set[tuple[int, str, str | None]] = set()
        self._detail_code: str | None = None
        self._history_code: str | None = None
        self._snapshot = CitizenQuerySnapshot()
        self._reconcile_on_next_list = False

    def snapshot(self) -> CitizenQuerySnapshot:
        return self._snapshot

    def invalidate(self) -> None:
        self._generation += 1
        self._loaded_cursors.clear()
        self._loading_cursors.clear()
        self._history_cursors.clear()
        self._history_loading_cursors.clear()
        self._detail_code = None
        self._history_code = None
        self._snapshot.evidence_previews.clear()
        self._snapshot = CitizenQuerySnapshot()
        self._reconcile_on_next_list = False

    clear_private_state = invalidate

    async def load_reports(self, *, limit: int = 20, cursor: str | None = None) -> CitizenQuerySnapshot:
        generation = self._generation
        load_key = (generation, cursor)
        if cursor in self._loaded_cursors or load_key in self._loading_cursors:
            return self._snapshot
        self._loading_cursors.add(load_key)
        if cursor is None:
            self._snapshot.list_state = QueryState.LOADING
            self._snapshot.list_error = None
            self._snapshot.detail = None
            self._snapshot.history.clear()
            self._snapshot.evidence_previews.clear()
            self._snapshot.detail_state = QueryState.EMPTY
            self._snapshot.history_state = QueryState.EMPTY
            self._snapshot.public_state = QueryState.EMPTY
            self._snapshot.public_error = None
            self._snapshot.requested_detail_code = None
            self._snapshot.verified_report_code = None
        else:
            self._snapshot.list_state = QueryState.LOADING_MORE
        self._snapshot.state = self._snapshot.list_state
        scope = self._access.capture_request_scope()
        connector = self._bind_private(scope)
        if connector is None:
            self._loading_cursors.discard(load_key)
            self._snapshot.list_state = QueryState.ERROR
            self._snapshot.list_error = "La sesión ya no está disponible."
            self._snapshot.state = QueryState.ERROR
            self._snapshot.error = self._snapshot.list_error
            return self._snapshot
        try:
            response = await asyncio.to_thread(connector.list_my_reports, limit, cursor)
            if await self._handle_expired(scope, response):
                return self._snapshot
            if not self._valid(scope, generation):
                return self._snapshot
            payload = _data(response)
            if payload is None:
                raise QueryResponseError(_error_message(response))
            values = payload.get("items", [])
            if not isinstance(values, list):
                raise QueryResponseError("La respuesta de reportes no es válida.")
            if cursor is None:
                if self._reconcile_on_next_list:
                    self._snapshot.items = self._reconcile_by_code(self._snapshot.items, values)
                    self._reconcile_on_next_list = False
                else:
                    self._snapshot.items = values
            else:
                self._snapshot.items.extend(values)
            self._snapshot.next_cursor = payload.get("next_cursor")
            self._snapshot.list_state = QueryState.READY if self._snapshot.items else QueryState.EMPTY
            self._snapshot.state = self._snapshot.list_state
            self._snapshot.error = None
            self._snapshot.list_error = None
            if cursor is None:
                self._snapshot.verified_report_code = None
            self._loaded_cursors.add(cursor)
        except Exception as error:
            if self._valid(scope, generation):
                self._snapshot.list_state = QueryState.STALE if self._snapshot.items else QueryState.ERROR
                self._snapshot.list_error = _error_message(error)
                self._snapshot.state = self._snapshot.list_state
                self._snapshot.error = self._snapshot.list_error
        finally:
            self._loading_cursors.discard(load_key)
        return self._snapshot

    async def refresh_reports(self, *, limit: int = 20) -> CitizenQuerySnapshot:
        previous = self._snapshot
        self._generation += 1
        self._loaded_cursors.clear()
        self._loading_cursors.clear()
        self._snapshot = CitizenQuerySnapshot(
            state=QueryState.LOADING,
            items=list(previous.items),
            next_cursor=None,
            list_state=QueryState.LOADING,
            list_error=None,
        )
        self._reconcile_on_next_list = True
        return await self.load_reports(limit=limit)

    async def load_private_detail(self, code: str) -> CitizenQuerySnapshot:
        self._generation += 1
        generation = self._generation
        self._detail_code = code
        self._history_code = code
        self._history_cursors.clear()
        self._history_loading_cursors.clear()
        self._snapshot.evidence_previews.clear()
        self._snapshot.public_detail = None
        self._snapshot.public_state = QueryState.EMPTY
        self._snapshot.public_error = None
        self._snapshot.detail = None
        self._snapshot.verified_report_code = None
        self._snapshot.requested_detail_code = code
        self._snapshot.history = []
        self._snapshot.detail_state = QueryState.LOADING
        self._snapshot.history_state = QueryState.EMPTY
        self._snapshot.state = QueryState.LOADING
        self._snapshot.detail_error = None
        scope = self._access.capture_request_scope()
        connector = self._bind_private(scope)
        if connector is None:
            self._snapshot.detail_state = QueryState.ERROR
            self._snapshot.detail_error = "La sesión ya no está disponible."
            self._snapshot.state = QueryState.ERROR
            self._snapshot.error = self._snapshot.detail_error
            return self._snapshot
        try:
            response = await asyncio.to_thread(connector.get_my_report, code)
            if await self._handle_expired(scope, response):
                return self._snapshot
            if not self._valid(scope, generation) or self._detail_code != code:
                return self._snapshot
            if _status_code(response) == 404:
                self._snapshot.detail = None
                self._snapshot.detail_state = QueryState.NOT_FOUND
                self._snapshot.state = QueryState.NOT_FOUND
            else:
                payload = _data(response)
                if payload is None:
                    raise QueryResponseError(_error_message(response))
                self._snapshot.detail = payload
                self._snapshot.verified_report_code = code
                self._snapshot.detail_state = QueryState.READY
                self._snapshot.state = QueryState.READY
        except Exception as error:
            if self._valid(scope, generation):
                self._snapshot.detail_state = QueryState.ERROR
                self._snapshot.detail_error = _error_message(error)
                self._snapshot.state = QueryState.ERROR
                self._snapshot.error = self._snapshot.detail_error
        return self._snapshot

    async def ensure_private_detail(self, code: str) -> CitizenQuerySnapshot:
        if self._snapshot.verified_report_code == code and self._snapshot.detail is not None:
            return self._snapshot
        if self._detail_code == code and self._snapshot.detail_state is QueryState.LOADING:
            return self._snapshot
        return await self.load_private_detail(code)

    async def load_history(self, code: str, *, limit: int = 50, cursor: str | None = None) -> CitizenQuerySnapshot:
        if self._history_code != code:
            self._history_code = code
            self._history_cursors.clear()
            self._history_loading_cursors.clear()
            self._snapshot.history = []
            self._snapshot.next_history_cursor = None
        generation = self._generation
        load_key = (generation, code, cursor)
        if cursor in self._history_cursors or load_key in self._history_loading_cursors:
            return self._snapshot
        self._history_loading_cursors.add(load_key)
        self._snapshot.history_state = QueryState.LOADING_MORE if cursor else QueryState.LOADING
        self._snapshot.state = self._snapshot.history_state
        scope = self._access.capture_request_scope()
        connector = self._bind_private(scope)
        if connector is None:
            self._history_loading_cursors.discard(load_key)
            self._snapshot.history_state = QueryState.ERROR
            self._snapshot.history_error = "La sesión ya no está disponible."
            return self._snapshot
        try:
            response = await asyncio.to_thread(connector.list_my_report_history, code, limit, cursor)
            if await self._handle_expired(scope, response):
                return self._snapshot
            if not self._valid(scope, generation) or self._history_code != code:
                return self._snapshot
            payload = _data(response)
            if payload is None:
                raise QueryResponseError(_error_message(response))
            values = payload.get("items", [])
            if not isinstance(values, list):
                raise QueryResponseError("La respuesta del historial no es válida.")
            if cursor is None:
                self._snapshot.history = values
            else:
                self._snapshot.history.extend(values)
            self._snapshot.next_history_cursor = payload.get("next_cursor")
            self._snapshot.history_state = QueryState.READY if self._snapshot.history else QueryState.EMPTY
            self._snapshot.state = self._snapshot.history_state
            self._snapshot.error = None
            self._snapshot.history_error = None
            self._history_cursors.add(cursor)
        except Exception as error:
            if self._valid(scope, generation):
                self._snapshot.history_state = QueryState.STALE if self._snapshot.history else QueryState.ERROR
                self._snapshot.history_error = _error_message(error)
        finally:
            self._history_loading_cursors.discard(load_key)
        return self._snapshot

    async def load_public(self, code: str) -> CitizenQuerySnapshot:
        self._generation += 1
        generation = self._generation
        self._loaded_cursors.clear()
        self._loading_cursors.clear()
        self._history_cursors.clear()
        self._history_loading_cursors.clear()
        self._detail_code = code
        self._history_code = None
        self._snapshot.items.clear()
        self._snapshot.history.clear()
        self._snapshot.next_cursor = None
        self._snapshot.next_history_cursor = None
        self._snapshot.list_state = QueryState.EMPTY
        self._snapshot.detail_state = QueryState.EMPTY
        self._snapshot.history_state = QueryState.EMPTY
        self._snapshot.list_error = None
        self._snapshot.detail_error = None
        self._snapshot.history_error = None
        self._snapshot.detail = None
        self._snapshot.public_detail = None
        self._snapshot.verified_report_code = None
        self._snapshot.requested_detail_code = code
        self._snapshot.evidence_previews.clear()
        self._snapshot.verified_report_code = None
        self._snapshot.public_state = QueryState.LOADING
        self._snapshot.state = QueryState.LOADING
        self._snapshot.public_error = None
        self._snapshot.error = None
        try:
            response = await asyncio.to_thread(self._connector.get_public_report, code)
            if generation != self._generation or self._detail_code != code:
                return self._snapshot
            if _status_code(response) == 404:
                self._snapshot.public_detail = None
                self._snapshot.public_state = QueryState.NOT_FOUND
                self._snapshot.state = QueryState.NOT_FOUND
            else:
                payload = _data(response)
                if payload is None:
                    raise QueryResponseError(_error_message(response))
                self._snapshot.public_detail = payload
                self._snapshot.verified_report_code = None
                self._snapshot.public_state = QueryState.READY
                self._snapshot.state = QueryState.READY
                self._snapshot.error = None
        except Exception as error:
            if generation == self._generation:
                self._snapshot.public_detail = None
                self._snapshot.public_state = QueryState.ERROR
                self._snapshot.public_error = _error_message(error)
                self._snapshot.state = QueryState.ERROR
                self._snapshot.error = self._snapshot.public_error
        return self._snapshot

    @staticmethod
    def _reconcile_by_code(previous: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
        previous_by_code = {
            str(item.get("code")): item
            for item in previous
            if isinstance(item, dict) and item.get("code") is not None
        }
        reconciled: list[dict[str, Any]] = []
        for item in incoming:
            code = str(item.get("code", ""))
            prior = previous_by_code.get(code, {})
            merged = dict(prior)
            merged.update(item)
            reconciled.append(merged)
        return reconciled

    async def load_evidence_preview(self, evidence_id: int) -> CitizenQuerySnapshot:
        if type(evidence_id) is not int or evidence_id <= 0:
            return self._snapshot
        scope = self._access.capture_request_scope()
        connector = self._bind_private(scope)
        generation = self._generation
        if connector is None:
            self._snapshot.detail_error = "La sesión ya no está disponible."
            return self._snapshot
        try:
            response = await asyncio.to_thread(connector.download_evidence, evidence_id=evidence_id)
            if await self._handle_expired(scope, response):
                _close_response(response)
                return self._snapshot
            if not self._valid(scope, generation):
                _close_response(response)
                return self._snapshot
            if not isinstance(response, BinaryConnectorResponse) or response.status_code != 200:
                if isinstance(response, BinaryConnectorResponse):
                    response.stream.close()
                self._snapshot.error = "La fotografía no está disponible."
                return self._snapshot
            stream = response.stream
            content = stream.read(10_000_001)
            stream.close()
            if not isinstance(content, bytes):
                self._snapshot.error = "La fotografía no está disponible."
                return self._snapshot
            if len(content) > 10_000_000:
                self._snapshot.error = "La fotografía supera el tamaño permitido."
            else:
                self._snapshot.evidence_previews[evidence_id] = content
        except Exception as error:
            if self._valid(scope, generation):
                self._snapshot.error = _error_message(error)
        return self._snapshot

    def clear_evidence_previews(self) -> None:
        self._snapshot.evidence_previews.clear()

    def _bind_private(self, scope: RequestScope | None) -> CitizenReportConnector | None:
        if scope is None:
            return None
        bound = self._access.bind_connector_for_scope(scope, self._connector)
        return bound if bound is not None else None

    def _valid(self, scope: RequestScope, generation: int) -> bool:
        return generation == self._generation and self._access.is_current_request_scope(scope)

    async def _handle_expired(self, scope: RequestScope, response: object) -> bool:
        if self._handle_protected_response is None:
            return False
        return await self._handle_protected_response(scope, response)


def _status_code(response: object) -> int:
    value = getattr(response, "status_code", None)
    return value if type(value) is int else 0


def _data(response: object) -> dict[str, Any] | None:
    payload = getattr(response, "payload", None)
    if not isinstance(payload, dict) or payload.get("success") is not True:
        return None
    value = payload.get("data")
    return value if isinstance(value, dict) else None


def _error_message(value: object) -> str:
    payload = getattr(value, "payload", None)
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
    return str(value) or "No fue posible consultar el reporte."


def _close_response(response: object) -> None:
    stream = getattr(response, "stream", None)
    if stream is not None:
        stream.close()


__all__ = ["CitizenQueryController", "CitizenQuerySnapshot", "QueryResponseError", "QueryState"]
