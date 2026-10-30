"""Client-side registration state and lifecycle coordination.

The module is UI-framework agnostic so an Android screen can bind its widgets
without putting network, validation, or retry rules in the view itself.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
import threading
import unicodedata
from typing import Any, Protocol
from uuid import uuid4

from .validation import EMAIL_PATTERN


class RegistrationStatus(str, Enum):
    EDITING = "editing"
    PROCESSING = "processing"
    REJECTED = "rejected"
    UNCONFIRMED = "unconfirmed"
    COMPLETED = "completed"


# Spanish/domain-neutral aliases used by UI adapters.
RegistrationState = RegistrationStatus


@dataclass(frozen=True, slots=True)
class RegistrationAttempt:
    """Immutable snapshot sent for one user-confirmed attempt."""

    attempt_id: str
    payload: dict[str, str] = field(repr=False)


@dataclass
class RegistrationFormState:
    """UI state kept separately from Android controls."""

    first_name: str = ""
    last_name: str = ""
    email: str = ""
    password: str = field(default="", repr=False)
    confirm_password: str = field(default="", repr=False)
    status: RegistrationStatus = RegistrationStatus.EDITING
    field_errors: dict[str, str] = field(default_factory=dict)
    general_message: str | None = None
    correlation_id: str | None = None
    attempt_id: str | None = None
    focus_field: str | None = None
    continue_to_login: bool = False

    @property
    def processing(self) -> bool:
        return self.status is RegistrationStatus.PROCESSING

    @property
    def can_submit(self) -> bool:
        return self.status in {
            RegistrationStatus.EDITING,
            RegistrationStatus.REJECTED,
            RegistrationStatus.UNCONFIRMED,
        } and not self.processing

    @property
    def passwords_visible(self) -> bool:
        return False

    def public_snapshot(self) -> dict[str, str]:
        """Return only the fields accepted by ``CitizenRegistrationInput``."""

        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "password": self.password,
        }

    def __repr__(self) -> str:
        return (
            "RegistrationFormState("
            f"first_name={self.first_name!r}, last_name={self.last_name!r}, "
            f"email={self.email!r}, status={self.status!r}, "
            f"field_errors={self.field_errors!r}, general_message={self.general_message!r}, "
            f"correlation_id={self.correlation_id!r}, attempt_id={self.attempt_id!r}, "
            f"focus_field={self.focus_field!r}, continue_to_login={self.continue_to_login!r})"
        )


class RegistrationConnector(Protocol):
    def register_citizen(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
    ) -> object: ...


class RegistrationController:
    """Coordinate one registration attempt at a time.

    ``submit`` is deliberately synchronous for deterministic controller use;
    Android callers should invoke it from a worker and publish the resulting
    state on the UI thread, or use ``submit_async``.
    """

    _FIELD_ORDER = ("first_name", "last_name", "email", "password", "confirm_password")
    _EMAIL_PATTERN = EMAIL_PATTERN
    _KNOWN_FIELDS = frozenset(_FIELD_ORDER)

    def __init__(
        self,
        connector: RegistrationConnector | object,
        *,
        state: RegistrationFormState | None = None,
        on_state_changed: Callable[[RegistrationFormState], None] | None = None,
    ) -> None:
        self.connector = connector
        self.state = state or RegistrationFormState()
        self._on_state_changed = on_state_changed
        self._lock = threading.RLock()
        self._attempt_counter = 0

    def set_field(self, field_name: str, value: object) -> RegistrationFormState:
        """Update one editable field and remove only its stale local error."""

        if field_name not in self._KNOWN_FIELDS:
            raise ValueError(f"unknown registration field: {field_name}")
        if type(value) is not str:
            raise TypeError(f"{field_name} must be a string")
        with self._lock:
            if self.state.processing or self.state.status is RegistrationStatus.COMPLETED:
                return self._copy_state()
            setattr(self.state, field_name, value)
            self.state.field_errors.pop(field_name, None)
            if field_name in {"password", "confirm_password"}:
                self.state.field_errors.pop("password_match", None)
            if self.state.status in {
                RegistrationStatus.UNCONFIRMED,
                RegistrationStatus.REJECTED,
            }:
                self.state.status = RegistrationStatus.EDITING
                self.state.general_message = None
                self.state.correlation_id = None
            snapshot = self._copy_state()
        self._notify(snapshot)
        return snapshot

    def validate_local(self) -> dict[str, str]:
        """Validate the current fields without contacting the API."""

        with self._lock:
            values = self.state.public_snapshot()
            confirmation = self.state.confirm_password
        errors: dict[str, str] = {}

        self._validate_name(values["first_name"], "first_name", errors)
        self._validate_name(values["last_name"], "last_name", errors)
        if not values["email"]:
            errors["email"] = "El correo electrónico es obligatorio."
        elif self._EMAIL_PATTERN.fullmatch(values["email"]) is None:
            errors["email"] = "El correo electrónico no tiene un formato válido."
        if values["password"] == "":
            errors["password"] = "La contraseña es obligatoria."
        if confirmation == "":
            errors["confirm_password"] = "La confirmación de contraseña es obligatoria."
        elif values["password"] != confirmation:
            errors["password_match"] = "Las contraseñas deben coincidir exactamente."
        return errors

    def begin_attempt(self) -> RegistrationAttempt | None:
        """Validate and freeze one request, preventing duplicate submissions."""

        with self._lock:
            if not self.state.can_submit:
                return None
        errors = self.validate_local()
        with self._lock:
            if errors:
                self.state.field_errors = dict(errors)
                self.state.status = RegistrationStatus.EDITING
                self.state.general_message = None
                self.state.focus_field = self._first_focus_field(errors)
                snapshot = self._copy_state()
                attempt = None
            else:
                self._attempt_counter += 1
                attempt_id = f"registration-{self._attempt_counter}-{uuid4().hex}"
                self.state.status = RegistrationStatus.PROCESSING
                self.state.field_errors.clear()
                self.state.general_message = None
                self.state.focus_field = None
                self.state.continue_to_login = False
                self.state.attempt_id = attempt_id
                payload = self.state.public_snapshot()
                snapshot = self._copy_state()
                attempt = RegistrationAttempt(attempt_id, payload)
        self._notify(snapshot)
        return attempt

    def submit(self) -> RegistrationFormState:
        """Perform one request and apply its result without automatic retry."""

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
        on_finished: Callable[[RegistrationFormState], None] | None = None,
    ) -> str | None:
        """Run the connector on a daemon worker and return the attempt ID."""

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

        threading.Thread(target=worker, name="sgfap-registration", daemon=True).start()
        return attempt.attempt_id

    def apply_response(
        self,
        response: object,
        *,
        attempt_id: str | None = None,
    ) -> RegistrationFormState:
        """Interpret one structured response and ignore stale attempts."""

        with self._lock:
            if not self._is_current_attempt(attempt_id):
                return self._copy_state()
        status_code, payload = _response_parts(response)
        if not isinstance(payload, Mapping) or not {"success", "data", "error"}.issubset(payload):
            return self._set_unconfirmed(attempt_id, None)

        success = payload.get("success")
        data = payload.get("data")
        error = payload.get("error")
        if status_code == 201 and success is True and error is None and _valid_user_output(data):
            with self._lock:
                if not self._is_current_attempt(attempt_id):
                    return self._copy_state()
                self.state.status = RegistrationStatus.COMPLETED
                self.state.password = ""
                self.state.confirm_password = ""
                self.state.field_errors.clear()
                self.state.general_message = "La cuenta fue creada correctamente."
                self.state.continue_to_login = True
                self.state.correlation_id = None
                self.state.attempt_id = None
                snapshot = self._copy_state()
            self._notify(snapshot)
            return snapshot

        if success is True or error is None or not isinstance(error, Mapping):
            return self._set_unconfirmed(attempt_id, None)
        if not self._error_status_is_coherent(status_code, error):
            return self._set_unconfirmed(attempt_id, _string_or_none(error.get("correlation_id")))

        code = _string_or_none(error.get("code"))
        message = _string_or_none(error.get("message")) or "No fue posible completar el registro."
        correlation_id = _string_or_none(error.get("correlation_id"))
        details = error.get("details")
        field_errors = self._field_errors_for(code, details)
        if code == "AUTH-001":
            message = "No fue posible acceder al servicio de registro."
            field_errors = {}
        with self._lock:
            if not self._is_current_attempt(attempt_id):
                return self._copy_state()
            self.state.status = RegistrationStatus.REJECTED
            self.state.field_errors = field_errors
            self.state.general_message = message
            self.state.correlation_id = correlation_id
            self.state.attempt_id = None
            self.state.focus_field = self._first_focus_field(field_errors)
            self.state.continue_to_login = False
            snapshot = self._copy_state()
        self._notify(snapshot)
        return snapshot

    def apply_transport_error(
        self,
        error: BaseException,
        *,
        attempt_id: str | None = None,
        request_sent: bool | None = None,
    ) -> RegistrationFormState:
        """Classify a transport failure without claiming server cancellation."""

        with self._lock:
            if not self._is_current_attempt(attempt_id):
                return self._copy_state()
        if request_sent is False:
            with self._lock:
                self.state.status = RegistrationStatus.REJECTED
                self.state.general_message = "No fue posible enviar el registro."
                self.state.attempt_id = None
                self.state.continue_to_login = False
                snapshot = self._copy_state()
            self._notify(snapshot)
            return snapshot
        return self._set_unconfirmed(attempt_id, None)

    def export_state(self, *, include_sensitive: bool = False) -> dict[str, object]:
        """Return lifecycle state suitable for a screen/view-model snapshot.

        Passwords are omitted by default and should never be written to disk or
        diagnostics. The snapshot never triggers another network request.
        """

        with self._lock:
            value: dict[str, object] = {
                "first_name": self.state.first_name,
                "last_name": self.state.last_name,
                "email": self.state.email,
                "status": self.state.status.value,
                "field_errors": dict(self.state.field_errors),
                "general_message": self.state.general_message,
                "correlation_id": self.state.correlation_id,
                "attempt_id": self.state.attempt_id,
                "focus_field": self.state.focus_field,
                "continue_to_login": self.state.continue_to_login,
            }
            if include_sensitive:
                value["password"] = self.state.password
                value["confirm_password"] = self.state.confirm_password
            return value

    def restore_state(self, value: Mapping[str, object]) -> RegistrationFormState:
        """Restore view state without replaying the pending request."""

        with self._lock:
            for name in ("first_name", "last_name", "email"):
                candidate = value.get(name)
                if isinstance(candidate, str):
                    setattr(self.state, name, candidate)
            status = value.get("status")
            if isinstance(status, RegistrationStatus):
                self.state.status = status
            elif isinstance(status, str):
                try:
                    self.state.status = RegistrationStatus(status)
                except ValueError:
                    pass
            errors = value.get("field_errors")
            if isinstance(errors, Mapping):
                self.state.field_errors = {
                    str(field_name): str(message)
                    for field_name, message in errors.items()
                    if str(field_name) in self._KNOWN_FIELDS or str(field_name) == "password_match"
                }
            for name in ("general_message", "correlation_id", "attempt_id", "focus_field"):
                candidate = value.get(name)
                if candidate is None or isinstance(candidate, str):
                    setattr(self.state, name, candidate)
            continue_to_login = value.get("continue_to_login")
            if isinstance(continue_to_login, bool):
                self.state.continue_to_login = continue_to_login
            # Clear sensitive values unless the caller explicitly provides an
            # in-memory snapshot; persistence restoration must not resurrect them.
            if "password" in value and isinstance(value["password"], str):
                self.state.password = value["password"]
            else:
                self.state.password = ""
            if "confirm_password" in value and isinstance(value["confirm_password"], str):
                self.state.confirm_password = value["confirm_password"]
            else:
                self.state.confirm_password = ""
            snapshot = self._copy_state()
        self._notify(snapshot)
        return snapshot

    snapshot = export_state
    restore = restore_state

    def abandon(self) -> RegistrationFormState:
        """Leave the screen and invalidate any response that may arrive later."""

        with self._lock:
            self.state.password = ""
            self.state.confirm_password = ""
            self.state.attempt_id = None
            self.state.status = RegistrationStatus.EDITING
            self.state.field_errors.clear()
            self.state.general_message = None
            self.state.correlation_id = None
            self.state.focus_field = None
            self.state.continue_to_login = False
            snapshot = self._copy_state()
        self._notify(snapshot)
        return snapshot

    def reset(self) -> RegistrationFormState:
        """Start a new registration flow with no state from a previous one."""

        with self._lock:
            self.state = RegistrationFormState()
            snapshot = self._copy_state()
        self._notify(snapshot)
        return snapshot

    def _send(self, payload: Mapping[str, str]) -> object:
        method = getattr(self.connector, "register_citizen", None)
        if callable(method):
            return method(**dict(payload))
        execute = getattr(self.connector, "execute", None)
        if callable(execute):
            return execute("users.register_citizen", body=dict(payload))
        raise TypeError("registration connector does not expose a registration operation")

    def _set_unconfirmed(self, attempt_id: str | None, correlation_id: str | None) -> RegistrationFormState:
        with self._lock:
            if not self._is_current_attempt(attempt_id):
                return self._copy_state()
            self.state.status = RegistrationStatus.UNCONFIRMED
            self.state.general_message = "No fue posible confirmar el resultado del registro."
            self.state.correlation_id = correlation_id
            self.state.attempt_id = None
            self.state.continue_to_login = False
            snapshot = self._copy_state()
        self._notify(snapshot)
        return snapshot

    def _field_errors_for(self, code: str | None, details: object) -> dict[str, str]:
        result: dict[str, str] = {}
        if isinstance(details, (list, tuple)):
            for detail in details:
                if not isinstance(detail, Mapping):
                    continue
                field = _string_or_none(detail.get("field"))
                reason = _string_or_none(detail.get("reason")) or "El valor requiere corrección."
                if field in self._KNOWN_FIELDS:
                    result[field] = reason
        if code == "CON-001" and not result:
            result["email"] = "El correo electrónico ya está asociado a otra cuenta."
        return result

    @staticmethod
    def _error_status_is_coherent(status_code: int, error: Mapping[str, object]) -> bool:
        code = _string_or_none(error.get("code"))
        expected = {
            "VAL-001": {400},
            "VAL-002": {400},
            "RES-001": {404},
            "HTTP-001": {404},
            "HTTP-002": {405},
            "TKT-001": {409},
            "AUTH-001": {401},
            "PER-001": {403},
            "USR-001": {403},
            "CON-001": {409},
            "REL-001": {422},
            "CAT-001": {500},
            "SYS-001": {500},
            "SYS-002": {500},
        }
        return code in expected and status_code in expected[code]

    def _is_current_attempt(self, attempt_id: str | None) -> bool:
        return self.state.attempt_id is not None and attempt_id == self.state.attempt_id

    def _copy_state(self) -> RegistrationFormState:
        return RegistrationFormState(
            first_name=self.state.first_name,
            last_name=self.state.last_name,
            email=self.state.email,
            password=self.state.password,
            confirm_password=self.state.confirm_password,
            status=self.state.status,
            field_errors=dict(self.state.field_errors),
            general_message=self.state.general_message,
            correlation_id=self.state.correlation_id,
            attempt_id=self.state.attempt_id,
            focus_field=self.state.focus_field,
            continue_to_login=self.state.continue_to_login,
        )

    def _notify(self, state: RegistrationFormState) -> None:
        if self._on_state_changed is not None:
            self._on_state_changed(state)

    @classmethod
    def _validate_name(cls, value: str, field_name: str, errors: dict[str, str]) -> None:
        if not value or not any(not character.isspace() for character in value):
            errors[field_name] = "El campo es obligatorio."
            return
        for character in value:
            category = unicodedata.category(character)
            if character.isspace() or character in "-'’ʼ" or category.startswith(("L", "M")):
                continue
            errors[field_name] = "El nombre solo puede contener letras, espacios, guiones o apóstrofes."
            return

    @classmethod
    def _first_focus_field(cls, errors: Mapping[str, str]) -> str | None:
        return next((field_name for field_name in cls._FIELD_ORDER if field_name in errors), None)


def _response_parts(response: object) -> tuple[int, object]:
    if isinstance(response, Mapping):
        status = response.get("status_code", response.get("status"))
        payload = response.get("payload", response)
    else:
        status = getattr(response, "status_code", getattr(response, "status", None))
        payload = getattr(response, "payload", None)
    return (status if type(status) is int else 0, payload)


def _valid_user_output(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    required = {"id", "first_name", "last_name", "email", "role_id", "active"}
    return required.issubset(value) and type(value["id"]) is int and type(value["role_id"]) is int and type(value["active"]) is bool and all(
        type(value[field]) is str for field in ("first_name", "last_name", "email")
    )


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


__all__ = [
    "RegistrationAttempt",
    "RegistrationConnector",
    "RegistrationController",
    "RegistrationFormState",
    "RegistrationStatus",
    "RegistrationState",
]
