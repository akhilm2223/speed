#!/usr/bin/env python3
"""
Seed the database with camera locations and pre-computed detections.
Run this once before the demo.
"""
import os
import psycopg
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "traffic_violations_db"),
    "user": os.getenv("DB_USER", "myuser"),
    "password": os.getenv("DB_PASSWORD", "mypassword"),
}

# 3 Manhattan Camera locations with real videos
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

# Road segments for each camera
ROAD_SEGMENTS = [
    {"segment_id": "SEG-1", "name": "Times Square", "borough": "Manhattan", "zone_type": "high_traffic", "latitude": 40.7580, "longitude": -73.9855},
    {"segment_id": "SEG-2", "name": "Houston St & FDR", "borough": "Manhattan", "zone_type": "accident_zone", "latitude": 40.7142, "longitude": -73.9782},
    {"segment_id": "SEG-3", "name": "West Side Hwy & 57th", "borough": "Manhattan", "zone_type": "accident_zone", "latitude": 40.7714, "longitude": -73.9916},
]

# Pre-registered drivers (will accumulate violations during demo)
DRIVERS = [
    {"plate_id": "NYC-SPEED-01", "registration_state": "NY"},
    {"plate_id": "NYC-SPEED-02", "registration_state": "NY"},
    {"plate_id": "MN-FAST-77", "registration_state": "NY"},
    {"plate_id": "TS-TAXI-42", "registration_state": "NY"},
]

def setup_ai_schema():
    """Create AI enforcement tables."""
    schema_path = Path(__file__).parent / "sql" / "ai_schema.sql"
    
    with psycopg.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(schema_path.read_text())
        conn.commit()
    print("✓ AI schema created")

def seed_data():
    """Seed cameras, segments, and drivers."""
    with psycopg.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # Clear existing demo data
            cur.execute("DELETE FROM ai_violations")
            cur.execute("DELETE FROM dmv_alerts")
            cur.execute("DELETE FROM cameras")
            cur.execute("DELETE FROM drivers WHERE plate_id LIKE 'NYC-%' OR plate_id LIKE 'BK-%' OR plate_id LIKE 'QNS-%'")
            cur.execute("DELETE FROM road_segments")
            
            # Insert road segments
            for seg in ROAD_SEGMENTS:
                cur.execute("""
                    INSERT INTO road_segments (segment_id, name, borough, zone_type, latitude, longitude)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (seg["segment_id"], seg["name"], seg["borough"], seg["zone_type"], seg["latitude"], seg["longitude"]))
            print(f"✓ Inserted {len(ROAD_SEGMENTS)} road segments")
            
            # Insert cameras
            for i, cam in enumerate(CAMERAS):
                cur.execute("""
                    INSERT INTO cameras (camera_id, name, segment_id, latitude, longitude, borough, zone_type, description, video_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (cam["camera_id"], cam["name"], f"SEG-{i+1}", cam["latitude"], cam["longitude"], 
                      cam["borough"], cam["zone_type"], cam["description"], cam["video_url"]))
            print(f"✓ Inserted {len(CAMERAS)} cameras")
            
            # Insert drivers
            for driver in DRIVERS:
                cur.execute("""
                    INSERT INTO drivers (plate_id, registration_state)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (driver["plate_id"], driver["registration_state"]))
            print(f"✓ Inserted {len(DRIVERS)} drivers")
            
        conn.commit()

if __name__ == "__main__":
    print("=" * 50)
    print("  SEEDING CAMERA DEMO DATA")
    print("=" * 50)
    setup_ai_schema()
    seed_data()
    print("\n✓ Done! Ready for demo.")
