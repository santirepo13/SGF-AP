"""Executable local HTTP connector for the SGF-AP API."""

from __future__ import annotations

import argparse
import base64
from collections.abc import Mapping, Sequence
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import socket
from string import Formatter
import sys
from uuid import uuid4
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from config import ConnectorConfig, load_connector_config

_TIMEOUT_SECONDS = 10
_RELEVANT_RESPONSE_HEADERS = frozenset({"allow", "content-type", "www-authenticate", "x-correlation-id"})


@dataclass(frozen=True, slots=True)
class ConnectorOperation:
    """One HTTP operation exposed by the remote SGF-AP API."""

    method: str
    path: str


@dataclass(frozen=True, slots=True)
class ConnectorResponse:
    """A complete structured response received from the remote API."""

    status_code: int
    headers: dict[str, str]
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ConnectorRunResult:
    """The aggregate result of one complete, reversible connector test plan."""

    run_id: str
    succeeded: int
    failed: int
    cleanup_succeeded: bool


class _Tee:
    """Write connector diagnostics to the terminal and one local log file."""

    def __init__(self, *streams: object) -> None:
        self._streams = streams

    def write(self, text: str) -> int:
        for stream in self._streams:
            stream.write(text)
        return len(text)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


class ConnectorError(Exception):
    """A safe local connector failure that never contains credentials."""


class ConnectorTransportError(ConnectorError):
    """A connection failure for which the remote outcome may be unknown."""

    def __init__(self, message: str, *, request_sent: bool | None = None) -> None:
        super().__init__(message)
        self.request_sent = request_sent


class ConnectorTimeoutError(ConnectorTransportError):
    """A request exceeded the connector's configured network timeout."""


