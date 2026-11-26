"""Flet views for private citizen reports and public code lookup."""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from typing import Any

from .citizen_queries import CitizenQueryController, QueryState
from .display_dates import format_display_date


class CitizenQueryViews:
    def __init__(
        self,
        ft: Any,
        controller: CitizenQueryController,
        *,
        refresh: Callable[[], None],
        close: Callable[[], None],
        open_private_detail: Callable[[str], None],
        open_public: Callable[[str], None],
        can_verify_private: Callable[[], bool] | None = None,
        verify_private_ownership: Callable[[str], Awaitable[bool]] | None = None,
    ) -> None:
        self.ft = ft
        self.controller = controller
        self._refresh = refresh
        self._close = close
        self._open_private_detail = open_private_detail
        self._open_public = open_public
        self._can_verify_private = can_verify_private or (lambda: False)
        self._verify_private_ownership = verify_private_ownership
        self._code = ""

    def build_reports(self) -> Any:
        snapshot = self.controller.snapshot()
        controls: list[Any] = [
            self.ft.Text("Mis reportes", size=22, weight=self.ft.FontWeight.BOLD),
            self.ft.Row(
                controls=[
                    self.ft.Button("Actualizar", on_click=self._refresh_reports),
                    self.ft.TextButton("Volver", on_click=lambda _: self._close()),
                ],
                wrap=True,
            ),
        ]
        controls.append(self._state_text(snapshot.list_state, snapshot.list_error))
        if snapshot.list_state is QueryState.STALE:
            controls.append(self.ft.Text("Mostrando lectura anterior"))
        if snapshot.list_state in {QueryState.ERROR, QueryState.STALE}:
            controls.append(self.ft.Button("Reintentar", on_click=self._refresh_reports))
        for item in snapshot.items:
            code = str(item.get("code", ""))
            controls.append(
                self.ft.Container(
                    padding=10,
                    content=self.ft.Column(
                        controls=[
                            self.ft.Text(code, weight=self.ft.FontWeight.BOLD, selectable=True),
                            self.ft.Text(f'{item.get("failure_type_label", "")} · {item.get("status_label", "")}'),
                            self.ft.Text(self._date(item.get("last_updated_at")), size=12),
                            self.ft.Button("Verificar y abrir detalle", on_click=self._verify_and_open_detail(code)),
                        ],
                        spacing=5,
                    ),
                )
            )
        if snapshot.next_cursor:
            controls.append(self.ft.Button("Cargar más", on_click=self._load_more))
        if snapshot.list_state is QueryState.EMPTY:
            controls.append(self.ft.Text("No tienes reportes"))
        return self.ft.Column(controls=controls, spacing=10, horizontal_alignment=self.ft.CrossAxisAlignment.STRETCH)

    def build_public(self) -> Any:
        snapshot = self.controller.snapshot()
        detail = snapshot.public_detail or {}
        controls: list[Any] = [
            self.ft.Text("Consulta pública", size=22, weight=self.ft.FontWeight.BOLD),
            self.ft.TextField(label="Código del reporte", value=self._code, on_change=self._code_changed),
            self.ft.Button("Buscar", on_click=self._search_public),
            self._state_text(snapshot.public_state, snapshot.public_error),
        ]
        if snapshot.public_state is QueryState.NOT_FOUND:
            controls.append(self.ft.Text("No encontramos un reporte con ese código"))
        elif snapshot.public_state is QueryState.READY and detail:
            controls.extend(
                [
                    self.ft.Text(f'Código: {detail.get("code", "")}', selectable=True),
                    self.ft.Text(f'Estado: {detail.get("status_label", "")}'),
                    self.ft.Text(self._date(detail.get("last_updated_at"))),
                    self.ft.Text(str(detail.get("public_summary", ""))),
                ]
            )
            code = str(detail.get("code", ""))
            if self._can_verify_private():
                if snapshot.verified_report_code == code:
                    controls.append(self.ft.Button("Ver mi reporte", on_click=lambda _: self._open_private_detail(code)))
                else:
                    controls.append(
                        self.ft.TextButton(
                            "Verificar si este es mi reporte",
                            on_click=self._verify_public_ownership(code),
                        )
                    )
        if snapshot.public_state is QueryState.ERROR:
            controls.append(self.ft.Button("Reintentar", on_click=self._search_public))
        controls.append(self.ft.TextButton("Volver", on_click=lambda _: self._close()))
        return self.ft.Column(controls=controls, spacing=10, horizontal_alignment=self.ft.CrossAxisAlignment.STRETCH)

    def set_public_code(self, code: str) -> None:
        self._code = code

    def build_private_detail(self) -> Any:
        snapshot = self.controller.snapshot()
        detail = snapshot.detail or {}
        controls: list[Any] = [
            self.ft.Text("Detalle de mi reporte", size=22, weight=self.ft.FontWeight.BOLD),
            self._state_text(snapshot.detail_state, snapshot.detail_error),
        ]
        if snapshot.detail_state is QueryState.NOT_FOUND:
            controls.append(self.ft.Text("Reporte no disponible"))
        elif snapshot.detail_state is QueryState.READY and detail:
            controls.extend(
                [
                    self.ft.Text(f'Código: {detail.get("code", "")}', selectable=True),
                    self.ft.Text(f'Estado: {detail.get("status_label", "")}'),
                    self.ft.Text(self._date(detail.get("last_updated_at"))),
                    self.ft.Text(str(detail.get("public_summary", ""))),
                    self.ft.Text("Descripción", weight=self.ft.FontWeight.BOLD),
                    self.ft.Text(str(detail.get("description", ""))),
                    self.ft.Text(f'Dirección: {detail.get("formatted_address") or "No disponible"}'),
                    self.ft.Text(f'Correo de contacto: {detail.get("contact_email") or "No disponible"}'),
                    self.ft.Text(f'Teléfono de contacto: {detail.get("contact_phone") or "No disponible"}'),
                    self.ft.Text(f'Avisos por correo: {"Sí" if detail.get("email_notifications") else "No"}'),
                    self.ft.Text("Fotografías", weight=self.ft.FontWeight.BOLD),
                    self.ft.Text("Historial", weight=self.ft.FontWeight.BOLD),
                ]
            )
            for evidence in detail.get("evidences", []):
                evidence_id = evidence.get("evidence_id")
                if type(evidence_id) is not int:
                    continue
                controls.append(
                    self.ft.Column(
                        controls=[
                            self.ft.Text(f'{evidence.get("media_type", "Imagen")} · {evidence.get("size_bytes", "")} bytes'),
                            self._evidence_control(snapshot.evidence_previews, evidence_id, evidence),
                        ]
                    )
                )
            for event in snapshot.history:
                controls.append(self.ft.Text(f'{self._date(event.get("occurred_at"))} · {event.get("label", "")}'))
            if snapshot.history_state in {QueryState.ERROR, QueryState.STALE}:
                controls.append(self.ft.Text(snapshot.history_error or "No fue posible consultar el historial."))
                controls.append(self.ft.Button("Reintentar historial", on_click=lambda _: self._retry_history(str(detail.get("code", "")))))
            if snapshot.next_history_cursor:
                code = str(detail.get("code", ""))
                controls.append(self.ft.Button("Cargar más historial", on_click=lambda _: self._load_history(code)))
        if snapshot.detail_state in {QueryState.ERROR, QueryState.STALE}:
            code = str(self._controller_code(snapshot))
            controls.append(self.ft.Button("Reintentar", on_click=lambda _: self._retry_detail(code)))
        controls.append(self.ft.TextButton("Volver", on_click=lambda _: self._close()))
        return self.ft.Column(controls=controls, spacing=10, horizontal_alignment=self.ft.CrossAxisAlignment.STRETCH)

    def _state_text(self, state: QueryState, error: str | None) -> Any:
        if state is QueryState.LOADING:
            return self.ft.ProgressRing(width=22, height=22)
        if state is QueryState.LOADING_MORE:
            return self.ft.Text("Cargando más…")
        if state in {QueryState.ERROR, QueryState.STALE}:
            return self.ft.Text(error or "No fue posible consultar el reporte.")
        return self.ft.Text("")

    def _open_detail(self, code: str):
        return lambda _: self._open_private_detail(code)

    def _verify_public_ownership(self, code: str):
        async def verify(event: Any) -> None:
            if self._verify_private_ownership is not None:
                verified = await self._verify_private_ownership(code)
                if not verified or self.controller.snapshot().verified_report_code != code:
                    self._refresh()
                    return
            self._refresh()

        return verify

    def _verify_and_open_detail(self, code: str):
        async def verify(event: Any) -> None:
            snapshot = await self.controller.ensure_private_detail(code)
            if snapshot.detail_state is QueryState.READY and snapshot.detail is not None and snapshot.verified_report_code == code:
                self._open_private_detail(code)
            else:
                self._refresh()

        return verify

    async def _refresh_reports(self, event: Any) -> None:
        await self.controller.refresh_reports()
        self._refresh()

    async def _load_more(self, event: Any) -> None:
        cursor = self.controller.snapshot().next_cursor
        if cursor:
            await self.controller.load_reports(cursor=cursor)
            self._refresh()

    async def _search_public(self, event: Any) -> None:
        await self.controller.load_public(self._code)
        self._refresh()

    async def _load_history(self, code: str) -> None:
        cursor = self.controller.snapshot().next_history_cursor
        await self.controller.load_history(code, cursor=cursor)
        self._refresh()

    def _controller_code(self, snapshot) -> str:
        return snapshot.requested_detail_code or str((snapshot.detail or {}).get("code", ""))

    async def _retry_detail(self, code: str) -> None:
        if code:
            await self.controller.load_private_detail(code)
            if self.controller.snapshot().detail_state is QueryState.READY:
                await self.controller.load_history(code)
        self._refresh()

    async def _retry_history(self, code: str) -> None:
        if code:
            await self.controller.load_history(code)
        self._refresh()

    def _preview(self, evidence_id: int):
        async def load(event: Any) -> None:
            await self.controller.load_evidence_preview(evidence_id)
            self._refresh()

        return load

    def _evidence_control(self, previews: dict[int, bytes], evidence_id: int, evidence: dict[str, Any]) -> Any:
        if evidence_id in previews:
            return self.ft.Image(
                src_base64=base64.b64encode(previews[evidence_id]).decode("ascii"),
                height=180,
                fit=self.ft.BoxFit.CONTAIN,
            )
        if evidence.get("content_available"):
            return self.ft.TextButton("Ver fotografía", on_click=self._preview(evidence_id))
        return self.ft.Text("Imagen no disponible")

    def _code_changed(self, event: Any) -> None:
        value = getattr(getattr(event, "control", None), "value", "")
        self._code = value if isinstance(value, str) else ""

    @staticmethod
    def _date(value: object) -> str:
        if not isinstance(value, str):
            return "Fecha no disponible"
        try:
            return format_display_date(value)
        except ValueError:
            return "Fecha no disponible"


__all__ = ["CitizenQueryViews"]
