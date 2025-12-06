#!/usr/bin/env python3
"""
Simple camera seeding - adds cameras with calibration values to the existing schema.
Includes meters_per_pixel for real speed estimation.

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

# Camera locations with video files and calibration values
# meters_per_pixel is calibrated per camera for accurate speed estimation
CAMERAS = [
    {
        "camera_id": "CAM-1",
        "name": "Times Square",
        "latitude": 40.7580,
        "longitude": -73.9855,
        "borough": "Manhattan",
        "zone_type": "high_traffic",
        "description": "Times Square - highest pedestrian density zone",
        "video_url": "/timesquare.mp4",
        "speed_limit": 15,           # 15 MPH in pedestrian zone
        "meters_per_pixel": 0.035,   # Closer camera, smaller scale
    },
    {
        "camera_id": "CAM-2",
        "name": "Wall Street",
        "latitude": 40.7074,
        "longitude": -74.0113,
        "borough": "Manhattan",
        "zone_type": "financial_district",
        "description": "Wall Street - Financial District high-speed corridor",
        "video_url": "/wallstreet.mp4",
        "speed_limit": 30,           # 30 MPH city street
        "meters_per_pixel": 0.042,   # Mid-range camera
    },
    {
        "camera_id": "CAM-3",
        "name": "Barclays Center",
        "latitude": 40.6826,
        "longitude": -73.9754,
        "borough": "Brooklyn",
        "zone_type": "event_venue",
        "description": "Barclays Center - Atlantic Ave high traffic zone",
        "video_url": "/brooklyn.mp4",
        "speed_limit": 30,           # 30 MPH city street
        "meters_per_pixel": 0.04,    # Mid-range camera
    },
    {
        "camera_id": "CAM-4",
        "name": "Hudson Valley Albany",
        "latitude": 42.6526,
        "longitude": -73.7562,
        "borough": "Albany",
        "zone_type": "highway",
        "description": "Hudson Valley - I-87 high-speed corridor",
        "video_url": "/hudson valley albany.mp4",
        "speed_limit": 55,           # 55 MPH highway
        "meters_per_pixel": 0.06,    # Farther camera, larger scale
    },
    {
        "camera_id": "CAM-5",
        "name": "JFK Airport",
        "latitude": 40.6413,
        "longitude": -73.7781,
        "borough": "Queens",
        "zone_type": "airport",
        "description": "JFK Airport - Airport access road speed enforcement",
        "video_url": "/JFK_Airport_Speeding_Camry_Video.mp4",
        "speed_limit": 25,           # 25 MPH airport zone
        "meters_per_pixel": 0.045,   # Mid-range camera
    }
]


def seed_cameras():
    print("=" * 60)
    print("  CAMERA SEEDING WITH CALIBRATION VALUES")
    print("=" * 60)
    
    print("\nConnecting to database...")
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Check if cameras table exists and has new columns
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'cameras'
    """)
    columns = [row[0] for row in cur.fetchall()]
    print(f"Current columns: {columns}")
    
    # Add new columns if they don't exist
    if 'speed_limit' not in columns:
        print("Adding speed_limit column...")
        cur.execute("ALTER TABLE cameras ADD COLUMN speed_limit INTEGER DEFAULT 30")
    
    if 'meters_per_pixel' not in columns:
        print("Adding meters_per_pixel column...")
        cur.execute("ALTER TABLE cameras ADD COLUMN meters_per_pixel FLOAT DEFAULT 0.05")
    
    conn.commit()
    
    # Clear existing cameras (delete related violations first due to foreign key constraint)
    print("\nClearing existing data...")
    cur.execute("DELETE FROM ai_violations WHERE camera_id IN (SELECT camera_id FROM cameras)")
    print("  ✓ Cleared related ai_violations")
    cur.execute("DELETE FROM cameras")
    print("  ✓ Cleared existing cameras")
    
    # Insert cameras with calibration values
    for cam in CAMERAS:
        cur.execute("""
            INSERT INTO cameras (
                camera_id, name, latitude, longitude, borough, zone_type, 
                description, video_url, is_active, speed_limit, meters_per_pixel
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true, %s, %s)
        """, (
            cam["camera_id"], cam["name"], cam["latitude"], cam["longitude"],
            cam["borough"], cam["zone_type"], cam["description"], cam["video_url"],
            cam["speed_limit"], cam["meters_per_pixel"]
        ))
        print(f"  ✓ {cam['name']}: {cam['speed_limit']} MPH, {cam['meters_per_pixel']} m/px")
    
    conn.commit()
    
    # Verify
    print("\n" + "-" * 60)
    print("Cameras in database:")
    print("-" * 60)
    cur.execute("""
        SELECT camera_id, name, speed_limit, meters_per_pixel, video_url 
        FROM cameras ORDER BY camera_id
    """)
    for row in cur:
        print(f"  {row[0]}: {row[1]}")
        print(f"          Speed Limit: {row[2]} MPH")
        print(f"          Calibration: {row[3]} m/px")
        print(f"          Video: {row[4]}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("  ✓ Done! Cameras seeded with calibration values.")
    print("=" * 60)


if __name__ == "__main__":
    seed_cameras()