class ConnectorResponseError(ConnectorError):
    """A remote response could not be interpreted as the SGF-AP envelope."""

    def __init__(self, message: str, *, status_code: int | None = None, headers: Mapping[str, str] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.headers = dict(headers or {})
        self.request_sent = True


class _NoRedirectHandler(HTTPRedirectHandler):
    """Return redirection responses to the caller instead of following another destination."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


OPERATIONS: dict[str, ConnectorOperation] = {
    "catalogs.list_municipalities": ConnectorOperation("GET", "/catalogs/municipalities"),
    "catalogs.list_communes": ConnectorOperation("GET", "/catalogs/municipalities/{municipality_id}/communes"),
    "catalogs.list_neighborhoods_by_municipality": ConnectorOperation("GET", "/catalogs/municipalities/{municipality_id}/neighborhoods"),
    "catalogs.list_neighborhoods_by_commune": ConnectorOperation("GET", "/catalogs/communes/{commune_id}/neighborhoods"),
    "catalogs.list_neighborhoods_without_commune": ConnectorOperation("GET", "/catalogs/municipalities/{municipality_id}/neighborhoods/without-commune"),
    "catalogs.list_road_types": ConnectorOperation("GET", "/catalogs/road-types"),
    "catalogs.list_road_suffix_letters": ConnectorOperation("GET", "/catalogs/road-suffix-letters"),
    "catalogs.list_road_bis_codes": ConnectorOperation("GET", "/catalogs/road-bis-codes"),
    "catalogs.list_road_quadrants": ConnectorOperation("GET", "/catalogs/road-quadrants"),
    "catalogs.list_cross_suffix_letters": ConnectorOperation("GET", "/catalogs/cross-suffix-letters"),
    "catalogs.list_cross_bis_codes": ConnectorOperation("GET", "/catalogs/cross-bis-codes"),
    "catalogs.list_cross_quadrants": ConnectorOperation("GET", "/catalogs/cross-quadrants"),
    "catalogs.list_roles": ConnectorOperation("GET", "/catalogs/roles"),
    "catalogs.list_priorities": ConnectorOperation("GET", "/catalogs/priorities"),
    "catalogs.list_failure_types": ConnectorOperation("GET", "/catalogs/failure-types"),
    "catalogs.list_failure_types_by_priority": ConnectorOperation("GET", "/catalogs/priorities/{priority_id}/failure-types"),
    "catalogs.list_statuses": ConnectorOperation("GET", "/catalogs/statuses"),
    "catalogs.list_actions": ConnectorOperation("GET", "/catalogs/actions"),
    "addresses.get_by_id": ConnectorOperation("GET", "/addresses/{address_id}"),
    "addresses.find_by_components": ConnectorOperation("GET", "/addresses/search"),
    "addresses.create_or_reuse": ConnectorOperation("POST", "/addresses"),
    "addresses.format_address": ConnectorOperation("GET", "/addresses/{address_id}/formatted"),
    "users.get_by_id": ConnectorOperation("GET", "/users/{user_id}"),
    "users.get_by_email": ConnectorOperation("GET", "/users/by-email"),
    "users.register_citizen": ConnectorOperation("POST", "/users/register"),
    "users.list_by_filters": ConnectorOperation("GET", "/users"),
    "users.create": ConnectorOperation("POST", "/users"),
    "users.update": ConnectorOperation("PATCH", "/users/{user_id}"),
    "users.set_active": ConnectorOperation("PATCH", "/users/{user_id}/activation"),
    "crews.list_all": ConnectorOperation("GET", "/crews"),
    "crews.get_by_id": ConnectorOperation("GET", "/crews/{crew_id}"),
    "crews.create": ConnectorOperation("POST", "/crews"),
    "crews.update": ConnectorOperation("PATCH", "/crews/{crew_id}"),
    "crews.get_membership": ConnectorOperation("GET", "/crew-members/{user_id}"),
    "crews.list_members": ConnectorOperation("GET", "/crews/{crew_id}/members"),
    "crews.add_member": ConnectorOperation("POST", "/crews/{crew_id}/members"),
    "crews.change_crew": ConnectorOperation("PATCH", "/crew-members/{user_id}"),
    "crews.remove_member": ConnectorOperation("DELETE", "/crew-members/{user_id}"),
    "tickets.create": ConnectorOperation("POST", "/tickets"),
    "tickets.list_by_filters": ConnectorOperation("GET", "/tickets"),
    "tickets.get_by_code": ConnectorOperation("GET", "/tickets/by-code/{code}"),
    "tickets.get_by_id": ConnectorOperation("GET", "/tickets/{ticket_id}"),
    "tickets.validate": ConnectorOperation("POST", "/tickets/{ticket_id}/validate"),
    "tickets.prioritize": ConnectorOperation("POST", "/tickets/{ticket_id}/prioritize"),
    "tickets.assign": ConnectorOperation("POST", "/tickets/{ticket_id}/assign"),
    "tickets.attention": ConnectorOperation("POST", "/tickets/{ticket_id}/attention"),
    "tickets.block": ConnectorOperation("POST", "/tickets/{ticket_id}/block"),
    "tickets.request_closure": ConnectorOperation("POST", "/tickets/{ticket_id}/request-closure"),
    "tickets.review_closure": ConnectorOperation("POST", "/tickets/{ticket_id}/review-closure"),
    "evidences.get_by_id": ConnectorOperation("GET", "/evidences/{evidence_id}"),
    "evidences.list_by_ticket": ConnectorOperation("GET", "/evidences"),
    "evidences.list_by_ticket_and_uploader": ConnectorOperation("GET", "/evidences"),
    "evidences.create_metadata": ConnectorOperation("POST", "/evidences"),
    "history.get_event": ConnectorOperation("GET", "/history-events/{event_id}"),
    "history.list_by_ticket": ConnectorOperation("GET", "/history-events"),
}


class LocalConnector:
    """Execute one configured SGF-AP HTTP operation at a time."""

    def __init__(self, config: ConnectorConfig, *, opener: Any | None = None) -> None:
        self._config = config
        self._opener = opener or build_opener(_NoRedirectHandler())

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, object] | None = None,
        body: Mapping[str, object] | None = None,
        headers: Mapping[str, object] | None = None,
    ) -> ConnectorResponse:
        """Send one authenticated request and retain every structured API response."""

        url = self._url(path, params)
        data = _encode_body(body)
        request_headers = self._request_headers(headers, has_body=data is not None)
        request = Request(url, data=data, headers=request_headers, method=method.upper())
        try:
            with self._opener.open(request, timeout=_TIMEOUT_SECONDS) as response:
                return _decode_response(response.status, response.headers, response.read())
        except HTTPError as error:
            return _decode_response(error.code, error.headers, error.read())
        except socket.timeout as error:
            raise ConnectorTimeoutError(
                f"No se recibió una respuesta dentro de {_TIMEOUT_SECONDS} segundos; el resultado remoto puede ser desconocido.",
                request_sent=None,
            ) from error
        except URLError as error:
            if isinstance(error.reason, socket.timeout):
                raise ConnectorTimeoutError(
                    f"No se recibió una respuesta dentro de {_TIMEOUT_SECONDS} segundos; el resultado remoto puede ser desconocido.",
                    request_sent=None,
                ) from error
            raise ConnectorTransportError(
                "No fue posible conectar con la API remota; el resultado remoto puede ser desconocido.",
                request_sent=False,
            ) from error
        except OSError as error:
            raise ConnectorTransportError(
                "La conexión con la API remota fue interrumpida; el resultado remoto puede ser desconocido.",
                request_sent=None,
            ) from error

    def execute(
        self,
        operation: str,
        *,
        path_params: Mapping[str, object] | None = None,
        params: Mapping[str, object] | None = None,
        body: Mapping[str, object] | None = None,
        headers: Mapping[str, object] | None = None,
    ) -> ConnectorResponse:
        """Resolve a named operation, encode its route parameters, and send it once."""

        definition = OPERATIONS.get(operation)
        if definition is None:
            raise ConnectorError(f"La operación '{operation}' no existe. Use --list-operations para consultar las disponibles.")
        path = _render_path(definition.path, path_params)
        return self.request(definition.method, path, params=params, body=body, headers=headers)

    def register_citizen(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
    ) -> ConnectorResponse:
        """Send exactly the public citizen-registration fields once."""

        return self.execute(
            "users.register_citizen",
            body={
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "password": password,
            },
        )

    def _url(self, path: str, params: Mapping[str, object] | None) -> str:
        if not path.startswith("/"):
            raise ConnectorError("La ruta de una operación debe ser relativa al servidor configurado.")
        query = _encode_query(params)
        return f"{self._config.base_url}{path}" + (f"?{query}" if query else "")

    def _request_headers(self, extra_headers: Mapping[str, object] | None, *, has_body: bool) -> dict[str, str]:
        headers = {
            name: value
            for name, value in _safe_extra_headers(extra_headers).items()
            if name.lower() not in {"accept", "content-type"}
        }
        headers["Accept"] = "application/json"
        if has_body:
            headers["Content-Type"] = "application/json"
        token = base64.b64encode(f"{self._config.user}:{self._config.password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
        return headers


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse one connector operation and JSON objects provided from the terminal."""

    parser = argparse.ArgumentParser(description="Ejecuta una operación HTTP de SGF-AP mediante el conector local.")
    parser.add_argument("operation", nargs="?", help="Nombre de la operación registrada.")
    parser.add_argument("--path-params", metavar="JSON", help="Objeto JSON con los parámetros de ruta.")
    parser.add_argument("--params", metavar="JSON", help="Objeto JSON con los parámetros de consulta.")
    parser.add_argument("--body", metavar="JSON", help="Objeto JSON con el cuerpo de la solicitud.")
    parser.add_argument("--headers", metavar="JSON", help="Objeto JSON con cabeceras HTTP adicionales permitidas.")
    parser.add_argument("--run-all", metavar="PLAN_JSON", help="Ejecuta todas las operaciones de un plan JSON y limpia los datos de prueba al terminar.")
    parser.add_argument("--list-operations", action="store_true", help="Muestra las operaciones disponibles sin cargar configuración.")
    parsed = parser.parse_args(arguments)
    if parsed.list_operations:
        return parsed
    if (parsed.operation is None) == (parsed.run_all is None):
        parser.error("Indique OPERACION o --run-all PLAN_JSON, pero no ambos.")
    if parsed.run_all is not None:
        if any(getattr(parsed, name) is not None for name in ("path_params", "params", "body", "headers")):
            parser.error("--path-params, --params, --body y --headers se definen dentro del plan usado por --run-all.")
        return parsed
    for name in ("path_params", "params", "body", "headers"):
        value = getattr(parsed, name)
        if value is not None:
            try:
                setattr(parsed, name, _parse_json_object(value, f"--{name.replace('_', '-')}"))
            except argparse.ArgumentTypeError as error:
                parser.error(str(error))
    return parsed


def display_response(operation: str, response: ConnectorResponse) -> None:
    """Print safe diagnostic metadata and the complete structured response payload."""

    definition = OPERATIONS[operation]
    print(f"Operación: {operation}")
    print(f"Solicitud: {definition.method} {definition.path}")
    print(f"Estado HTTP: {response.status_code}")
    print(json.dumps(response.payload, ensure_ascii=False, indent=2, sort_keys=True))
    correlation_id = _correlation_id(response)
    if correlation_id:
        print(f"Correlación: {correlation_id}")


def main(arguments: Sequence[str] | None = None) -> int:
    """Run exactly one selected connector operation and return a shell exit code."""

    try:
        parsed = parse_arguments(arguments)
    except SystemExit as error:
        return int(error.code)
    if parsed.list_operations:
        _display_operations()
        return 0
    if parsed.run_all is not None:
        return _run_all(parsed.run_all)
    if parsed.operation not in OPERATIONS:
        print(f"Error del conector: la operación '{parsed.operation}' no existe. Use --list-operations.", file=sys.stderr)
        return 2
    try:
        connector = LocalConnector(load_connector_config())
    except (ValueError, OSError) as error:
        print(f"Error de configuración del conector: {error}", file=sys.stderr)
        return 2
    try:
        response = connector.execute(
            parsed.operation,
            path_params=parsed.path_params,
            params=parsed.params,
            body=parsed.body,
            headers=parsed.headers,
        )
    except ConnectorResponseError as error:
        _display_response_error(error)
        return 1
    except ConnectorError as error:
        print(f"Error del conector: {error}", file=sys.stderr)
        return 1

    display_response(parsed.operation, response)
    return 0 if response.status_code < 400 and response.payload["success"] is True else 1


def _connector_log_directory() -> Path:
    """Store each temporary run log beside the executable connector."""

    return Path(__file__).resolve().parent


def _run_all(plan_file: str) -> int:
    """Persist all output from one full plan run in a temporary local log file."""

    log_path = _connector_log_directory() / f"sgf-ap-connector-{uuid4().hex}.log"
    try:
        with log_path.open("w", encoding="utf-8") as log_file:
            with redirect_stdout(_Tee(sys.stdout, log_file)), redirect_stderr(_Tee(sys.stderr, log_file)):
                print(f"Registro temporal: {log_path}")
                return _execute_full_plan(plan_file)
    except OSError:
        print("Error del conector: no fue posible crear el registro temporal.", file=sys.stderr)
        return 1


def _execute_full_plan(plan_file: str) -> int:
    """Execute every operation in a plan, then remove the run's test data from PostgreSQL."""

    try:
        plan = _load_test_plan(plan_file)
        connector_config = load_connector_config()
        from api.config import load_database_config

        database_config = load_database_config()
    except Exception as error:
        print(f"Error de configuración del conector: {error}", file=sys.stderr)
        return 2

    run_id = f"ct-{uuid4().hex[:12]}"
    started_at = datetime.now(timezone.utc)
    context: dict[str, object] = {
        "run_id": run_id,
        "now": started_at.isoformat(),
    }
    created_address_ids: set[int] = set()
    succeeded = 0
    failed = 0
    cleanup_succeeded = False
    connector = LocalConnector(connector_config)
    print(f"Ejecución de prueba: {run_id}")
    try:
        for index, step in enumerate(plan, start=1):
            operation = step["operation"]
            try:
                resolved = _resolve_step(step, context)
                _require_test_marker(operation, resolved.get("body"), run_id)
                response = connector.execute(
                    operation,
                    path_params=resolved.get("path_params"),
                    params=resolved.get("params"),
                    body=resolved.get("body"),
                    headers=resolved.get("headers"),
                )
                display_response(operation, response)
                if response.status_code < 400 and response.payload["success"] is True:
                    succeeded += 1
                    _save_step_result(step, response, context)
                    _record_created_address(operation, response, created_address_ids)
                else:
                    failed += 1
                    _record_failed_step(step, response, context)
                    print(f"Resultado no exitoso en el paso {index}: {operation}.", file=sys.stderr)
            except ConnectorResponseError as error:
                failed += 1
                print(f"Paso {index} ({operation}):", file=sys.stderr)
                _display_response_error(error)
            except ConnectorError as error:
                failed += 1
                print(f"Error del conector en el paso {index} ({operation}): {error}", file=sys.stderr)
    finally:
        try:
            _cleanup_test_data(database_config, run_id, created_address_ids, started_at)
            cleanup_succeeded = True
            print(f"Limpieza completada para la ejecución {run_id}.")
        except ConnectorError as error:
            print(f"Error de limpieza para la ejecución {run_id}: {error}", file=sys.stderr)

    result = ConnectorRunResult(run_id, succeeded, failed, cleanup_succeeded)
    print(f"Operaciones exitosas: {result.succeeded}; fallidas: {result.failed}.")
    return 0 if result.failed == 0 and result.cleanup_succeeded else 1


def _load_test_plan(plan_file: str) -> list[dict[str, object]]:
    path = Path(plan_file)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConnectorError("No fue posible leer el plan de pruebas.") from error
    except json.JSONDecodeError as error:
        raise ConnectorError("El plan de pruebas debe contener JSON válido.") from error
    if not isinstance(value, Mapping) or not isinstance(value.get("operations"), list):
        raise ConnectorError("El plan debe ser un objeto con una lista operations.")
    operations: list[dict[str, object]] = []
    for item in value["operations"]:
        if not isinstance(item, Mapping) or not isinstance(item.get("operation"), str):
            raise ConnectorError("Cada elemento del plan debe incluir el nombre string operation.")
        operation = item["operation"]
        if operation not in OPERATIONS:
            raise ConnectorError(f"El plan contiene una operación inexistente: {operation}.")
        operations.append(dict(item))
    names = [item["operation"] for item in operations]
    missing = sorted(set(OPERATIONS) - set(names))
    if missing:
        raise ConnectorError(f"El plan debe incluir todas las operaciones; faltan: {', '.join(missing)}.")
    return operations


def _resolve_step(step: Mapping[str, object], context: Mapping[str, object]) -> dict[str, object]:
    resolved = {
        name: _resolve_plan_value(value, context)
        for name, value in step.items()
        if name in {"path_params", "params", "body", "headers"}
    }
    for name, value in resolved.items():
        if not isinstance(value, Mapping):
            raise ConnectorError(f"{name} debe resolver a un objeto JSON.")
    return resolved


def _resolve_plan_value(value: object, context: Mapping[str, object]) -> object:
    if isinstance(value, str):
        substituted = value.replace("{run_id}", str(context["run_id"])).replace("{now}", str(context["now"]))
        if substituted.startswith("$"):
            return _resolve_reference(substituted, context)
        return substituted
    if isinstance(value, list):
        return [_resolve_plan_value(item, context) for item in value]
    if isinstance(value, Mapping):
        return {str(name): _resolve_plan_value(item, context) for name, item in value.items()}
    return value


def _record_failed_step(step: Mapping[str, object], response: ConnectorResponse, context: dict[str, object]) -> None:
    save_as = step.get("save_as")
    if isinstance(save_as, str) and save_as.isidentifier():
        context[f"__failure_{save_as}"] = f"{step['operation']} devolvió HTTP {response.status_code}"


def _resolve_reference(reference: str, context: Mapping[str, object]) -> object:
    match = re.fullmatch(r"\$([A-Za-z_]\w*)((?:\.[A-Za-z_]\w*|\[\d+\])*)", reference)
    if match is None:
        raise ConnectorError(f"La referencia del plan es inválida: {reference}.")
    source = match.group(1)
    value = context.get(source)
    if value is None:
        failure = context.get(f"__failure_{source}")
        suffix = f"; {failure}." if isinstance(failure, str) else "."
        raise ConnectorError(f"La referencia del plan no está disponible: {reference}{suffix}")
    for name, index in re.findall(r"\.([A-Za-z_]\w*)|\[(\d+)\]", match.group(2)):
        if name:
            if not isinstance(value, Mapping) or name not in value:
                raise ConnectorError(f"La referencia del plan no está disponible: {reference}.")
            value = value[name]
        else:
            if not isinstance(value, list):
                raise ConnectorError(f"La referencia del plan no está disponible: {reference}.")
            try:
                value = value[int(index)]
            except IndexError as error:
                raise ConnectorError(f"La referencia del plan está vacía o no contiene el índice requerido: {reference}.") from error
    return value


def _require_test_marker(operation: str, body: object, run_id: str) -> None:
    required_marker_fields = {
        "users.create": "email",
        "users.register_citizen": "email",
        "crews.create": "name",
        "tickets.create": "code",
        "evidences.create_metadata": "file_path",
    }
    field = required_marker_fields.get(operation)
    if field is None:
        return
    if not isinstance(body, Mapping) or not isinstance(body.get(field), str) or run_id not in body[field]:
        raise ConnectorError(f"{operation} debe incluir {{run_id}} en body.{field} para permitir la limpieza directa.")


def _save_step_result(step: Mapping[str, object], response: ConnectorResponse, context: dict[str, object]) -> None:
    save_as = step.get("save_as")
    if save_as is None:
        return
    if not isinstance(save_as, str) or not save_as.isidentifier():
        raise ConnectorError("save_as debe ser un identificador válido.")
    context[save_as] = response.payload["data"]


def _record_created_address(operation: str, response: ConnectorResponse, address_ids: set[int]) -> None:
    if operation != "addresses.create_or_reuse":
        return
    data = response.payload["data"]
    if isinstance(data, Mapping) and isinstance(data.get("id"), int):
        address_ids.add(data["id"])


def _cleanup_test_data(database_config: object, run_id: str, address_ids: set[int], started_at: datetime) -> None:
    """Delete only data tagged by this run after the HTTP operations have completed."""

    try:
        import psycopg
    except ModuleNotFoundError as error:
        raise ConnectorError("psycopg es necesaria para limpiar los datos de prueba.") from error
    connection_kwargs = getattr(database_config, "connection_kwargs", None)
    if not isinstance(connection_kwargs, Mapping):
        raise ConnectorError("La configuración de PostgreSQL no está disponible para la limpieza.")
    marker = f"%{run_id}%"
    try:
        with psycopg.connect(**connection_kwargs) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM evidences WHERE file_path LIKE %s OR ticket_id IN (SELECT id FROM tickets WHERE code LIKE %s)",
                    (marker, marker),
                )
                cursor.execute(
                    "DELETE FROM history_events WHERE ticket_id IN (SELECT id FROM tickets WHERE code LIKE %s) OR user_id IN (SELECT id FROM users WHERE email LIKE %s)",
                    (marker, marker),
                )
                cursor.execute(
                    "DELETE FROM crew_members WHERE user_id IN (SELECT id FROM users WHERE email LIKE %s) OR crew_id IN (SELECT id FROM crews WHERE name LIKE %s)",
                    (marker, marker),
                )
                cursor.execute("DELETE FROM tickets WHERE code LIKE %s", (marker,))
                if address_ids:
                    cursor.execute(
                        "DELETE FROM addresses AS address WHERE address.id = ANY(%s) AND address.created_at >= %s AND NOT EXISTS (SELECT 1 FROM tickets WHERE address_id = address.id)",
                        (list(address_ids), started_at - timedelta(minutes=5)),
                    )
                cursor.execute("DELETE FROM users WHERE email LIKE %s", (marker,))
                cursor.execute("DELETE FROM crews WHERE name LIKE %s", (marker,))
    except Exception as error:
        raise ConnectorError("No fue posible limpiar los datos de prueba en PostgreSQL.") from error


