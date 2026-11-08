CREATE TABLE priorities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(12) NOT NULL UNIQUE CHECK (name IN ('High','Standard'))
);

INSERT INTO priorities (name) VALUES ('High'), ('Standard');


CREATE TABLE failure_types (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    priority_id INT NOT NULL REFERENCES priorities(id)
);

INSERT INTO failure_types (name, priority_id) VALUES
    ('Exposed cable', 1),
    ('Pole fall risk', 1),
    ('Box without cover', 1),
    ('Light out', 2),
    ('Intermittent', 2),
    ('Tree Branches', 1);


CREATE TABLE statuses (
    id SERIAL PRIMARY KEY,
    name VARCHAR(24) NOT NULL UNIQUE CHECK (name IN (
        'Registered','Validated','Prioritized','Assigned','InProgress',
        'Blocked','PendingClosure','Resolved'
    ))
);

INSERT INTO statuses (name) VALUES
    ('Registered'),
    ('Validated'),
    ('Prioritized'),
    ('Assigned'),
    ('InProgress'),
    ('Blocked'),
    ('PendingClosure'),
    ('Resolved');


CREATE TABLE actions (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE CHECK (name IN (
        'Registration','Validation','Prioritization','Assignment','Attention',
        'Blockage','Unblock','ClosureRequest','Approval','Rejection'
    ))
);

INSERT INTO actions (name) VALUES
    ('Registration'),
    ('Validation'),
    ('Prioritization'),
    ('Assignment'),
    ('Attention'),
    ('Blockage'),
    ('Unblock'),
    ('ClosureRequest'),
    ('Approval'),
    ('Rejection');

CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    code VARCHAR(24) NOT NULL UNIQUE,
    reported_by INT NOT NULL REFERENCES users(id),
    failure_type_id INT NOT NULL REFERENCES failure_types(id),
    description TEXT NOT NULL,
    address_id INT REFERENCES addresses(id),
    status_id INT NOT NULL REFERENCES statuses(id) DEFAULT 1,
    priority_id INT REFERENCES priorities(id),
    contact_email TEXT,
    contact_phone TEXT,
    diagnosis TEXT,
    solution TEXT,
    crew_id INT REFERENCES crews(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE evidences (
    id SERIAL PRIMARY KEY,
    ticket_id INT NOT NULL REFERENCES tickets(id),
    file_path TEXT NOT NULL UNIQUE,
    captured_at TIMESTAMPTZ NOT NULL,
    uploaded_by INT NOT NULL REFERENCES users(id)
);


CREATE TABLE history_events (
    id BIGSERIAL PRIMARY KEY,
    ticket_id INT NOT NULL REFERENCES tickets(id),
    user_id INT REFERENCES users(id),
    action_id INT NOT NULL REFERENCES actions(id),
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE operation_attempts (
    actor_user_id INT NOT NULL REFERENCES users(id),
    operation VARCHAR(128) NOT NULL,
    request_key VARCHAR(128) NOT NULL,
    request_digest CHAR(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    result_payload JSONB NOT NULL,
    committed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (actor_user_id, operation, request_key)
);

CREATE TABLE ticket_match_guards (
    scope_type VARCHAR(16) NOT NULL CHECK (scope_type = 'address'),
    scope_id INT NOT NULL REFERENCES addresses(id),
    failure_type_id INT NOT NULL REFERENCES failure_types(id),
    PRIMARY KEY (scope_type, scope_id, failure_type_id)
);

CREATE INDEX tickets_open_match_lookup_idx
    ON tickets (address_id, failure_type_id, status_id, created_at DESC, code ASC);

BEGIN;

ALTER TABLE evidences
    ALTER COLUMN captured_at DROP NOT NULL;

ALTER TABLE evidences
    ADD COLUMN IF NOT EXISTS uploaded_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS capture_source VARCHAR(32) NULL,
    ADD COLUMN IF NOT EXISTS media_type VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS size_bytes BIGINT NULL CHECK (size_bytes >= 0),
    ADD COLUMN IF NOT EXISTS purpose VARCHAR(32) NULL;

UPDATE evidences
SET
    capture_source = COALESCE(capture_source, 'legacy_declared'),
    purpose = COALESCE(purpose, 'legacy');

CREATE TABLE evidence_uploads (
    id UUID PRIMARY KEY,
    actor_user_id INT NOT NULL REFERENCES users(id),
    request_key VARCHAR(128) NOT NULL,
    upload_key VARCHAR(128) NOT NULL,
    purpose VARCHAR(32) NOT NULL CHECK (purpose = 'report'),
    state VARCHAR(16) NOT NULL CHECK (
        state IN ('receiving', 'ready', 'consumed', 'expired', 'deleted')
    ),
    storage_key VARCHAR(256) NULL UNIQUE,
    content_sha256 CHAR(64) NULL CHECK (
        content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-f]{64}$'
    ),
    size_bytes BIGINT NULL CHECK (size_bytes IS NULL OR size_bytes >= 0),
    media_type VARCHAR(64) NULL,
    captured_at TIMESTAMPTZ NULL,
    capture_source VARCHAR(32) NOT NULL CHECK (
        capture_source IN ('camera', 'device_metadata', 'user_declared', 'unknown')
    ),
    received_at TIMESTAMPTZ NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    lease_expires_at TIMESTAMPTZ NULL,
    evidence_id INT NULL UNIQUE REFERENCES evidences(id),
    delete_requested_at TIMESTAMPTZ NULL,
    delete_attempts INT NOT NULL DEFAULT 0 CHECK (delete_attempts >= 0),
    CONSTRAINT evidence_upload_capture_consistency CHECK (
        (capture_source = 'unknown' AND captured_at IS NULL)
        OR capture_source <> 'unknown'
    ),
    CONSTRAINT evidence_upload_ready_metadata CHECK (
        state NOT IN ('ready', 'consumed')
        OR (
            storage_key IS NOT NULL
            AND content_sha256 IS NOT NULL
            AND size_bytes IS NOT NULL
            AND media_type IS NOT NULL
            AND received_at IS NOT NULL
        )
    ),
    CONSTRAINT evidence_upload_consumed_link CHECK (
        state <> 'consumed' OR evidence_id IS NOT NULL
    ),
    UNIQUE (actor_user_id, purpose, request_key, upload_key)
);

CREATE INDEX evidence_uploads_actor_attempt_idx
    ON evidence_uploads (actor_user_id, purpose, request_key, state, expires_at);

CREATE INDEX evidence_uploads_cleanup_idx
    ON evidence_uploads (state, expires_at, lease_expires_at)
    WHERE state IN ('receiving', 'ready', 'expired');

COMMIT;


BEGIN;

CREATE TABLE citizen_contributions (
    id UUID PRIMARY KEY,
    ticket_id INT NOT NULL REFERENCES tickets(id),
    actor_user_id INT NOT NULL REFERENCES users(id),
    request_key VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (ticket_id, actor_user_id, request_key)
);

CREATE TABLE citizen_contribution_evidences (
    contribution_id UUID NOT NULL REFERENCES citizen_contributions(id),
    evidence_id INT NOT NULL UNIQUE REFERENCES evidences(id),
    PRIMARY KEY (contribution_id, evidence_id)
);

CREATE INDEX citizen_contributions_actor_request_idx
    ON citizen_contributions (actor_user_id, request_key, created_at DESC);

COMMIT;
