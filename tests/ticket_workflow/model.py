"""Executable reference model for the R/P/C ticket-processing graphs.

The English method names correspond to registrar, priorizar and revisar_cierre.
The model covers registration, prioritization and closure-review transactions.
"""

from dataclasses import dataclass, field
from typing import Any


INSERT_TICKET = """INSERT INTO tickets
    (code, reported_by, failure_type_id, description, address_id, status_id)
    VALUES (%s, %s, %s, %s, %s,
        (SELECT id FROM statuses WHERE name = %s)) RETURNING id"""
INSERT_EVIDENCE = """INSERT INTO evidences
    (ticket_id, file_path, captured_at, uploaded_by) VALUES (%s, %s, %s, %s)"""
INSERT_HISTORY = """INSERT INTO history_events (ticket_id, user_id, action_id)
    VALUES (%s, %s, (SELECT id FROM actions WHERE name = %s))"""
SELECT_PRIORITY = """SELECT s.name, p.id, p.name FROM tickets t
    JOIN statuses s ON s.id = t.status_id
    JOIN failure_types f ON f.id = t.failure_type_id
    JOIN priorities p ON p.id = f.priority_id WHERE t.id = %s"""
UPDATE_PRIORITY = """UPDATE tickets SET priority_id = %s,
    status_id = (SELECT id FROM statuses WHERE name = %s) WHERE id = %s"""
SELECT_CLOSURE = """SELECT s.name, t.solution FROM tickets t
    JOIN statuses s ON s.id = t.status_id WHERE t.id = %s"""
COUNT_EVIDENCES = "SELECT COUNT(*) FROM evidences WHERE ticket_id = %s"
UPDATE_STATUS = """UPDATE tickets SET
    status_id = (SELECT id FROM statuses WHERE name = %s) WHERE id = %s"""


@dataclass
class ReferenceTicket:
    connection: Any
    cursor: Any
    id: int | None = None
    code: str = "TEST-REGISTER-001"
    description: str = "Luz apagada"
    address_id: int | None = 11
    failure_type_id: int = 4
    evidences: list[dict[str, Any]] = field(default_factory=list)

    def register(self, user_id: int) -> int | None:
        if self.description.strip() == "":  # R2
            return None  # R3
        if self.address_id is None:  # R4
            return None  # R3
        try:
            self.cursor.execute(INSERT_TICKET, (self.code, user_id,
                self.failure_type_id, self.description, self.address_id, "Registered"))  # R5
            ticket_id = self.cursor.fetchone()[0]  # R6
            i = 0  # R7
            while i < len(self.evidences):  # R8
                evidence = self.evidences[i]
                self.cursor.execute(INSERT_EVIDENCE, (ticket_id, evidence["file_path"],
                    evidence["captured_at"], user_id))  # R9
                i += 1  # R10
            self.cursor.execute(INSERT_HISTORY, (ticket_id, user_id, "Registration"))  # R11
            self.connection.commit()  # R12
            self.id = ticket_id  # R13: never assigned before successful commit
            return ticket_id
        except Exception:  # R14
            self.connection.rollback()
            raise  # R15; a rollback exception propagates with original context (R16)

    def prioritize(self, user_id: int) -> str | None:
        try:
            self.cursor.execute(SELECT_PRIORITY, (self.id,))  # P2
            status, priority_id, priority = self.cursor.fetchone()  # P3
            if status != "Validated":  # P4
                self.connection.commit()  # P5
                return None  # P6
            self.cursor.execute(UPDATE_PRIORITY, (priority_id, "Prioritized", self.id))  # P7
            self.cursor.execute(INSERT_HISTORY, (self.id, user_id, "Prioritization"))  # P8
            self.connection.commit()  # P9
            return priority  # P10
        except Exception:  # P11
            self.connection.rollback()
            raise  # P12/P13

    def review_closure(self, user_id: int, action: str) -> str:
        try:
            self.cursor.execute(SELECT_CLOSURE, (self.id,))  # C2
            status, solution = self.cursor.fetchone()  # C3
            if status != "PendingClosure":  # C4
                self.connection.commit()  # C5
                return status  # C6
            if action == "Approval":  # C7
                if solution is None:  # C8
                    solution = ""  # C9
                if solution.strip() == "":  # C10
                    self.connection.commit()  # C11
                    return "PendingClosure"  # C12
                self.cursor.execute(COUNT_EVIDENCES, (self.id,))  # C13
                quantity = self.cursor.fetchone()[0]  # C14
                if quantity == 0:  # C15
                    self.connection.commit()  # C16
                    return "PendingClosure"  # C17
                destination = "Resolved"  # C18
            else:
                destination = "InProgress"  # C19; prepared domain: Rejection
            self.cursor.execute(UPDATE_STATUS, (destination, self.id))  # C20
            self.cursor.execute(INSERT_HISTORY, (self.id, user_id, action))  # C21
            self.connection.commit()  # C22
            return destination  # C23
        except Exception:  # C24
            self.connection.rollback()
            raise  # C25/C26
