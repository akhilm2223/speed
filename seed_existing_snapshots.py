#!/usr/bin/env python3
"""
Seeds ai_violations records for existing snapshot images.
This allows teammates who pull the repo to see the pre-existing snapshots.

Run: python ingest/seed_existing_snapshots.py
"""
import os
import re
from datetime import datetime
from pathlib import Path
import psycopg
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "traffic_violations_db"),
    "user": os.getenv("DB_USER", "myuser"),
    "password": os.getenv("DB_PASSWORD", "mypassword"),
}

# Path to snapshots folder (relative to project root)
SNAPSHOTS_DIR = Path(__file__).parent.parent / "snapshots"


def parse_snapshot_filename(filename):
    """
    Parse snapshot filename to extract camera_id, plate_id, and timestamp.
    Format: CAM-X_PLATE_TIMESTAMP.jpg
    Example: CAM-1_NY00000_1764894747.jpg
    """
    match = re.match(r'^(CAM-\d+)_([A-Z0-9-]+)_(\d+)\.jpg$', filename)
    if match:
        return {
            "camera_id": match.group(1),
            "plate_id": match.group(2),
            "timestamp": int(match.group(3)),
        }
    return None


def seed_existing_snapshots():
    print("=" * 60)
    print("  SEEDING AI_VIOLATIONS FROM EXISTING SNAPSHOTS")
    print("=" * 60)
    
    if not SNAPSHOTS_DIR.exists():
        print(f"ERROR: Snapshots directory not found: {SNAPSHOTS_DIR}")
        return
    
    # Get all jpg files in snapshots folder
    snapshot_files = list(SNAPSHOTS_DIR.glob("*.jpg"))
    print(f"\nFound {len(snapshot_files)} snapshot files")
    
    if not snapshot_files:
        print("No snapshots to process.")
        return
    
    print("\nConnecting to database...")
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Get camera speed limits
    cur.execute("SELECT camera_id, speed_limit, latitude, longitude FROM cameras")
    cameras = {row[0]: {"speed_limit": row[1], "lat": row[2], "lng": row[3]} for row in cur.fetchall()}
    print(f"Found {len(cameras)} cameras in database")
    
    if not cameras:
        print("ERROR: No cameras in database. Run seed_cameras_simple.py first!")
        cur.close()
        conn.close()
        return
    
    seeded_count = 0
    skipped_count = 0
    
    for snapshot_path in snapshot_files:
        parsed = parse_snapshot_filename(snapshot_path.name)
        if not parsed:
            print(f"  ⚠ Skipping (invalid format): {snapshot_path.name}")
            skipped_count += 1
            continue
        
        camera_id = parsed["camera_id"]
        plate_id = parsed["plate_id"]
        timestamp = parsed["timestamp"]
        
        if camera_id not in cameras:
            print(f"  ⚠ Skipping (unknown camera {camera_id}): {snapshot_path.name}")
            skipped_count += 1
            continue
        
        camera = cameras[camera_id]
        speed_limit = camera["speed_limit"]
        
        # Check if this snapshot already exists in database
        cur.execute("""
            SELECT 1 FROM ai_violations WHERE screenshot_path = %s
        """, (str(snapshot_path),))
        
        if cur.fetchone():
            print(f"  ✓ Already exists: {snapshot_path.name}")
            skipped_count += 1
            continue
        
        # Generate realistic violation data
        speed_detected = speed_limit + 15 + (hash(plate_id) % 20)  # 15-35 over limit
        
        # Convert timestamp to datetime
        try:
            detected_at = datetime.fromtimestamp(timestamp)
        except:
            detected_at = datetime.now()
        
        # Insert ai_violation record
        cur.execute("""
            INSERT INTO ai_violations (
                camera_id, plate_id, violation_type, points,
                speed_detected, speed_limit, screenshot_path,
                detected_at, ocr_confidence
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING violation_id
        """, (
            camera_id,
            plate_id,
            "speeding",
            3,  # Default points
            speed_detected,
            speed_limit,
            str(snapshot_path),
            detected_at,
            0.85 + (hash(plate_id) % 15) / 100  # Random confidence 0.85-0.99
        ))
        
        violation_id = cur.fetchone()[0]
        
        # Also insert into main violations table for full integration
        cur.execute("""
            INSERT INTO violations (
                plate_id, plate_state, violation_code,
                date_of_violation, fine_amount, latitude, longitude,
                police_agency
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            plate_id,
            "NY",
            "1180A",  # Speeding violation code
            detected_at.date(),
            150 + (speed_detected - speed_limit) * 10,  # Fine based on speed over
            camera["lat"],
            camera["lng"],
            "AI Camera System"
        ))
        
        print(f"  ✓ Seeded: {snapshot_path.name} → {speed_detected} MPH (limit {speed_limit})")
        seeded_count += 1
    
    conn.commit()
    cur.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print(f"  DONE!")
    print(f"  ✓ Seeded: {seeded_count} violations")
    print(f"  ⊘ Skipped: {skipped_count} files")
    print("=" * 60)


if __name__ == "__main__":
    seed_existing_snapshots()

