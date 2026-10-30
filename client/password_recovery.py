"""In-memory controller for the three manual password-recovery steps."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
import threading
from typing import Protocol

from .validation import EMAIL_PATTERN


class RecoveryStep(str, Enum):
    REQUEST = "request"
    VERIFY = "verify"
    RESET = "reset"
    COMPLETED = "completed"


@dataclass
class PasswordRecoveryState:
    step: RecoveryStep = RecoveryStep.REQUEST
    email: str = ""
    request_id: str | None = field(default=None, repr=False)
    code: str = field(default="", repr=False)
    reset_token: str | None = field(default=None, repr=False)
    new_password: str = field(default="", repr=False)
    password_confirmation: str = field(default="", repr=False)
    processing: bool = False
    field_errors: dict[str, str] = field(default_factory=dict)
    message: str | None = None

    def __repr__(self) -> str:
        return f"PasswordRecoveryState(step={self.step!r}, email={self.email!r}, processing={self.processing!r}, message={self.message!r})"


class PasswordRecoveryConnector(Protocol):
    def request_password_recovery(self, *, email: str) -> object: ...
    def verify_password_recovery(self, *, request_id: str, code: str) -> object: ...
    def complete_password_recovery(self, *, reset_token: str, new_password: str, password_confirmation: str) -> object: ...


class PasswordRecoveryController:
    def __init__(self, connector: PasswordRecoveryConnector | object) -> None:
        self.connector = connector
        self.state = PasswordRecoveryState()
        self._lock = threading.RLock()

    def set_field(self, name: str, value: object) -> PasswordRecoveryState:
        if name not in {"email", "code", "new_password", "password_confirmation"}:
            raise ValueError(f"unknown recovery field: {name}")
        if type(value) is not str:
            raise TypeError(f"{name} must be a string")
        with self._lock:
            if self.state.processing or self.state.step is RecoveryStep.COMPLETED:
                return self._copy()
            setattr(self.state, name, value)
            self.state.field_errors.pop(name, None)
            self.state.message = None
            return self._copy()

    def request(self) -> PasswordRecoveryState:
        with self._lock:
            if self.state.processing:
                return self._copy()
            error = self._email_error()
            if error:
                self.state.field_errors = {"email": error}
                return self._copy()
            self.state.processing = True
            self.state.field_errors.clear()
            self.state.message = None
            email = self.state.email
        try:
            response = self._call("request_password_recovery", email=email)
        except BaseException:
            return self._unavailable()
        status, payload = _response_parts(response)
        if status == 202 and _success_data(payload, {"request_id", "message"}):
            data = payload["data"]
            if isinstance(data["request_id"], str) and data["request_id"] and isinstance(data["message"], str):
                with self._lock:
                    self.state.request_id = data["request_id"]
                    self.state.code = ""
                    self.state.reset_token = None
                    self.state.step = RecoveryStep.VERIFY
                    self.state.processing = False
                    self.state.message = data["message"]
                    return self._copy()
        return self._failure(status, payload)

    def verify(self) -> PasswordRecoveryState:
        with self._lock:
            if self.state.processing:
                return self._copy()
            error = self._code_error()
            if error:
                self.state.field_errors = {"code": error}
                return self._copy()
            request_id, code = self.state.request_id, self.state.code
            if not request_id:
                self._restart("Solicita un código nuevo para continuar.")
                return self._copy()
            self.state.processing = True
            self.state.field_errors.clear()
            self.state.message = None
        try:
            response = self._call("verify_password_recovery", request_id=request_id, code=code)
        except BaseException:
            return self._unavailable()
        status, payload = _response_parts(response)
        if status == 200 and _success_data(payload, {"reset_token", "expires_at"}):
            data = payload["data"]
            if isinstance(data["reset_token"], str) and data["reset_token"] and isinstance(data["expires_at"], str):
                with self._lock:
                    self.state.reset_token = data["reset_token"]
                    self.state.code = ""
                    self.state.step = RecoveryStep.RESET
                    self.state.processing = False
                    self.state.message = "Código confirmado. Establece tu nueva contraseña."
                    return self._copy()
        return self._failure(status, payload)

    def complete(self) -> PasswordRecoveryState:
        with self._lock:
            if self.state.processing:
                return self._copy()
            errors = self._password_errors()
            if errors:
                self.state.field_errors = errors
                return self._copy()
            token = self.state.reset_token
            if not token:
                self._restart("Solicita un código nuevo para continuar.")
                return self._copy()
            self.state.processing = True
            self.state.field_errors.clear()
            self.state.message = None
            password = self.state.new_password
            confirmation = self.state.password_confirmation
        try:
            response = self._call(
                "complete_password_recovery",
                reset_token=token,
                new_password=password,
                password_confirmation=confirmation,
            )
        except BaseException:
            return self._unavailable()
        status, payload = _response_parts(response)
        if status == 200 and _success_data(payload, {"completed_at"}):
            with self._lock:
                self.state.step = RecoveryStep.COMPLETED
                self.state.processing = False
                self.state.code = ""
                self.state.reset_token = None
                self.state.new_password = ""
                self.state.password_confirmation = ""
                self.state.message = "La contraseña fue establecida. Ingresa con la nueva contraseña."
                return self._copy()
        return self._failure(status, payload)

    def start_over(self) -> PasswordRecoveryState:
        """Return to the email step while retaining only the non-sensitive address."""

        with self._lock:
            email = self.state.email
            self.state = PasswordRecoveryState(email=email)
            return self._copy()

    def abandon(self) -> PasswordRecoveryState:
        with self._lock:
            self.state = PasswordRecoveryState()
            return self._copy()

    def _call(self, name: str, **kwargs: str) -> object:
        method = getattr(self.connector, name, None)
        if not callable(method):
            raise TypeError("recovery connector is unavailable")
        return method(**kwargs)

    def _failure(self, status: int, payload: object) -> PasswordRecoveryState:
        code = _error_code(payload)
        with self._lock:
            self.state.processing = False
            if code in {"REC-001"}:
                self._restart("El código no es válido o ya venció. Solicita uno nuevo.")
            elif code == "REC-002":
                self.state.message = "Debes esperar antes de solicitar o verificar otro código."
            elif code in {"REC-003", "AUTH-001"} or status >= 500:
                self.state.message = "La recuperación no está disponible en este momento."
            elif code in {"VAL-001", "VAL-002"}:
                self.state.message = "Revisa los datos e inténtalo nuevamente."
            else:
                self.state.message = "No fue posible confirmar esta operación. Inténtalo nuevamente."
            return self._copy()

    def _unavailable(self) -> PasswordRecoveryState:
        with self._lock:
            self.state.processing = False
            self.state.message = "No fue posible comunicarse con el servicio. Inténtalo nuevamente."
            return self._copy()

    def _restart(self, message: str) -> None:
        self.state.step = RecoveryStep.REQUEST
        self.state.request_id = None
        self.state.code = ""
        self.state.reset_token = None
        self.state.new_password = ""
        self.state.password_confirmation = ""
        self.state.message = message

    def _email_error(self) -> str | None:
        if not self.state.email:
            return "El correo electrónico es obligatorio."
        if EMAIL_PATTERN.fullmatch(self.state.email) is None:
            return "El correo electrónico no tiene un formato válido."
        return None

    def _code_error(self) -> str | None:
        if not self.state.code:
            return "El código es obligatorio."
        if len(self.state.code) != 8 or not self.state.code.isascii() or not self.state.code.isdecimal():
            return "El código debe tener ocho dígitos."
        return None

    def _password_errors(self) -> dict[str, str]:
        result: dict[str, str] = {}
        if self.state.new_password == "":
            result["new_password"] = "La nueva contraseña es obligatoria."
        if self.state.password_confirmation == "":
            result["password_confirmation"] = "La confirmación es obligatoria."
        elif self.state.new_password != self.state.password_confirmation:
            result["password_confirmation"] = "La confirmación no coincide con la nueva contraseña."
        return result

    def _copy(self) -> PasswordRecoveryState:
        return PasswordRecoveryState(
            step=self.state.step,
            email=self.state.email,
            request_id=self.state.request_id,
            code=self.state.code,
            reset_token=self.state.reset_token,
            new_password=self.state.new_password,
            password_confirmation=self.state.password_confirmation,
            processing=self.state.processing,
            field_errors=dict(self.state.field_errors),
            message=self.state.message,
        )


def _response_parts(response: object) -> tuple[int, object]:
    if isinstance(response, Mapping):
        status = response.get("status_code", response.get("status"))
        payload = response.get("payload", response)
    else:
        status = getattr(response, "status_code", getattr(response, "status", None))
        payload = getattr(response, "payload", None)
    return (status if type(status) is int else 0, payload)


def _success_data(payload: object, fields: set[str]) -> bool:
    return (
        isinstance(payload, Mapping)
        and set(payload) == {"success", "data", "error"}
        and payload.get("success") is True
        and payload.get("error") is None
        and isinstance(payload.get("data"), Mapping)
        and set(payload["data"]) == fields
    )


def _error_code(payload: object) -> str | None:
    if not isinstance(payload, Mapping) or payload.get("success") is not False:
        return None
    error = payload.get("error")
    code = error.get("code") if isinstance(error, Mapping) else None
    return code if isinstance(code, str) else None


__all__ = ["PasswordRecoveryController", "PasswordRecoveryState", "RecoveryStep"]
