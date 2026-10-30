"""Client-side registration state tests without an Android runtime."""

from __future__ import annotations

from client.registration import RegistrationController, RegistrationStatus


class ResponseConnector:
    def __init__(self, response) -> None:
        self.response = response
        self.calls: list[dict[str, str]] = []

    def register_citizen(self, **payload: str):
        self.calls.append(payload)
        return self.response


def _complete(controller: RegistrationController) -> None:
    for field, value in {
        "first_name": "Ana",
        "last_name": "Gómez",
        "email": "ana@example.test",
        "password": " exact password ",
        "confirm_password": " exact password ",
    }.items():
        controller.set_field(field, value)


def test_client_submits_only_the_public_registration_fields_and_cleans_passwords() -> None:
    connector = ResponseConnector(
        {
            "status_code": 201,
            "payload": {
                "success": True,
                "data": {"id": 4, "first_name": "Ana", "last_name": "Gómez", "email": "ana@example.test", "role_id": 2, "active": True},
                "error": None,
            },
        }
    )
    controller = RegistrationController(connector)
    _complete(controller)

    state = controller.submit()

    assert set(connector.calls[0]) == {"first_name", "last_name", "email", "password"}
    assert state.status is RegistrationStatus.COMPLETED
    assert state.password == "" and state.confirm_password == ""
    assert state.continue_to_login is True


def test_client_prevents_a_second_pending_submission_and_ignores_stale_response() -> None:
    connector = ResponseConnector({"status_code": 500, "payload": {"success": False, "data": None, "error": {"code": "SYS-002", "message": "safe", "correlation_id": "c", "details": []}}})
    controller = RegistrationController(connector)
    _complete(controller)

    current = controller.begin_attempt()
    assert current is not None
    assert controller.begin_attempt() is None
    controller.apply_response(
        {"status_code": 201, "payload": {"success": True, "data": {"id": 1, "first_name": "x", "last_name": "x", "email": "x@example.test", "role_id": 1, "active": True}, "error": None}},
        attempt_id="old-attempt",
    )
    controller.apply_response(
        {"status_code": 201, "payload": {"success": True, "data": {"id": 1, "first_name": "x", "last_name": "x", "email": "x@example.test", "role_id": 1, "active": True}, "error": None}},
    )

    assert controller.state.status is RegistrationStatus.PROCESSING


def test_client_treats_timeout_like_failures_as_unconfirmed_and_explicit_no_send_as_retryable() -> None:
    controller = RegistrationController(ResponseConnector(None))
    _complete(controller)
    attempt = controller.begin_attempt()
    assert attempt is not None

    uncertain = controller.apply_transport_error(RuntimeError("timeout"), attempt_id=attempt.attempt_id, request_sent=None)
    assert uncertain.status is RegistrationStatus.UNCONFIRMED

    retry = controller.begin_attempt()
    assert retry is not None
    not_sent = controller.apply_transport_error(RuntimeError("offline"), attempt_id=retry.attempt_id, request_sent=False)
    assert not_sent.status is RegistrationStatus.REJECTED
    assert "enviar" in (not_sent.general_message or "")


def test_client_maps_duplicate_email_by_code_without_matching_message_text() -> None:
    controller = RegistrationController(ResponseConnector(None))
    _complete(controller)
    attempt = controller.begin_attempt()
    assert attempt is not None

    result = controller.apply_response(
        {"status_code": 409, "payload": {"success": False, "data": None, "error": {"code": "CON-001", "message": "changed wording", "correlation_id": "c", "details": []}}},
        attempt_id=attempt.attempt_id,
    )

    assert result.status is RegistrationStatus.REJECTED
    assert "email" in result.field_errors
