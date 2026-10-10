"""The 56 ticket-workflow cases, with separate IDs for every AD variant."""

from dataclasses import dataclass
from datetime import datetime, timezone


CAPTURED_AT = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class WorkflowCase:
    case_id: str
    description: str
    explanation: str
    method: str
    expected: object
    calls: tuple[str, ...]
    fault: str | None = None
    rollback_fault: bool = False
    description_input: str = "Luz apagada"
    address_id: int | None = 11
    evidence_count: int = 0
    priority_row: tuple = ("Validated", 97, "High")
    closure_row: tuple = ("PendingClosure", "Fotocelda reemplazada")
    action: str = "Approval"
    count: int = 1
    graph_path: str = ""


REGISTER = ("insert_ticket", "fetch_id", "insert_history", "commit")
PRIORITIZE = ("select_priority", "fetch_priority", "update_priority", "insert_history", "commit")
CLOSE = ("select_closure", "fetch_closure", "count_evidence", "fetch_count", "update_status", "insert_history", "commit")
READ_PRIORITY = ("select_priority", "fetch_priority", "commit")
READ_CLOSURE = ("select_closure", "fetch_closure", "commit")


def failure_calls(calls, fault):
    return (*calls[:calls.index(fault) + 1], "rollback")


def case(number, title, explanation, method, expected, calls, **kwargs):
    return WorkflowCase(f"PE-{number:02d}", title, explanation, method, expected, tuple(calls), **kwargs)


