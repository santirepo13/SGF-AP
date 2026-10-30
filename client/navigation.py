"""Framework-neutral navigation and initial access-screen state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class ScreenName(str, Enum):
    LOGIN = "login"
    REGISTER = "register"
    RECOVER_PASSWORD = "recover_password"


@dataclass
class LoginFormState:
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
    ) -> None:
        self.active_screen = ScreenName.LOGIN
        self.login = LoginFormState()
        self._on_screen_closed = on_screen_closed
        self._listeners: list[Callable[[ScreenName], None]] = []

    def add_listener(self, listener: Callable[[ScreenName], None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[ScreenName], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def open(self, screen: ScreenName) -> bool:
        """Switch screens once; repeated requests do not create instances."""

        if screen is self.active_screen:
            return False
        previous = self.active_screen
        self._close(previous)
        self.active_screen = screen
        for listener in tuple(self._listeners):
            listener(screen)
        return True

    def create_account(self) -> bool:
        return self.open(ScreenName.REGISTER)

    def recover_password(self) -> bool:
        return self.open(ScreenName.RECOVER_PASSWORD)

    def back_to_login(self) -> bool:
        return self.open(ScreenName.LOGIN)

    def continue_to_login(self) -> bool:
        return self.open(ScreenName.LOGIN)

    def close(self) -> None:
        self._close(self.active_screen)
        self._listeners.clear()

    def _close(self, screen: ScreenName) -> None:
        if screen is ScreenName.REGISTER:
            # The registration controller owns the actual password cleanup;
            # this callback lets the screen adapter invoke it before disposal.
            pass
        if self._on_screen_closed is not None:
            self._on_screen_closed(screen)


__all__ = ["LoginFormState", "NavigationController", "ScreenName"]
