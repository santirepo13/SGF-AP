"""Flet controls for the structured-address citizen report form."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from .citizen_report import CitizenReportController, CitizenReportFormState, CitizenReportStatus
from .design_tokens import COLORS


class CitizenReportView:
    """Render the citizen form without embedding transport or ticket decisions in Flet callbacks."""

    _INITIAL_CATALOGS = {
        "failure_types": "/catalogs/failure-types",
        "municipalities": "/catalogs/municipalities",
        "road_types": "/catalogs/road-types",
        "road_suffix_letters": "/catalogs/road-suffix-letters",
        "road_bis_codes": "/catalogs/road-bis-codes",
        "road_quadrants": "/catalogs/road-quadrants",
        "cross_suffix_letters": "/catalogs/cross-suffix-letters",
        "cross_bis_codes": "/catalogs/cross-bis-codes",
        "cross_quadrants": "/catalogs/cross-quadrants",
    }

    def __init__(
        self,
        ft: Any,
        controller: CitizenReportController,
        *,
        account_id: Callable[[], int | None],
        capture_scope: Callable[[], object | None],
        handle_protected_response: Callable[[object | None, object | None], Awaitable[bool]],
        refresh: Callable[[], None],
        close: Callable[[], None],
        open_ticket: Callable[[str], None],
    ) -> None:
        self.ft = ft
        self.controller = controller
        self._account_id = account_id
        self._capture_scope = capture_scope
        self._handle_protected_response = handle_protected_response
        self._refresh = refresh
        self._close = close
        self._open_ticket = open_ticket
        self._catalogs: dict[str, tuple[dict[str, object], ...]] = {}
        self._communes: tuple[dict[str, object], ...] = ()
        self._neighborhoods: tuple[dict[str, object], ...] = ()
        self._municipality_id: int | None = None
        self._commune_id: int | None = None
        self._catalog_loading = False
        self._catalog_error: str | None = None

    async def load_initial_catalogs(self) -> None:
        if self._catalog_loading or self._catalogs:
            return
        self._catalog_loading = True
        self._catalog_error = None
        self._refresh()
        try:
            loaded: dict[str, tuple[dict[str, object], ...]] = {}
            for name, path in self._INITIAL_CATALOGS.items():
                loaded[name] = await asyncio.to_thread(self.controller.load_catalog, path)
            self._catalogs = loaded
        except BaseException:
            self._catalog_error = "No fue posible cargar las opciones del formulario. Inténtalo nuevamente."
        finally:
            self._catalog_loading = False
            self._refresh()

    def build(self) -> Any:
        if self._catalog_loading:
            return self.ft.Column(
                controls=[
                    self.ft.ProgressRing(width=24, height=24),
                    self.ft.Text("Cargando opciones del reporte…"),
                ],
                horizontal_alignment=self.ft.CrossAxisAlignment.CENTER,
            )
        if not self._catalogs:
            return self.ft.Column(
                controls=[
                    self.ft.Text("Registrar falla de alumbrado", size=22, weight=self.ft.FontWeight.BOLD),
                    self.ft.Text(
                        self._catalog_error or "Carga las opciones para completar la dirección estructurada.",
                        text_align=self.ft.TextAlign.CENTER,
                    ),
                    self.ft.Button("Cargar opciones", on_click=self._load_click),
                    self.ft.TextButton("Volver", on_click=lambda _: self._close()),
                ],
                horizontal_alignment=self.ft.CrossAxisAlignment.STRETCH,
                spacing=12,
            )
        state = self.controller.snapshot()
        if state.status is CitizenReportStatus.CONFIRMED:
            return self._confirmation(state)
        if state.status is CitizenReportStatus.MATCHES:
            return self._matches(state)
        if state.status is CitizenReportStatus.UNKNOWN:
            return self._unknown(state)
        return self._form(state)

    async def _load_click(self, event: Any) -> None:
        await self.load_initial_catalogs()

    def _form(self, state: CitizenReportFormState) -> Any:
        disabled = state.processing
        submit_disabled = state.processing or state.operation_key_reused
        controls: list[Any] = [
            self.ft.Text("Registrar falla de alumbrado", size=22, weight=self.ft.FontWeight.BOLD),
            self.ft.Text("Indica la falla y la dirección estructurada donde la observaste."),
            self._dropdown(
                label="Tipo de falla",
                value=str(state.failure_type_id) if state.failure_type_id is not None else None,
                options=self._id_options(self._catalogs["failure_types"]),
                on_change=self._failure_changed,
                disabled=disabled,
            ),
            self._field_error(state, "failure_type_id"),
            self._field("description", "Descripción de la falla", state.description, disabled=disabled, multiline=True),
            self._field_error(state, "description"),
            self.ft.Divider(),
            self.ft.Text("Dirección estructurada", weight=self.ft.FontWeight.BOLD),
            self._dropdown(
                label="Municipio (opcional para orientar barrios)",
                value=str(self._municipality_id) if self._municipality_id is not None else None,
                options=self._id_options(self._catalogs["municipalities"]),
                on_change=self._municipality_changed,
                disabled=disabled,
            ),
            self._dropdown(
                label="Comuna",
                value=str(self._commune_id) if self._commune_id is not None else None,
                options=self._id_options(self._communes),
                on_change=self._commune_changed,
                disabled=disabled or self._municipality_id is None,
            ),
            self._dropdown(
                label="Barrio (opcional)",
                value=str(state.neighborhood_id) if state.neighborhood_id is not None else None,
                options=self._id_options(self._neighborhoods),
                on_change=self._neighborhood_changed,
                disabled=disabled or not self._neighborhoods,
            ),
            self._dropdown(
                label="Tipo de vía",
                value=state.road_type_code or None,
                options=self._code_options(self._catalogs["road_types"]),
                on_change=self._change_text("road_type_code"),
                disabled=disabled,
            ),
            self._field_error(state, "road_type_code"),
            self._field("road_number", "Número de vía (1–999)", state.road_number, disabled=disabled),
            self._field_error(state, "road_number"),
            self._dropdown(
                label="Letra de vía (opcional)",
                value=state.road_suffix_letter_code or None,
                options=self._code_options(self._catalogs["road_suffix_letters"]),
                on_change=self._change_text("road_suffix_letter_code"),
                disabled=disabled,
            ),
            self._dropdown(
                label="Código BIS de vía (opcional)",
                value=state.road_bis_code or None,
                options=self._code_options(self._catalogs["road_bis_codes"]),
                on_change=self._change_text("road_bis_code"),
                disabled=disabled,
            ),
            self._dropdown(
                label="Sufijo BIS de vía (opcional)",
                value=state.road_bis_suffix or None,
                options=self._letter_options(),
                on_change=self._change_text("road_bis_suffix"),
                disabled=disabled,
            ),
            self._dropdown(
                label="Cuadrante de vía (opcional)",
                value=state.road_quadrant_code or None,
                options=self._code_options(self._catalogs["road_quadrants"]),
                on_change=self._change_text("road_quadrant_code"),
                disabled=disabled,
            ),
            self._field("cross_road_number", "Número de cruce (1–999)", state.cross_road_number, disabled=disabled),
            self._field_error(state, "cross_road_number"),
            self._dropdown(
                label="Letra de cruce (opcional)",
                value=state.cross_suffix_letter_code or None,
                options=self._code_options(self._catalogs["cross_suffix_letters"]),
                on_change=self._change_text("cross_suffix_letter_code"),
                disabled=disabled,
            ),
            self._dropdown(
                label="Código BIS de cruce (opcional)",
                value=state.cross_bis_code or None,
                options=self._code_options(self._catalogs["cross_bis_codes"]),
                on_change=self._change_text("cross_bis_code"),
                disabled=disabled,
            ),
            self._dropdown(
                label="Sufijo BIS de cruce (opcional)",
                value=state.cross_bis_suffix or None,
                options=self._letter_options(),
                on_change=self._change_text("cross_bis_suffix"),
                disabled=disabled,
            ),
            self._dropdown(
                label="Cuadrante de cruce (opcional)",
                value=state.cross_quadrant_code or None,
                options=self._code_options(self._catalogs["cross_quadrants"]),
                on_change=self._change_text("cross_quadrant_code"),
                disabled=disabled,
            ),
            self._field("door_plate_number", "Número de placa (1–9999)", state.door_plate_number, disabled=disabled),
            self._field_error(state, "door_plate_number"),
            self.ft.Divider(),
            self.ft.Text("Datos de contacto (opcionales)", weight=self.ft.FontWeight.BOLD),
            self._field("contact_email", "Correo electrónico", state.contact_email, disabled=disabled),
            self._field_error(state, "contact_email"),
            self._field("contact_phone", "Teléfono", state.contact_phone, disabled=disabled),
            self._field_error(state, "contact_phone"),
            self.ft.Text("Los avisos por correo no están disponibles todavía; estos contactos no cambian tu identidad.", size=12),
        ]
        if self._catalog_error:
            controls.insert(2, self.ft.Text(self._catalog_error, color=COLORS["error"].hex))
        if state.processing:
            controls.append(self.ft.ProgressRing(width=22, height=22))
        if state.general_message:
            controls.append(self.ft.Text(state.general_message, color=self._message_color(state)))
        if state.storage_warning:
            controls.append(self.ft.Text(state.storage_warning, color=COLORS["warning"].hex))
        if state.operation_key_reused:
            controls.append(
                self.ft.Text(
                    "No reenvíes esta clave. Descarta el borrador o modifica la intención antes de crear otra.",
                    color=COLORS["warning"].hex,
                )
            )
            controls.append(self.ft.TextButton("Descartar borrador local", on_click=self._discard))
        controls.extend(
            [
                self.ft.Button("Enviar reporte", on_click=self._submit, disabled=submit_disabled),
                self.ft.TextButton("Volver", on_click=lambda _: self._close(), disabled=disabled),
            ]
        )
        return self.ft.Column(controls=controls, spacing=9, horizontal_alignment=self.ft.CrossAxisAlignment.STRETCH)

    def _confirmation(self, state: CitizenReportFormState) -> Any:
        ticket = state.confirmation or {}
        code = str(ticket.get("code", ""))
        return self.ft.Column(
            controls=[
                self.ft.Text("Reporte registrado", size=22, weight=self.ft.FontWeight.BOLD),
                self.ft.Text(f"Código: {code}", selectable=True),
                self.ft.Text(f"Estado: {ticket.get('status', 'Registered')}"),
                self.ft.Text(f"Fecha y hora: {ticket.get('created_at', '')}"),
                self.ft.Button("Abrir consulta", on_click=lambda _: self._open_ticket(code)),
                self.ft.TextButton("Volver al área ciudadana", on_click=lambda _: self._close()),
            ],
            spacing=12,
            horizontal_alignment=self.ft.CrossAxisAlignment.STRETCH,
        )

    def _matches(self, state: CitizenReportFormState) -> Any:
        items = [
            self.ft.Text("Ya existe un reporte abierto", size=22, weight=self.ft.FontWeight.BOLD),
            self.ft.Text("No se creó un nuevo reporte. Puedes conservar estas referencias para consultarlas."),
        ]
        for match in state.matches:
            items.append(
                self.ft.Container(
                    padding=10,
                    content=self.ft.Column(
                        controls=[
                            self.ft.Text(str(match["code"]), weight=self.ft.FontWeight.BOLD),
                            self.ft.Text(f"{match['progress_label']} · {match['status']}"),
                            self.ft.Text(str(match["created_at"]), size=12),
                        ]
                    ),
                )
            )
        items.append(self.ft.Text("El aporte de fotografías estará disponible en el recorrido de evidencias.", size=12))
        items.append(self.ft.TextButton("Volver al área ciudadana", on_click=lambda _: self._close()))
        return self.ft.Column(controls=items, spacing=10, horizontal_alignment=self.ft.CrossAxisAlignment.STRETCH)

    def _unknown(self, state: CitizenReportFormState) -> Any:
        return self.ft.Column(
            controls=[
                self.ft.Text("Confirmación pendiente", size=22, weight=self.ft.FontWeight.BOLD),
                self.ft.Text(state.general_message or "No se pudo confirmar el resultado del intento."),
                self.ft.Text(f"Clave del intento: {state.request_key or ''}", selectable=True),
                self.ft.Button("Comprobar intento", on_click=self._check),
                self.ft.Button("Reenviar el mismo intento", on_click=self._retry),
                self.ft.TextButton("Descartar borrador local", on_click=self._discard),
                self.ft.TextButton("Volver", on_click=lambda _: self._close()),
            ],
            spacing=12,
            horizontal_alignment=self.ft.CrossAxisAlignment.STRETCH,
        )

    def _field(self, name: str, label: str, value: str, *, disabled: bool, multiline: bool = False) -> Any:
        def changed(event: Any) -> None:
            candidate = getattr(getattr(event, "control", None), "value", "")
            self.controller.set_field(name, candidate if isinstance(candidate, str) else "")

        return self.ft.TextField(
            label=label,
            value=value,
            disabled=disabled,
            multiline=multiline,
            min_lines=3 if multiline else None,
            max_lines=5 if multiline else None,
            on_change=changed,
        )

    def _dropdown(self, *, label: str, value: str | None, options: list[Any], on_change, disabled: bool) -> Any:
        return self.ft.Dropdown(
            label=label,
            value=value,
            options=[self._option("", "Selecciona")] + options,
            on_change=on_change,
            disabled=disabled,
        )

    def _field_error(self, state: CitizenReportFormState, name: str) -> Any:
        value = state.field_errors.get(name, "")
        return self.ft.Text(value, color=COLORS["error"].hex, size=12, visible=bool(value))

    async def _submit(self, event: Any) -> None:
        account_id = self._account_id()
        if account_id is None:
            return
        scope = self._capture_scope()
        await asyncio.to_thread(self.controller.submit, account_id)
        if await self._handle_protected_response(scope, self.controller.take_last_protected_response()):
            return
        self._refresh()

    async def _retry(self, event: Any) -> None:
        account_id = self._account_id()
        if account_id is None:
            return
        scope = self._capture_scope()
        await asyncio.to_thread(self.controller.retry_pending, account_id)
        if await self._handle_protected_response(scope, self.controller.take_last_protected_response()):
            return
        self._refresh()

    async def _check(self, event: Any) -> None:
        account_id = self._account_id()
        if account_id is None:
            return
        scope = self._capture_scope()
        await asyncio.to_thread(self.controller.check_pending, account_id)
        if await self._handle_protected_response(scope, self.controller.take_last_protected_response()):
            return
        self._refresh()

    async def _discard(self, event: Any) -> None:
        account_id = self._account_id()
        if account_id is None:
            return
        await self.controller.discard_pending(account_id)
        self._refresh()

    async def _failure_changed(self, event: Any) -> None:
        value = self._event_value(event)
        self.controller.set_failure_type(int(value) if value else None)
        self._refresh()

    async def _municipality_changed(self, event: Any) -> None:
        value = self._event_value(event)
        self._municipality_id = int(value) if value else None
        self._commune_id = None
        self._communes = ()
        self._neighborhoods = ()
        self.controller.set_neighborhood(None)
        if self._municipality_id is not None:
            try:
                self._communes = await asyncio.to_thread(
                    self.controller.load_catalog,
                    f"/catalogs/municipalities/{self._municipality_id}/communes",
                )
                self._neighborhoods = await asyncio.to_thread(
                    self.controller.load_catalog,
                    f"/catalogs/municipalities/{self._municipality_id}/neighborhoods",
                )
            except BaseException:
                self._catalog_error = "No fue posible cargar las opciones de ubicación."
        self._refresh()

    async def _commune_changed(self, event: Any) -> None:
        value = self._event_value(event)
        self._commune_id = int(value) if value else None
        self._neighborhoods = ()
        self.controller.set_neighborhood(None)
        if self._commune_id is not None:
            try:
                self._neighborhoods = await asyncio.to_thread(
                    self.controller.load_catalog,
                    f"/catalogs/communes/{self._commune_id}/neighborhoods",
                )
            except BaseException:
                self._catalog_error = "No fue posible cargar los barrios de la comuna."
        self._refresh()

    async def _neighborhood_changed(self, event: Any) -> None:
        value = self._event_value(event)
        self.controller.set_neighborhood(int(value) if value else None)
        self._refresh()

    def _change_text(self, name: str):
        async def changed(event: Any) -> None:
            self.controller.set_field(name, self._event_value(event))
            self._refresh()

        return changed

    def _id_options(self, values: tuple[dict[str, object], ...]) -> list[Any]:
        return [
            self._option(
                str(value["id"]),
                str(value.get("name", value["id"])),
            )
            for value in values
            if type(value.get("id")) is int
        ]

    def _code_options(self, values: tuple[dict[str, object], ...]) -> list[Any]:
        return [
            self._option(
                str(value["code"]),
                str(value.get("name", value["code"])),
            )
            for value in values
            if value.get("code") is not None
        ]

    def _letter_options(self) -> list[Any]:
        return [self._option(letter, letter) for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]

    def _option(self, key: str, text: str) -> Any:
        option_type = getattr(self.ft, "DropdownOption", None)
        if option_type is not None:
            return option_type(key=key, text=text)
        legacy = getattr(getattr(self.ft, "dropdown", None), "Option", None)
        if legacy is None:
            raise RuntimeError("La versión instalada de Flet no admite opciones de selector.")
        return legacy(key=key, text=text)

    @staticmethod
    def _event_value(event: Any) -> str:
        value = getattr(getattr(event, "control", None), "value", "")
        return value if isinstance(value, str) else ""

    def _message_color(self, state: CitizenReportFormState) -> str:
        return COLORS["error"].hex if state.status is CitizenReportStatus.REJECTED else COLORS["text_secondary"].hex


__all__ = ["CitizenReportView"]
