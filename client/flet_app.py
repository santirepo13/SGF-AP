"""Responsive Flet presentation layer for SGF-AP access flows."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from .authentication import AuthenticationState
from .design_tokens import COLORS
from .http_connector import RegistrationHttpConnector, build_registration_connector
from .login import LoginController, LoginFormState, LoginOutput, LoginStatus
from .navigation import NavigationController, ScreenName
from .registration import RegistrationController, RegistrationStatus


MOTO_EDGE_50_FUSION_PREVIEW_WIDTH = 432
MOTO_EDGE_50_FUSION_PREVIEW_HEIGHT = 960
_DESKTOP_PLATFORMS = frozenset({"windows", "linux", "macos"})


class _UnavailableConnector:
    """Provides a safe failure when local API configuration is unavailable."""

    def __init__(self, reason: BaseException) -> None:
        self.reason = reason

    def register_citizen(self, **kwargs: str) -> object:
        raise RuntimeError("registration service configuration is unavailable") from self.reason

    def login(self, **kwargs: str) -> object:
        raise RuntimeError("login service configuration is unavailable") from self.reason


def main(page: Any, *, connector_factory: Callable[[], RegistrationHttpConnector] | None = None) -> None:
    """Build responsive login, registration, recovery, and role landing views."""

    ft = _load_flet()
    page.title = "SGF-AP"
    page.bgcolor = COLORS["background_general"].hex
    page.padding = 0
    _configure_phone_preview_window(page)

    authenticated = AuthenticationState()
    configuration_message: str | None = None
    try:
        connector = (
            connector_factory()
            if connector_factory is not None
            else build_registration_connector(access_token_supplier=authenticated.access_token_for_request)
        )
    except Exception as error:
        connector = _UnavailableConnector(error)
        configuration_message = _configuration_message(error)

    login: LoginController | None = None
    registration = RegistrationController(connector)

    def closed(screen: ScreenName) -> None:
        if screen is ScreenName.LOGIN and login is not None:
            login.abandon()
        elif screen is ScreenName.REGISTER:
            registration.abandon()

    navigation = NavigationController(on_screen_closed=closed)

    def establish_authenticated(output: LoginOutput) -> None:
        role_name = output.user.get("role_name")
        if not isinstance(role_name, str):
            raise ValueError("El rol recibido no es válido.")
        # Resolve the destination before making state visible. If either action
        # fails, no partial user/token state survives.
        destination = navigation.destination_for_role(role_name)
        try:
            authenticated.establish(
                user=output.user,
                access_token=output.access_token,
                expires_at=output.expires_at,
            )
            navigation.open(destination)
        except BaseException:
            authenticated.clear()
            raise

    login = LoginController(connector, on_authenticated=establish_authenticated)

    def refresh() -> None:
        page.update()

    def centered(control: Any) -> Any:
        return ft.Container(content=control, alignment=ft.Alignment.CENTER)

    def error_text(value: str | None) -> Any:
        return ft.Text(value or "", color=COLORS["error"].hex, size=12, visible=bool(value))

    def replace(content: Any, *, vertically_centered: bool = False) -> None:
        page.clean()
        page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    expand=True,
                    padding=20,
                    bgcolor=COLORS["background_general"].hex,
                    content=ft.Column(
                        expand=True,
                        alignment=(
                            ft.MainAxisAlignment.CENTER
                            if vertically_centered
                            else ft.MainAxisAlignment.START
                        ),
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[content],
                        scroll=ft.ScrollMode.AUTO,
                    ),
                ),
            )
        )
        refresh()

    def render_current() -> None:
        active = navigation.active_screen
        if active is ScreenName.LOGIN:
            render_login()
        elif active is ScreenName.REGISTER:
            render_registration()
        elif active is ScreenName.RECOVER_PASSWORD:
            render_recovery()
        else:
            render_role_destination(active)

    def render_login() -> None:
        assert login is not None
        state = login.state
        email_error = error_text(state.field_errors.get("email"))
        password_error = error_text(state.field_errors.get("password"))
        message = ft.Text(
            state.general_message or configuration_message or "",
            color=COLORS["error"].hex if configuration_message else _login_status_color(state.status),
            visible=bool(state.general_message) or configuration_message is not None,
            text_align=ft.TextAlign.CENTER,
        )
        progress = ft.ProgressRing(width=22, height=22, visible=state.processing)
        email = ft.TextField(label="Correo electrónico", value=state.email, disabled=state.processing)
        password = ft.TextField(
            label="Contraseña",
            value=state.password,
            password=True,
            can_reveal_password=False,
            disabled=state.processing,
        )
        submit = ft.Button(
            "Ingresar",
            bgcolor=COLORS["primary"].hex,
            color=COLORS["text_on_primary"].hex,
            disabled=configuration_message is not None or not state.can_submit,
        )

        def update_local_errors(snapshot: LoginFormState) -> None:
            email_error.value = snapshot.field_errors.get("email", "")
            email_error.visible = bool(email_error.value)
            password_error.value = snapshot.field_errors.get("password", "")
            password_error.visible = bool(password_error.value)
            if snapshot.general_message is None and snapshot.status is LoginStatus.EDITING:
                message.value = ""
                message.visible = False
            refresh()

        def email_changed(event: Any) -> None:
            value = getattr(getattr(event, "control", None), "value", "")
            update_local_errors(login.set_field("email", value if isinstance(value, str) else ""))

        def password_changed(event: Any) -> None:
            value = getattr(getattr(event, "control", None), "value", "")
            update_local_errors(login.set_field("password", value if isinstance(value, str) else ""))

        async def submit_login(event: Any) -> None:
            if configuration_message is not None:
                return
            submit.disabled = True
            email.disabled = True
            password.disabled = True
            progress.visible = True
            refresh()
            await asyncio.to_thread(login.submit)
            render_current()

        def open_registration(event: Any) -> None:
            navigation.create_account()
            render_current()

        def open_recovery(event: Any) -> None:
            navigation.recover_password()
            render_current()

        email.on_change = email_changed
        password.on_change = password_changed
        try:
            password.on_submit = submit_login
        except (AttributeError, TypeError):
            pass
        submit.on_click = submit_login
        _apply_email_keyboard(ft, email)
        _disable_password_assistance(password, ft)
        replace(
            ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                spacing=12,
                controls=[
                    centered(ft.Text("SGF-AP", size=30, weight=ft.FontWeight.BOLD, color=COLORS["primary"].hex)),
                    centered(ft.Text("Ingresar", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"].hex)),
                    centered(
                        ft.Text(
                            "Accede con el correo y la contraseña de tu cuenta.",
                            color=COLORS["text_secondary"].hex,
                            text_align=ft.TextAlign.CENTER,
                        )
                    ),
                    email,
                    email_error,
                    password,
                    password_error,
                    centered(ft.Row(controls=[progress, submit], alignment=ft.MainAxisAlignment.CENTER)),
                    centered(message),
                    centered(ft.TextButton("Crear cuenta ciudadana", on_click=open_registration)),
                    centered(ft.TextButton("¿Olvidaste tu contraseña?", on_click=open_recovery)),
                ],
            ),
            vertically_centered=True,
        )

    def registration_text_field(name: str, label: str, *, secret: bool = False) -> Any:
        state = registration.state

        def changed(event: Any) -> None:
            value = getattr(getattr(event, "control", None), "value", "")
            registration.set_field(name, value if isinstance(value, str) else "")

        field = ft.TextField(
            label=label,
            value=getattr(state, name),
            password=secret,
            can_reveal_password=False,
            on_change=changed,
            disabled=state.status is RegistrationStatus.PROCESSING,
        )
        if name == "email":
            _apply_email_keyboard(ft, field)
        if secret:
            _disable_password_assistance(field, ft)
        return field

    def render_registration() -> None:
        state = registration.state
        first_name = registration_text_field("first_name", "Nombre")
        last_name = registration_text_field("last_name", "Apellido")
        email = registration_text_field("email", "Correo electrónico")
        password = registration_text_field("password", "Contraseña", secret=True)
        confirm_password = registration_text_field("confirm_password", "Confirmar contraseña", secret=True)
        progress = ft.ProgressRing(width=22, height=22, visible=state.status is RegistrationStatus.PROCESSING)
        status = ft.Text(
            state.general_message or configuration_message or "",
            color=COLORS["error"].hex if configuration_message else _registration_status_color(state.status),
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
            if configuration_message is not None:
                return
            submit.disabled = True
            progress.visible = True
            refresh()
            await asyncio.to_thread(registration.submit)
            render_registration()

        def back(event: Any) -> None:
            navigation.back_to_login()
            render_current()

        def continue_to_login(event: Any) -> None:
            navigation.continue_to_login()
            render_current()

        submit.on_click = submit_click
        controls = [
            centered(ft.Text("Crear cuenta ciudadana", size=24, weight=ft.FontWeight.BOLD, color=COLORS["primary"].hex)),
            centered(ft.Text("Completa tus datos para acceder a las funciones ciudadanas.", color=COLORS["text_secondary"].hex, text_align=ft.TextAlign.CENTER)),
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
            centered(ft.Row(controls=[progress, submit], alignment=ft.MainAxisAlignment.CENTER)),
            centered(status),
        ]
        if state.continue_to_login:
            controls.append(centered(ft.Button("Continuar al ingreso", on_click=continue_to_login)))
        controls.append(centered(ft.TextButton("Volver al ingreso", on_click=back)))
        replace(
            ft.Column(
                controls=controls,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                spacing=8,
            )
        )

    def render_recovery() -> None:
        def back(event: Any) -> None:
            navigation.back_to_login()
            render_current()

        replace(
            ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                spacing=14,
                controls=[
                    centered(ft.Text("Recuperar contraseña", size=24, weight=ft.FontWeight.BOLD, color=COLORS["primary"].hex)),
                    centered(
                        ft.Text(
                            "La recuperación de contraseña estará disponible próximamente.",
                            color=COLORS["text_secondary"].hex,
                            text_align=ft.TextAlign.CENTER,
                        )
                    ),
                    centered(ft.TextButton("Volver al ingreso", on_click=back)),
                ],
            ),
            vertically_centered=True,
        )

    def render_role_destination(destination: ScreenName) -> None:
        session = authenticated.session
        if session is None:
            navigation.back_to_login()
            render_current()
            return
        role_name = str(session.user.get("role_name", ""))
        first_name = str(session.user.get("first_name", ""))

        def logout(event: Any) -> None:
            authenticated.clear()
            assert login is not None
            login.reset()
            navigation.back_to_login()
            render_current()

        labels = {
            ScreenName.CITIZEN: "Área ciudadana",
            ScreenName.OPERATOR: "Área de operador",
            ScreenName.COORDINATOR: "Área de coordinación",
            ScreenName.CREW: "Área de cuadrilla",
            ScreenName.ADMIN: "Área de administración",
        }
        replace(
            ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                spacing=14,
                controls=[
                    centered(ft.Text("SGF-AP", size=30, weight=ft.FontWeight.BOLD, color=COLORS["primary"].hex)),
                    centered(ft.Text(labels[destination], size=22, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"].hex)),
                    centered(ft.Text(f"Bienvenido/a, {first_name}.", color=COLORS["text_secondary"].hex, text_align=ft.TextAlign.CENTER)),
                    centered(ft.Text(f"Rol: {role_name}", color=COLORS["text_secondary"].hex, text_align=ft.TextAlign.CENTER)),
                    centered(ft.Text("Este punto de entrada estará disponible con las funciones de tu rol.", color=COLORS["text_secondary"].hex, text_align=ft.TextAlign.CENTER)),
                    centered(ft.TextButton("Cerrar sesión", on_click=logout)),
                ],
            ),
            vertically_centered=True,
        )

    def on_view_pop(event: Any) -> None:
        active = navigation.active_screen
        if active in {ScreenName.REGISTER, ScreenName.RECOVER_PASSWORD}:
            navigation.back_to_login()
            render_current()
        elif active is ScreenName.LOGIN:
            assert login is not None
            login.abandon()
        else:
            authenticated.clear()
            assert login is not None
            login.reset()
            navigation.back_to_login()
            render_current()

    def on_disconnect(event: Any) -> None:
        assert login is not None
        login.abandon()
        registration.abandon()
        authenticated.clear()

    try:
        page.on_view_pop = on_view_pop
        page.on_disconnect = on_disconnect
    except (AttributeError, TypeError):
        pass

    render_current()


def _configure_phone_preview_window(page: Any) -> None:
    """Use a portrait 20:9 Moto preview window on desktop without fixing the UI."""

    platform = getattr(getattr(page, "platform", None), "value", getattr(page, "platform", None))
    if platform is not None and platform not in _DESKTOP_PLATFORMS:
        return
    window = getattr(page, "window", None)
    if window is None:
        return
    try:
        window.width = MOTO_EDGE_50_FUSION_PREVIEW_WIDTH
        window.height = MOTO_EDGE_50_FUSION_PREVIEW_HEIGHT
        window.min_width = 320
        window.min_height = 640
        window.resizable = True
    except (AttributeError, TypeError):
        return


def _apply_email_keyboard(ft: Any, field: Any) -> None:
    keyboard_type = getattr(getattr(ft, "KeyboardType", None), "EMAIL", None)
    if keyboard_type is None:
        return
    try:
        field.keyboard_type = keyboard_type
    except (AttributeError, TypeError):
        return


def _disable_password_assistance(field: Any, ft: Any) -> None:
    values: list[tuple[str, object]] = [("autocorrect", False), ("enable_suggestions", False)]
    capitalization = getattr(getattr(ft, "TextCapitalization", None), "NONE", None)
    if capitalization is not None:
        values.append(("capitalization", capitalization))
    for name, value in values:
        try:
            setattr(field, name, value)
        except (AttributeError, TypeError):
            continue


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
    """Return a safe, actionable local configuration message."""

    if isinstance(error, ValueError):
        return str(error)
    return "No se pudo cargar la configuración local del servicio."


def _registration_status_color(status: RegistrationStatus) -> str:
    if status is RegistrationStatus.COMPLETED:
        return COLORS["success"].hex
    if status is RegistrationStatus.UNCONFIRMED:
        return COLORS["warning"].hex
    if status is RegistrationStatus.REJECTED:
        return COLORS["error"].hex
    return COLORS["text_secondary"].hex


def _login_status_color(status: LoginStatus) -> str:
    if status is LoginStatus.COMPLETED:
        return COLORS["success"].hex
    if status is LoginStatus.UNCONFIRMED:
        return COLORS["warning"].hex
    if status is LoginStatus.REJECTED:
        return COLORS["error"].hex
    return COLORS["text_secondary"].hex


__all__ = ["main", "run"]
