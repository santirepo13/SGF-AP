"""Flet presentation layer for the SGF-AP login and registration flow.

The domain/controller layer remains usable without Flet.  This module is the
thin visual adapter used by ``main.py`` during desktop, web, and Flet mobile
preview runs.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from .design_tokens import COLORS
from .http_connector import RegistrationHttpConnector, build_registration_connector
from .navigation import NavigationController, ScreenName
from .registration import RegistrationController, RegistrationFormState, RegistrationStatus


class _UnavailableConnector:
    """Connector used when local configuration is unavailable at app startup."""

    def __init__(self, reason: BaseException) -> None:
        self.reason = reason

    def register_citizen(self, **kwargs: str) -> object:
        raise RuntimeError("registration service configuration is unavailable") from self.reason


def main(page: Any, *, connector_factory: Callable[[], RegistrationHttpConnector] | None = None) -> None:
    """Render the initial login screen and the citizen-registration screen."""

    ft = _load_flet()
    page.title = "SGF-AP"
    page.bgcolor = COLORS["background_general"].hex
    page.padding = 0
    page.scroll = getattr(ft, "ScrollMode", type("ScrollMode", (), {"AUTO": "auto"})).AUTO

    navigation = NavigationController()
    connector_error: BaseException | None = None
    try:
        connector = (connector_factory or build_registration_connector)()
    except BaseException as error:  # Configuration errors are shown in the UI.
        connector_error = error
        connector = _UnavailableConnector(error)

    registration = RegistrationController(connector)

    def update_page() -> None:
        """Refresh the current Flet tree without assuming a particular Flet version."""

        update = getattr(page, "update", None)
        if callable(update):
            update()

    def field_value(event: Any) -> str:
        value = getattr(getattr(event, "control", None), "value", "")
        return value if isinstance(value, str) else ""

    def make_text_field(
        *,
        name: str,
        label: str,
        value: str = "",
        password: bool = False,
        on_change: Callable[[Any], None] | None = None,
    ) -> Any:
        kwargs: dict[str, object] = {
            "label": label,
            "value": value,
            "width": 420,
            "autofill_hint": _autofill_hint(ft, name),
            "password": password,
            "can_reveal_password": False if password else None,
            "on_change": on_change,
        }
        # Flet versions differ on whether None-valued optional properties are
        # accepted by the constructor.
        return _construct(ft.TextField, {key: value for key, value in kwargs.items() if value is not None})

    def text_for_error(message: str | None) -> Any:
        return ft.Text(
            message or "",
            color=COLORS["error"].hex,
            size=12,
            visible=bool(message),
        )

    def card(content: Any) -> Any:
        return ft.Container(
            content=content,
            width=480,
            padding=24,
            bgcolor=COLORS["surface"].hex,
            border_radius=12,
            shadow=_shadow(ft),
        )

    def page_body(content: Any) -> Any:
        return ft.SafeArea(
            expand=True,
            content=ft.Container(
                expand=True,
                alignment=_alignment(ft, "center"),
                padding=24,
                content=content,
            ),
        )

    def show_message(message: str, *, color: str, visible: bool = True) -> Any:
        return ft.Container(
            content=ft.Text(message, color=color, size=13),
            bgcolor=_message_background(color),
            padding=12,
            border_radius=8,
            visible=visible,
        )

    def render_login() -> None:
        navigation.active_screen = ScreenName.LOGIN
        email = make_text_field(name="email", label="Correo electrónico")
        password = make_text_field(name="password", label="Contraseña", password=True)
        login_message = ft.Text("", color=COLORS["error"].hex, visible=False)

        def login_click(event: Any) -> None:
            login_message.value = "El ingreso estará disponible cuando se habilite la autenticación ciudadana."
            login_message.visible = True
            update_page()

        def create_account_click(event: Any) -> None:
            navigation.create_account()
            render_registration()

        def recover_click(event: Any) -> None:
            login_message.value = "La recuperación de contraseña aún no está habilitada."
            login_message.visible = True
            update_page()

        login_button = _button(ft, "Ingresar", on_click=login_click, primary=True)
        create_button = _text_button(ft, "Crear cuenta ciudadana", on_click=create_account_click)
        recover_button = _text_button(ft, "¿Olvidaste tu contraseña?", on_click=recover_click)
        content = ft.Column(
            horizontal_alignment=_cross_alignment(ft, "center"),
            spacing=14,
            controls=[
                ft.Text("SGF-AP", size=30, weight=_font_weight(ft, "bold"), color=COLORS["primary"].hex),
                ft.Text("Ingreso ciudadano", size=20, weight=_font_weight(ft, "bold"), color=COLORS["text_primary"].hex),
                ft.Text("Reporta y consulta fallas de alumbrado público.", color=COLORS["text_secondary"].hex, text_align=_text_align(ft, "center")),
                email,
                password,
                login_message,
                login_button,
                create_button,
                recover_button,
            ],
        )
        page.clean()
        page.add(page_body(card(content)))
        update_page()

    def render_registration() -> None:
        state = registration.state
        first_name = make_text_field(
            name="first_name",
            label="Nombre",
            value=state.first_name,
            on_change=lambda event: registration.set_field("first_name", field_value(event)),
        )
        last_name = make_text_field(
            name="last_name",
            label="Apellido",
            value=state.last_name,
            on_change=lambda event: registration.set_field("last_name", field_value(event)),
        )
        email = make_text_field(
            name="email",
            label="Correo electrónico",
            value=state.email,
            on_change=lambda event: registration.set_field("email", field_value(event)),
        )
        password = make_text_field(
            name="password",
            label="Contraseña",
            value=state.password,
            password=True,
            on_change=lambda event: registration.set_field("password", field_value(event)),
        )
        confirm_password = make_text_field(
            name="confirm_password",
            label="Confirmar contraseña",
            value=state.confirm_password,
            password=True,
            on_change=lambda event: registration.set_field("confirm_password", field_value(event)),
        )
        error_labels = {
            "first_name": text_for_error(state.field_errors.get("first_name")),
            "last_name": text_for_error(state.field_errors.get("last_name")),
            "email": text_for_error(state.field_errors.get("email")),
            "password": text_for_error(state.field_errors.get("password")),
            "confirm_password": text_for_error(
                state.field_errors.get("confirm_password") or state.field_errors.get("password_match")
            ),
        }
        status_text = ft.Text(
            state.general_message or "",
            color=_status_color(state.status),
            visible=bool(state.general_message),
            text_align=_text_align(ft, "center"),
        )
        progress = ft.ProgressRing(visible=state.status is RegistrationStatus.PROCESSING, width=22, height=22)
        submit_button = _button(
            ft,
            "Crear cuenta",
            on_click=None,
            primary=True,
            disabled=not state.can_submit,
        )
        back_button = _text_button(ft, "Volver al ingreso", on_click=None)
        continue_button = _button(ft, "Continuar al ingreso", on_click=None, primary=True, visible=state.continue_to_login)

        async def submit_click(event: Any) -> None:
            # The controller suppresses duplicate attempts; the worker keeps
            # urllib/Flet network I/O off the UI event loop.
            submit_button.disabled = True
            progress.visible = True
            update_page()
            result = await asyncio.to_thread(registration.submit)
            apply_state(result)

        def back_click(event: Any) -> None:
            registration.abandon()
            navigation.back_to_login()
            render_login()

        def continue_click(event: Any) -> None:
            registration.abandon()
            navigation.continue_to_login()
            render_login()

        submit_button.on_click = submit_click
        back_button.on_click = back_click
        continue_button.on_click = continue_click

        if connector_error is not None and not state.general_message:
            status_text.value = "No se pudo cargar la configuración del servicio."
            status_text.color = COLORS["error"].hex
            status_text.visible = True

        content = ft.Column(
            horizontal_alignment=_cross_alignment(ft, "center"),
            spacing=8,
            scroll=getattr(ft, "ScrollMode", type("ScrollMode", (), {"AUTO": "auto"})).AUTO,
            controls=[
                ft.Text("Crear cuenta ciudadana", size=24, weight=_font_weight(ft, "bold"), color=COLORS["primary"].hex),
                ft.Text(
                    "Completa tus datos para acceder a las funciones ciudadanas.",
                    color=COLORS["text_secondary"].hex,
                    text_align=_text_align(ft, "center"),
                ),
                first_name,
                error_labels["first_name"],
                last_name,
                error_labels["last_name"],
                email,
                error_labels["email"],
                password,
                error_labels["password"],
                confirm_password,
                error_labels["confirm_password"],
                ft.Row(alignment=_main_alignment(ft, "center"), controls=[progress, submit_button]),
                status_text,
                continue_button,
                back_button,
            ],
        )
        page.clean()
        page.add(page_body(card(content)))
        update_page()

        def apply_state(result: RegistrationFormState) -> None:
            # Re-rendering preserves all non-secret values in the controller
            # and guarantees that stale field errors disappear consistently.
            render_registration()

    render_login()


def run() -> None:
    """Start the Flet development/runtime host."""

    ft = _load_flet()
    runner = getattr(ft, "run", None)
    if callable(runner):
        runner(main)
        return
    app = getattr(ft, "app", None)
    if callable(app):
        app(target=main)
        return
    raise RuntimeError("The installed Flet version has no supported application runner")


def _load_flet() -> Any:
    try:
        import flet as ft
    except ModuleNotFoundError as error:  # Keep API-only imports independent of UI dependencies.
        raise RuntimeError("Install the mobile dependencies with: py -m pip install -r mobile/requirements.txt") from error
    return ft


def _construct(factory: Callable[..., Any], values: dict[str, object]) -> Any:
    try:
        return factory(**values)
    except TypeError:
        # Older Flet releases do not accept every newer optional TextField
        # property; retry with the stable core properties only.
        stable = {key: values[key] for key in ("label", "value", "width", "password", "on_change") if key in values}
        return factory(**stable)


def _button(ft: Any, text: str, *, on_click: Callable[[Any], Any] | None, primary: bool, disabled: bool = False, visible: bool = True) -> Any:
    button_type = getattr(ft, "Button", None) or getattr(ft, "ElevatedButton")
    kwargs = {"text": text, "on_click": on_click, "disabled": disabled, "visible": visible}
    if primary:
        kwargs["style"] = _button_style(ft)
    try:
        return button_type(**kwargs)
    except TypeError:
        kwargs.pop("style", None)
        return button_type(text, on_click=on_click, disabled=disabled, visible=visible)


def _text_button(ft: Any, text: str, *, on_click: Callable[[Any], Any]) -> Any:
    button_type = getattr(ft, "TextButton", None) or getattr(ft, "TextButton")
    try:
        return button_type(text=text, on_click=on_click, style=_text_button_style(ft))
    except TypeError:
        return button_type(text, on_click=on_click)


def _button_style(ft: Any) -> object:
    style_type = getattr(ft, "ButtonStyle", None)
    if style_type is None:
        return None
    try:
        return style_type(bgcolor=COLORS["primary"].hex, color=COLORS["text_on_primary"].hex)
    except TypeError:
        return None


def _text_button_style(ft: Any) -> object:
    style_type = getattr(ft, "ButtonStyle", None)
    if style_type is None:
        return None
    try:
        return style_type(color=COLORS["primary"].hex)
    except TypeError:
        return None


def _shadow(ft: Any) -> object:
    shadow_type = getattr(ft, "BoxShadow", None)
    if shadow_type is None:
        return None
    try:
        return shadow_type(blur_radius=12, spread_radius=1, color=COLORS["shadow"].hex)
    except TypeError:
        return None


def _alignment(ft: Any, name: str) -> object:
    alignment = getattr(ft, "Alignment", None)
    if alignment is not None and name == "center":
        center = getattr(alignment, "CENTER", None)
        if center is not None:
            return center
        try:
            return alignment(0, 0)
        except TypeError:
            pass
    return getattr(getattr(ft, "MainAxisAlignment", object), "CENTER", "center")


def _main_alignment(ft: Any, name: str) -> object:
    return getattr(getattr(ft, "MainAxisAlignment", object), name.upper(), "center")


def _cross_alignment(ft: Any, name: str) -> object:
    return getattr(getattr(ft, "CrossAxisAlignment", object), name.upper(), "center")


def _text_align(ft: Any, name: str) -> object:
    return getattr(getattr(ft, "TextAlign", object), name.upper(), "center")


def _font_weight(ft: Any, name: str) -> object:
    return getattr(getattr(ft, "FontWeight", object), name.upper(), "bold")


def _autofill_hint(ft: Any, name: str) -> object | None:
    hints = getattr(ft, "AutofillHint", None)
    if hints is None:
        return None
    mapping = {"email": "EMAIL", "password": "PASSWORD", "confirm_password": "NEW_PASSWORD"}
    return getattr(hints, mapping.get(name, "NAME"), None)


def _status_color(status: RegistrationStatus) -> str:
    if status is RegistrationStatus.COMPLETED:
        return COLORS["success"].hex
    if status is RegistrationStatus.UNCONFIRMED:
        return COLORS["warning"].hex
    if status is RegistrationStatus.REJECTED:
        return COLORS["error"].hex
    return COLORS["text_secondary"].hex


def _message_background(color: str) -> str:
    if color == COLORS["error"].hex:
        return COLORS["error_background"].hex
    if color == COLORS["success"].hex:
        return COLORS["success_background"].hex
    return COLORS["info_background"].hex


__all__ = ["main", "run"]
