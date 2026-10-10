"""All 56 ticket-workflow cases, with their exact expectations.

PE cases exercise the reference graphs with controlled cursor failures.
AD cases include every individual variant. SQL cases use real PostgreSQL.
The PostgreSQL fixture is required for this entire file; failures are not skipped.
"""

if __name__ == "__main__":
    # Direct execution hands this file to pytest so its database fixture runs.
    import sys
    from pathlib import Path
    import pytest

    project_root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pytest.ini").is_file())
    sys.path.insert(0, str(project_root))
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))

from dataclasses import asdict, replace
import json
import sys
from unittest.mock import Mock

import psycopg
import pytest

from api.contracts import EvidenceCreateInput, TicketCreateInput
from api.errors import ApplicationError, ErrorHandler, PersistenceContext
from api.repositories import EvidenceRepository, TicketRepository
from tests.ticket_workflow.inventory import AD_CASES, CAPTURED_AT, PE_CASES, SQL_CASES
from tests.ticket_workflow.model import ReferenceTicket


pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("workflow_database")]


def report(record_property, case, inputs, output):
    """Attach the case, observed inputs, and outcome to the accumulated report."""
    for name, value in {
        "case_id": case.case_id,
        "description": case.description,
        "explanation": case.explanation,
        "inputs": json.dumps(inputs, ensure_ascii=False, default=str),
        "actual_output": json.dumps(output, ensure_ascii=False, default=str),
        "requirement": {"register": "HU-001", "prioritize": "HU-005",
                        "review_closure": "HU-010", "sql": "SQL constraints and atomicity"}[case.method],
    }.items():
        record_property(name, value)


class ReferenceHarness:
    """Fail exactly the call named by a case and keep the attempted call order."""

    def __init__(self, case):
        """Prepare a model, fake connection, and exact failure point for one case."""
        self.case = case
        self.calls = []
        self.sql_calls = []
        self.loop_values = []
        self.original_error = RuntimeError("injected failure at " + str(case.fault))
        self.rollback_error = RuntimeError("injected rollback failure")
        self.cursor = Mock(spec=["execute", "fetchone"])
        self.connection = Mock(spec=["commit", "rollback"])
        self.cursor.execute.side_effect = self.execute
        self.cursor.fetchone.side_effect = self.fetchone
        self.connection.commit.side_effect = self.commit
        self.connection.rollback.side_effect = self.rollback
        self.pending_fetch = None
        self.evidence_index = 0
        self.confirmed = False
        self.model = ReferenceTicket(
            self.connection, self.cursor,
            id=None if case.method == "register" else 301,
            description=case.description_input, address_id=case.address_id,
            evidences=[{"file_path": f"workflow/photo-{index + 1}.jpg", "captured_at": CAPTURED_AT} for index in range(case.evidence_count)],
        )

    def attempt(self, name):
        """Record an operation and raise only at the selected failure point."""
        self.calls.append(name)
        if name == self.case.fault:
            raise self.original_error

    def execute(self, query, params):
        """Translate each model query into an operation that the case can verify."""
        normalized = " ".join(query.split())
        self.sql_calls.append({"query": normalized, "parameters": list(params)})
        if normalized.startswith("INSERT INTO tickets"):
            name, self.pending_fetch = "insert_ticket", "fetch_id"
        elif normalized.startswith("INSERT INTO evidences"):
            name = f"insert_evidence:{self.evidence_index}"
            self.evidence_index += 1
        elif normalized.startswith("INSERT INTO history_events"):
            name = "insert_history"
        elif normalized.startswith("SELECT COUNT(*)"):
            name, self.pending_fetch = "count_evidence", "fetch_count"
        elif normalized.startswith("SELECT s.name, p.id, p.name"):
            name, self.pending_fetch = "select_priority", "fetch_priority"
        elif normalized.startswith("SELECT s.name, t.solution"):
            name, self.pending_fetch = "select_closure", "fetch_closure"
        elif normalized.startswith("UPDATE tickets SET priority_id"):
            name = "update_priority"
        else:
            assert normalized.startswith("UPDATE tickets SET status_id")
            name = "update_status"
        self.attempt(name)

    def fetchone(self):
        """Return the case's selected database row unless this fetch must fail."""
        self.attempt(self.pending_fetch)
        return {"fetch_id": (101,), "fetch_priority": self.case.priority_row,
                "fetch_closure": self.case.closure_row, "fetch_count": (self.case.count,)}[self.pending_fetch]

    def commit(self):
        """Record a commit and ensure registration IDs appear only afterward."""
        if self.case.method == "register":
            assert self.model.id is None, "ID assigned before successful commit"
        self.attempt("commit")
        self.confirmed = True

    def rollback(self):
        """Record a rollback and optionally trigger a second failure."""
        self.calls.append("rollback")
        if self.case.rollback_fault:
            raise self.rollback_error

    def invoke(self):
        """Run the selected workflow method while observing its evidence loop."""
        previous = sys.gettrace()

        def observe(frame, event, arg):
            """Track loop positions while preserving any existing trace hook."""
            if previous is not None:
                previous(frame, event, arg)
            if frame.f_code is ReferenceTicket.register.__code__ and event == "line" and "i" in frame.f_locals:
                value = frame.f_locals["i"]
                if not self.loop_values or self.loop_values[-1] != value:
                    self.loop_values.append(value)
            return observe

        sys.settrace(observe)
        try:
            if self.case.method == "review_closure":
                return self.model.review_closure(7, self.case.action)
            return getattr(self.model, self.case.method)(7)
        finally:
            sys.settrace(previous)