PE_CASES = (
    case(1, "Register a ticket without photographs", "Creates ticket 101 and its Registration history, commits once, and sets the ticket ID only after confirmation.", "register", 101, REGISTER,
         graph_path="R1 R2 R4 R5 R6 R7 R8 R11 R12 R13 RX"),
    case(2, "Reject an empty report description", "An empty description returns None before any SQL, commit, or rollback; the ticket ID stays unset.", "register", None, (), description_input="",
         graph_path="R1 R2 R3 RX"),
    case(3, "Reject registration without an address", "With a meaningful description but no address, registration stops without contacting the database.", "register", None, (), address_id=None,
         graph_path="R1 R2 R4 R3 RX"),
    case(4, "Register a ticket with one photograph", "Inserts one photograph for ticket 101 and uploader 7, advances the loop from 0 to 1, and commits ticket, photograph, and history together.", "register", 101,
         ("insert_ticket", "fetch_id", "insert_evidence:0", "insert_history", "commit"), evidence_count=1,
         graph_path="R1 R2 R4 R5 R6 R7 R8 R9 R10 R8 R11 R12 R13 RX"),
    case(5, "Roll back when the ticket insert fails", "The ticket INSERT raises the injected error; rollback is attempted once, the same exception escapes, and no later SQL runs.", "register", "original_error", failure_calls(REGISTER, "insert_ticket"), fault="insert_ticket",
         graph_path="R1 R2 R4 R5 R14 R15 RX"),
    case(6, "Roll back when retrieving the new ticket ID fails", "fetchone fails after the ticket insert; no photographs or history are inserted, and rollback propagates the identical error.", "register", "original_error", failure_calls(REGISTER, "fetch_id"), fault="fetch_id",
         graph_path="R1 R2 R4 R5 R6 R14 R15 RX"),
    case(7, "Roll back when the photograph insert fails", "After recovering ID 101, the photograph insert fails; history and commit are skipped and the ticket ID remains unset.", "register", "original_error",
         ("insert_ticket", "fetch_id", "insert_evidence:0", "rollback"), evidence_count=1, fault="insert_evidence:0",
         graph_path="R1 R2 R4 R5 R6 R7 R8 R9 R14 R15 RX"),
    case(8, "Roll back registration when its history insert fails", "Ticket insertion succeeds but Registration history fails; one rollback runs, no commit occurs, and the original exception is preserved.", "register", "original_error", failure_calls(REGISTER, "insert_history"), fault="insert_history",
         graph_path="R1 R2 R4 R5 R6 R7 R8 R11 R14 R15 RX"),
    case(9, "Roll back registration when commit fails", "Commit is attempted once and fails before confirmation; rollback runs and self.id remains None.", "register", "original_error", failure_calls(REGISTER, "commit"), fault="commit",
         graph_path="R1 R2 R4 R5 R6 R7 R8 R11 R12 R14 R15 RX"),
    case(10, "Preserve both registration and rollback errors", "The ticket insert and rollback both fail; the rollback error escapes with the insert error as its exception context.", "register", "rollback_error", ("insert_ticket", "rollback"), fault="insert_ticket", rollback_fault=True,
         graph_path="R1 R2 R4 R5 R14 R16 RX"),
    case(11, "Prioritize a validated high-risk ticket", "Uses the queried priority ID 97 to update ticket 301, records Prioritization by user 7, commits, and returns High.", "prioritize", "High", PRIORITIZE,
         graph_path="P1 P2 P3 P4 P7 P8 P9 P10 PX"),
    case(12, "Leave an unvalidated ticket unchanged", "A Registered ticket ends with a read commit and returns None; neither priority nor history is written.", "prioritize", None, READ_PRIORITY, priority_row=("Registered", 98, "Standard"),
         graph_path="P1 P2 P3 P4 P5 P6 PX"),
    case(13, "Roll back a failed prioritization query", "The initial priority SELECT fails; rollback runs once and no fetch, update, history, or commit follows.", "prioritize", "original_error", failure_calls(PRIORITIZE, "select_priority"), fault="select_priority",
         graph_path="P1 P2 P11 P12 PX"),
    case(14, "Roll back a failed priority-row retrieval", "The SELECT succeeds but fetchone fails; the same error is propagated after rollback without writes.", "prioritize", "original_error", failure_calls(PRIORITIZE, "fetch_priority"), fault="fetch_priority",
         graph_path="P1 P2 P3 P11 P12 PX"),
    case(15, "Handle failure finishing the unvalidated-ticket read", "On a Registered ticket the read commit fails; exactly one commit and one rollback are attempted and the original error escapes.", "prioritize", "original_error", failure_calls(READ_PRIORITY, "commit"), fault="commit", priority_row=("Registered", 98, "Standard"),
         graph_path="P1 P2 P3 P4 P5 P11 P12 PX"),
    case(16, "Roll back when the priority update fails", "A valid priority query is followed by a failed UPDATE; no history or commit follows and rollback preserves the failure.", "prioritize", "original_error", failure_calls(PRIORITIZE, "update_priority"), fault="update_priority",
         graph_path="P1 P2 P3 P4 P7 P11 P12 PX"),
    case(17, "Roll back a priority change without history", "The priority UPDATE succeeds but its history INSERT fails; the operation rolls back instead of returning High.", "prioritize", "original_error", failure_calls(PRIORITIZE, "insert_history"), fault="insert_history",
         graph_path="P1 P2 P3 P4 P7 P8 P11 P12 PX"),
    case(18, "Roll back a failed prioritization commit", "After update and history, commit fails before taking effect; one rollback occurs and no success result is returned.", "prioritize", "original_error", failure_calls(PRIORITIZE, "commit"), fault="commit",
         graph_path="P1 P2 P3 P4 P7 P8 P9 P11 P12 PX"),
    case(19, "Preserve prioritization and rollback errors", "The initial priority query and rollback fail; the rollback error retains the original query failure as its cause.", "prioritize", "rollback_error", ("select_priority", "rollback"), fault="select_priority", rollback_fault=True,
         graph_path="P1 P2 P11 P13 PX"),
    case(20, "Approve closure with a solution and photograph", "Counts photographs only for ticket 301, updates it to Resolved, records Approval by user 7, and commits once.", "review_closure", "Resolved", CLOSE,
         graph_path="C1 C2 C3 C4 C7 C8 C10 C13 C14 C15 C18 C20 C21 C22 C23 CX"),
    case(21, "Keep a ticket outside PendingClosure unchanged", "An InProgress ticket returns InProgress after a read commit without counting photographs or writing anything.", "review_closure", "InProgress", READ_CLOSURE, closure_row=("InProgress", "Trabajo en curso"),
         graph_path="C1 C2 C3 C4 C5 C6 CX"),
    case(22, "Return a rejected closure to InProgress", "Rejection changes ticket 301 to InProgress and records Rejection without executing the photograph-count query.", "review_closure", "InProgress", ("select_closure", "fetch_closure", "update_status", "insert_history", "commit"), action="Rejection",
         graph_path="C1 C2 C3 C4 C7 C19 C20 C21 C22 C23 CX"),
    case(23, "Keep closure pending when the solution is empty", "An empty solution causes a read commit and returns PendingClosure; no photograph count, update, or history is attempted.", "review_closure", "PendingClosure", READ_CLOSURE, closure_row=("PendingClosure", ""),
         graph_path="C1 C2 C3 C4 C7 C8 C10 C11 C12 CX"),
    case(24, "Normalize a missing solution before reviewing closure", "A None solution becomes an empty string and returns PendingClosure after a read commit without writes.", "review_closure", "PendingClosure", READ_CLOSURE, closure_row=("PendingClosure", None),
         graph_path="C1 C2 C3 C4 C7 C8 C9 C10 C11 C12 CX"),
    case(25, "Keep closure pending when no photograph exists", "A valid solution with a count of zero returns PendingClosure after a read commit without update or history.", "review_closure", "PendingClosure", ("select_closure", "fetch_closure", "count_evidence", "fetch_count", "commit"), count=0,
         graph_path="C1 C2 C3 C4 C7 C8 C10 C13 C14 C15 C16 C17 CX"),
    case(26, "Roll back a failed closure-state query", "The initial closure SELECT fails; one rollback occurs with no fetch, count, or writes.", "review_closure", "original_error", failure_calls(CLOSE, "select_closure"), fault="select_closure",
         graph_path="C1 C2 C24 C25 CX"),
    case(27, "Roll back a failed closure-row retrieval", "fetchone fails after the closure SELECT; the identical exception escapes after rollback and no later SQL executes.", "review_closure", "original_error", failure_calls(CLOSE, "fetch_closure"), fault="fetch_closure",
         graph_path="C1 C2 C3 C24 C25 CX"),
    case(28, "Handle a failed read commit for an incompatible closure state", "An InProgress ticket's read commit fails; one commit and one rollback are attempted without writes.", "review_closure", "original_error", failure_calls(READ_CLOSURE, "commit"), fault="commit", closure_row=("InProgress", "Trabajo en curso"),
         graph_path="C1 C2 C3 C4 C5 C24 C25 CX"),
    case(29, "Handle a failed read commit for an empty solution", "The empty-solution guard attempts a read commit; its error escapes after rollback without a count or writes.", "review_closure", "original_error", failure_calls(READ_CLOSURE, "commit"), fault="commit", closure_row=("PendingClosure", ""),
         graph_path="C1 C2 C3 C4 C7 C8 C10 C11 C24 C25 CX"),
    case(30, "Roll back when counting photographs fails", "A meaningful solution reaches the ticket-specific COUNT, which fails; no state update or history follows.", "review_closure", "original_error", failure_calls(CLOSE, "count_evidence"), fault="count_evidence",
         graph_path="C1 C2 C3 C4 C7 C8 C10 C13 C24 C25 CX"),
    case(31, "Roll back when retrieving the photograph count fails", "The COUNT succeeds but fetchone fails; closure is not approved and rollback propagates the same exception.", "review_closure", "original_error", failure_calls(CLOSE, "fetch_count"), fault="fetch_count",
         graph_path="C1 C2 C3 C4 C7 C8 C10 C13 C14 C24 C25 CX"),
    case(32, "Handle a failed read commit when no photograph exists", "A count of zero reaches the read commit, which fails; rollback occurs without a ticket update or history.", "review_closure", "original_error", ("select_closure", "fetch_closure", "count_evidence", "fetch_count", "commit", "rollback"), fault="commit", count=0,
         graph_path="C1 C2 C3 C4 C7 C8 C10 C13 C14 C15 C16 C24 C25 CX"),
    case(33, "Roll back a failed closure-state update", "After valid solution and evidence checks, the UPDATE fails; Approval history and commit are skipped.", "review_closure", "original_error", failure_calls(CLOSE, "update_status"), fault="update_status",
         graph_path="C1 C2 C3 C4 C7 C8 C10 C13 C14 C15 C18 C20 C24 C25 CX"),
    case(34, "Roll back closure when Approval history fails", "The state UPDATE succeeds but Approval history fails; rollback prevents an apparent successful closure.", "review_closure", "original_error", failure_calls(CLOSE, "insert_history"), fault="insert_history",
         graph_path="C1 C2 C3 C4 C7 C8 C10 C13 C14 C15 C18 C20 C21 C24 C25 CX"),
    case(35, "Roll back when the closure commit fails", "State and history writes are followed by a failed commit; one rollback runs and Resolved is never returned.", "review_closure", "original_error", failure_calls(CLOSE, "commit"), fault="commit",
         graph_path="C1 C2 C3 C4 C7 C8 C10 C13 C14 C15 C18 C20 C21 C22 C24 C25 CX"),
    case(36, "Preserve closure-query and rollback errors", "Both the initial closure query and rollback fail; the rollback exception escapes with the original query failure as context.", "review_closure", "rollback_error", ("select_closure", "rollback"), fault="select_closure", rollback_fault=True,
         graph_path="C1 C2 C24 C26 CX"),
)