def _render_path(template: str, path_params: Mapping[str, object] | None) -> str:
    values = {} if path_params is None else dict(path_params)
    required = _path_parameter_names(template)
    missing = [name for name in required if name not in values or values[name] is None]
    unexpected = sorted(set(values) - set(required))
    if missing:
        raise ConnectorError(f"Faltan parámetros de ruta: {', '.join(missing)}.")
    if unexpected:
        raise ConnectorError(f"La operación no admite parámetros de ruta: {', '.join(unexpected)}.")
    return template.format(**{name: quote(str(values[name]), safe="") for name in required})


def _path_parameter_names(template: str) -> tuple[str, ...]:
    names: list[str] = []
    formatter = Formatter()
    for _, field_name, _, _ in formatter.parse(template):
        if field_name is not None:
            if not field_name.isidentifier():
                raise ConnectorError("La operación contiene una plantilla de ruta inválida.")
            names.append(field_name)
    return tuple(names)


def _encode_query(params: Mapping[str, object] | None) -> str:
    if params is None:
        return ""
    encoded: list[tuple[str, str]] = []
    for name, value in params.items():
        if value is None:
            continue
        if isinstance(value, list):
            encoded.extend((str(name), _query_value(item)) for item in value)
        else:
            encoded.append((str(name), _query_value(value)))
    return urlencode(encoded, doseq=True)


