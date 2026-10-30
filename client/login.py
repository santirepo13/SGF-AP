"""Framework-neutral login state, validation, and response coordination."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
from types import MappingProxyType
from typing import Protocol
from uuid import uuid4

from .authentication import SUPPORTED_ROLE_NAMES
from .validation import EMAIL_PATTERN


class LoginStatus(str, Enum):
    EDITING = "editing"
    PROCESSING = "processing"
    REJECTED = "rejected"
    UNCONFIRMED = "unconfirmed"
    COMPLETED = "completed"


LoginState = LoginStatus


@dataclass(frozen=True, slots=True)
class LoginAttempt:
    """Immutable credentials snapshot used exactly once for a login request."""

    attempt_id: str
    payload: dict[str, str] = field(repr=False)


@dataclass(frozen=True, slots=True)
class LoginOutput:
    """Validated public output delivered to authenticated-state coordination."""

    user: Mapping[str, object]
    access_token: str = field(repr=False)
    expires_at: datetime


@dataclass
class LoginFormState:
    email: str = ""
    password: str = field(default="", repr=False)
    status: LoginStatus = LoginStatus.EDITING
    field_errors: dict[str, str] = field(default_factory=dict)
    general_message: str | None = None
    correlation_id: str | None = None
    attempt_id: str | None = None
    focus_field: str | None = None

    @property
    def processing(self) -> bool:
        return self.status is LoginStatus.PROCESSING

    @property
    def can_submit(self) -> bool:
        return self.status in {LoginStatus.EDITING, LoginStatus.REJECTED, LoginStatus.UNCONFIRMED}

    def public_snapshot(self) -> dict[str, str]:
        return {"email": self.email, "password": self.password}

    def __repr__(self) -> str:
        return (
            "LoginFormState("
            f"email={self.email!r}, status={self.status!r}, "
            f"field_errors={self.field_errors!r}, general_message={self.general_message!r}, "
            f"correlation_id={self.correlation_id!r}, attempt_id={self.attempt_id!r}, "
            f"focus_field={self.focus_field!r})"
        )


class LoginConnector(Protocol):
    def login(self, *, email: str, password: str) -> object: ...


class LoginController:
    """Coordinate a single login attempt while keeping credentials in memory."""

    _FIELD_ORDER = ("email", "password")
    _KNOWN_FIELDS = frozenset(_FIELD_ORDER)
    _EMAIL_PATTERN = EMAIL_PATTERN

    def __init__(
        self,
        connector: LoginConnector | object,
        *,
        state: LoginFormState | None = None,
        on_state_changed: Callable[[LoginFormState], None] | None = None,
        on_authenticated: Callable[[LoginOutput], None] | None = None,
    ) -> None:
        self.connector = connector
        self.state = state or LoginFormState()
        self._on_state_changed = on_state_changed
        self._on_authenticated = on_authenticated
        self._lock = threading.RLock()
        self._attempt_counter = 0

    def set_field(self, field_name: str, value: object) -> LoginFormState:
        """Update one editable field and remove only that field's stale error."""

        if field_name not in self._KNOWN_FIELDS:
            raise ValueError(f"unknown login field: {field_name}")
        if type(value) is not str:
            raise TypeError(f"{field_name} must be a string")
        with self._lock:
            if self.state.processing or self.state.status is LoginStatus.COMPLETED:
                return self._copy_state()
            setattr(self.state, field_name, value)
            self.state.field_errors.pop(field_name, None)
            if self.state.status in {LoginStatus.REJECTED, LoginStatus.UNCONFIRMED}:
                self.state.status = LoginStatus.EDITING
                self.state.general_message = None
                self.state.correlation_id = None
            snapshot = self._copy_state()
        self._notify(snapshot)
        return snapshot

    def validate_local(self) -> dict[str, str]:
        """Validate required fields and email syntax without altering credentials."""

        with self._lock:
            values = self.state.public_snapshot()
        errors: dict[str, str] = {}
        if not values["email"]:
            errors["email"] = "El correo electrónico es obligatorio."
        elif self._EMAIL_PATTERN.fullmatch(values["email"]) is None:
            errors["email"] = "El correo electrónico no tiene un formato válido."
        if values["password"] == "":
            errors["password"] = "La contraseña es obligatoria."
        return errors

    def begin_attempt(self) -> LoginAttempt | None:
        """Validate and freeze one request while rejecting duplicate submissions."""

        with self._lock:
            if not self.state.can_submit:
                return None
        errors = self.validate_local()
        with self._lock:
            if errors:
                self.state.field_errors = dict(errors)
                self.state.status = LoginStatus.EDITING
                self.state.general_message = None
                self.state.focus_field = self._first_focus_field(errors)
                snapshot = self._copy_state()
                attempt = None
            else:
                self._attempt_counter += 1
                attempt_id = f"login-{self._attempt_counter}-{uuid4().hex}"
                payload = self.state.public_snapshot()
                self.state.status = LoginStatus.PROCESSING
                self.state.field_errors.clear()
                self.state.general_message = None
                self.state.correlation_id = None
                self.state.focus_field = None
                self.state.attempt_id = attempt_id
                snapshot = self._copy_state()
                attempt = LoginAttempt(attempt_id=attempt_id, payload=payload)
        self._notify(snapshot)
        return attempt

    def submit(self) -> LoginFormState:
        """Perform one login request; callers can run this on a worker thread."""

        attempt = self.begin_attempt()
        if attempt is None:
            return self._copy_state()
        try:
            response = self._send(attempt.payload)
        except BaseException as error:
            return self.apply_transport_error(
                error,
                attempt_id=attempt.attempt_id,
                request_sent=getattr(error, "request_sent", None),
            )
        return self.apply_response(response, attempt_id=attempt.attempt_id)

    def submit_async(
        self,
        *,
        on_finished: Callable[[LoginFormState], None] | None = None,
    ) -> str | None:
        """Run the connector in a daemon worker and keep exactly one attempt active."""

        attempt = self.begin_attempt()
        if attempt is None:
            return None

        def worker() -> None:
            try:
                response = self._send(attempt.payload)
                result = self.apply_response(response, attempt_id=attempt.attempt_id)
            except BaseException as error:
                result = self.apply_transport_error(
                    error,
                    attempt_id=attempt.attempt_id,
                    request_sent=getattr(error, "request_sent", None),
                )
            if on_finished is not None:
                on_finished(result)

        threading.Thread(target=worker, name="sgfap-login", daemon=True).start()
        return attempt.attempt_id

    def apply_response(self, response: object, *, attempt_id: str | None = None) -> LoginFormState:
        """Accept only a complete confirmed login output for the current attempt."""

        with self._lock:
            if not self._is_current_attempt(attempt_id):
                return self._copy_state()
        status_code, payload = _response_parts(response)
        if not isinstance(payload, Mapping) or not {"success", "data", "error"}.issubset(payload):
            return self._set_unconfirmed(attempt_id, None)

        success = payload.get("success")
        data = payload.get("data")
        error = payload.get("error")
        output = _login_output(data)
        if status_code == 200 and success is True and error is None and output is not None:
            with self._lock:
                if not self._is_current_attempt(attempt_id):
                    return self._copy_state()
                self.state.status = LoginStatus.COMPLETED
                self.state.password = ""
                self.state.field_errors.clear()
                self.state.general_message = "Ingreso aceptado."
                self.state.correlation_id = None
                self.state.attempt_id = None
                self.state.focus_field = None
                snapshot = self._copy_state()
            self._notify(snapshot)
            return self._deliver_authenticated(snapshot, output)

        if success is True or error is None or not isinstance(error, Mapping):
            return self._set_unconfirmed(attempt_id, None)
        correlation_id = _string_or_none(error.get("correlation_id"))
        if not self._error_status_is_coherent(status_code, error):
            return self._set_unconfirmed(attempt_id, correlation_id)

        code = _string_or_none(error.get("code"))
        details = error.get("details")
        field_errors = self._field_errors_for(code, details)
        message = self._message_for(code, _string_or_none(error.get("message")))
        with self._lock:
            if not self._is_current_attempt(attempt_id):
                return self._copy_state()
            self.state.status = LoginStatus.REJECTED
            self.state.field_errors = field_errors
            self.state.general_message = message
            self.state.correlation_id = correlation_id
            self.state.attempt_id = None
            self.state.focus_field = self._first_focus_field(field_errors)
            snapshot = self._copy_state()
        self._notify(snapshot)
        return snapshot

    def apply_transport_error(
        self,
        error: BaseException,
        *,
        attempt_id: str | None = None,
        request_sent: bool | None = None,
    ) -> LoginFormState:
        """Return safely to an editable state without claiming authentication."""

        with self._lock:
            if not self._is_current_attempt(attempt_id):
                return self._copy_state()
            if request_sent is False:
                self.state.status = LoginStatus.REJECTED
                self.state.general_message = "No fue posible comunicarse con el servicio de ingreso."
            else:
                self.state.status = LoginStatus.UNCONFIRMED
                self.state.general_message = "No fue posible confirmar el ingreso. Inténtalo nuevamente."
            self.state.attempt_id = None
            self.state.correlation_id = None
            snapshot = self._copy_state()
        self._notify(snapshot)
        return snapshot

    def export_state(self, *, include_sensitive: bool = False) -> dict[str, object]:
        """Return only screen state; passwords stay out unless retained in memory explicitly."""

        with self._lock:
            value: dict[str, object] = {
                "email": self.state.email,
                "status": self.state.status.value,
                "field_errors": dict(self.state.field_errors),
                "general_message": self.state.general_message,
                "correlation_id": self.state.correlation_id,
                "attempt_id": self.state.attempt_id,
                "focus_field": self.state.focus_field,
            }
            if include_sensitive:
                value["password"] = self.state.password
            return value

    snapshot = export_state

    def restore_state(self, value: Mapping[str, object]) -> LoginFormState:
        """Restore an in-memory view snapshot without replaying an HTTP request."""

        with self._lock:
            email = value.get("email")
            if isinstance(email, str):
                self.state.email = email
            status = value.get("status")
            if isinstance(status, LoginStatus):
                self.state.status = status
            elif isinstance(status, str):
                try:
                    self.state.status = LoginStatus(status)
                except ValueError:
                    pass
            errors = value.get("field_errors")
            if isinstance(errors, Mapping):
                self.state.field_errors = {
                    str(name): str(message)
                    for name, message in errors.items()
                    if str(name) in self._KNOWN_FIELDS
                }
            for name in ("general_message", "correlation_id", "attempt_id", "focus_field"):
                candidate = value.get(name)
                if candidate is None or isinstance(candidate, str):
                    setattr(self.state, name, candidate)
            self.state.password = value.get("password") if isinstance(value.get("password"), str) else ""
            snapshot = self._copy_state()
        self._notify(snapshot)
        return snapshot

    restore = restore_state

    def abandon(self) -> LoginFormState:
        """Invalidate in-flight callbacks and erase credentials when leaving login."""

        with self._lock:
            self.state.email = ""
            self.state.password = ""
            self.state.status = LoginStatus.EDITING
            self.state.field_errors.clear()
            self.state.general_message = None
            self.state.correlation_id = None
            self.state.attempt_id = None
            self.state.focus_field = None
            snapshot = self._copy_state()
        self._notify(snapshot)
        return snapshot

    def reset(self) -> LoginFormState:
        with self._lock:
            self.state = LoginFormState()
            snapshot = self._copy_state()
        self._notify(snapshot)
        return snapshot

    def _send(self, payload: Mapping[str, str]) -> object:
        method = getattr(self.connector, "login", None)
        if callable(method):
            return method(**dict(payload))
        execute = getattr(self.connector, "execute", None)
        if callable(execute):
            return execute("users.login", body=dict(payload))
        raise TypeError("login connector does not expose a login operation")

    def _deliver_authenticated(self, snapshot: LoginFormState, output: LoginOutput) -> LoginFormState:
        if self._on_authenticated is None:
            return snapshot
        try:
            self._on_authenticated(output)
        except BaseException:
            with self._lock:
                if self.state.status is not LoginStatus.COMPLETED:
                    return self._copy_state()
                self.state.status = LoginStatus.REJECTED
                self.state.general_message = "No fue posible continuar hacia el área de la cuenta."
                self.state.field_errors.clear()
                self.state.correlation_id = None
                snapshot = self._copy_state()
            self._notify(snapshot)
        return snapshot

    def _set_unconfirmed(self, attempt_id: str | None, correlation_id: str | None) -> LoginFormState:
        with self._lock:
            if not self._is_current_attempt(attempt_id):
                return self._copy_state()
            self.state.status = LoginStatus.UNCONFIRMED
            self.state.general_message = "No fue posible confirmar el ingreso. Inténtalo nuevamente."
            self.state.correlation_id = correlation_id
            self.state.attempt_id = None
            self.state.focus_field = None
            snapshot = self._copy_state()
        self._notify(snapshot)
        return snapshot

    def _field_errors_for(self, code: str | None, details: object) -> dict[str, str]:
        if code not in {"VAL-001", "VAL-002"}:
            return {}
        result: dict[str, str] = {}
        if isinstance(details, (list, tuple)):
            for detail in details:
                if not isinstance(detail, Mapping):
                    continue
                field_name = _string_or_none(detail.get("field"))
                reason = _string_or_none(detail.get("reason")) or "El valor requiere corrección."
                if field_name in self._KNOWN_FIELDS:
                    result[field_name] = reason
        return result

    @staticmethod
    def _message_for(code: str | None, server_message: str | None) -> str | None:
        if code == "USR-002":
            return "El correo electrónico o la contraseña son incorrectos."
        if code == "USR-001":
            return "La cuenta no se encuentra habilitada."
        if code == "AUTH-001":
            return "No fue posible acceder técnicamente al servicio de ingreso."
        if code in {"CAT-001", "SYS-001", "SYS-002"}:
            return "No fue posible completar el ingreso."
        return server_message or "No fue posible completar el ingreso."

    @staticmethod
    def _error_status_is_coherent(status_code: int, error: Mapping[str, object]) -> bool:
        code = _string_or_none(error.get("code"))
        expected = {
            "VAL-001": {400},
            "VAL-002": {400},
            "AUTH-001": {401},
            "USR-001": {403},
            "USR-002": {401},
            "USR-003": {401},
            "USR-004": {401},
            "USR-005": {401},
            "CAT-001": {500},
            "SYS-001": {500},
            "SYS-002": {500},
        }
        return code in expected and status_code in expected[code]

    def _is_current_attempt(self, attempt_id: str | None) -> bool:
        return self.state.attempt_id is not None and self.state.attempt_id == attempt_id

    def _copy_state(self) -> LoginFormState:
        return LoginFormState(
            email=self.state.email,
            password=self.state.password,
            status=self.state.status,
            field_errors=dict(self.state.field_errors),
            general_message=self.state.general_message,
            correlation_id=self.state.correlation_id,
            attempt_id=self.state.attempt_id,
            focus_field=self.state.focus_field,
        )

    def _notify(self, state: LoginFormState) -> None:
        if self._on_state_changed is not None:
            self._on_state_changed(state)

    @classmethod
    def _first_focus_field(cls, errors: Mapping[str, str]) -> str | None:
        return next((name for name in cls._FIELD_ORDER if name in errors), None)