def assert_sql_parameters(harness):
    """Independent expected arguments, including fixture IDs 101, 301 and 7."""
    case = harness.case
    for operation, sql_call in zip((name for name in harness.calls if name.startswith(("insert_", "select_", "update_", "count_"))), harness.sql_calls, strict=True):
        query = sql_call["query"]
        actual = sql_call["parameters"]
        if operation == "insert_ticket":
            expected = ["TEST-REGISTER-001", 7, 4, case.description_input, case.address_id, "Registered"]
            assert "SELECT id FROM statuses WHERE name = %s" in query
        elif operation.startswith("insert_evidence:"):
            index = int(operation.split(":")[1])
            expected = [101, f"workflow/photo-{index + 1}.jpg", CAPTURED_AT, 7]
        elif operation == "insert_history":
            action = {"register": "Registration", "prioritize": "Prioritization", "review_closure": case.action}[case.method]
            expected = [101 if case.method == "register" else 301, 7, action]
            assert "SELECT id FROM actions WHERE name = %s" in query
        elif operation == "update_priority":
            expected = [case.priority_row[1], "Prioritized", 301]
        elif operation == "update_status":
            expected = ["Resolved" if case.action == "Approval" else "InProgress", 301]
        else:
            expected = [301]
            assert "WHERE" in query and "= %s" in query
            if operation == "count_evidence":
                assert query == "SELECT COUNT(*) FROM evidences WHERE ticket_id = %s"
        assert actual == expected, (case.case_id, operation, actual, expected)


def run_reference_case(case, record_property):
    """Execute one workflow path, compare its steps, and publish its evidence."""
    # Prepare a fresh model and injected database behavior for this case only.
    harness = ReferenceHarness(case)
    output = {}
    try:
        # Check either the expected exception path or the successful return value.
        if case.fault:
            with pytest.raises(RuntimeError) as raised:
                harness.invoke()
            expected_error = harness.rollback_error if case.rollback_fault else harness.original_error
            assert raised.value is expected_error
            if case.rollback_fault:
                assert raised.value.__context__ is harness.original_error
            output["exception"] = "rollback_error" if case.rollback_fault else "same original_error instance"
            output["original_error_retained_as_context"] = case.rollback_fault
            assert harness.confirmed is False
        else:
            returned = harness.invoke()
            assert returned == case.expected
            output["returned"] = returned
        # Match every observed database call, transaction attempt, and SQL argument.
        assert tuple(harness.calls) == case.calls
        assert harness.connection.commit.call_count == case.calls.count("commit")
        assert harness.connection.rollback.call_count == case.calls.count("rollback")
        assert_sql_parameters(harness)
        # Registration may assign an ID only after a confirmed commit.
        if case.method == "register":
            assert harness.model.id == (101 if harness.confirmed else None)
            if harness.confirmed:
                assert harness.cursor.execute.call_count == case.evidence_count + 2
                assert harness.loop_values == list(range(case.evidence_count + 1))
            if case.fault == "insert_evidence:1":
                assert harness.loop_values == [0, 1]
        output.update({"commit_attempts": harness.connection.commit.call_count,
                       "rollback_attempts": harness.connection.rollback.call_count,
                       "ticket_id_after_operation": harness.model.id,
                       "calls": harness.calls, "loop_i": harness.loop_values})
    finally:
        # Keep the input and outcome evidence even when the tested path raises.
        report(record_property, case,
               {"preparation": "F-R" if case.method == "register" else "F-P" if case.method == "prioritize" else "F-C",
                "scope": "workflow reference model with exact injected cursor failures; PostgreSQL fixture connected",
                "user_id": 7, "initial_ticket_id": None if case.method == "register" else 301,
                "code": harness.model.code, "description": case.description_input,
                "address_id": case.address_id, "failure_type_id": 4,
                "evidences": harness.model.evidences, "priority_query_row": case.priority_row,
                "closure_query_row": case.closure_row, "action": case.action, "evidence_count": case.count,
                "failure_at": case.fault, "rollback_failure": case.rollback_fault,
                "sql": harness.sql_calls, "expected_graph_path": case.graph_path,
                "expected_return_or_exception": case.expected, "expected_calls": case.calls}, output)