def _query_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def _encode_body(body: Mapping[str, object] | None) -> bytes | None:
    if body is None:
        return None
    if not isinstance(body, Mapping):
        raise ConnectorError("El cuerpo debe ser un objeto JSON.")
    try:
        return json.dumps(dict(body), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ConnectorError("El cuerpo contiene valores que no pueden serializarse como JSON.") from error


def _safe_extra_headers(headers: Mapping[str, object] | None) -> dict[str, str]:
    if headers is None:
        return {}
    if not isinstance(headers, Mapping):
        raise ConnectorError("Las cabeceras adicionales deben ser un objeto JSON.")
    safe_headers: dict[str, str] = {}
    for name, value in headers.items():
        header_name = str(name)
        if header_name.lower() == "authorization":
            raise ConnectorError("Authorization es administrada por el conector y no puede reemplazarse.")
        safe_headers[header_name] = str(value)
    return safe_headers


def _decode_response(status_code: int, headers: Any, content: bytes) -> ConnectorResponse:
    relevant_headers = _relevant_headers(headers)
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConnectorResponseError(
            "La API devolvió una respuesta no JSON o incompatible.",
            status_code=status_code,
            headers=relevant_headers,
        ) from error
    if not isinstance(payload, dict) or set(("success", "data", "error")) - set(payload):
        raise ConnectorResponseError(
            "La API devolvió un JSON incompatible con el formato de respuesta esperado.",
            status_code=status_code,
            headers=relevant_headers,
        )
    return ConnectorResponse(status_code=status_code, headers=relevant_headers, payload=payload)


def _relevant_headers(headers: Any) -> dict[str, str]:
    if headers is None:
        return {}
    return {
        name: value
        for name, value in headers.items()
        if name.lower() in _RELEVANT_RESPONSE_HEADERS and name.lower() != "authorization"
    }


def _parse_json_object(value: str, option: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError(f"{option} debe contener JSON válido.") from error
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError(f"{option} debe ser un objeto JSON.")
    return parsed


def _display_operations() -> None:
    for name, definition in OPERATIONS.items():
        print(f"{name}: {definition.method} {definition.path}")


def _correlation_id(response: ConnectorResponse) -> str | None:
    error = response.payload.get("error")
    if isinstance(error, Mapping) and isinstance(error.get("correlation_id"), str):
        return error["correlation_id"]
    for name, value in response.headers.items():
        if name.lower() == "x-correlation-id":
            return value
    return None


def _display_response_error(error: ConnectorResponseError) -> None:
    if error.status_code is not None:
        print(f"Estado HTTP: {error.status_code}", file=sys.stderr)
    correlation_id = next(
        (value for name, value in error.headers.items() if name.lower() == "x-correlation-id"),
        None,
    )
    if correlation_id:
        print(f"Correlación: {correlation_id}", file=sys.stderr)
    print(f"Error del conector: {error}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
