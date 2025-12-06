-- Simple schema for traffic violations

-- Vehicles table
CREATE TABLE IF NOT EXISTS vehicles (
    plate_id            VARCHAR(16) NOT NULL,
    registration_state  VARCHAR(10) NOT NULL,
    PRIMARY KEY (plate_id, registration_state)
);

-- Violations table
CREATE TABLE IF NOT EXISTS violations (
    violation_id          BIGSERIAL PRIMARY KEY,
    driver_license_number VARCHAR(32) NOT NULL,
    driver_full_name      VARCHAR(128) NOT NULL,
    date_of_birth         DATE NOT NULL,
    license_state         VARCHAR(10) NOT NULL,
    plate_id              VARCHAR(16) NOT NULL,
    plate_state           VARCHAR(10) NOT NULL,
    violation_code        VARCHAR(64) NOT NULL,
    date_of_violation     TIMESTAMPTZ NOT NULL,
    disposition           VARCHAR(64) NOT NULL,
    latitude              DECIMAL(10, 8) NOT NULL,
    longitude             DECIMAL(11, 8) NOT NULL,
    police_agency         VARCHAR(128) NOT NULL,
    ticket_issuer         VARCHAR(128) NOT NULL,
    source_type           VARCHAR(64) NOT NULL,
    created_at            TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    FOREIGN KEY (plate_id, plate_state) REFERENCES vehicles (plate_id, registration_state) ON DELETE CASCADE
);

-- Driver License Summary Table
-- Simple table tracking total speeding tickets and points per person
CREATE TABLE IF NOT EXISTS driver_license_summary (
    driver_license_number VARCHAR(32) NOT NULL,
    license_state         VARCHAR(10) NOT NULL,
    total_speeding_tickets INTEGER DEFAULT 0,
    points_on_license      INTEGER DEFAULT 0,
    updated_at             TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (driver_license_number, license_state)
);

-- Cameras table
CREATE TABLE IF NOT EXISTS cameras (
    camera_id    VARCHAR(32) PRIMARY KEY,
    name         VARCHAR(128) NOT NULL,
    latitude     DECIMAL(10, 8) NOT NULL,
    longitude    DECIMAL(11, 8) NOT NULL,
    borough      VARCHAR(32),
    zone_type    VARCHAR(32),
    description  TEXT,
    video_url    TEXT,
    is_active    BOOLEAN DEFAULT true,
    speed_limit  INTEGER DEFAULT 30,
    meters_per_pixel FLOAT DEFAULT 0.05,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- AI violations table
CREATE TABLE IF NOT EXISTS ai_violations (
    violation_id   BIGSERIAL PRIMARY KEY,
    camera_id      VARCHAR(32) REFERENCES cameras(camera_id),
    plate_id       VARCHAR(16),
    violation_type VARCHAR(32),
    points         INTEGER,
    speed_detected DECIMAL(5, 1),
    speed_limit    INTEGER,
    is_school_zone BOOLEAN,
    latitude       DECIMAL(10, 8),
    longitude      DECIMAL(11, 8),
    screenshot_path TEXT,
    ocr_confidence  DECIMAL(4, 3),
    detected_at    TIMESTAMPTZ DEFAULT NOW()
);

-- DMV alerts table
CREATE TABLE IF NOT EXISTS dmv_alerts (
    alert_id              BIGSERIAL PRIMARY KEY,
    plate_id             VARCHAR(16) NOT NULL,
    driver_license_number VARCHAR(32),
    status               VARCHAR(32) NOT NULL,
    alert_type           VARCHAR(32),
    risk_score_at_alert  INTEGER,
    crash_risk_at_alert  DECIMAL(5, 2),
    total_violations_at_alert INTEGER,
    reason               TEXT,
    responsible_party    VARCHAR(64),
    due_date             TIMESTAMPTZ,
    enforcement_stage    VARCHAR(32),
    court_name           VARCHAR(128),
    notes                TEXT,
    resolved_at          TIMESTAMPTZ,
    updated_at           TIMESTAMPTZ,
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_violations_plate_date ON violations(plate_id, plate_state, date_of_violation DESC);
CREATE INDEX IF NOT EXISTS idx_violations_code ON violations(violation_code);
CREATE INDEX IF NOT EXISTS idx_dmv_alerts_plate ON dmv_alerts(plate_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_violations_camera ON ai_violations(camera_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_violations_plate ON ai_violations(plate_id);
