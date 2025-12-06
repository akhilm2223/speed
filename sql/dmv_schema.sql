-- DMV ISA Enforcement Schema
-- Enhanced risk view with severity, recency, time-of-day, and geography signals

DROP VIEW IF EXISTS dmv_risk_view;

CREATE OR REPLACE VIEW dmv_risk_view AS
SELECT 
    v.plate_id,
    v.registration_state,
    
    -- Core counts
    COUNT(*) AS violation_count,
    COUNT(*) * 3 AS risk_points,
    
    -- Dates
    MAX(issue_date) AS last_violation,
    MIN(issue_date) AS first_violation,
    
    -- Severity breakdown (1180D = high-tier, 1180A = low-tier)
    COUNT(*) FILTER (WHERE violation_code = '1180D') AS high_tier_count,
    COUNT(*) FILTER (WHERE violation_code = '1180A') AS low_tier_count,
    
    -- Recency (last 60 days from max date in dataset - Sep 30, 2025)
    COUNT(*) FILTER (WHERE issue_date >= '2025-08-01') AS recent_violations_60d,
    
    -- Nighttime violations (22:00 - 04:00)
    COUNT(*) FILTER (
        WHERE EXTRACT(HOUR FROM issue_date) >= 22 
           OR EXTRACT(HOUR FROM issue_date) < 4
    ) AS night_violations,
    
    -- Geography
    SPLIT_PART(MAX(v.violation_location), ',', 1) AS primary_borough,
    COUNT(DISTINCT SPLIT_PART(v.violation_location, ',', 1)) AS borough_count

FROM violations v
WHERE 
    v.registration_state = 'NY'
    AND v.plate_id NOT LIKE 'UNK%'
    AND v.plate_id != 'NA'
    AND LENGTH(v.plate_id) >= 4
GROUP BY 
    v.plate_id, v.registration_state
HAVING 
    COUNT(*) >= 2;

-- DMV Alerts table for enforcement actions
CREATE TABLE IF NOT EXISTS dmv_alerts (
    alert_id BIGSERIAL PRIMARY KEY,
    plate_id VARCHAR(16) NOT NULL,
    registration_state VARCHAR(10) NOT NULL DEFAULT 'NY',
    alert_type VARCHAR(32) NOT NULL DEFAULT 'ISA_REQUIRED',
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    reason TEXT,
    risk_score_at_alert INTEGER,
    total_violations_at_alert INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_dmv_alerts_plate ON dmv_alerts(plate_id);
CREATE INDEX IF NOT EXISTS idx_dmv_alerts_status ON dmv_alerts(status);
CREATE INDEX IF NOT EXISTS idx_dmv_alerts_created ON dmv_alerts(created_at DESC);
