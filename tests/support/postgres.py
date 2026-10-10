"""Isolated PostgreSQL fixture for the connected ticket-workflow suite."""

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from api.config import PostgresConnectionProvider, load_database_config


@dataclass
class WorkflowDatabase:
    provider: PostgresConnectionProvider
    schema: str
    user_id: int
    address_id: int
    statuses: dict[str, int]
    failures: dict[str, tuple[int, int, str]]

    @contextmanager
    def connection(self):
        with self.provider.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(self.schema)))
            connection.commit()
            try:
                yield connection
            finally:
                connection.rollback()


@pytest.fixture(scope="session")
def workflow_database():
    config = load_database_config()
    provider = PostgresConnectionProvider(
        config, connector=lambda **kwargs: psycopg.connect(**kwargs, connect_timeout=10)
    )
    schema = "sgfap_workflow_" + uuid4().hex
    # This schema is created by the fixture. No application table is modified.
    with provider.connection() as setup:
        setup.autocommit = True
        with setup.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            with setup.cursor() as cursor:
                cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
                root = Path(__file__).resolve().parents[2]
                for script in ("geolocation.sql", "addresses.sql", "user_related.sql", "ticket_related.sql"):
                    cursor.execute((root / "db" / script).read_text(encoding="utf-8"))
                statuses = ("Registered", "Validated", "Prioritized", "Assigned", "InProgress", "Blocked", "PendingClosure", "Resolved")
                status_ids = {name: 1 if index == 0 else index + 60 for index, name in enumerate(statuses)}
                for name, identifier in status_ids.items():
                    cursor.execute("INSERT INTO statuses (id, name) VALUES (%s, %s)", (identifier, name))
                for index, name in enumerate(("Registration", "Validation", "Prioritization", "Assignment", "Attention", "Blockage", "ClosureRequest", "Approval", "Rejection"), 41):
                    cursor.execute("INSERT INTO actions (id, name) VALUES (%s, %s)", (index, name))
                cursor.execute("""INSERT INTO users (id, first_name, last_name, email, password_hash, role_id)
                    VALUES (7, 'workflow', 'Coordinator', 'workflow@example.invalid', 'fixture-only',
                        (SELECT id FROM roles WHERE name = 'Coordinator'))""")
                cursor.execute("""INSERT INTO addresses
                    (id, road_type_code, road_number, cross_road_number, door_plate_number)
                    VALUES (11, 'CL', 10, 20, 4)""")
                cursor.execute("""SELECT f.name, f.id, p.id, p.name FROM failure_types f
                    JOIN priorities p ON p.id = f.priority_id""")
                failures = {name: (identifier, priority_id, priority) for name, identifier, priority_id, priority in cursor.fetchall()}
            yield WorkflowDatabase(provider, schema, 7, 11, status_ids, failures)
        finally:
            # Only remove the exact, newly created fixture schema and its rows.
            with setup.cursor() as cursor:
                cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
