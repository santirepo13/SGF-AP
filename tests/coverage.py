"""Run every test and accumulate one CSV row per executed case.

The runner discovers files, asks pytest for JUnit results, combines those
results with runtime traces, writes the case report, and checks workflow
coverage before returning a success or failure status.

Usage:
    python tests/coverage.py
    python tests/coverage.py --csv traceability_tests/results.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TESTS_DIR.parent
# Direct execution starts inside tests/, so restore the project import root.
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from tests.ticket_workflow.inventory import WORKFLOW_CASE_IDS

DEFAULT_CSV = PROJECT_DIR / "traceability_tests" / "test_results.csv"
PRIORITY_CASES = WORKFLOW_CASE_IDS


def discovered_tests() -> tuple[Path, ...]:
    """Find every test file recursively so no Scrum is left out."""
    return tuple(sorted(TESTS_DIR.rglob("test_*.py")))


def pytest_command(arguments: list[str], junit_path: Path) -> list[str]:
    """Build the pytest command that records one JUnit result per case."""
    return [
        sys.executable,
        "-m",
        "pytest",
        "-vv",
        "-o", "junit_family=xunit1",
        "--junitxml",
        str(junit_path),
        *arguments,
        *(str(path) for path in discovered_tests()),
    ]


_METHOD_DESCRIPTIONS: dict[str, str] | None = None
# Direct tests need explicit wording because their function names are not reports.
_DIRECT_EXPLANATIONS = {
    "test_load_database_config_from_dotenv_file": "Database settings are loaded from the local configuration file when no environment values override them.",
    "test_environment_values_override_dotenv_file": "Database settings supplied by the environment take precedence over values in the local file.",
    "test_connection_provider_passes_config_and_closes_connection": "The connection provider passes the configured settings to the connector and closes the connection after use.",
    "test_connection_failure_is_centralized_and_keeps_cause": "A refused database connection becomes a consistent application error while retaining the original failure for diagnosis.",
    "test_provider_connection_can_be_injected_into_repository": "A repository can use a connection supplied by the provider, read the requested municipality, and release both the cursor and connection.",
    "test_postgresql_read_and_connection_close": "A real PostgreSQL connection answers a simple query and is closed when the read finishes.",
    "test_user_create_applies_sql_default_for_active": "A newly created user is active by default when no active status is supplied.",
    "test_user_output_excludes_password_hash": "The public user record does not expose the stored password hash.",
    "test_partial_updates_distinguish_unset_from_none": "A partial user update distinguishes an omitted name from an email explicitly cleared.",
    "test_nullable_address_components_default_to_none": "Optional address details remain absent when they are not supplied.",
    "test_address_sql_ranges_are_enforced": "Address creation rejects a road number below its minimum and a door number above its maximum.",
    "test_persisted_datetime_requires_timezone": "A saved address requires a date and time with a time zone; a timezone-free value is rejected.",
    "test_ticket_attention_supports_unset_and_none": "Ticket attention distinguishes a diagnosis left unchanged from one explicitly cleared.",
    "test_ticket_code_sql_length_is_enforced": "A ticket code longer than the database allows is rejected before it is saved.",
    "test_operation_result_invariants": "Successful results retain their data, failed results retain their error, and a failure without an error is rejected.",
    "test_catalog_sql_checks_are_represented": "Known role and priority names are accepted, while unknown role and action names are rejected.",
    "test_actor_policy_is_explicit": "Registering a ticket requires an actor, while looking up a ticket does not; missing actor details are rejected.",
    "test_catalog_lookup_uses_typed_identifier": "A role lookup keeps the identifier supplied by its caller.",
    "test_contract_edge_cases_are_preserved": "Contracts preserve an explicit inactive user, distinguish omitted from cleared email, accept either closure decision, and retain large history identifiers.",
    "test_error_code_catalog_is_complete_and_immutable": "Every public error has one catalogue entry, and those entries cannot be changed during execution.",
    "test_application_error_uses_catalog_and_preserves_cause": "An invalid reference uses the catalogue's public message while retaining its original internal cause.",
    "test_public_error_reuses_scrum_one_contract_without_cause": "A public error includes a safe message, field detail, and tracking reference without exposing its internal cause.",
    "test_existing_correlation_is_preserved_and_missing_one_is_generated": "An existing tracking reference is kept, and a new one is generated when none was supplied.",
    "test_not_null_from_internal_write_is_not_user_validation": "A missing value caused by an internal database write is reported as a database failure, not blamed on the user.",
    "test_unexpected_exception_is_sys_002_and_technical_message_is_hidden": "An unexpected internal failure returns a safe public message without leaking a secret from the exception.",
    "test_known_error_keeps_its_code_through_handler": "A known permission error keeps its meaning and original tracking reference when handled.",
    "test_every_repository_implementation_matches_its_interface_methods": "Every repository exposes the methods and argument names promised by its interface.",
    "test_service_implementations_match_their_service_interfaces": "Every service matches its interface's methods, arguments, defaults, and return types.",
    "test_repository_inventory_contains_22_interfaces_and_70_methods": "The repository inventory includes every expected interface and operation.",
    "test_service_inventory_contains_7_interfaces_and_55_methods": "The service inventory includes every expected interface and operation.",
    "test_case_registry_rejects_duplicate_ids_and_preserves_traceability": "The case registry keeps each case linked to its test file and rejects repeated identifiers.",
    "test_pipeline_sets_correlation_invokes_service_once_and_logs_result": "A valid request receives a tracking reference, calls the service once, and records its successful completion.",
    "test_invalid_input_stops_before_service": "Invalid request data is rejected before the service is called.",
    "test_inactive_actor_stops_protected_operation": "An inactive user cannot start a protected operation, and the service is not called.",
    "test_valid_false_result_is_preserved": "A service response containing false remains a successful result rather than becoming an error.",
    "test_interruption_is_logged_with_the_central_error_code": "A rejected request is logged as unsuccessful with the reason for rejection.",
    "test_supplied_correlation_is_preserved_on_failure": "A failed request retains the tracking reference supplied by its caller.",
    "test_existing_context_correlation_is_preserved": "A successful request retains the tracking reference already present in its context.",
    "test_operation_method_mismatch_is_rejected_before_service": "A request naming a different operation is rejected before any service method runs.",
    "test_service_is_invoked_once_and_false_is_valid_data": "The service runs only once, and a false response is treated as valid data.",
    "test_actor_absent_inactive_and_forbidden_cases_are_distinct": "Missing identity, inactive identity, and denied permission are handled separately without calling the service.",
    "test_logging_failure_does_not_repeat_service_or_change_result": "A logging failure neither repeats the service call nor changes its successful response.",
    "test_incompatible_annotated_result_becomes_internal_error": "A service response with the wrong declared type becomes a safe internal error.",
    "test_known_service_error_keeps_public_shape_and_correlation": "A service's known error keeps its public format and receives the request's tracking reference.",
    "test_all_22_models_are_constructible": "Every expected data model can be created with representative valid values.",
    "test_model_fields_match_address_table": "The address model contains the same fields as its database table.",
    "test_nullable_relationships_are_preserved": "Optional links between neighborhoods, tickets, histories, and other records remain absent when not supplied.",
    "test_enum_rejects_unknown_sql_value": "An unknown stored role name is rejected instead of silently becoming a valid role.",
    "test_models_require_timezone_aware_dates": "Ticket creation rejects a date and time that has no time zone.",
    "test_repository_maps_rows_and_parameterizes_values_without_transaction_control": "A municipality lookup uses bound query values, returns the matching record, and leaves transaction control to its caller.",
    "test_address_component_lookup_uses_null_safe_parameters": "An address lookup can match optional details that are absent without building unsafe query text.",
    "test_ticket_update_uses_allowlist_and_none_clears_nullable_value": "A ticket update changes only permitted fields and can clear an optional contact number.",
    "test_ticket_geographic_filters_are_parameterized_and_deterministic": "Ticket searches bind geographic filters as values and use a stable result order.",
    "test_address_catalog_keeps_numeric_quadrant_code_contract": "Address catalogue lookup preserves the expected type of a road code.",
    "test_user_service_uses_injected_repository_and_excludes_password_hash": "The user service reads through its supplied repository and returns user details without the password hash.",
    "test_parameterized_explanations_identify_each_scenario": "Each tested configuration or database failure has its own plain-language explanation without technical error codes.",
    "test_component_explanations_describe_operations_without_case_or_method_codes": "Repository and service failures are described by the affected operation rather than internal method names.",
    "test_catalog_and_enum_explanations_use_readable_names": "Catalogue errors and stored values are described in ordinary words instead of internal names.",
    "test_csv_rejects_duplicate_explanations": "The report refuses to save two cases with the same explanation, even when spacing or capitalization differs.",
}


def _method_descriptions() -> dict[str, str]:
    """Pair repository and service case IDs with their tested methods."""
    global _METHOD_DESCRIPTIONS
    if _METHOD_DESCRIPTIONS is not None:
        return _METHOD_DESCRIPTIONS
    result: dict[str, str] = {}
    try:
        from tests.support.component_catalog import REPOSITORY_PAIRS, SERVICE_PAIRS, public_methods
        for prefix, pairs in (
            ("R4", REPOSITORY_PAIRS), ("S6", SERVICE_PAIRS),
        ):
            index = 1
            for interface, implementation in pairs:
                for method in public_methods(interface):
                    result[f"{prefix}-{index:02d}"] = f"{implementation.__name__}.{method}"
                    index += 1
    except Exception:
        pass
    _METHOD_DESCRIPTIONS = result
    return result
def _description(nodeid: str, case_id: str) -> str:
    """Choose a short description from the case registry or test name."""
    base_id, _, variant = case_id.partition(".")
    mapped = _method_descriptions().get(base_id)
    if mapped:
        variants = {
            "V": "valid execution",
            "N": "expected absence or empty result",
            "E": "centralized error and preserved cause",
        }
        return f"{mapped} ({variants.get(variant, variant or 'case')})"
    if case_id.startswith(("S1-", "S2-", "S3-", "S5-", "S7-", "S8-", "S9-", "PE-", "AD-", "RUN-")):
        return f"Traceability case {case_id}"
    name = nodeid.rsplit("::", 1)[-1].split("[", 1)[0]
    name = re.sub(r"^test_", "", name).replace("_", " ")
    return name[:1].upper() + name[1:]


def _runtime_description(trace: dict[str, object], nodeid: str, case_id: str) -> str:
    """Identify the exact method exercised by a parametrized case."""
    parameters = trace.get("parameters", {})
    if isinstance(parameters, dict):
        method = parameters.get("method", "").strip("'\"")
        implementation = parameters.get("implementation", "")
        class_match = re.search(r"\.([A-Za-z][A-Za-z0-9_]*)(?:'>|'>)$", implementation)
        if method and class_match:
            return f"{class_match.group(1)}.{method}"
    return _description(nodeid, case_id)


def _human_operation(trace: dict[str, object], nodeid: str, case_id: str) -> str:
    """Turn a repository or service method into an understandable action."""
    description = _runtime_description(trace, nodeid, case_id)
    if "." not in description:
        return description.lower()
    class_name, method = description.split(".", 1)
    entity = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", class_name.removesuffix("Repository").removesuffix("Service")).lower()
    if method.startswith("get_by_"):
        criterion = method.removeprefix("get_by_").replace("_", " ")
        criterion = re.sub(r"\bid\b", "identifier", criterion)
        return f"looking up the {entity} record by {criterion}"
    if method.startswith("find_by_"):
        criterion = method.removeprefix("find_by_").replace("_", " ")
        return f"finding the {entity} record from its {criterion}"
    if method.startswith("list_"):
        target = method.removeprefix("list_").replace("_", " ")
        if target == "all":
            return f"listing all {entity} records"
        if target.startswith(("by ", "without ")):
            return f"listing {entity} records {target}"
        return f"listing {target} through the {entity} service"
    actions = {
        "add_member": "adding a member to",
        "assign": "assigning",
        "block": "blocking",
        "change_crew": "changing the crew for",
        "create": "creating",
        "create_event": "recording an event for",
        "create_metadata": "creating metadata for",
        "create_or_reuse": "creating or reusing",
        "format_address": "formatting",
        "get_event": "retrieving an event from",
        "get_membership": "retrieving membership from",
        "prioritize": "prioritizing",
        "record_attention": "recording attention for",
        "remove": "removing",
        "remove_member": "removing a member from",
        "request_closure": "requesting closure for",
        "review_closure": "reviewing closure for",
        "set_active": "changing the active status of",
        "update": "updating",
        "update_crew": "updating the crew for",
        "validate": "validating",
    }
    return f"{actions.get(method, method.replace('_', ' '))} the {entity} record"


def _explanation(trace: dict[str, object], nodeid: str, case_id: str) -> str:
    """Describe what the case verifies without repeating machine-only codes."""
    description = _runtime_description(trace, nodeid, case_id)
    parameters = trace.get("parameters", {})
    name = nodeid.rsplit("::", 1)[-1]
    scenario_text = {
        "VALID": "a valid value is accepted and preserved",
        "OMITIDO": "an omitted required value is rejected",
        "NULL": "NULL is rejected where the field is not nullable",
        "TIPO": "an incompatible type is rejected",
        "NULL_PERMITIDO": "NULL is preserved because the field is nullable",
        "VALOR_PERMITIDO": "a valid nullable value is preserved",
        "SIN_CAMBIO": "an omitted update preserves the previous value",
        "CAMBIO": "a supplied update replaces the previous value",
        "V": "the operation succeeds with valid data",
        "N": "the documented absence or empty result is preserved",
        "E": "the failure is classified and propagated without hiding its cause",
        "TX_OK": "all related writes complete as one transaction",
        "TX_PRIMERA": "a failure in the first write prevents a partial result",
        "TX_HISTORIAL": "a history failure prevents success after the main update",
        "TX_COMMIT": "a commit failure is reported as a transaction failure",
        "TX_ROLLBACK": "the original failure and rollback failure remain distinguishable",
        "TX_RESULTADO": "a failed operation result stops the coordinated operation",
        "TX_COMPARTIDA": "all participants use the same transaction context",
        "TX_RECURSOS_OK": "resources are released after successful completion",
        "TX_RECURSOS_ERROR": "resources are released after failure",
    }
    # Contract variants and component matrices need their own readable outcomes.
    if case_id.startswith("S1."):
        parts = case_id.split(".")
        scenario = scenario_text.get(parts[-1], "the contract-specific case is verified")
        field = " ".join(parts[1:-1]).replace("_", " ")
        return f"For {field}, checks that {scenario}."
    if case_id.startswith("R4-"):
        operation = _human_operation(trace, nodeid, case_id)
        if case_id.endswith(".N"):
            method = description.rsplit(".", 1)[-1]
            outcome = "an empty list" if method.startswith("list") else "no removal" if method == "remove" else "no record"
            return f"If {operation} yields no match, the repository returns {outcome}."
        return f"When the database fails while {operation}, the repository reports an application error and preserves the original cause."
    if case_id.startswith("S6-"):
        operation = _human_operation(trace, nodeid, case_id)
        return f"When a dependency fails while {operation}, the service returns a failed result and preserves the request's tracking reference."
    if case_id.startswith("S3-"):
        situations = {
            "REQUIRED_FIELD_MISSING": "a required value is missing",
            "INVALID_VALUE": "a supplied value is invalid",
            "RESOURCE_NOT_FOUND": "a requested record does not exist",
            "INVALID_REFERENCE": "a related record does not exist",
            "UNIQUE_CONFLICT": "a unique value is already in use",
            "INACTIVE_USER": "a user account is inactive",
            "FORBIDDEN_OPERATION": "the user lacks permission",
            "INVALID_TICKET_STATE": "the ticket is in the wrong state",
            "CATALOG_VALUE_UNAVAILABLE": "a required catalogue option is unavailable",
            "PERSISTENCE_FAILURE": "the database operation fails",
            "UNEXPECTED_ERROR": "an unexpected internal error occurs",
        }
        situation = situations.get(case_id.removeprefix("S3-"), "an application error occurs")
        return f"The error catalogue provides a clear message and category when {situation}."
    if "." in case_id:
        base, variant = case_id.rsplit(".", 1)
        if variant in scenario_text:
            subject = re.sub(r"^test_", "", name.split("[", 1)[0]).replace("_", " ")
            return f"For {subject}, checks that {scenario_text[variant]}."
    if re.match(r"(?:PE|AD|RUN)-", case_id):
        return f"Checks the documented situation: {description}."
    if re.match(r"S[2-9]-", case_id):
        return f"Checks the documented behavior: {description}."
    # Configuration variants differ by the missing setting or invalid port.
    if "missing_database_parameter_is_invalid" in name:
        missing = str(parameters.get("missing", "the required setting")).strip("'\"")
        settings = {
            "DB_HOST": "server address",
            "DB_PORT": "connection port",
            "DB_NAME": "database name",
            "DB_USER": "user name",
            "DB_PASSWORD": "password",
        }
        return f"When the database {settings.get(missing, 'required setting')} is omitted, the configuration is rejected before connecting."
    if "invalid_port_is_rejected" in name:
        port = str(parameters.get("port", "the supplied value")).strip("'\"")
        problems = {
            "not-a-number": "contains text instead of a number",
            "0": "is zero",
            "65536": "exceeds the allowed range",
        }
        return f"When the database connection port {problems.get(port, 'is invalid')}, the configuration is rejected before connecting."
    # Database codes stay in trace inputs; the explanation names the user impact.
    if "persistence_sqlstate_translation" in name:
        sqlstate = str(parameters.get("sqlstate", "unknown")).strip("'\"")
        outcomes = {
            "23502": "When a required input is missing, the system reports that a mandatory value was not provided.",
            "23503": "When a submitted reference points to no record, the system reports an invalid reference.",
            "23505": "When a unique value is already in use, the system reports a conflict.",
            "23514": "When submitted data breaks a database rule, the system reports invalid input.",
            "22001": "When submitted text is too long for its field, the system reports invalid input.",
            "22P02": "When submitted text cannot be converted to the expected type, the system reports invalid input.",
            "22003": "When a submitted number is outside the allowed range, the system reports invalid input.",
            "08006": "When the database connection fails, the system reports an internal database problem.",
            "40001": "When concurrent transactions conflict, the system reports an internal database problem.",
            "40P01": "When database operations deadlock, the system reports an internal database problem.",
        }
        return outcomes.get(sqlstate, "When the database rejects an operation, the system reports a safe application error.")
    if "enum_sql_round_trip" in name:
        value = str(parameters.get("value", "the catalog value")).strip("'\"")
        enum_match = re.search(r"<enum '([^']+)'>", str(parameters.get("enum_type", "")))
        enum_type = enum_match.group(1) if enum_match else ""
        kind = {
            "RoleName": "user role",
            "PriorityName": "ticket priority",
            "StatusName": "ticket status",
            "ActionName": "ticket history action",
        }.get(enum_type, "catalogue")
        human_value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value).lower()
        return f"The {kind} value '{human_value}' remains unchanged when read from and written to the database."
    if "technical_failures" in name:
        return f"Checks that {description} converts a database failure into the central error format while preserving its cause internally."
    if "centralized_failure" in name:
        return f"Checks that {description} returns the central error result and preserves the operation correlation."
    # Non-parametrized tests use manually written outcomes instead of name parsing.
    direct_explanation = _DIRECT_EXPLANATIONS.get(name.split("[", 1)[0])
    if direct_explanation:
        return direct_explanation
    if not isinstance(parameters, dict) or not parameters:
        return f"Checks {description} and verifies its documented result."
    return f"Checks {description} using the documented scenario for this case; technical values are recorded separately in inputs."


def _case_id(nodeid: str) -> str:
    """Read an explicit case ID or derive a stable ID from its test node."""
    match = re.search(r"(?:S[1-9]|R4|PE|AD|SQL|RUN)-[A-Za-z0-9_.-]+", nodeid)
    if match:
        return match.group(0)
    module = nodeid.split("::", 1)[0].rsplit("/", 1)[-1]
    name = nodeid.rsplit("::", 1)[-1].split("[", 1)[0]
    return f"AUTO.{module}.{name}"


def _test_command(testcase: ET.Element) -> str:
    """Produce a command that reruns the individual pytest case."""
    properties = {prop.attrib["name"]: prop.attrib.get("value", "")
                  for prop in testcase.findall("./properties/property")}
    nodeid = properties.get("nodeid")
    if not nodeid:
        module = testcase.attrib.get("file") or testcase.attrib.get("classname", "").replace(".", "/") + ".py"
        nodeid = f"{module}::{testcase.attrib.get('name', '')}"
    return f'python -m pytest "{nodeid.replace(chr(92), "/")}" -v'


def _test_rows(xml_path: Path, command: str, global_output: str, trace_path: Path) -> list[dict[str, str]]:
    """Merge JUnit outcomes, case properties, and captured runtime inputs."""
    traces = json.loads(trace_path.read_text(encoding="utf-8")) if trace_path.exists() else {}

    def trace_for(nodeid: str, classname: str, name: str) -> dict[str, object]:
        """Find captured inputs for a JUnit case, falling back by test name."""
        if nodeid in traces:
            return traces[nodeid]
        suffix = f"{classname}::{name}"
        for key, value in traces.items():
            if key.endswith(suffix) or key.rsplit("::", 1)[-1] == name:
                return value
        return {"locals": {}, "queries": []}
    if not xml_path.exists() or xml_path.stat().st_size == 0:
        return [{
            "id": "RUN-ERROR",
            "description": "pytest could not create a test report",
            "explanation": "The test runner could not produce a JUnit result file.",
            "command": command,
            "inputs": "runner: " + " ".join(global_output.split())[-1000:],
            "result": "error",
            "seconds": "",
        }]
    root = ET.parse(xml_path).getroot()
    rows: list[dict[str, str]] = []
    # Each JUnit testcase becomes one report row, including parametrized cases.
    for testcase in root.iter("testcase"):
        properties = {prop.attrib["name"]: prop.attrib.get("value", "")
                      for prop in testcase.findall("./properties/property")}
        nodeid = properties.get("nodeid") or f"{testcase.attrib.get('classname', '')}::{testcase.attrib.get('name', '')}".strip(":")
        trace = trace_for(nodeid, testcase.attrib.get("classname", ""), testcase.attrib.get("name", ""))
        case_id = properties.get("case_id", _case_id(nodeid))
        captured_case_id = trace.get("parameters", {}).get("case_id") or trace.get("locals", {}).get("case_id")
        if isinstance(captured_case_id, str):
            candidate = captured_case_id.strip("'\"")
            if candidate.startswith(("S1-", "S2-", "S3-", "R4-", "S5-", "S6-", "S7-", "S8-", "S9-", "PE-", "AD-", "RUN-")):
                case_id = candidate
        # Preserve the actual outcome instead of assuming a passing test.
        failure = testcase.find("failure")
        error = testcase.find("error")
        skipped = testcase.find("skipped")
        if failure is not None:
            status = "failed"
            output = failure.attrib.get("message", "") + " " + (failure.text or "")
        elif error is not None:
            status = "error"
            output = error.attrib.get("message", "") + " " + (error.text or "")
        elif skipped is not None:
            status = "skipped"
            output = skipped.attrib.get("message", "") or (skipped.text or "")
        else:
            status = "passed"
            output = "test completed successfully"
        if properties.get("inputs"):
            inputs = properties["inputs"]
        elif not any(trace.get(key) for key in ("parameters", "locals", "queries")):
            inputs = "no explicit runtime inputs"
        else:
            inputs = json.dumps(trace, ensure_ascii=False, separators=(",", ":"))
        if status == "passed" and properties.get("actual_output"):
            actual = json.loads(properties["actual_output"])
            output = "passed; " + "; ".join(f"{key.replace('_', ' ')}={value}" for key, value in actual.items())
        elif status == "passed":
            output = "passed"
        # Explicit workflow evidence takes precedence over generated wording.
        rows.append({
            "id": case_id,
            "description": properties.get("description") or _runtime_description(trace, nodeid, case_id),
            "explanation": properties.get("explanation") or _explanation(trace, nodeid, case_id),
            "command": _test_command(testcase),
            "inputs": inputs,
            "result": " ".join(output.split()),
            "seconds": testcase.attrib.get("time", ""),
        })
    return rows


def _prioritize_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Place the required workflow paths first while retaining all other cases."""
    ranks = {case_id: rank for rank, case_id in enumerate(PRIORITY_CASES)}
    # Preserve every executed variant, including cases sharing a requirement ID.
    return sorted(rows, key=lambda row: ranks.get(row["id"], len(ranks)))


