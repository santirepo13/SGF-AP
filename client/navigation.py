"""Framework-neutral navigation and authenticated-role destinations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class ScreenName(str, Enum):
    LOGIN = "login"
    REGISTER = "register"
    RECOVER_PASSWORD = "recover_password"
    CITIZEN = "citizen"
    OPERATOR = "operator"
    COORDINATOR = "coordinator"
    CREW = "crew"
    ADMIN = "admin"


ROLE_DESTINATIONS: dict[str, ScreenName] = {
    "Citizen": ScreenName.CITIZEN,
    "Operator": ScreenName.OPERATOR,
    "Coordinator": ScreenName.COORDINATOR,
    "Crew": ScreenName.CREW,
    "Admin": ScreenName.ADMIN,
}
PROTECTED_SCREENS = frozenset(ROLE_DESTINATIONS.values())


@dataclass
class LoginFormState:
    """Legacy lightweight state retained for existing navigation consumers."""

    email: str = ""
    password: str = field(default="", repr=False)
    message: str | None = None
    focus_order: tuple[str, ...] = ("email", "password", "login", "create_account", "recover_password")

    def __repr__(self) -> str:
        return f"LoginFormState(email={self.email!r}, message={self.message!r}, focus_order={self.focus_order!r})"


class NavigationController:
    """Keep one active screen and make transitions idempotent."""

    def __init__(
        self,
        *,
        on_screen_closed: Callable[[ScreenName], None] | None = None,
        access_allowed: Callable[[], bool] | None = None,
    ) -> None:
        self.active_screen = ScreenName.LOGIN
        self.login = LoginFormState()
        self._on_screen_closed = on_screen_closed
        self._access_allowed = access_allowed or (lambda: True)
        self._listeners: list[Callable[[ScreenName], None]] = []

    def add_listener(self, listener: Callable[[ScreenName], None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[ScreenName], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def open(self, screen: ScreenName) -> bool:
        """Switch screens once and never open a private area without confirmed access."""

        if screen in PROTECTED_SCREENS and not self._access_allowed():
            return self.revoke_access()
        if screen is self.active_screen:
            return False
        previous = self.active_screen
        self._close(previous)
        self.active_screen = screen
        for listener in tuple(self._listeners):
            listener(screen)
        return True

    def revoke_access(self) -> bool:
        """Discard any protected destination so back navigation cannot revive it."""

        if self.active_screen is ScreenName.LOGIN:
            return False
        previous = self.active_screen
        self._close(previous)
        self.active_screen = ScreenName.LOGIN
        for listener in tuple(self._listeners):
            listener(ScreenName.LOGIN)
        return True

    def create_account(self) -> bool:
        return self.open(ScreenName.REGISTER)

    def recover_password(self) -> bool:
        return self.open(ScreenName.RECOVER_PASSWORD)

    def back_to_login(self) -> bool:
        return self.open(ScreenName.LOGIN)

    def continue_to_login(self) -> bool:
        return self.open(ScreenName.LOGIN)

    def destination_for_role(self, role_name: str) -> ScreenName:
        if type(role_name) is not str or role_name not in ROLE_DESTINATIONS:
            raise ValueError("No existe un destino de navegación para el rol recibido.")
        return ROLE_DESTINATIONS[role_name]

    def continue_after_login(self, role_name: str) -> bool:
        """Open the server-reported role destination exactly once."""

        return self.open(self.destination_for_role(role_name))

    def close(self) -> None:
        self._close(self.active_screen)
        self._listeners.clear()

    def _close(self, screen: ScreenName) -> None:
        if self._on_screen_closed is not None:
            self._on_screen_closed(screen)


__all__ = ["LoginFormState", "NavigationController", "PROTECTED_SCREENS", "ROLE_DESTINATIONS", "ScreenName"]
