CREATE INDEX IF NOT EXISTS tickets_citizen_query_idx
    ON tickets (reported_by, created_at DESC, code DESC);

CREATE INDEX IF NOT EXISTS history_events_citizen_query_idx
    ON history_events (ticket_id, event_time ASC, id ASC);

ALTER TABLE tickets
    ADD COLUMN IF NOT EXISTS email_notifications BOOLEAN NOT NULL DEFAULT FALSE;
