"""Flet presentation layer for the SGF-AP login and registration flow."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from .design_tokens import COLORS
from .http_connector import RegistrationHttpConnector, build_registration_connector
from .registration import RegistrationController, RegistrationFormState, RegistrationStatus


class _UnavailableConnector:
    """Displays a safe failure when client configuration is unavailable."""

    def __init__(self, reason: BaseException) -> None:
        self.reason = reason

    def register_citizen(self, **kwargs: str) -> object:
        raise RuntimeError("registration service configuration is unavailable") from self.reason


def main(page: Any, *, connector_factory: Callable[[], RegistrationHttpConnector] | None = None) -> None:
    """Build the login screen and the citizen-registration screen."""

    ft = _load_flet()
    page.title = "SGF-AP"
    page.bgcolor = COLORS["background_general"].hex
    page.padding = 0

    configuration_message: str | None = None
    try:
        connector = (connector_factory or build_registration_connector)()
    except Exception as error:
        connector = _UnavailableConnector(error)
        configuration_message = _configuration_message(error)
    registration = RegistrationController(connector)

    def refresh() -> None:
        page.update()

    def text_field(name: str, label: str, *, secret: bool = False) -> Any:
        state = registration.state

        def changed(event: Any) -> None:
            value = getattr(getattr(event, "control", None), "value", "")
            registration.set_field(name, value if isinstance(value, str) else "")

        return ft.TextField(
            label=label,
            value=getattr(state, name),
            width=420,
            password=secret,
            can_reveal_password=False,
            on_change=changed,
        )

    def error_text(value: str | None) -> Any:
        return ft.Text(value or "", color=COLORS["error"].hex, size=12, visible=bool(value))

    def card(content: Any) -> Any:
        return ft.Container(
            content=content,
            width=480,
            padding=24,
            bgcolor=COLORS["surface"].hex,
            border_radius=12,
            shadow=ft.BoxShadow(blur_radius=12, spread_radius=1, color=COLORS["shadow"].hex),
        )

    def root(content: Any) -> Any:
        return ft.SafeArea(
            content=ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                padding=24,
                content=content,
            ),
            expand=True,
        )

    def replace(content: Any) -> None:
        page.clean()
        page.add(root(card(content)))
        refresh()

    def render_login() -> None:
        email = ft.TextField(label="Correo electrónico", width=420)
        password = ft.TextField(label="Contraseña", width=420, password=True, can_reveal_password=False)
        message = ft.Text("", color=COLORS["error"].hex, visible=False, text_align=ft.TextAlign.CENTER)

        def unavailable(event: Any) -> None:
            message.value = "El ingreso aún no está habilitado."
            message.visible = True
            refresh()

        def open_registration(event: Any) -> None:
            render_registration()

        content = ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
            controls=[
                ft.Text("SGF-AP", size=30, weight=ft.FontWeight.BOLD, color=COLORS["primary"].hex),
                ft.Text("Ingreso ciudadano", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"].hex),
                ft.Text("Reporta y consulta fallas de alumbrado público.", color=COLORS["text_secondary"].hex, text_align=ft.TextAlign.CENTER),
                email,
                password,
                message,
                ft.Button("Ingresar", bgcolor=COLORS["primary"].hex, color=COLORS["text_on_primary"].hex, on_click=unavailable),
                ft.TextButton("Crear cuenta ciudadana", on_click=open_registration),
                ft.TextButton("¿Olvidaste tu contraseña?", on_click=unavailable),
            ],
        )
        replace(content)

    def render_registration() -> None:
        state = registration.state
        first_name = text_field("first_name", "Nombre")
        last_name = text_field("last_name", "Apellido")
        email = text_field("email", "Correo electrónico")
        password = text_field("password", "Contraseña", secret=True)
        confirm_password = text_field("confirm_password", "Confirmar contraseña", secret=True)
        progress = ft.ProgressRing(width=22, height=22, visible=state.status is RegistrationStatus.PROCESSING)
        status = ft.Text(
            state.general_message or configuration_message or "",
            color=COLORS["error"].hex if configuration_message else _status_color(state.status),
            visible=bool(state.general_message) or configuration_message is not None,
            text_align=ft.TextAlign.CENTER,
        )
        submit = ft.Button(
            "Crear cuenta",
            bgcolor=COLORS["primary"].hex,
            color=COLORS["text_on_primary"].hex,
            disabled=configuration_message is not None or not state.can_submit,
        )

        async def submit_click(event: Any) -> None:
            submit.disabled = True
            progress.visible = True
            refresh()
            result = await asyncio.to_thread(registration.submit)
            apply_state(result)

        def back(event: Any) -> None:
            registration.abandon()
            render_login()

        def continue_to_login(event: Any) -> None:
            registration.abandon()
            render_login()

        def apply_state(result: RegistrationFormState) -> None:
            render_registration()

        submit.on_click = submit_click
        controls = [
            ft.Text("Crear cuenta ciudadana", size=24, weight=ft.FontWeight.BOLD, color=COLORS["primary"].hex),
            ft.Text("Completa tus datos para acceder a las funciones ciudadanas.", color=COLORS["text_secondary"].hex, text_align=ft.TextAlign.CENTER),
            first_name,
            error_text(state.field_errors.get("first_name")),
            last_name,
            error_text(state.field_errors.get("last_name")),
            email,
            error_text(state.field_errors.get("email")),
            password,
            error_text(state.field_errors.get("password")),
            confirm_password,
            error_text(state.field_errors.get("confirm_password") or state.field_errors.get("password_match")),
            ft.Row(controls=[progress, submit], alignment=ft.MainAxisAlignment.CENTER),
            status,
        ]
        if state.continue_to_login:
            controls.append(ft.Button("Continuar al ingreso", on_click=continue_to_login))
        controls.append(ft.TextButton("Volver al ingreso", on_click=back))
        replace(ft.Column(controls=controls, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8, scroll=ft.ScrollMode.AUTO))

    render_login()


def run() -> None:
    """Start the Flet runtime."""

    _load_flet().run(main)


def _load_flet() -> Any:
    try:
        import flet as ft
    except ModuleNotFoundError as error:
        raise RuntimeError("Install Flet with: python -m pip install -r mobile/requirements.txt") from error
    return ft


def _configuration_message(error: Exception) -> str:
    """Return an actionable configuration message without exposing secrets."""

    if isinstance(error, ValueError):
        return str(error)
    return "No se pudo cargar la configuración local del servicio."


def _status_color(status: RegistrationStatus) -> str:
    if status is RegistrationStatus.COMPLETED:
        return COLORS["success"].hex
    if status is RegistrationStatus.UNCONFIRMED:
        return COLORS["warning"].hex
    if status is RegistrationStatus.REJECTED:
        return COLORS["error"].hex
    return COLORS["text_secondary"].hex


__all__ = ["main", "run"]
