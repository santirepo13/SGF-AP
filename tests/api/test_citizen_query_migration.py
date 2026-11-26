"""Citizen query schema change is represented in the SQL migration."""

from pathlib import Path


def test_query_migration_adds_owner_order_indexes_and_persisted_preference() -> None:
    migration = Path(__file__).resolve().parents[2] / "db" / "migrations" / "005_06_citizen_query_indexes.sql"
    sql = migration.read_text(encoding="utf-8")
    assert "ON tickets (reported_by, created_at DESC, code DESC)" in sql
    assert "ON history_events (ticket_id, event_time ASC, id ASC)" in sql
    assert "ADD COLUMN IF NOT EXISTS email_notifications BOOLEAN NOT NULL DEFAULT FALSE" in sql
