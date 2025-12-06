#!/usr/bin/env python3
"""
Simple camera seeding - just adds cameras to the existing schema.
Run: python seed_cameras_simple.py
"""
import os
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

# Camera locations with video files in public folder
CAMERAS = [
    {
        "camera_id": "CAM-1",
        "name": "Times Square",
        "latitude": 40.7580,
        "longitude": -73.9855,
        "borough": "Manhattan",
        "zone_type": "high_traffic",
        "description": "Times Square - highest pedestrian density zone",
        "video_url": "/timesquare.mp4"
    },
    {
        "camera_id": "CAM-2",
        "name": "Houston St & FDR Drive",
        "latitude": 40.7142,
        "longitude": -73.9782,
        "borough": "Manhattan",
        "zone_type": "accident_zone",
        "description": "Lower East Side - high accident corridor",
        "video_url": "/Video_Creation_Request_Fulfilled.mp4"
    },
    {
        "camera_id": "CAM-3",
        "name": "West Side Highway & 57th",
        "latitude": 40.7714,
        "longitude": -73.9916,
        "borough": "Manhattan",
        "zone_type": "accident_zone",
        "description": "West Side Highway - dangerous intersection",
        "video_url": "/Video_Generation_Successful.mp4"
    }
]

def seed_cameras():
    print("Connecting to database...")
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Check if cameras table exists with correct schema
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'cameras'
    """)
    columns = [row[0] for row in cur.fetchall()]
    print(f"Cameras table columns: {columns}")
    
    if not columns:
        print("Creating cameras table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cameras (
                camera_id    VARCHAR(32) PRIMARY KEY,
                name         VARCHAR(128) NOT NULL,
                latitude     DECIMAL(10, 8) NOT NULL,
                longitude    DECIMAL(11, 8) NOT NULL,
                borough      VARCHAR(64),
                zone_type    VARCHAR(32),
                description  TEXT,
                video_url    VARCHAR(512),
                is_active    BOOLEAN DEFAULT true,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.commit()
    
    # Clear existing cameras
    cur.execute("DELETE FROM cameras")
    print("Cleared existing cameras")
    
    # Insert cameras
    for cam in CAMERAS:
        cur.execute("""
            INSERT INTO cameras (camera_id, name, latitude, longitude, borough, zone_type, description, video_url, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true)
        """, (
            cam["camera_id"], cam["name"], cam["latitude"], cam["longitude"],
            cam["borough"], cam["zone_type"], cam["description"], cam["video_url"]
        ))
        print(f"  ✓ Added {cam['name']}")
    
    conn.commit()
    
    # Verify
    cur.execute("SELECT camera_id, name, video_url FROM cameras")
    print("\nCameras in database:")
    for row in cur:
        print(f"  {row[0]}: {row[1]} -> {row[2]}")
    
    cur.close()
    conn.close()
    print("\n✓ Done! Cameras seeded.")

if __name__ == "__main__":
    seed_cameras()