def write_csv(rows: list[dict[str, str]], csv_path: Path) -> Path:
    """Reject empty or repeated explanations before writing the case report."""
    # Compare normalized wording so capitalization and spacing cannot hide repeats.
    explanations: set[str] = set()
    for row in rows:
        explanation = row["explanation"].strip()
        if not explanation:
            raise ValueError(f"Missing explanation for case {row['id']}")
        normalized = " ".join(explanation.split()).casefold()
        if normalized in explanations:
            raise ValueError(f"Duplicate explanation for case {row['id']}")
        explanations.add(normalized)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    columns = ("id", "description", "explanation", "inputs", "command", "result", "seconds")
    try:
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        return csv_path
    except PermissionError:
        # A spreadsheet may lock the original report; do not lose this run's data.
        fallback = csv_path.with_name(f"{csv_path.stem}_latest{csv_path.suffix}")
        with fallback.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        print(f"WARNING: CSV path is locked or read-only; wrote fallback report: {fallback}", file=sys.stderr)
        return fallback


def run_all_tests(arguments: list[str] | None = None) -> int:
    """Run the full suite, write its CSV, and enforce required coverage."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    options, extra = parser.parse_known_args(arguments or [])

    pytest_args = list(extra)
    os.environ["RUN_POSTGRES_INTEGRATION"] = "1"

    tests = discovered_tests()
    if not tests:
        print("No test files were discovered.", file=sys.stderr)
        return 1

    options.csv.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="sgfap-", suffix=".xml", delete=False) as temporary:
        junit_path = Path(temporary.name)
    trace_path = options.csv.with_suffix(".trace.json")
    os.environ["SGFAP_TRACE_FILE"] = str(trace_path)

    # Execute pytest once; its JUnit file and trace supply the report evidence.
    command = pytest_command(pytest_args, junit_path)
    command_text = "python tests/coverage.py"
    completed = subprocess.run(
        command,
        cwd=PROJECT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )
    print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")

    # Explain and save every executed variant, then inspect measured coverage.
    rows = _prioritize_rows(_test_rows(junit_path, command_text, completed.stdout + completed.stderr, trace_path))
    report_path = write_csv(rows, options.csv)
    print(f"CSV report: {report_path}")
    print(f"Cases reported: {len(rows)}")
    measurement_path = trace_path.with_name("workflow_coverage.json")
    coverage_missing = True
    if measurement_path.exists():
        measured = json.loads(measurement_path.read_text(encoding="utf-8"))
        print(f"workflow model coverage: {measured['executed_lines']}/{measured['measurable_lines']} lines "
              f"({measured['line_percent']}%); {measured['executed_branches']}/{measured['branches']} "
              f"if/while exits ({measured['branch_percent']}%)")
        print(f"workflow coverage report: {measurement_path}")
        coverage_missing = bool(measured["missing_lines"] or measured["missing_branches"])
        if coverage_missing:
            print(f"Missing workflow lines: {measured['missing_lines']}; branches: {measured['missing_branches']}", file=sys.stderr)
    # Passing pytest is insufficient if a required path or branch was missed.
    missing = set(WORKFLOW_CASE_IDS) - {row["id"] for row in rows}
    blocked = [row["id"] for row in rows
               if row["id"] in WORKFLOW_CASE_IDS and not row["result"].startswith("passed")]
    if missing:
        print("Missing required workflow cases: " + ", ".join(sorted(missing)), file=sys.stderr)
    if blocked:
        print("Unverified required workflow cases: " + ", ".join(blocked), file=sys.stderr)
    return 1 if completed.returncode or missing or blocked or coverage_missing else 0


if __name__ == "__main__":
    raise SystemExit(run_all_tests(sys.argv[1:]))
