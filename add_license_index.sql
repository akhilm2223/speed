-- Add index on driver_license_number for faster license-based queries
CREATE INDEX IF NOT EXISTS idx_violations_license ON violations(driver_license_number);
CREATE INDEX IF NOT EXISTS idx_violations_license_trim ON violations(TRIM(driver_license_number));

