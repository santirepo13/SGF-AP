"""Framework-independent citizen lighting-failure form and attempt lifecycle."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
import threading
from typing import Any
from uuid import uuid4

from .report_attempt_storage import (
    ReportAttemptStorage,
    ReportAttemptStorageError,
    StoredReportAttempt,
)
from .validation import EMAIL_PATTERN


class CitizenReportStatus(str, Enum):
    EDITING = "editing"
    SUBMITTING = "submitting"
    CONFIRMED = "confirmed"
    MATCHES = "matches"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


@dataclass
class CitizenReportFormState:
    failure_type_id: int | None = None
    description: str = ""
    road_type_code: str = ""
    road_number: str = ""
    cross_road_number: str = ""
    door_plate_number: str = ""
    road_suffix_letter_code: str = ""
    road_bis_code: str = ""
    road_bis_suffix: str = ""
    road_quadrant_code: str = ""
    cross_suffix_letter_code: str = ""
    cross_bis_code: str = ""
    cross_bis_suffix: str = ""
    cross_quadrant_code: str = ""
    neighborhood_id: int | None = None
    contact_email: str = ""
    contact_phone: str = ""
    email_notifications: bool = False
    address_id: int | None = None
    address_version: int = 0
    status: CitizenReportStatus = CitizenReportStatus.EDITING
    field_errors: dict[str, str] = field(default_factory=dict)
    general_message: str | None = None
    correlation_id: str | None = None
    request_key: str | None = None
    confirmation: dict[str, object] | None = None
    matches: tuple[dict[str, object], ...] = ()
    pending_payload: dict[str, object] | None = field(default=None, repr=False)
    operation_key_reused: bool = False
    storage_warning: str | None = None

    @property
    def processing(self) -> bool:
        return self.status is CitizenReportStatus.SUBMITTING

    @property
    def can_submit(self) -> bool:
        return (
            self.status in {CitizenReportStatus.EDITING, CitizenReportStatus.REJECTED}
            and not self.operation_key_reused
            and not self.processing
        )


class CitizenReportController:
    """Freeze, persist, and recover one citizen-owned report intention at a time."""

    _ADDRESS_FIELDS = frozenset(
        {
            "road_type_code",
            "road_number",
            "cross_road_number",
            "door_plate_number",
            "road_suffix_letter_code",
            "road_bis_code",
            "road_bis_suffix",
            "road_quadrant_code",
            "cross_suffix_letter_code",
            "cross_bis_code",
            "cross_bis_suffix",
            "cross_quadrant_code",
            "neighborhood_id",
        }
    )
    _TEXT_FIELDS = frozenset(
        {
            "description",
            "road_type_code",
            "road_number",
            "cross_road_number",
            "door_plate_number",
            "road_suffix_letter_code",
            "road_bis_code",
            "road_bis_suffix",
            "road_quadrant_code",
            "cross_suffix_letter_code",
            "cross_bis_code",
            "cross_bis_suffix",
            "cross_quadrant_code",
            "contact_email",
            "contact_phone",
        }
    )

    def __init__(
        self,
        connector: object,
        attempt_storage: ReportAttemptStorage,
        *,
        state: CitizenReportFormState | None = None,
    ) -> None:
        self.connector = connector
        self.storage = attempt_storage
        self.state = state or CitizenReportFormState()
        self._lock = threading.RLock()
        self._last_protected_response: object | None = None

    def set_field(self, name: str, value: object) -> CitizenReportFormState:
        if name not in self._TEXT_FIELDS:
            raise ValueError(f"unknown citizen report text field: {name}")
        if type(value) is not str:
            raise TypeError(f"{name} must be text")
        with self._lock:
            if not self._editable():
                return self._copy_state()
            setattr(self.state, name, value)
            self._after_change(name)
            return self._copy_state()

    def set_failure_type(self, value: int | None) -> CitizenReportFormState:
        if value is not None and (type(value) is not int or value <= 0):
            raise ValueError("failure_type_id must be a positive integer or None")
        with self._lock:
            if not self._editable():
                return self._copy_state()
            self.state.failure_type_id = value
            self._after_change("failure_type_id")
            return self._copy_state()

    def set_neighborhood(self, value: int | None) -> CitizenReportFormState:
        if value is not None and (type(value) is not int or value <= 0):
            raise ValueError("neighborhood_id must be a positive integer or None")
        with self._lock:
            if not self._editable():
                return self._copy_state()
            self.state.neighborhood_id = value
            self._after_change("neighborhood_id")
            return self._copy_state()

    def set_email_notifications(self, value: bool) -> CitizenReportFormState:
        if type(value) is not bool:
            raise TypeError("email_notifications must be a boolean")
        with self._lock:
            if not self._editable():
                return self._copy_state()
            self.state.email_notifications = value
            self._after_change("email_notifications")
            return self._copy_state()

    def validate_local(self) -> dict[str, str]:
        with self._lock:
            state = self._copy_state()
        errors: dict[str, str] = {}
        if state.failure_type_id is None:
            errors["failure_type_id"] = "Selecciona el tipo de falla."
        if not state.description.strip():
            errors["description"] = "Describe la falla."
        elif len(state.description) > 4_000:
            errors["description"] = "La descripción supera 4.000 caracteres."
        if not state.road_type_code:
            errors["road_type_code"] = "Selecciona el tipo de vía."
        elif len(state.road_type_code) > 2:
            errors["road_type_code"] = "El tipo de vía no es válido."
        self._validate_number(state.road_number, "road_number", 1, 999, errors)
        self._validate_number(state.cross_road_number, "cross_road_number", 1, 999, errors)
        self._validate_number(state.door_plate_number, "door_plate_number", 1, 9_999, errors)
        self._validate_optional_length(state.road_suffix_letter_code, "road_suffix_letter_code", 2, errors)
        self._validate_optional_length(state.road_bis_code, "road_bis_code", 3, errors)
        self._validate_optional_length(state.cross_suffix_letter_code, "cross_suffix_letter_code", 2, errors)
        self._validate_optional_length(state.cross_bis_code, "cross_bis_code", 3, errors)
        self._validate_optional_letter(state.road_bis_suffix, "road_bis_suffix", errors)
        self._validate_optional_letter(state.cross_bis_suffix, "cross_bis_suffix", errors)
        self._validate_optional_number(state.road_quadrant_code, "road_quadrant_code", errors)
        self._validate_optional_number(state.cross_quadrant_code, "cross_quadrant_code", errors)
        if state.contact_email and self._email_is_valid(state.contact_email) is False:
            errors["contact_email"] = "El correo de contacto no tiene un formato válido."
        if len(state.contact_phone) > 32:
            errors["contact_phone"] = "El teléfono admite hasta 32 caracteres."
        return errors

    def submit(self, account_id: int) -> CitizenReportFormState:
        """Resolve the structured address, persist the frozen intent, then register it."""

        with self._lock:
            if not self.state.can_submit:
                return self._copy_state()
        errors = self.validate_local()
        if errors:
            with self._lock:
                self.state.field_errors = errors
                self.state.general_message = None
                self.state.status = CitizenReportStatus.EDITING
                return self._copy_state()

        self._set_submitting()
        try:
            address_response = self._call("create_or_reuse_address", self._address_payload())
            self._remember_protected_response(address_response)
        except BaseException as error:
            return self._apply_transport_error(error)
        address_id = self._address_id_from_response(address_response)
        if address_id is None:
            return self._apply_rejection(address_response, "No fue posible confirmar la dirección.")

        with self._lock:
            self.state.address_id = address_id
            request_key = self.state.request_key or uuid4().hex
            self.state.request_key = request_key
            payload = self._report_payload(request_key, address_id)
            self.state.pending_payload = dict(payload)
        try:
            self._await_storage(self.storage.save(StoredReportAttempt(account_id, request_key, payload)))
            with self._lock:
                self.state.storage_warning = None
        except (ReportAttemptStorageError, ValueError):
            with self._lock:
                self.state.storage_warning = (
                    "No se pudo guardar este intento de forma protegida; "
                    "si cierras la aplicación no podrás recuperarlo automáticamente."
                )
        try:
            response = self._call("register_report", payload)
            self._remember_protected_response(response)
        except BaseException as error:
            return self._apply_transport_error(error)
        return self._apply_registration_response(response, account_id)

    def retry_pending(self, account_id: int) -> CitizenReportFormState:
        """Resend the exact stored intent without changing its request key or address."""

        with self._lock:
            payload = self.state.pending_payload
            if (
                self.state.status not in {CitizenReportStatus.UNKNOWN, CitizenReportStatus.REJECTED}
                or self.state.operation_key_reused
                or payload is None
            ):
                return self._copy_state()
            self.state.status = CitizenReportStatus.SUBMITTING
            self.state.general_message = None
            self.state.field_errors.clear()
        try:
            response = self._call("register_report", payload)
            self._remember_protected_response(response)
        except BaseException as error:
            return self._apply_transport_error(error)
        return self._apply_registration_response(response, account_id)

    def check_pending(self, account_id: int) -> CitizenReportFormState:
        with self._lock:
            request_key = self.state.request_key
            if self.state.status is not CitizenReportStatus.UNKNOWN or not request_key:
                return self._copy_state()
            self.state.status = CitizenReportStatus.SUBMITTING
            self.state.general_message = None
        try:
            response = self._call("get_report_attempt", request_key=request_key)
            self._remember_protected_response(response)
        except BaseException as error:
            return self._apply_transport_error(error)
        status_code, payload = _response_parts(response)
        data = _successful_data(status_code, payload)
        if not isinstance(data, Mapping):
            return self._set_unknown("No fue posible confirmar el intento anterior.", _correlation_id(payload))
        if not _is_attempt_output(data, request_key):
            return self._set_unknown("El servicio devolvió una recuperación incompatible.", None)
        if data["state"] == "not_found":
            return self._set_unknown(
                "El intento aún no tiene un resultado confirmado. Puedes comprobarlo o reenviar exactamente el mismo intento.",
                None,
            )
        result = data["result"]
        assert isinstance(result, Mapping)
        return self._apply_registration_data(result, account_id)

    async def restore_pending(self, account_id: int) -> CitizenReportFormState:
        """Load only the current account's saved uncertainty; never replay it automatically."""

        try:
            stored = await self.storage.load(account_id)
        except ReportAttemptStorageError:
            with self._lock:
                self.state.storage_warning = "No se pudo recuperar un intento de reporte guardado."
                return self._copy_state()
        if stored is None:
            return self.snapshot()
        with self._lock:
            self.state.request_key = stored.request_key
            self.state.pending_payload = dict(stored.payload)
            self.state.failure_type_id = _positive_int_or_none(stored.payload.get("failure_type_id"))
            self.state.address_id = _positive_int_or_none(stored.payload.get("address_id"))
            self.state.description = _string_or_empty(stored.payload.get("description"))
            self.state.contact_email = _string_or_empty(stored.payload.get("contact_email"))
            self.state.contact_phone = _string_or_empty(stored.payload.get("contact_phone"))
            self.state.email_notifications = stored.payload.get("email_notifications") is True
            self.state.operation_key_reused = False
            self.state.status = CitizenReportStatus.UNKNOWN
            self.state.general_message = "Hay un intento pendiente de confirmación."
            self.state.field_errors.clear()
            return self._copy_state()

    async def discard_pending(self, account_id: int) -> CitizenReportFormState:
        """Discard local recovery data without claiming that a remote request was cancelled."""

        with self._lock:
            request_key = self.state.request_key
        try:
            await self.storage.clear(account_id, request_key)
        except ReportAttemptStorageError:
            with self._lock:
                self.state.storage_warning = "No se pudo eliminar el intento guardado en este dispositivo."
                return self._copy_state()
        with self._lock:
            self.state.request_key = None
            self.state.pending_payload = None
            self.state.operation_key_reused = False
            self.state.status = CitizenReportStatus.EDITING
            self.state.general_message = "El borrador local fue descartado. Esto no cancela un envío que ya haya sido procesado."
            self.state.correlation_id = None
            self.state.confirmation = None
            self.state.matches = ()
            return self._copy_state()

    def load_catalog(self, path: str) -> tuple[dict[str, object], ...]:
        response = self._call("list_catalog", path)
        status_code, payload = _response_parts(response)
        data = _successful_data(status_code, payload)
        if not isinstance(data, list) or any(not isinstance(item, Mapping) for item in data):
            raise ValueError("catalog response is invalid")
        return tuple(dict(item) for item in data)

    def snapshot(self) -> CitizenReportFormState:
        with self._lock:
            return self._copy_state()

    def take_last_protected_response(self) -> object | None:
        """Return one completed protected response so the access coordinator can inspect it."""

        with self._lock:
            value = self._last_protected_response
            self._last_protected_response = None
            return value

    def abandon(self) -> CitizenReportFormState:
        with self._lock:
            if self.state.status is CitizenReportStatus.SUBMITTING:
                return self._copy_state()
            self.state.field_errors.clear()
            self.state.general_message = None
            self.state.correlation_id = None
            return self._copy_state()

    def reset(self) -> CitizenReportFormState:
        """Discard only in-memory report data when the authenticated account changes."""

        with self._lock:
            self.state = CitizenReportFormState()
            self._last_protected_response = None
            return self._copy_state()

    def _editable(self) -> bool:
        return self.state.status in {CitizenReportStatus.EDITING, CitizenReportStatus.REJECTED}

    def _after_change(self, name: str) -> None:
        self.state.field_errors.pop(name, None)
        self.state.general_message = None
        self.state.correlation_id = None
        self.state.confirmation = None
        self.state.matches = ()
        self.state.operation_key_reused = False
        if name in self._ADDRESS_FIELDS:
            self.state.address_id = None
            self.state.address_version += 1
        if self.state.status is CitizenReportStatus.REJECTED:
            self.state.status = CitizenReportStatus.EDITING
            self.state.request_key = None
            self.state.pending_payload = None

    def _address_payload(self) -> dict[str, object]:
        with self._lock:
            state = self._copy_state()
        return {
            "road_type_code": state.road_type_code,
            "road_number": int(state.road_number),
            "cross_road_number": int(state.cross_road_number),
            "door_plate_number": int(state.door_plate_number),
            "road_suffix_letter_code": state.road_suffix_letter_code or None,
            "road_bis_code": state.road_bis_code or None,
            "road_bis_suffix": state.road_bis_suffix or None,
            "road_quadrant_code": _optional_int(state.road_quadrant_code),
            "cross_suffix_letter_code": state.cross_suffix_letter_code or None,
            "cross_bis_code": state.cross_bis_code or None,
            "cross_bis_suffix": state.cross_bis_suffix or None,
            "cross_quadrant_code": _optional_int(state.cross_quadrant_code),
            "neighborhood_id": state.neighborhood_id,
        }

    def _report_payload(self, request_key: str, address_id: int) -> dict[str, object]:
        with self._lock:
            state = self._copy_state()
        assert state.failure_type_id is not None
        payload: dict[str, object] = {
            "request_key": request_key,
            "failure_type_id": state.failure_type_id,
            "address_id": address_id,
            "description": state.description,
            "email_notifications": state.email_notifications,
        }
        if state.contact_email:
            payload["contact_email"] = state.contact_email
        if state.contact_phone:
            payload["contact_phone"] = state.contact_phone
        return payload

    def _set_submitting(self) -> None:
        with self._lock:
            self.state.status = CitizenReportStatus.SUBMITTING
            self.state.field_errors.clear()
            self.state.general_message = None
            self.state.correlation_id = None
            self.state.confirmation = None
            self.state.matches = ()

    def _address_id_from_response(self, response: object) -> int | None:
        status_code, payload = _response_parts(response)
        data = _successful_data(status_code, payload)
        if isinstance(data, Mapping) and type(data.get("id")) is int and data["id"] > 0:
            return data["id"]
        return None

    def _apply_registration_response(self, response: object, account_id: int) -> CitizenReportFormState:
        status_code, payload = _response_parts(response)
        data = _successful_data(status_code, payload)
        if isinstance(data, Mapping):
            return self._apply_registration_data(data, account_id)
        if _is_error(payload) and _coherent_error(status_code, payload):
            if _is_result_unknown(payload):
                return self._set_unknown(
                    "No fue posible confirmar el resultado del envío. Comprueba o reenvía exactamente el mismo intento.",
                    _correlation_id(payload),
                )
            return self._apply_rejection(payload, "No fue posible registrar la falla.")
        return self._set_unknown("No fue posible confirmar el resultado del envío.", _correlation_id(payload))

    def _apply_registration_data(self, data: Mapping[str, object], account_id: int) -> CitizenReportFormState:
        with self._lock:
            expected_key = self.state.request_key
        if not _is_registration_output(data, expected_key):
            return self._set_unknown("El servicio devolvió una confirmación incompatible.", None)
        outcome = data["outcome"]
        if outcome == "created":
            ticket = data["ticket"]
            assert isinstance(ticket, Mapping)
            with self._lock:
                self.state.status = CitizenReportStatus.CONFIRMED
                self.state.confirmation = dict(ticket)
                self.state.matches = ()
                self.state.general_message = "La falla fue registrada correctamente."
                self.state.field_errors.clear()
                request_key = self.state.request_key
                snapshot = self._copy_state()
            self._clear_saved(account_id, request_key)
            return snapshot
        matches = data["matches"]
        assert isinstance(matches, list)
        with self._lock:
            self.state.status = CitizenReportStatus.MATCHES
            self.state.matches = tuple(dict(item) for item in matches)
            self.state.confirmation = None
            self.state.general_message = "Ya existe un reporte abierto para esta dirección y tipo de falla."
            self.state.field_errors.clear()
            request_key = self.state.request_key
            snapshot = self._copy_state()
        self._clear_saved(account_id, request_key)
        return snapshot

    def _apply_rejection(self, response: object, fallback: str) -> CitizenReportFormState:
        status_code, payload = _response_parts(response)
        if isinstance(response, Mapping) and "success" in response:
            payload = response
        error = payload.get("error") if isinstance(payload, Mapping) else None
        message = fallback
        field_errors: dict[str, str] = {}
        correlation_id = None
        operation_key_reused = False
        if isinstance(error, Mapping):
            message = _string_or_empty(error.get("message")) or fallback
            correlation_id = _string_or_none(error.get("correlation_id"))
            field_errors = _field_errors(error.get("details"))
            if error.get("code") == "CON-005":
                operation_key_reused = True
                message = "Esta clave de intento ya corresponde a otros datos. Recupera el intento correcto o descarta este borrador antes de iniciar otro."
        with self._lock:
            self.state.status = CitizenReportStatus.REJECTED
            self.state.operation_key_reused = operation_key_reused
            self.state.field_errors = field_errors
            self.state.general_message = message
            self.state.correlation_id = correlation_id
            return self._copy_state()

    def _apply_transport_error(self, error: BaseException) -> CitizenReportFormState:
        if getattr(error, "request_sent", None) is False:
            with self._lock:
                self.state.status = CitizenReportStatus.REJECTED
                self.state.general_message = "No fue posible enviar el reporte. Puedes reintentar el mismo intento."
                return self._copy_state()
        return self._set_unknown("No fue posible confirmar el resultado del envío.", None)

    def _set_unknown(self, message: str, correlation_id: str | None) -> CitizenReportFormState:
        with self._lock:
            self.state.status = CitizenReportStatus.UNKNOWN
            self.state.general_message = message
            self.state.correlation_id = correlation_id
            self.state.field_errors.clear()
            return self._copy_state()

    def _clear_saved(self, account_id: int, request_key: str | None) -> None:
        if request_key is None:
            return
        try:
            self._await_storage(self.storage.clear(account_id, request_key))
        except ReportAttemptStorageError:
            with self._lock:
                self.state.storage_warning = "El resultado fue confirmado, pero no se pudo eliminar el intento local guardado."

    def _remember_protected_response(self, response: object) -> None:
        with self._lock:
            self._last_protected_response = response

    def _call(self, method_name: str, *args, **kwargs) -> object:
        method = getattr(self.connector, method_name, None)
        if not callable(method):
            raise TypeError(f"citizen connector does not expose {method_name}")
        return method(*args, **kwargs)

    @staticmethod
    def _await_storage(awaitable):
        return asyncio.run(awaitable)

    def _copy_state(self) -> CitizenReportFormState:
        return CitizenReportFormState(
            failure_type_id=self.state.failure_type_id,
            description=self.state.description,
            road_type_code=self.state.road_type_code,
            road_number=self.state.road_number,
            cross_road_number=self.state.cross_road_number,
            door_plate_number=self.state.door_plate_number,
            road_suffix_letter_code=self.state.road_suffix_letter_code,
            road_bis_code=self.state.road_bis_code,
            road_bis_suffix=self.state.road_bis_suffix,
            road_quadrant_code=self.state.road_quadrant_code,
            cross_suffix_letter_code=self.state.cross_suffix_letter_code,
            cross_bis_code=self.state.cross_bis_code,
            cross_bis_suffix=self.state.cross_bis_suffix,
            cross_quadrant_code=self.state.cross_quadrant_code,
            neighborhood_id=self.state.neighborhood_id,
            contact_email=self.state.contact_email,
            contact_phone=self.state.contact_phone,
            email_notifications=self.state.email_notifications,
            address_id=self.state.address_id,
            address_version=self.state.address_version,
            status=self.state.status,
            field_errors=dict(self.state.field_errors),
            general_message=self.state.general_message,
            correlation_id=self.state.correlation_id,
            request_key=self.state.request_key,
            confirmation=dict(self.state.confirmation) if self.state.confirmation is not None else None,
            matches=tuple(dict(item) for item in self.state.matches),
            pending_payload=dict(self.state.pending_payload) if self.state.pending_payload is not None else None,
            operation_key_reused=self.state.operation_key_reused,
            storage_warning=self.state.storage_warning,
        )

    @staticmethod
    def _validate_number(value: str, field: str, minimum: int, maximum: int, errors: dict[str, str]) -> None:
        if not value:
            errors[field] = "Este componente de dirección es obligatorio."
            return
        try:
            number = int(value)
        except ValueError:
            errors[field] = "Ingresa un número entero."
            return
        if not minimum <= number <= maximum:
            errors[field] = f"El valor debe estar entre {minimum} y {maximum}."

    @staticmethod
    def _validate_optional_number(value: str, field: str, errors: dict[str, str]) -> None:
        if not value:
            return
        try:
            if int(value) <= 0:
                raise ValueError
        except ValueError:
            errors[field] = "Selecciona un valor válido."

    @staticmethod
    def _validate_optional_length(value: str, field: str, maximum: int, errors: dict[str, str]) -> None:
        if value and len(value) > maximum:
            errors[field] = "El valor seleccionado no es válido."

    @staticmethod
    def _validate_optional_letter(value: str, field: str, errors: dict[str, str]) -> None:
        if value and (len(value) != 1 or not value.isupper() or not value.isalpha()):
            errors[field] = "Selecciona una letra válida."

    @staticmethod
    def _email_is_valid(value: str) -> bool:
        return EMAIL_PATTERN.fullmatch(value) is not None


