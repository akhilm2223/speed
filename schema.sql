-- Database schema for traffic_violations_db
-- This schema defines the structure for tracking traffic violations and vehicles

-- Create vehicles table
CREATE TABLE IF NOT EXISTS vehicles (
    plate_id VARCHAR(16) NOT NULL,
    registration_state VARCHAR(10) NOT NULL,
    PRIMARY KEY (plate_id, registration_state)
);

-- Create unique index on vehicles
CREATE UNIQUE INDEX IF NOT EXISTS pk_vehicle 
ON vehicles (plate_id, registration_state);

-- Create violations table
CREATE TABLE IF NOT EXISTS violations (
    violation_id BIGSERIAL PRIMARY KEY,
    plate_id VARCHAR(16) NOT NULL,
    registration_state VARCHAR(10) NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    violation_code VARCHAR(64) NOT NULL,
    issue_date TIMESTAMP WITH TIME ZONE,
    violation_location VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    FOREIGN KEY (plate_id, registration_state) 
        REFERENCES vehicles(plate_id, registration_state)
);



