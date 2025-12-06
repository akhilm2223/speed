#!/usr/bin/env python3
"""
Quick database check and fix script
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

def check_database():
    """Check database status."""
    try:
        conn = psycopg.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print("\n" + "="*60)
        print("  DATABASE STATUS CHECK")
        print("="*60 + "\n")
        
        # Check violations
        cur.execute("SELECT COUNT(*) FROM violations")
        violations_count = cur.fetchone()[0]
        print(f"✓ Violations: {violations_count:,}")
        
        # Check vehicles
        cur.execute("SELECT COUNT(*) FROM vehicles")
        vehicles_count = cur.fetchone()[0]
        print(f"✓ Vehicles: {vehicles_count:,}")
        
        # Check cameras
        cur.execute("SELECT COUNT(*) FROM cameras")
        cameras_count = cur.fetchone()[0]
        print(f"✓ Cameras: {cameras_count}")
        
        # Check driver summaries
        cur.execute("SELECT COUNT(*) FROM driver_license_summary")
        drivers_count = cur.fetchone()[0]
        print(f"✓ Driver Summaries: {drivers_count:,}")
        
        # Check DMV alerts
        cur.execute("SELECT COUNT(*) FROM dmv_alerts")
        alerts_count = cur.fetchone()[0]
        print(f"✓ DMV Alerts: {alerts_count}")
        
        # Check AI violations
        cur.execute("SELECT COUNT(*) FROM ai_violations")
        ai_violations_count = cur.fetchone()[0]
        print(f"✓ AI Violations: {ai_violations_count}")
        
        # Check AI violations with screenshots
        cur.execute("SELECT COUNT(*) FROM ai_violations WHERE screenshot_path IS NOT NULL")
        ai_with_screenshots = cur.fetchone()[0]
        print(f"✓ AI Violations with Screenshots: {ai_with_screenshots}")
        
        # Show recent AI violations with screenshots
        if ai_with_screenshots > 0:
            print("\n  Recent AI Violations with Screenshots:")
            cur.execute("""
                SELECT camera_id, plate_id, speed_detected, screenshot_path 
                FROM ai_violations 
                WHERE screenshot_path IS NOT NULL 
                ORDER BY violation_id DESC 
                LIMIT 5
            """)
            for row in cur.fetchall():
                print(f"    {row[0]}: {row[1]} @ {row[2]} MPH - {row[3]}")
        
        print("\n" + "="*60)
        
        if violations_count == 0:
            print("\n⚠ WARNING: No violations in database!")
            print("\nTo load data, run:")
            print("  python generate_ny_state_violations.py")
            print("  python seed_cameras_simple.py")
        else:
            print("\n✓ Database looks good!")
        
        print("="*60 + "\n")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Database error: {e}\n")
        print("Make sure PostgreSQL is running:")
        print("  docker ps")
        print("\nIf not running, start it:")
        print("  docker start <container_id>")

if __name__ == "__main__":
    check_database()