def _response_parts(response: object) -> tuple[int, object]:
    if isinstance(response, Mapping):
        status = response.get("status_code", response.get("status"))
        payload = response.get("payload", response)
    else:
        status = getattr(response, "status_code", getattr(response, "status", None))
        payload = getattr(response, "payload", None)
    return (status if type(status) is int else 0, payload)


def _successful_data(status_code: int, payload: object) -> object:
    if (
        status_code == 200
        and isinstance(payload, Mapping)
        and set(payload) == {"success", "data", "error"}
        and payload.get("success") is True
        and payload.get("error") is None
    ):
        return payload.get("data")
    return None


def _is_error(payload: object) -> bool:
    return isinstance(payload, Mapping) and payload.get("success") is False and isinstance(payload.get("error"), Mapping)


def _coherent_error(status_code: int, payload: object) -> bool:
    if not _is_error(payload):
        return False
    error = payload["error"]
    assert isinstance(error, Mapping)
    code = error.get("code")
    expected = {
        "VAL-001": {400},
        "VAL-002": {400},
        "USR-001": {403},
        "USR-003": {401},
        "USR-004": {401},
        "USR-005": {401},
        "PER-001": {403},
        "CON-005": {409},
        "REL-001": {422},
        "CAT-001": {500},
        "SYS-001": {500},
        "SYS-002": {500},
    }
    return type(code) is str and status_code in expected.get(code, set())


