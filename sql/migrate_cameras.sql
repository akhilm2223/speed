-- Migration: Add meters_per_pixel and speed_limit columns to cameras table
-- Run this if you have existing camera data

-- Add new columns if they don't exist
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS speed_limit INTEGER DEFAULT 30;
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS meters_per_pixel FLOAT DEFAULT 0.05;

-- Update existing cameras with calibrated values
UPDATE cameras SET 
    meters_per_pixel = 0.035,
    speed_limit = 15
WHERE camera_id = 'CAM-1';

UPDATE cameras SET 
    meters_per_pixel = 0.042,
    speed_limit = 30
WHERE camera_id = 'CAM-2';

UPDATE cameras SET 
    meters_per_pixel = 0.04,
    speed_limit = 30
WHERE camera_id = 'CAM-3';

UPDATE cameras SET 
    meters_per_pixel = 0.06,
    speed_limit = 55
WHERE camera_id = 'CAM-4';

-- Add OCR confidence column to ai_violations if not exists
ALTER TABLE ai_violations ADD COLUMN IF NOT EXISTS ocr_confidence DECIMAL(4, 3);

-- Add index for camera violations lookup
CREATE INDEX IF NOT EXISTS idx_ai_violations_camera ON ai_violations(camera_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_violations_plate ON ai_violations(plate_id);

