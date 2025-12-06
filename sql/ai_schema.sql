-- AI Enforcement Demo Schema
-- Extends existing schema with AI detection tables

-- Drivers table: tracks risk scores per plate
CREATE TABLE IF NOT EXISTS drivers (
    plate_id            VARCHAR(16) NOT NULL,
    registration_state  VARCHAR(10) NOT NULL DEFAULT 'NY',
    total_violations    INTEGER NOT NULL DEFAULT 0,
    current_risk_points INTEGER NOT NULL DEFAULT 0,
    first_violation_date TIMESTAMPTZ,
    last_violation_date  TIMESTAMPTZ,
    isa_status          VARCHAR(20) NOT NULL DEFAULT 'NONE', -- NONE, MONITOR, ISA_REQUIRED
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (plate_id, registration_state)
);

-- AI-detected violations from camera feeds
CREATE TABLE IF NOT EXISTS ai_violations (
    violation_id        BIGSERIAL PRIMARY KEY,
    camera_id           VARCHAR(32) NOT NULL,
    plate_id            VARCHAR(16) NOT NULL,
    registration_state  VARCHAR(10) NOT NULL DEFAULT 'NY',
    violation_type      VARCHAR(64) NOT NULL, -- excessive_speed, school_zone_speeding, etc.
    points              INTEGER NOT NULL DEFAULT 3,
    speed_detected      INTEGER, -- mph if available
    speed_limit         INTEGER, -- posted limit
    is_school_zone      BOOLEAN DEFAULT FALSE,
    latitude            DECIMAL(10, 6),
    longitude           DECIMAL(10, 6),
    video_timestamp     VARCHAR(16), -- timestamp in video where detected
    confidence          DECIMAL(4, 2), -- CV confidence score
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_ai_violations_driver
        FOREIGN KEY (plate_id, registration_state)
        REFERENCES drivers (plate_id, registration_state)
        ON DELETE CASCADE
);

-- DMV alerts for ISA enforcement
CREATE TABLE IF NOT EXISTS dmv_alerts (
    alert_id            BIGSERIAL PRIMARY KEY,
    plate_id            VARCHAR(16) NOT NULL,
    registration_state  VARCHAR(10) NOT NULL DEFAULT 'NY',
    alert_type          VARCHAR(32) NOT NULL, -- ISA_REQUIRED, MONITOR, WARNING
    reason              TEXT NOT NULL,
    risk_score_at_alert INTEGER NOT NULL,
    total_violations_at_alert INTEGER NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'PENDING', -- PENDING, SENT, ACKNOWLEDGED
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ,
    CONSTRAINT fk_dmv_alerts_driver
        FOREIGN KEY (plate_id, registration_state)
        REFERENCES drivers (plate_id, registration_state)
        ON DELETE CASCADE
);

-- Road segment risk tracking
CREATE TABLE IF NOT EXISTS road_segments (
    segment_id          VARCHAR(32) PRIMARY KEY,
    name                VARCHAR(128) NOT NULL,
    borough             VARCHAR(32),
    zone_type           VARCHAR(32), -- school_zone, arterial, residential, corridor
    latitude            DECIMAL(10, 6) NOT NULL,
    longitude           DECIMAL(10, 6) NOT NULL,
    total_violations    INTEGER NOT NULL DEFAULT 0,
    risk_score          INTEGER NOT NULL DEFAULT 0,
    last_violation_date TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Cameras table
CREATE TABLE IF NOT EXISTS cameras (
    camera_id           VARCHAR(32) PRIMARY KEY,
    name                VARCHAR(128) NOT NULL,
    segment_id          VARCHAR(32) REFERENCES road_segments(segment_id),
    latitude            DECIMAL(10, 6) NOT NULL,
    longitude           DECIMAL(10, 6) NOT NULL,
    video_url           VARCHAR(255),
    borough             VARCHAR(32),
    zone_type           VARCHAR(32),
    description         TEXT,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_ai_violations_camera ON ai_violations(camera_id);
CREATE INDEX IF NOT EXISTS idx_ai_violations_plate ON ai_violations(plate_id);
CREATE INDEX IF NOT EXISTS idx_dmv_alerts_plate ON dmv_alerts(plate_id);
CREATE INDEX IF NOT EXISTS idx_dmv_alerts_status ON dmv_alerts(status);