def _is_result_unknown(payload: object) -> bool:
    if not _is_error(payload):
        return False
    error = payload["error"]
    assert isinstance(error, Mapping)
    details = error.get("details")
    return isinstance(details, list) and any(
        isinstance(detail, Mapping) and detail.get("reason") == "result_unknown"
        for detail in details
    )


def _correlation_id(payload: object) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    error = payload.get("error")
    return _string_or_none(error.get("correlation_id")) if isinstance(error, Mapping) else None


def _field_errors(value: object) -> dict[str, str]:
    if not isinstance(value, list):
        return {}
    result: dict[str, str] = {}
    for item in value:
        if not isinstance(item, Mapping):
            continue
        field = _string_or_none(item.get("field"))
        reason = _string_or_none(item.get("reason"))
        if field and reason:
            result[field] = reason
    return result


def _is_registration_output(value: Mapping[str, object], expected_key: str | None) -> bool:
    if set(value) != {"request_key", "outcome", "ticket", "matches"}:
        return False
    if type(value.get("request_key")) is not str or value["request_key"] != expected_key:
        return False
    outcome = value.get("outcome")
    ticket = value.get("ticket")
    matches = value.get("matches")
    if type(matches) is not list or any(not _is_match(item) for item in matches):
        return False
    if outcome == "created":
        return not matches and _is_confirmation(ticket)
    return outcome == "matches" and ticket is None and bool(matches)


def _is_attempt_output(value: Mapping[str, object], expected_key: str) -> bool:
    if set(value) != {"request_key", "state", "result"} or value.get("request_key") != expected_key:
        return False
    state = value.get("state")
    result = value.get("result")
    if state == "not_found":
        return result is None
    return state == "committed" and isinstance(result, Mapping) and _is_registration_output(result, expected_key)


def _is_confirmation(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == {"code", "created_at", "status", "evidence_count"}
        and type(value.get("code")) is str
        and type(value.get("created_at")) is str
        and value.get("status") == "Registered"
        and type(value.get("evidence_count")) is int
        and value["evidence_count"] >= 0
    )


def _is_match(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == {"code", "status", "created_at", "progress_label"}
        and all(type(value.get(field)) is str for field in ("code", "status", "created_at", "progress_label"))
    )


def _optional_int(value: str) -> int | None:
    return int(value) if value else None


def _positive_int_or_none(value: object) -> int | None:
    return value if type(value) is int and value > 0 else None


def _string_or_empty(value: object) -> str:
    return value if type(value) is str else ""


def _string_or_none(value: object) -> str | None:
    return value if type(value) is str else None


__all__ = [
    "CitizenReportController",
    "CitizenReportFormState",
    "CitizenReportStatus",
]
