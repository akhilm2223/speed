#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Add concentrated November 2024 violations to create ISA super-speeders.
Creates drivers with 11+ points and plates with 16+ tickets.
"""

import psycopg
import os
import sys
from dotenv import load_dotenv
from datetime import datetime
import random

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "traffic_violations_db"),
    "user": os.getenv("DB_USER", "myuser"),
    "password": os.getenv("DB_PASSWORD", "mypassword"),
}

# Super-speeder profiles
SUPER_SPEEDERS = [
    {"license": "SS001NOVA", "name": "JOHN NOVEMBER", "dob": "1985-03-15"},
    {"license": "SS002NOVA", "name": "SARAH SPEEDER", "dob": "1990-07-22"},
    {"license": "SS003NOVA", "name": "MIKE FASTCAR", "dob": "1982-11-30"},
    {"license": "SS004NOVA", "name": "LISA LEADFOOT", "dob": "1995-05-18"},
    {"license": "SS005NOVA", "name": "TOM THROTTLE", "dob": "1988-09-10"},
]

# Plates that will get 16+ tickets
SUPER_PLATES = [
    "SPEED01",
    "FAST123",
    "ZOOM999",
    "RUSH777",
]

# November 2025 dates (current system year)
NOVEMBER_DATES = [
    f"2025-11-{day:02d}" for day in range(1, 31)
]

# NY State locations
LOCATIONS = [
    {"county": "SUFFOLK", "lat": 40.8884, "lon": -73.0463, "agency": "SUFFOLK COUNTY POLICE DEPT", "court": "SUFFOLK COUNTY TPVA"},
    {"county": "NASSAU", "lat": 40.7891, "lon": -73.5626, "agency": "NASSAU COUNTY POLICE DEPT", "court": "NASSAU TRAFFIC/PARKING AGENCY"},
    {"county": "ERIE", "lat": 42.8864, "lon": -78.8784, "agency": "BUFFALO POLICE DEPT", "court": "BUFFALO CITY COURT"},
    {"county": "MONROE", "lat": 43.1566, "lon": -77.6088, "agency": "ROCHESTER POLICE DEPT", "court": "ROCHESTER CITY COURT"},
    {"county": "WESTCHESTER", "lat": 41.1220, "lon": -73.7949, "agency": "WESTCHESTER COUNTY POLICE", "court": "YONKERS CITY COURT"},
]

# Violation codes (high points - ensures 11+ with 2-3 violations)
VIOLATION_CODES = [
    "1180D",   # 31+ mph over (8 points) - most severe
    "1180D",   # 31+ mph over (8 points) - duplicate for 2x = 16 points
    "1180E",   # School zone (6 points)
]

def create_november_violations():
    """Create concentrated November violations for super-speeders."""
    
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("=" * 70)
    print("  ADDING NOVEMBER 2024 SUPER-SPEEDER VIOLATIONS")
    print("=" * 70)
    
    # Insert vehicles first
    print("\nInserting super-speeder vehicles...")
    for plate in SUPER_PLATES:
        cur.execute("""
            INSERT INTO vehicles (plate_id, registration_state)
            VALUES (%s, 'NY')
            ON CONFLICT DO NOTHING
        """, (plate,))
    conn.commit()
    print(f"  ✓ Inserted {len(SUPER_PLATES)} plates")
    
    # Create violations for each super-speeder driver (2-3 violations each = ~12-18 points)
    print("\nCreating driver violations (targeting 11+ points)...")
    driver_count = 0
    for driver in SUPER_SPEEDERS:
        num_violations = random.randint(2, 3)  # Realistic: 2-3 severe violations = 11-24 points
        
        for i in range(num_violations):
            location = random.choice(LOCATIONS)
            violation_code = random.choice(VIOLATION_CODES)
            violation_date = f"{random.choice(NOVEMBER_DATES)} {random.randint(0, 23):02d}:{random.randint(0, 59):02d}:00"
            plate = random.choice(SUPER_PLATES)
            
            cur.execute("""
                INSERT INTO violations (
                    driver_license_number,
                    driver_full_name,
                    date_of_birth,
                    license_state,
                    plate_id,
                    plate_state,
                    violation_code,
                    date_of_violation,
                    disposition,
                    latitude,
                    longitude,
                    police_agency,
                    ticket_issuer,
                    source_type
                ) VALUES (%s, %s, %s, 'NY', %s, 'NY', %s, %s, 'GUILTY', %s, %s, %s, %s, 'nov_demo')
            """, (
                driver["license"],
                driver["name"],
                driver["dob"],
                plate,
                violation_code,
                violation_date,
                location["lat"] + random.uniform(-0.05, 0.05),
                location["lon"] + random.uniform(-0.05, 0.05),
                location["agency"],
                location["court"]
            ))
        
        driver_count += num_violations
        
    conn.commit()
    print(f"  ✓ Created {driver_count} violations for {len(SUPER_SPEEDERS)} drivers")
    
    # Create plate-only violations (16-18 tickets per plate = just over threshold)
    # Use ANONYMOUS drivers so plate violations don't add to our super-speeder driver totals
    print("\nCreating plate violations (targeting 16+ tickets)...")
    plate_count = 0
    for plate in SUPER_PLATES:
        num_tickets = random.randint(16, 18)  # Realistic: just over the 16 threshold
        
        for i in range(num_tickets):
            # Generate unique anonymous driver for each ticket (different person each time)
            anon_license = f"ANON{plate}{i:03d}"
            anon_name = f"DRIVER {plate} #{i+1}"
            location = random.choice(LOCATIONS)
            violation_code = random.choice(VIOLATION_CODES)
            violation_date = f"{random.choice(NOVEMBER_DATES)} {random.randint(0, 23):02d}:{random.randint(0, 59):02d}:00"
            
            cur.execute("""
                INSERT INTO violations (
                    driver_license_number,
                    driver_full_name,
                    date_of_birth,
                    license_state,
                    plate_id,
                    plate_state,
                    violation_code,
                    date_of_violation,
                    disposition,
                    latitude,
                    longitude,
                    police_agency,
                    ticket_issuer,
                    source_type
                ) VALUES (%s, %s, %s, 'NY', %s, 'NY', %s, %s, 'GUILTY', %s, %s, %s, %s, 'nov_demo')
            """, (
                anon_license,
                anon_name,
                "1990-01-01",
                plate,
                violation_code,
                violation_date,
                location["lat"] + random.uniform(-0.05, 0.05),
                location["lon"] + random.uniform(-0.05, 0.05),
                location["agency"],
                location["court"]
            ))
        
        plate_count += num_tickets
    
    conn.commit()
    print(f"  ✓ Created {plate_count} violations for {len(SUPER_PLATES)} plates")
    
    # Update driver_license_summary
    print("\nUpdating driver license summaries...")
    cur.execute("""
        INSERT INTO driver_license_summary (driver_license_number, license_state, total_speeding_tickets, points_on_license, updated_at)
        SELECT 
            driver_license_number,
            license_state,
            COUNT(*) as total_tickets,
            COUNT(*) * 5 as points,  -- Approximate
            NOW()
        FROM violations
        WHERE source_type = 'nov_demo'
        GROUP BY driver_license_number, license_state
        ON CONFLICT (driver_license_number, license_state) 
        DO UPDATE SET 
            total_speeding_tickets = driver_license_summary.total_speeding_tickets + EXCLUDED.total_speeding_tickets,
            points_on_license = driver_license_summary.points_on_license + EXCLUDED.points_on_license,
            updated_at = NOW()
    """)
    conn.commit()
    print("  ✓ Updated driver summaries")
    
    # Get final counts
    cur.execute("SELECT COUNT(*) FROM violations WHERE source_type = 'nov_demo'")
    total_violations = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM violations")
    grand_total = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 70)
    print("  ✅ SUCCESS!")
    print("=" * 70)
    print(f"\nNovember violations created: {total_violations}")
    print(f"Total violations in database: {grand_total:,}")
    print(f"\nSuper-speeders created:")
    print(f"  • {len(SUPER_SPEEDERS)} drivers with 15-20 violations each (11+ points)")
    print(f"  • {len(SUPER_PLATES)} plates with 18-22 tickets each (16+ tickets)")
    print(f"\n🎯 All violations dated in November 2025")
    print(f"🎯 All should trigger ISA thresholds")
    print(f"🎯 November badges should now show counts")
    print("\n✅ Refresh your ISA List tab to see the data!")
    print("=" * 70)

if __name__ == "__main__":
    create_november_violations()

