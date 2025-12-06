-- Migration: Add enforcement lifecycle columns to dmv_alerts
-- Run this if you have existing data in dmv_alerts table

-- Add new columns if they don't exist
ALTER TABLE dmv_alerts ADD COLUMN IF NOT EXISTS crash_risk_at_alert DECIMAL(5,2);
ALTER TABLE dmv_alerts ADD COLUMN IF NOT EXISTS responsible_party VARCHAR(64);
ALTER TABLE dmv_alerts ADD COLUMN IF NOT EXISTS due_date TIMESTAMPTZ;
ALTER TABLE dmv_alerts ADD COLUMN IF NOT EXISTS enforcement_stage VARCHAR(32);
ALTER TABLE dmv_alerts ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE dmv_alerts ADD COLUMN IF NOT EXISTS court_name VARCHAR(128);
ALTER TABLE dmv_alerts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Create index on due_date for follow-up queries
CREATE INDEX IF NOT EXISTS idx_dmv_alerts_due_date ON dmv_alerts(due_date);

-- Migrate existing statuses to new lifecycle
UPDATE dmv_alerts SET status = 'NOTICE_SENT' WHERE status = 'SENT';
UPDATE dmv_alerts SET enforcement_stage = status WHERE enforcement_stage IS NULL;
UPDATE dmv_alerts SET updated_at = COALESCE(resolved_at, created_at) WHERE updated_at IS NULL;
