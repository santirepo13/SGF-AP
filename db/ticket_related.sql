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


CREATE TABLE actions (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE CHECK (name IN (
        'Registration','Validation','Prioritization','Assignment','Attention',
        'Blockage','ClosureRequest','Approval','Rejection'
    ))
);

CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    code VARCHAR(24) NOT NULL UNIQUE,
    reported_by INT NOT NULL REFERENCES users(id),
    failure_type_id INT NOT NULL REFERENCES failure_types(id),
    description TEXT NOT NULL,
    address_id INT REFERENCES addresses(id),
    status_id INT NOT NULL REFERENCES statuses(id) DEFAULT (SELECT id FROM statuses WHERE name = 'Registered'),
    priority_id INT REFERENCES priorities(id),
    contact_email TEXT,
    contact_phone TEXT,
    diagnosis TEXT,
    solution TEXT,
    crew_id INT REFERENCES crews(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
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
