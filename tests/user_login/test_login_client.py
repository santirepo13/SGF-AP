"""Client login lifecycle, response handling, and role navigation coverage."""

from __future__ import annotations

from datetime import datetime, timezone

from client.authentication import AuthenticationState
from client.login import LoginController, LoginStatus
from client.navigation import NavigationController, ScreenName


class Connector:
    def __init__(self, response) -> None:
        self.response = response
        self.calls: list[dict[str, str]] = []

    def login(self, *, email: str, password: str):
        self.calls.append({"email": email, "password": password})
        return self.response


def _success(role_name: str = "Citizen") -> dict[str, object]:
    return {
        "status_code": 200,
        "payload": {
            "success": True,
            "data": {
                "user": {
                    "id": 4,
                    "first_name": "Ana",
                    "last_name": "Gómez",
                    "email": "ana@example.test",
                    "role_id": 2,
                    "role_name": role_name,
                    "active": True,
                },
                "access_token": "opaque-token",
                "expires_at": datetime.now(timezone.utc).isoformat(),
            },
            "error": None,
        },
    }


def test_login_controller_blocks_duplicate_attempts_and_cleans_password_on_success() -> None:
    connector = Connector(_success())
    controller = LoginController(connector)
    controller.set_field("email", "ana@example.test")
    controller.set_field("password", " exact Password ")

    attempt = controller.begin_attempt()
    duplicate = controller.begin_attempt()
    state = controller.apply_response(connector.login(**attempt.payload), attempt_id=attempt.attempt_id)  # type: ignore[union-attr]

    assert duplicate is None
    assert state.status is LoginStatus.COMPLETED
    assert state.password == ""
    assert connector.calls == [{"email": "ana@example.test", "password": " exact Password "}]


def test_login_controller_keeps_email_after_rejection_and_maps_generic_credentials() -> None:
    connector = Connector(
        {
            "status_code": 401,
            "payload": {
                "success": False,
                "data": None,
                "error": {"code": "USR-002", "message": "ignored", "correlation_id": "corr", "details": []},
            },
        }
    )
    controller = LoginController(connector)
    controller.set_field("email", "ana@example.test")
    controller.set_field("password", "wrong")

    state = controller.submit()

    assert state.status is LoginStatus.REJECTED
    assert state.email == "ana@example.test"
    assert state.general_message == "El correo electrónico o la contraseña son incorrectos."
    assert state.field_errors == {}


def test_authenticated_state_and_navigation_publish_a_role_destination_together() -> None:
    auth = AuthenticationState()
    navigation = NavigationController()
    session = auth.establish(
        user={
            "id": 4,
            "first_name": "Ana",
            "last_name": "Gómez",
            "email": "ana@example.test",
            "role_id": 2,
            "role_name": "Crew",
            "active": True,
        },
        access_token="opaque-token",
        expires_at=datetime.now(timezone.utc),
    )

    navigation.continue_after_login(str(session.user["role_name"]))

    assert auth.authenticated is True
    assert navigation.active_screen is ScreenName.CREW
    assert auth.access_token_for_request() == "opaque-token"
    assert "access_token" not in auth.public_snapshot()  # type: ignore[operator]