@pytest.mark.parametrize("case", PE_CASES, ids=[case.case_id for case in PE_CASES])
def test_independent_path(case, record_property):
    """Run each independently identified registration, priority, or closure path."""
    run_reference_case(case, record_property)


@pytest.mark.parametrize("case", AD_CASES[:-1], ids=[case.case_id for case in AD_CASES[:-1]])
def test_additional_variant(case, record_property, workflow_database):
    """Run extra input variants, using real catalogue IDs when prioritizing."""
    # Priority variants take their IDs from the database fixture, not hard-coded rows.
    if case.case_id.startswith("AD-03."):
        failure_name = case.description.removeprefix("Prioritize the catalog failure ")
        _, priority_id, priority = workflow_database.failures[failure_name]
        assert priority == case.expected
        case = replace(case, priority_row=("Validated", priority_id, priority))
    run_reference_case(case, record_property)


def insert_ticket(cursor, database, code, *, status="Registered", solution=None):
    """Insert one ticket and return its ID plus the values sent to PostgreSQL."""
    parameters = (code, database.user_id, database.failures["Light out"][0], "Luz apagada",
                  database.address_id, database.statuses[status], solution)
    cursor.execute("""INSERT INTO tickets
        (code, reported_by, failure_type_id, description, address_id, status_id, solution)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""", parameters)
    return cursor.fetchone()[0], parameters


def test_other_ticket_evidence_does_not_allow_closure(workflow_database, record_property):
    """Keep a reviewed ticket open when only a different ticket has a photo."""
    case = AD_CASES[-1]
    with workflow_database.connection() as connection:
        with connection.cursor() as cursor:
            reviewed, reviewed_inputs = insert_ticket(cursor, workflow_database, "TEST-OTHER-REVIEWED", status="PendingClosure", solution="Fotocelda reemplazada")
            other, other_inputs = insert_ticket(cursor, workflow_database, "TEST-OTHER-PHOTO")
            cursor.execute("INSERT INTO evidences (ticket_id, file_path, captured_at, uploaded_by) VALUES (%s, %s, %s, %s)",
                           (other, "workflow/other-ticket.jpg", CAPTURED_AT, workflow_database.user_id))
            connection.commit()
            model = ReferenceTicket(connection, cursor, id=reviewed)
            # Attempt approval, then compare evidence and history on both tickets.
            result = model.review_closure(workflow_database.user_id, "Approval")
            assert result == "PendingClosure"
            cursor.execute("SELECT COUNT(*) FROM evidences WHERE ticket_id = %s", (reviewed,))
            assert cursor.fetchone() == (0,)
            cursor.execute("SELECT COUNT(*) FROM evidences WHERE ticket_id = %s", (other,))
            assert cursor.fetchone() == (1,)
            cursor.execute("SELECT COUNT(*) FROM history_events WHERE ticket_id = %s", (reviewed,))
            assert cursor.fetchone() == (0,)
        report(record_property, case,
               {"reviewed_ticket": reviewed_inputs, "other_ticket": other_inputs,
                "evidence": [other, "workflow/other-ticket.jpg", CAPTURED_AT, workflow_database.user_id],
                "count_query": "SELECT COUNT(*) FROM evidences WHERE ticket_id = %s", "count_parameters": [reviewed]},
               {"returned": result, "reviewed_ticket_photos": 0, "other_ticket_photos": 1, "history_rows": 0})


def test_sql_accepts_24_character_code(workflow_database, record_property):
    """Save and read back a ticket code exactly at the allowed length."""
    case = SQL_CASES[0]
    code = "A" * 24
    with workflow_database.connection() as connection:
        with connection.cursor() as cursor:
            identifier, parameters = insert_ticket(cursor, workflow_database, code)
            cursor.execute("SELECT code FROM tickets WHERE id = %s", (identifier,))
            assert cursor.fetchone() == (code,)
        report(record_property, case, {"insert_parameters": parameters, "code_length": 24}, {"inserted": True, "ticket_id": identifier, "stored_code": code})


def test_sql_rejects_25_character_code(workflow_database, record_property):
    """Reject an overlong code and confirm no ticket row remains."""
    case = SQL_CASES[1]
    code = "B" * 25
    with workflow_database.connection() as connection:
        with connection.cursor() as cursor:
            with pytest.raises(psycopg.errors.StringDataRightTruncation) as raised:
                insert_ticket(cursor, workflow_database, code)
            # Classify the database rejection, undo the write, and verify absence.
            error = ErrorHandler.classify_exception(raised.value, persistence_context=PersistenceContext("tickets.create", "ticket", input_origin=True))
            assert error.code.value == "VAL-002"
            connection.rollback()
            cursor.execute("SELECT COUNT(*) FROM tickets WHERE code = %s", (code,))
            assert cursor.fetchone() == (0,)
        report(record_property, case, {"code": code, "code_length": 25, "reported_by": 7, "failure_type_id": workflow_database.failures["Light out"][0], "description": "Luz apagada", "address_id": 11, "status_id": workflow_database.statuses["Registered"], "solution": None}, {"error": error.code.value, "inserted_rows": 0})


