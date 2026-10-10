-- Lookup tables for address components (selectable options)

CREATE TABLE road_types (
    code VARCHAR(2) PRIMARY KEY,
    name TEXT NOT NULL
);

INSERT INTO road_types (code, name) VALUES
    ('CL', 'Calle'),
    ('KR', 'Carrera'),
    ('DG', 'Diagonal'),
    ('TV', 'Transversal'),
    ('CQ', 'Circular');



CREATE TABLE road_suffix_letters (
    code VARCHAR(2) PRIMARY KEY
);

INSERT INTO road_suffix_letters (code) VALUES
    ('A'),('B'),('C'),('D'),('E'),('F'),('G'),('H'),
    ('AA'),('AB'),('AC'),('AD'),('AE'),('AF'),('AG'),('AH'),
    ('BB'),('CC'),('DD'),('EE'),('FF'),('GG'),('HH');


CREATE TABLE road_bis_codes (
    code VARCHAR(3) PRIMARY KEY
);

INSERT INTO road_bis_codes (code) VALUES ('BIS');


CREATE TABLE road_quadrants (
    code INT PRIMARY KEY,
    name TEXT NOT NULL
);

INSERT INTO road_quadrants (code, name) VALUES
    (1, 'Sur'),
    (2, 'Este');


CREATE TABLE cross_suffix_letters (
    code VARCHAR(2) PRIMARY KEY
);

INSERT INTO cross_suffix_letters (code) VALUES
    ('A'),('B'),('C'),('D'),('E'),('F'),('G'),('H'),
    ('AA'),('AB'),('AC'),('AD'),('AE'),('AF'),('AG'),('AH'),
    ('BB'),('CC'),('DD'),('EE'),('FF'),('GG'),('HH');


CREATE TABLE cross_bis_codes (
    code VARCHAR(3) PRIMARY KEY
);

INSERT INTO cross_bis_codes (code) VALUES ('BIS');


CREATE TABLE cross_quadrants (
    code INT PRIMARY KEY,
    name TEXT NOT NULL
);

INSERT INTO cross_quadrants (code, name) VALUES
    (1, 'Sur'),
    (2, 'Este');


-- Main address table (references all lookups)
CREATE TABLE addresses (
    id SERIAL PRIMARY KEY,
    road_type_code VARCHAR(2) NOT NULL REFERENCES road_types(code),
    road_number SMALLINT NOT NULL CHECK (road_number BETWEEN 1 AND 999),
    road_suffix_letter_code VARCHAR(2) REFERENCES road_suffix_letters(code),
    road_bis_code VARCHAR(3) REFERENCES road_bis_codes(code),
    road_bis_suffix CHAR(1) CHECK (road_bis_suffix ~ '^[A-Z]$'),
    road_quadrant_code INT REFERENCES road_quadrants(code),
    cross_road_number SMALLINT NOT NULL CHECK (cross_road_number BETWEEN 1 AND 999),
    cross_suffix_letter_code VARCHAR(2) REFERENCES cross_suffix_letters(code),
    cross_bis_code VARCHAR(3) REFERENCES cross_bis_codes(code),
    cross_bis_suffix CHAR(1) CHECK (cross_bis_suffix ~ '^[A-Z]$'),
    cross_quadrant_code INT REFERENCES cross_quadrants(code),
    door_plate_number SMALLINT NOT NULL CHECK (door_plate_number BETWEEN 1 AND 9999),
    neighborhood_id INT REFERENCES neighborhoods(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Treat NULL address components as equal so the same partial address cannot
-- be inserted twice. Multiple tickets may still reference the same address.
CREATE UNIQUE INDEX addresses_components_unique_idx
ON addresses (
    road_type_code,
    road_number,
    (COALESCE(road_suffix_letter_code, '')),
    (COALESCE(road_bis_code, '')),
    (COALESCE(road_bis_suffix, '')),
    (COALESCE(road_quadrant_code, -1)),
    cross_road_number,
    (COALESCE(cross_suffix_letter_code, '')),
    (COALESCE(cross_bis_code, '')),
    (COALESCE(cross_bis_suffix, '')),
    (COALESCE(cross_quadrant_code, -1)),
    door_plate_number,
    (COALESCE(neighborhood_id, -1))
);
