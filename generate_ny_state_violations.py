#!/usr/bin/env python3
"""
Generate 100k NY traffic violations using provided coordinates.
Uses the NY State traffic violation schema from data.ny.gov.

Usage:
    python generate_ny_violations.py
"""
import csv
import os
import random
import string
from datetime import datetime, timedelta

import psycopg
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIG
# =============================================================================

COORDINATES_FILE = "new_york_state_coordinates.csv"
TARGET_VIOLATIONS = 100_000

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "traffic_violations_db"),
    "user": os.getenv("DB_USER", "myuser"),
    "password": os.getenv("DB_PASSWORD", "mypassword"),
}

# NY Speeding Violation Codes (from NY Vehicle & Traffic Law Section 1180)
VIOLATION_CODES = [
    ("1180A", "Speed in Zone - 1-10 MPH Over"),
    ("1180B", "Speed in Zone - 11-20 MPH Over"),
    ("1180C", "Speed in Zone - 21-30 MPH Over"),
    ("1180D", "Speed in Zone - 31+ MPH Over"),
    ("1180E", "Speed in School Zone"),
    ("1180F", "Speed in Work Zone"),
]

# Weighted distribution (more minor violations)
VIOLATION_WEIGHTS = [30, 35, 20, 10, 3, 2]  # 1180A most common, 1180D least

# NY Police Agencies
POLICE_AGENCIES = [
    "NYS Police - Troop T",
    "NYS Police - Troop F", 
    "NYS Police - Troop K",
    "NYS Police - Troop G",
    "NYS Police - Troop B",
    "NYS Police - Troop C",
    "NYS Police - Troop D",
    "NYS Police - Troop E",
    "NYPD",
    "Nassau County PD",
    "Suffolk County PD",
    "Westchester County PD",
    "Erie County Sheriff",
    "Monroe County Sheriff",
    "Albany PD",
    "Buffalo PD",
    "Rochester PD",
    "Syracuse PD",
    "Yonkers PD",
]

# NY Courts
COURTS = [
    "Albany City Court",
    "Buffalo City Court",
    "Rochester City Court",
    "Syracuse City Court",
    "Yonkers City Court",
    "New Rochelle City Court",
    "Mount Vernon City Court",
    "Schenectady City Court",
    "Utica City Court",
    "Troy City Court",
    "NYC TVB - Manhattan",
    "NYC TVB - Brooklyn",
    "NYC TVB - Queens",
    "NYC TVB - Bronx",
    "NYC TVB - Staten Island",
    "Suffolk District Court",
    "Nassau District Court",
    "Westchester County Court",
]

# States (mostly NY, some neighboring)
STATES = ["NY"] * 85 + ["NJ"] * 5 + ["CT"] * 3 + ["PA"] * 3 + ["MA"] * 2 + ["VT", "NH"]

# Days of week
DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def generate_plate():
    """Generate a random NY-style license plate."""
    formats = [
        lambda: f"{''.join(random.choices(string.ascii_uppercase, k=3))}{''.join(random.choices(string.digits, k=4))}",  # ABC1234
        lambda: f"{''.join(random.choices(string.digits, k=3))}{''.join(random.choices(string.ascii_uppercase, k=3))}",  # 123ABC
        lambda: f"{''.join(random.choices(string.ascii_uppercase, k=2))}-{''.join(random.choices(string.digits, k=4))}",  # AB-1234
    ]
    return random.choice(formats)()


def generate_violation_date():
    """Generate a random date in 2024-2025."""
    start = datetime(2024, 1, 1)
    end = datetime(2025, 9, 30)
    delta = end - start
    random_days = random.randint(0, delta.days)
    random_seconds = random.randint(0, 86400)
    return start + timedelta(days=random_days, seconds=random_seconds)


def load_coordinates():
    """Load coordinates from CSV file."""
    coords = []
    with open(COORDINATES_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row['lat'])
                lon = float(row['lon'])
                coords.append((lat, lon))
            except (ValueError, KeyError):
                continue
    return coords


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("  NY STATE TRAFFIC VIOLATIONS GENERATOR")
    print("=" * 60)
    
    # Load coordinates
    print(f"\nLoading coordinates from {COORDINATES_FILE}...")
    coordinates = load_coordinates()
    print(f"  Loaded {len(coordinates):,} coordinates")
    
    if len(coordinates) < TARGET_VIOLATIONS:
        raise SystemExit(
            f"ERROR: Need at least {TARGET_VIOLATIONS:,} coordinates, "
            f"found {len(coordinates):,}."
        )
    
    # Use each coordinate at most once by shuffling and taking the first N
    print(
        "  Shuffling coordinates and taking first "
        f"{TARGET_VIOLATIONS:,} for one-to-one mapping..."
    )
    random.shuffle(coordinates)
    coord_slice = coordinates[:TARGET_VIOLATIONS]
    
    # Generate violations
    print(f"\nGenerating {TARGET_VIOLATIONS:,} violations...")
    
    violations = []
    plate_pool = []  # For repeat offenders
    
    for i in range(TARGET_VIOLATIONS):
        # Use each coordinate exactly once
        lat, lon = coord_slice[i]
        
        # Generate or reuse plate (5% repeat offender chance)
        if plate_pool and random.random() < 0.05:
            plate = random.choice(plate_pool)
        else:
            plate = generate_plate()
            plate_pool.append(plate)
            if len(plate_pool) > 1000:
                plate_pool = plate_pool[-500:]
        
        # Generate violation details
        code, description = random.choices(VIOLATION_CODES, weights=VIOLATION_WEIGHTS)[0]
        violation_date = generate_violation_date()
        
        violation = {
            "plate_id": plate,
            "registration_state": random.choice(STATES),
            "violation_code": code,
            "violation_description": description,
            "violation_year": violation_date.year,
            "violation_month": violation_date.month,
            "violation_dow": DAYS_OF_WEEK[violation_date.weekday()],
            "age_at_violation": random.randint(17, 85),
            "gender": random.choices(["M", "F", "U"], weights=[55, 40, 5])[0],
            "state_of_license": random.choice(STATES),
            "police_agency": random.choice(POLICE_AGENCIES),
            "court": random.choice(COURTS),
            "source": random.choices(["TSLED", "TVB"], weights=[70, 30])[0],
            "latitude": lat,
            "longitude": lon,
            "issue_date": violation_date,
        }
        violations.append(violation)
        
        if (i + 1) % 10000 == 0:
            print(f"  Generated {i + 1:,} violations...")
    
    print(f"  Generated {len(violations):,} violations")
    
    # Save to database
    print("\nSaving to database...")
    save_to_database(violations)
    
    print("\n" + "=" * 60)
    print("  DONE!")
    print("=" * 60)