def test_sql_rejects_duplicate_ticket_code(workflow_database, record_property):
    """Reject a repeated ticket code while preserving the original ticket."""
    case = SQL_CASES[2]
    data = TicketCreateInput("TEST-DUPLICATE-CODE", 7, workflow_database.failures["Light out"][0], "Luz apagada", 11)
    with workflow_database.connection() as connection:
        repository = TicketRepository(connection)
        first = repository.create(data)
        connection.commit()
        with pytest.raises(ApplicationError) as raised:
            repository.create(data)
        assert raised.value.code.value == "CON-001"
        assert isinstance(raised.value.cause, psycopg.errors.UniqueViolation)
        connection.rollback()
        assert repository.get_by_code(data.code).id == first.id
        report(record_property, case, {"first_insert": asdict(data), "second_insert": asdict(data)}, {"error": raised.value.code.value, "original_ticket_id": first.id, "original_row_preserved": True})


def test_sql_rejects_duplicate_evidence_path(workflow_database, record_property):
    """Reject a repeated photograph path without attaching it to another ticket."""
    case = SQL_CASES[3]
    with workflow_database.connection() as connection:
        with connection.cursor() as cursor:
            first_ticket, first_inputs = insert_ticket(cursor, workflow_database, "TEST-PATH-FIRST")
            second_ticket, second_inputs = insert_ticket(cursor, workflow_database, "TEST-PATH-SECOND")
        repository = EvidenceRepository(connection)
        first_data = EvidenceCreateInput(first_ticket, "workflow/duplicate-path.jpg", CAPTURED_AT, 7)
        second_data = EvidenceCreateInput(second_ticket, first_data.file_path, CAPTURED_AT, 7)
        first = repository.create(first_data)
        connection.commit()
        with pytest.raises(ApplicationError) as raised:
            repository.create(second_data)
        assert raised.value.code.value == "CON-001"
        assert isinstance(raised.value.cause, psycopg.errors.UniqueViolation)
        connection.rollback()
        assert repository.list_by_ticket(second_ticket) == []
        assert repository.get_by_id(first.id).file_path == first_data.file_path
        report(record_property, case, {"first_ticket": first_inputs, "second_ticket": second_inputs, "first_evidence": asdict(first_data), "second_evidence": asdict(second_data)}, {"error": raised.value.code.value, "original_evidence_id": first.id, "second_ticket_evidences": 0})


def test_sql_rollback_leaves_no_partial_rows(workflow_database, record_property):
    """Roll back ticket, evidence, and history writes after a later conflict."""
    # Create all three kinds of rows before forcing a duplicate-path failure.
    case = SQL_CASES[4]
    code, path = "TEST-ROLLBACK-ALL", "workflow/rollback-all.jpg"
    with workflow_database.connection() as connection:
        with connection.cursor() as cursor:
            identifier, parameters = insert_ticket(cursor, workflow_database, code)
            cursor.execute("INSERT INTO evidences (ticket_id, file_path, captured_at, uploaded_by) VALUES (%s, %s, %s, %s)", (identifier, path, CAPTURED_AT, 7))
            cursor.execute("""INSERT INTO history_events (ticket_id, user_id, action_id)
                VALUES (%s, %s, (SELECT id FROM actions WHERE name = %s))""", (identifier, 7, "Registration"))
            with pytest.raises(psycopg.errors.UniqueViolation):
                cursor.execute("INSERT INTO evidences (ticket_id, file_path, captured_at, uploaded_by) VALUES (%s, %s, %s, %s)", (identifier, path, CAPTURED_AT, 7))
            connection.rollback()
        # Verify rollback from a different connection, rather than local mocks.
        with workflow_database.connection() as observer:
            with observer.cursor() as cursor:
                for table in ("tickets", "evidences", "history_events"):
                    column = "id" if table == "tickets" else "ticket_id"
                    cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = %s", (identifier,))
                    assert cursor.fetchone() == (0,), table
        report(record_property, case, {"ticket_parameters": parameters, "evidence_parameters": [identifier, path, CAPTURED_AT, 7], "history_parameters": [identifier, 7, "Registration"], "fault": "duplicate photograph path after all three table writes"}, {"rollback": True, "tickets": 0, "evidences": 0, "history_events": 0, "verified_by_separate_connection": True})