AD_CASES = (
    WorkflowCase("AD-01.SPACES", "Reject a report containing only spaces", "A single space is stripped to an empty description and no database call occurs.", "register", None, (), description_input=" "),
    WorkflowCase("AD-01.TABS_NEWLINES", "Reject a report containing only tabs and newlines", "Tab and newline characters are stripped before checking the description; no SQL or transaction call occurs.", "register", None, (), description_input="\t\n"),
    WorkflowCase("AD-01.TEXT", "Accept a report description containing meaningful text", "Luz apagada passes the first guard, reaches the address guard, and creates the ticket with its history.", "register", 101, REGISTER),
    WorkflowCase("AD-02.THREE_EVIDENCES", "Insert three different photographs exactly once", "The evidence loop advances 0, 1, 2, 3, performs five INSERTs, and commits once after all related rows.", "register", 101, ("insert_ticket", "fetch_id", "insert_evidence:0", "insert_evidence:1", "insert_evidence:2", "insert_history", "commit"), evidence_count=3),
    WorkflowCase("AD-02.SECOND_INSERT_FAILS", "Stop registration at the second failed photograph", "The second photograph fails; the third, history, and commit are skipped, rollback runs, and the ticket ID stays unset.", "register", "original_error", ("insert_ticket", "fetch_id", "insert_evidence:0", "insert_evidence:1", "rollback"), evidence_count=3, fault="insert_evidence:1"),
    *(WorkflowCase(f"AD-03.{name.upper().replace(' ', '_')}", f"Prioritize the catalog failure {name}", f"The actual catalog assigns {name} to {priority}; the UPDATE uses the queried priority ID and returns {priority}.", "prioritize", priority, PRIORITIZE, priority_row=("Validated", 97 if priority == "High" else 98, priority))
      for name, priority in (("Exposed cable", "High"), ("Pole fall risk", "High"), ("Box without cover", "High"), ("Light out", "Standard"), ("Intermittent", "Standard"), ("Tree Branches", "High"))),
    WorkflowCase("AD-04.SPACES", "Keep closure pending for a spaces-only solution", "A solution containing one space is insufficient; the read is committed and no evidence count or writes occur.", "review_closure", "PendingClosure", READ_CLOSURE, closure_row=("PendingClosure", " ")),
    WorkflowCase("AD-04.TEXT_NO_EVIDENCE", "Keep closure pending for a solution without photographs", "A meaningful solution and zero matching photographs return PendingClosure without state or history writes.", "review_closure", "PendingClosure", ("select_closure", "fetch_closure", "count_evidence", "fetch_count", "commit"), count=0),
    WorkflowCase("AD-04.TEXT_WITH_EVIDENCE", "Resolve a ticket with a solution and its photograph", "A meaningful solution and one matching photograph permit Resolved, Approval history, and one commit.", "review_closure", "Resolved", CLOSE),
    WorkflowCase("AD-05.OTHER_TICKET", "Exclude another ticket's photograph from closure", "A real PostgreSQL photograph belongs only to a different ticket; the reviewed ticket's count remains zero and closure stays pending.", "review_closure", "PendingClosure", ("select_closure", "fetch_closure", "count_evidence", "fetch_count", "commit"), count=0),
)