def _response_parts(response: object) -> tuple[int, object]:
    if isinstance(response, Mapping):
        status = response.get("status_code", response.get("status"))
        payload = response.get("payload", response)
    else:
        status = getattr(response, "status_code", getattr(response, "status", None))
        payload = getattr(response, "payload", None)
    return (status if type(status) is int else 0, payload)


def _login_output(value: object) -> LoginOutput | None:
    if not isinstance(value, Mapping) or set(value) != {"user", "access_token", "expires_at"}:
        return None
    user = value.get("user")
    access_token = value.get("access_token")
    expires_at = value.get("expires_at")
    if not _valid_user_output(user) or type(access_token) is not str or not access_token or not isinstance(expires_at, str):
        return None
    try:
        parsed_expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed_expiry.tzinfo is None or parsed_expiry.utcoffset() is None:
        return None
    return LoginOutput(
        user=MappingProxyType(dict(user)),
        access_token=access_token,
        expires_at=parsed_expiry,
    )


def _valid_user_output(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    required = {"id", "first_name", "last_name", "email", "role_id", "role_name", "active"}
    if set(value) != required:
        return False
    if type(value["id"]) is not int or type(value["role_id"]) is not int or type(value["active"]) is not bool:
        return False
    if any(type(value[field]) is not str for field in ("first_name", "last_name", "email", "role_name")):
        return False
    return value["role_name"] in SUPPORTED_ROLE_NAMES


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


__all__ = [
    "LoginAttempt",
    "LoginConnector",
    "LoginController",
    "LoginFormState",
    "LoginOutput",
    "LoginState",
    "LoginStatus",
]
