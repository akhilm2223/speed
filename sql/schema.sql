-- Database schema for traffic_violations_db
-- Supports BOTH:
--   1. NYC Open Data violations (from ingest.py) - basic fields only
--   2. NY State traffic violation data (from generate_ny_violations.py) - extended fields

-- =============================================================================
-- VEHICLES TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS vehicles (
    plate_id            VARCHAR(16) NOT NULL,
    registration_state  VARCHAR(10) NOT NULL,
    PRIMARY KEY (plate_id, registration_state)
);

-- =============================================================================
-- VIOLATIONS TABLE
-- Unified schema for both NYC and NY State data
-- NYC data uses: plate_id, registration_state, source_type, violation_code, 
--                violation_description, issue_date, violation_location
-- NY State adds: violation_year/month/dow, age, gender, license state, 
--                police_agency, court, source, lat/lon columns
-- =============================================================================
CREATE TABLE IF NOT EXISTS violations (
    violation_id          BIGSERIAL PRIMARY KEY,
    
    -- CORE FIELDS (required for both datasets)
    plate_id              VARCHAR(16) NOT NULL,
    registration_state    VARCHAR(10) NOT NULL,
    source_type           VARCHAR(32) DEFAULT 'police_stop',  -- police_stop, camera, etc.
    violation_code        VARCHAR(64) NOT NULL,               -- 1180A, 1180B, 1180C, 1180D, etc.
    violation_description VARCHAR(255),                       -- "Speeding 11-20 mph over limit"
    issue_date            TIMESTAMPTZ,                        -- When violation occurred
    violation_location    VARCHAR(255),                       -- "(lat, lon)" or address string
    
    -- NY STATE EXTENDED FIELDS (nullable - only populated by generate_ny_violations.py)
    violation_year        INTEGER,                            -- Calendar year
    violation_month       INTEGER,                            -- 1-12
    violation_dow         VARCHAR(16),                        -- Day of week (Monday, Tuesday, etc.)
    age_at_violation      INTEGER,                            -- Driver's age
    gender                VARCHAR(1),                         -- M, F, C (org), U (unknown)
    state_of_license      VARCHAR(64),                        -- License issuing state
    police_agency         VARCHAR(128),                       -- "NYS Police - Troop T", "NYPD", etc.
    county                VARCHAR(64),                        -- County (CRITICAL for county risk cards)
    court                 VARCHAR(128),                       -- "NYC TVB - Manhattan", etc. (CRITICAL for local court adapter)
    disposition           VARCHAR(64),                        -- Case outcome: GUILTY, DISMISSED, PENDING, etc. (CRITICAL for compliance)
    source                VARCHAR(16),                        -- TSLED or TVB (processing system)
    
    -- DIRECT COORDINATES (nullable - NYC data parses from violation_location)
    latitude              DECIMAL(10, 8),                     -- Direct lat column (NY State data)
    longitude             DECIMAL(11, 8),                     -- Direct lon column (NY State data)
    
    -- METADATA
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (plate_id, registration_state) 
        REFERENCES vehicles (plate_id, registration_state) ON DELETE CASCADE
);

-- =============================================================================
-- INDEXES
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_violations_plate ON violations(plate_id, registration_state);
CREATE INDEX IF NOT EXISTS idx_violations_code ON violations(violation_code);
CREATE INDEX IF NOT EXISTS idx_violations_date ON violations(issue_date);
CREATE INDEX IF NOT EXISTS idx_violations_location ON violations(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_violations_county ON violations(county);           -- For county risk cards
CREATE INDEX IF NOT EXISTS idx_violations_court ON violations(court);             -- For local court adapter
CREATE INDEX IF NOT EXISTS idx_violations_disposition ON violations(disposition); -- For compliance tracking

-- =============================================================================
-- DMV RISK VIEW (for monitoring high-risk drivers)
-- =============================================================================
CREATE OR REPLACE VIEW dmv_risk_view AS
SELECT 
    v.plate_id,
    v.registration_state,
    COUNT(*) as violation_count,
    SUM(CASE 
        WHEN v.violation_code = '1180D' THEN 8   -- 31+ mph over
        WHEN v.violation_code = '1180C' THEN 5   -- 21-30 mph over
        WHEN v.violation_code = '1180B' THEN 3   -- 11-20 mph over
        WHEN v.violation_code IN ('1180E', '1180F') THEN 6  -- School/Work zone
        ELSE 2                                    -- 1-10 mph over
    END) as risk_points,
    MIN(v.issue_date) as first_violation,
    MAX(v.issue_date) as last_violation
FROM violations v
GROUP BY v.plate_id, v.registration_state
ORDER BY risk_points DESC;

-- =============================================================================
-- CAMERAS TABLE (for AI speed detection cameras)
-- =============================================================================
CREATE TABLE IF NOT EXISTS cameras (
    camera_id    VARCHAR(32) PRIMARY KEY,
    name         VARCHAR(128) NOT NULL,
    latitude     DECIMAL(10, 8) NOT NULL,
    longitude    DECIMAL(11, 8) NOT NULL,
    borough      VARCHAR(64),
    zone_type    VARCHAR(32),              -- school_zone, work_zone, highway, etc.
    description  TEXT,
    video_url    VARCHAR(512),
    is_active    BOOLEAN DEFAULT true,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- AI DETECTIONS TABLE (violations detected by AI cameras)
-- =============================================================================
CREATE TABLE IF NOT EXISTS ai_detections (
    detection_id   BIGSERIAL PRIMARY KEY,
    camera_id      VARCHAR(32) REFERENCES cameras(camera_id),
    plate_id       VARCHAR(16),
    confidence     DECIMAL(5, 4),           -- 0.0000 to 1.0000
    speed_detected INTEGER,
    speed_limit    INTEGER,
    image_url      VARCHAR(512),
    detected_at    TIMESTAMPTZ DEFAULT NOW(),
    processed      BOOLEAN DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_ai_detections_camera ON ai_detections(camera_id);
CREATE INDEX IF NOT EXISTS idx_ai_detections_plate ON ai_detections(plate_id);

-- =============================================================================
-- DMV ALERTS TABLE (ISA enforcement notices with lifecycle)
-- Lifecycle: NEW → NOTICE_SENT → FOLLOW_UP_DUE → COMPLIANT → ESCALATED
-- =============================================================================
CREATE TABLE IF NOT EXISTS dmv_alerts (
    alert_id                    BIGSERIAL PRIMARY KEY,
    plate_id                    VARCHAR(16) NOT NULL,
    alert_type                  VARCHAR(32) NOT NULL,  -- ISA_REQUIRED, WARNING, etc.
    status                      VARCHAR(32) NOT NULL,  -- NEW, NOTICE_SENT, FOLLOW_UP_DUE, COMPLIANT, ESCALATED
    risk_score_at_alert         INTEGER,
    crash_risk_at_alert         DECIMAL(5,2),          -- Crash risk score 0-100
    total_violations_at_alert   INTEGER,
    reason                      TEXT,
    responsible_party           VARCHAR(64),           -- DMV, Court, Vendor
    due_date                    TIMESTAMPTZ,           -- Follow-up due date
    enforcement_stage           VARCHAR(32),           -- Current enforcement stage
    notes                       TEXT,                  -- Additional notes
    court_name                  VARCHAR(128),          -- Assigned court
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),
    resolved_at                 TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_dmv_alerts_plate ON dmv_alerts(plate_id);
CREATE INDEX IF NOT EXISTS idx_dmv_alerts_status ON dmv_alerts(status);
CREATE INDEX IF NOT EXISTS idx_dmv_alerts_due_date ON dmv_alerts(due_date);