SQL_CASES = (
    WorkflowCase("SQL-01", "Insert a ticket code with exactly 24 characters", "PostgreSQL accepts a 24-character code while every required reference remains valid.", "sql", "inserted", ()),
    WorkflowCase("SQL-02", "Reject a ticket code with 25 characters", "The real VARCHAR(24) column rejects 25 characters; no ticket is inserted and the error means invalid input.", "sql", "VAL-002", ()),
    WorkflowCase("SQL-03", "Reject a duplicate ticket code", "PostgreSQL rejects the second identical code; the original row survives and the repository reports a uniqueness conflict.", "sql", "CON-001", ()),
    WorkflowCase("SQL-04", "Reject a duplicate photograph path", "The real unique constraint rejects a reused file path, even on a different ticket, while the original photograph remains.", "sql", "CON-001", ()),
    WorkflowCase("SQL-05", "Revert ticket, photographs, and history after a failed write", "A failure after inserting ticket, photograph, and history causes rollback; a separate connection sees none of those rows.", "sql", "no partial rows", ()),
)

WORKFLOW_CASES = (*PE_CASES, *AD_CASES, *SQL_CASES)
WORKFLOW_CASE_IDS = tuple(item.case_id for item in WORKFLOW_CASES)
assert len(WORKFLOW_CASE_IDS) == len(set(WORKFLOW_CASE_IDS)) == 56