def save_to_database(violations):
    """Save violations to PostgreSQL database (APPENDS to existing data)."""
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Check if tables exist, create if not (but don't drop existing data!)
    print("  Checking tables...")
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'violations'
        )
    """)
    tables_exist = cur.fetchone()[0]
    
    if not tables_exist:
        print("  Tables don't exist - creating them...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                plate_id VARCHAR(16) NOT NULL,
                registration_state VARCHAR(10) NOT NULL,
                PRIMARY KEY (plate_id, registration_state)
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                violation_id BIGSERIAL PRIMARY KEY,
                plate_id VARCHAR(16) NOT NULL,
                registration_state VARCHAR(10) NOT NULL,
                source_type VARCHAR(32) DEFAULT 'police_stop',
                violation_code VARCHAR(64) NOT NULL,
                violation_description VARCHAR(255),
                violation_year INTEGER,
                violation_month INTEGER,
                violation_dow VARCHAR(16),
                age_at_violation INTEGER,
                gender VARCHAR(1),
                state_of_license VARCHAR(64),
                police_agency VARCHAR(128),
                court VARCHAR(128),
                source VARCHAR(16),
                latitude DECIMAL(10, 8),
                longitude DECIMAL(11, 8),
                issue_date TIMESTAMPTZ,
                violation_location VARCHAR(255),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                FOREIGN KEY (plate_id, registration_state) 
                    REFERENCES vehicles (plate_id, registration_state) ON DELETE CASCADE
            )
        """)
        conn.commit()
        print("  Tables created.")
    else:
        # Get current counts
        cur.execute("SELECT COUNT(*) FROM violations")
        existing_count = cur.fetchone()[0]
        print(f"  Tables exist - appending to {existing_count:,} existing violations")
        
        # Add missing columns if they don't exist (for compatibility with ingest.py schema)
        columns_to_add = [
            ("violation_year", "INTEGER"),
            ("violation_month", "INTEGER"),
            ("violation_dow", "VARCHAR(16)"),
            ("age_at_violation", "INTEGER"),
            ("gender", "VARCHAR(1)"),
            ("state_of_license", "VARCHAR(64)"),
            ("police_agency", "VARCHAR(128)"),
            ("court", "VARCHAR(128)"),
            ("source", "VARCHAR(16)"),
            ("latitude", "DECIMAL(10, 8)"),
            ("longitude", "DECIMAL(11, 8)"),
        ]
        for col_name, col_type in columns_to_add:
            try:
                cur.execute(f"ALTER TABLE violations ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            except Exception:
                pass  # Column might already exist
        conn.commit()
    
    # Insert vehicles (with ON CONFLICT to handle duplicates)
    print("  Inserting vehicles...")
    vehicles = set((v["plate_id"], v["registration_state"]) for v in violations)
    vehicle_list = list(vehicles)
    
    for i in range(0, len(vehicle_list), 5000):
        batch = vehicle_list[i:i + 5000]
        cur.executemany(
            "INSERT INTO vehicles (plate_id, registration_state) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            batch
        )
    conn.commit()
    print(f"    Inserted {len(vehicles):,} vehicles (duplicates skipped)")
    
    # Insert violations
    print("  Inserting violations...")
    inserted = 0
    for i in range(0, len(violations), 5000):
        batch = violations[i:i + 5000]
        for v in batch:
            location = f"({v['latitude']}, {v['longitude']})"
            cur.execute("""
                INSERT INTO violations (
                    plate_id, registration_state, source_type, violation_code, 
                    violation_description, violation_year, violation_month, violation_dow,
                    age_at_violation, gender, state_of_license, police_agency, court, source,
                    latitude, longitude, issue_date, violation_location
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                v["plate_id"], v["registration_state"], "ny_state_generated", v["violation_code"],
                v["violation_description"], v["violation_year"], v["violation_month"], v["violation_dow"],
                v["age_at_violation"], v["gender"], v["state_of_license"], v["police_agency"], 
                v["court"], v["source"], v["latitude"], v["longitude"], v["issue_date"], location
            ))
        conn.commit()
        inserted += len(batch)
        print(f"    Progress: {inserted:,}/{len(violations):,}")
    
    # Create indexes (IF NOT EXISTS to avoid errors)
    print("  Creating indexes...")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_violations_plate ON violations(plate_id, registration_state)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_violations_code ON violations(violation_code)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_violations_date ON violations(issue_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_violations_location ON violations(latitude, longitude)")
    conn.commit()
    
    # Final count
    cur.execute("SELECT COUNT(*) FROM violations")
    total_count = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    print(f"  Inserted {inserted:,} NY State violations")
    print(f"  Total violations in database: {total_count:,}")


if __name__ == "__main__":
    main()

