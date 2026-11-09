"""Flet presentation for the citizen temporary-photo flow."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from .citizen_evidence import CitizenEvidenceController, CitizenPhotoSelection, CitizenPhotoState
from .device_photos import DevicePhotoError, DevicePhotoPicker
from .design_tokens import COLORS


class CitizenEvidenceView:
    """Render selection, upload, retry, and removal without owning API credentials."""

    def __init__(
        self,
        ft: Any,
        controller: CitizenEvidenceController,
        picker: DevicePhotoPicker,
        *,
        handle_protected_response: Callable[[object | None, object | None], Awaitable[bool]],
        refresh: Callable[[], None],
    ) -> None:
        self.ft = ft
        self.controller = controller
        self.picker = picker
        self._handle_protected_response = handle_protected_response
        self._refresh = refresh
        self._message: str | None = None
        self._busy = False

    @property
    def can_submit_report(self) -> bool:
        return self.controller.can_submit_report()

    @property
    def can_contribute(self) -> bool:
        return bool(self.controller.ready_upload_ids()) and self.controller.can_submit_report()

    async def restore(self) -> None:
        try:
            await self.controller.restore_server_uploads()
        except RuntimeError as error:
            self._message = str(error)
        response = self.controller.take_last_protected_response()
        if response is not None:
            scope, value = response
            if await self._handle_protected_response(scope, value):
                return
        self._refresh()

    async def dispose(self) -> None:
        await self.picker.dispose()

    def clear_for_new_report(self) -> None:
        self._message = None
        self.controller.clear_account_private_state()

    def build(self, *, disabled: bool = False) -> Any:
        selections = self.controller.selections
        limit_reached = len(selections) >= self.controller.MAX_PHOTOS
        controls: list[Any] = [
            self.ft.Text("Fotografías (opcionales)", weight=self.ft.FontWeight.BOLD),
            self.ft.Text(
                "Puedes agregar hasta tres fotografías de máximo 10 MB. "
                "Se asocian al reporte solamente cuando el envío se confirma.",
                size=12,
            ),
            self.ft.Row(
                controls=[
                    self.ft.Button(
                        "Agregar fotografía",
                        on_click=self._choose,
                        disabled=disabled or self._busy or limit_reached,
                    ),
                    self.ft.Button(
                        "Tomar fotografía",
                        on_click=self._capture,
                        disabled=disabled or self._busy or limit_reached,
                    ),
                ],
                wrap=True,
            ),
        ]
        if self._message:
            controls.append(self.ft.Text(self._message, color=COLORS["error"].hex, size=12))
        if not selections:
            controls.append(self.ft.Text("No has agregado fotografías.", size=12))
        for selection in selections:
            controls.append(self._card(selection, disabled=disabled))
        return self.ft.Column(
            controls=controls,
            spacing=8,
            horizontal_alignment=self.ft.CrossAxisAlignment.STRETCH,
        )

    async def _choose(self, event: Any) -> None:
        await self._pick(self.picker.choose)

    async def _capture(self, event: Any) -> None:
        await self._pick(self.picker.capture)

    async def _pick(self, action: Callable[[], Awaitable[object | None]]) -> None:
        if self._busy:
            return
        self._busy = True
        self._message = None
        self._refresh()
        try:
            photo = await action()
            if photo is None:
                return
            selection = await self.controller.select_photo(photo)
            self._refresh()
            await self._upload(selection.selection_id)
        except (DevicePhotoError, RuntimeError, ValueError) as error:
            self._message = str(error)
        finally:
            self._busy = False
            self._refresh()

    def _upload_click(self, selection_id: str):
        async def handler(event: Any) -> None:
            await self._upload(selection_id)

        return handler

    async def _upload(self, selection_id: str) -> None:
        self._message = None
        try:
            await self.controller.upload(selection_id)
        except (RuntimeError, ValueError) as error:
            self._message = str(error)
        response = self.controller.take_last_protected_response()
        if response is not None:
            scope, value = response
            if await self._handle_protected_response(scope, value):
                return
        self._refresh()

    def _remove_click(self, selection_id: str):
        async def handler(event: Any) -> None:
            self._message = None
            try:
                await self.controller.remove(selection_id)
            except (RuntimeError, ValueError) as error:
                self._message = str(error)
            response = self.controller.take_last_protected_response()
            if response is not None:
                scope, value = response
                if await self._handle_protected_response(scope, value):
                    return
            self._refresh()

        return handler

    def _card(self, selection: CitizenPhotoSelection, *, disabled: bool) -> Any:
        state_text, state_color = self._state_text(selection)
        details = [
            self.ft.Text(selection.display_name, weight=self.ft.FontWeight.BOLD),
            self.ft.Text(self._source_text(selection.source), size=12),
            self.ft.Text(self._size_text(selection.size_bytes), size=12),
            self.ft.Text(state_text, color=state_color, size=12),
        ]
        if selection.preview is not None:
            details.insert(
                1,
                self.ft.Image(
                    src=selection.preview,
                    height=132,
                    fit=self.ft.BoxFit.CONTAIN,
                    gapless_playback=True,
                ),
            )
        if selection.state is CitizenPhotoState.UPLOADING:
            total = selection.size_bytes or 0
            value = selection.progress_bytes / total if total else None
            details.append(self.ft.ProgressBar(value=value))
            details.append(
                self.ft.Text(
                    f"{self._size_text(selection.progress_bytes)} de {self._size_text(total)}",
                    size=12,
                )
            )
        if selection.error_message:
            details.append(self.ft.Text(selection.error_message, color=COLORS["error"].hex, size=12))

        actions: list[Any] = []
        if selection.state in {CitizenPhotoState.SELECTED, CitizenPhotoState.FAILED}:
            label = "Reintentar carga" if selection.state is CitizenPhotoState.FAILED else "Subir fotografía"
            actions.append(
                self.ft.TextButton(
                    label,
                    on_click=self._upload_click(selection.selection_id),
                    disabled=disabled or self._busy,
                )
            )
        if selection.state is not CitizenPhotoState.ATTACHED:
            actions.append(
                self.ft.TextButton(
                    "Eliminar",
                    on_click=self._remove_click(selection.selection_id),
                    disabled=disabled or self._busy or selection.state is CitizenPhotoState.UPLOADING,
                )
            )
        if actions:
            details.append(self.ft.Row(controls=actions, wrap=True))
        return self.ft.Container(
            padding=10,
            border=self.ft.Border.all(1, COLORS["border"].hex),
            border_radius=8,
            content=self.ft.Column(
                controls=details,
                spacing=5,
                horizontal_alignment=self.ft.CrossAxisAlignment.STRETCH,
            ),
        )

    def _state_text(self, selection: CitizenPhotoSelection) -> tuple[str, str]:
        if selection.state is CitizenPhotoState.SELECTED:
            return "Lista para cargar", COLORS["text_secondary"].hex
        if selection.state is CitizenPhotoState.UPLOADING:
            return "Cargando fotografía…", COLORS["text_secondary"].hex
        if selection.state is CitizenPhotoState.READY:
            return "Lista para asociar al enviar", COLORS["success"].hex
        if selection.state is CitizenPhotoState.LOCAL_UNAVAILABLE:
            return "Lista en el servidor; sin copia local", COLORS["warning"].hex
        if selection.state is CitizenPhotoState.ATTACHED:
            return "Asociada al reporte", COLORS["success"].hex
        return "La carga necesita atención", COLORS["error"].hex

    @staticmethod
    def _source_text(source: str) -> str:
        return {
            "camera": "Tomada con la cámara",
            "device_metadata": "Seleccionada desde el dispositivo",
            "user_declared": "Agregada por la persona usuaria",
            "unknown": "Origen no especificado",
        }.get(source, "Origen no especificado")

    @staticmethod
    def _size_text(value: int | None) -> str:
        if type(value) is not int or value < 0:
            return "Tamaño no disponible"
        return f"{value / 1_000_000:.2f} MB"


__all__ = ["CitizenEvidenceView"]
