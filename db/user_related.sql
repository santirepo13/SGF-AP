CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(20) NOT NULL UNIQUE CHECK (name IN ('Citizen','Operator','Coordinator','Crew','Admin'))
);

INSERT INTO roles (name) VALUES
    ('Citizen'),
    ('Operator'),
    ('Coordinator'),
    ('Crew'),
    ('Admin');


CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role_id INT NOT NULL REFERENCES roles(id),
    active BOOLEAN NOT NULL DEFAULT TRUE
);


CREATE TABLE crews (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);


CREATE TABLE crew_members (
    user_id INT PRIMARY KEY REFERENCES users(id),
    crew_id INT NOT NULL REFERENCES crews(id)
);
