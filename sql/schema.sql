
-- Vehicles: identified by plate + registration state
CREATE TABLE IF NOT EXISTS vehicles (
    plate_id            VARCHAR(16) NOT NULL,  -- Common: plate_id / reg_plate_num
    registration_state  VARCHAR(10) NOT NULL,  -- Common: registration_state / reg_state_cd (increased for longer codes)

    CONSTRAINT pk_vehicle PRIMARY KEY (plate_id, registration_state)
);

-- Violations: core violation event data (per plate + state)
CREATE TABLE IF NOT EXISTS violations (
    violation_id        BIGSERIAL PRIMARY KEY,
    plate_id            VARCHAR(16) NOT NULL,
    registration_state  VARCHAR(10) NOT NULL,
    source_type         VARCHAR(32) NOT NULL,  -- 'police_stop' or 'traffic_camera'
    violation_code      VARCHAR(64) NOT NULL,
    issue_date          TIMESTAMPTZ,           -- When it happened
    violation_location  VARCHAR(255),          -- Human-readable location

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_violations_vehicle
        FOREIGN KEY (plate_id, registration_state)
        REFERENCES vehicles (plate_id, registration_state)
        ON DELETE CASCADE
);

