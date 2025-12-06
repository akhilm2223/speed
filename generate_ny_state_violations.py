#!/usr/bin/env python3
"""
Fetch NY State traffic violations from data.ny.gov API.
Adds random coordinates (from CSV) and license plates to real violation data.

Data Source: https://data.ny.gov/resource/q4hy-kbtf.json
Dataset: NY State Traffic Tickets Issued (10M+ records)

Usage:
    python generate_ny_state_violations.py
"""
import csv
import os
import random
import string
from datetime import datetime

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIG
# =============================================================================

# NY State Open Data API (real traffic violations)
NY_STATE_API_URL = "https://data.ny.gov/resource/q4hy-kbtf.json"

# Coordinates file for adding locations
COORDINATES_FILE = "new_york_state_coordinates.csv"

# Target number of violations to fetch
TARGET_VIOLATIONS = 100_000
BATCH_SIZE = 50_000  # API batch size

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "traffic_violations_db"),
    "user": os.getenv("DB_USER", "myuser"),
    "password": os.getenv("DB_PASSWORD", "mypassword"),
}

# Map violation codes to our standard codes for risk scoring
VIOLATION_CODE_MAP = {
    "1180A": "1180A",   # 1-10 mph over
    "1180B": "1180B",   # 11-20 mph over  
    "1180C": "1180C",   # 21-30 mph over
    "1180D": "1180D",   # 31+ mph over
    "1180D12": "1180B", # Speed in Zone 11-30 -> map to 1180B
    "1180D13": "1180D", # Speed in Zone 31+ -> map to 1180D
    "1180E": "1180E",   # School zone
    "1180F": "1180F",   # Work zone
}

# States mapping (full name to abbreviation)
STATE_ABBREV = {
    "NEW YORK": "NY",
    "NEW JERSEY": "NJ",
    "CONNECTICUT": "CT",
    "PENNSYLVANIA": "PA",
    "MASSACHUSETTS": "MA",
    "CALIFORNIA": "CA",
    "FLORIDA": "FL",
    "TEXAS": "TX",
    "VIRGINIA": "VA",
    "MARYLAND": "MD",
    "OHIO": "OH",
    "ILLINOIS": "IL",
    "GEORGIA": "GA",
    "NORTH CAROLINA": "NC",
    "MICHIGAN": "MI",
}

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


def normalize_violation_code(code):
    """Normalize violation code to standard format."""
    if not code:
        return "1180B"  # Default
    code = code.upper().strip()
    
    # Direct mapping
    if code in VIOLATION_CODE_MAP:
        return VIOLATION_CODE_MAP[code]
    
    # Try to extract base code (1180A, 1180B, etc.)
    if code.startswith("1180"):
        for base in ["1180A", "1180B", "1180C", "1180D", "1180E", "1180F"]:
            if base in code:
                return base
        # Default to 1180B if just "1180" prefix
        return "1180B"
    
    return "1180B"  # Default


def normalize_state(state_name):
    """Convert full state name to abbreviation."""
    if not state_name:
        return "NY"
    state_upper = state_name.upper().strip()
    return STATE_ABBREV.get(state_upper, "NY")


def get_violation_description(code):
    """Get description for violation code."""
    descriptions = {
        "1180A": "Speed in Zone - 1-10 MPH Over",
        "1180B": "Speed in Zone - 11-20 MPH Over",
        "1180C": "Speed in Zone - 21-30 MPH Over",
        "1180D": "Speed in Zone - 31+ MPH Over",
        "1180E": "Speed in School Zone",
        "1180F": "Speed in Work Zone",
    }
    return descriptions.get(code, "Speeding Violation")


# =============================================================================
# FETCH DATA FROM NY STATE API
# =============================================================================

def fetch_violations_from_api():
    """Fetch speeding violations from NY State Open Data API."""
    all_data = []
    offset = 0
    
    print(f"\nFetching violations from NY State Open Data API...")
    print(f"  URL: {NY_STATE_API_URL}")
    print(f"  Target: {TARGET_VIOLATIONS:,} records\n")
    
    while len(all_data) < TARGET_VIOLATIONS:
        # Build query - filter for speeding violations (1180*)
        params = {
            "$where": "violation_charged_code LIKE '1180%'",
            "$order": "violation_year DESC, violation_month DESC",
            "$limit": BATCH_SIZE,
            "$offset": offset,
        }
        
        batch_num = (offset // BATCH_SIZE) + 1
        print(f"  Batch {batch_num}...", end=" ", flush=True)
        
        try:
            response = requests.get(NY_STATE_API_URL, params=params, timeout=120)
            response.raise_for_status()
            rows = response.json()
        except Exception as e:
            print(f"Error: {e}")
            break
        
        if not rows:
            print("No more data.")
            break
        
        all_data.extend(rows)
        print(f"got {len(rows):,} (total: {len(all_data):,})")
        
        if len(rows) < BATCH_SIZE:
            break
        
        offset += BATCH_SIZE
    
    return all_data[:TARGET_VIOLATIONS]


# =============================================================================
# PROCESS AND ENRICH DATA
# =============================================================================

def process_violations(raw_data, coordinates):
    """Process raw API data and add coordinates + license plates."""
    print(f"\nProcessing {len(raw_data):,} violations...")
    
    # Shuffle coordinates for random assignment
    random.shuffle(coordinates)
    
    violations = []
    plate_pool = []  # For repeat offenders
    
    for i, row in enumerate(raw_data):
        # Get coordinate (cycle through if needed)
        coord_idx = i % len(coordinates)
        lat, lon = coordinates[coord_idx]
        
        # Generate or reuse plate (5% repeat offender chance)
        if plate_pool and random.random() < 0.05:
            plate = random.choice(plate_pool)
        else:
            plate = generate_plate()
            plate_pool.append(plate)
            if len(plate_pool) > 1000:
                plate_pool = plate_pool[-500:]
        
        # Extract and normalize fields from API data
        violation_code = normalize_violation_code(row.get("violation_charged_code"))
        state_of_license = normalize_state(row.get("state_of_license"))
        
        # Parse year/month for issue_date
        try:
            year = int(row.get("violation_year", 2024))
            month = int(row.get("violation_month", 1))
            day = random.randint(1, 28)  # Random day since not in API
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            issue_date = datetime(year, month, day, hour, minute)
        except (ValueError, TypeError):
            issue_date = datetime(2024, 1, 1)
        
        # Parse age
        try:
            age = int(row.get("age_at_violation", 30))
        except (ValueError, TypeError):
            age = random.randint(18, 65)
        
        violation = {
            "plate_id": plate,
            "registration_state": state_of_license,
            "violation_code": violation_code,
            "violation_description": row.get("violation_description") or get_violation_description(violation_code),
            "violation_year": int(row.get("violation_year", 2024)),
            "violation_month": int(row.get("violation_month", 1)),
            "violation_dow": row.get("violation_dow", "MONDAY"),
            "age_at_violation": age,
            "gender": row.get("gender", "U"),
            "state_of_license": state_of_license,
            "police_agency": row.get("police_agency", "NYS Police"),
            "court": row.get("court", "NYC TVB"),
            "source": row.get("source", "TVB"),
            "latitude": lat,
            "longitude": lon,
            "issue_date": issue_date,
        }
        violations.append(violation)
        
        if (i + 1) % 10000 == 0:
            print(f"  Processed {i + 1:,} violations...")
    
    print(f"  Processed {len(violations):,} violations")
    return violations


# =============================================================================
# SAVE TO DATABASE
# =============================================================================

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
                v["plate_id"], v["registration_state"], "ny_state_api", v["violation_code"],
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


# =============================================================================
# MAIN
# =============================================================================

def main():
    import time
    
    print("=" * 70)
    print("  NY STATE TRAFFIC VIOLATIONS - REAL DATA FROM data.ny.gov")
    print("=" * 70)
    
    start_time = time.time()
    
    # Load coordinates
    print(f"\nLoading coordinates from {COORDINATES_FILE}...")
    coordinates = load_coordinates()
    print(f"  Loaded {len(coordinates):,} coordinates")
    
    if len(coordinates) < 1000:
        raise SystemExit(
            f"ERROR: Need at least 1,000 coordinates, found {len(coordinates):,}."
        )
    
    # Fetch real data from NY State API
    raw_data = fetch_violations_from_api()
    
    if not raw_data:
        print("No data fetched from API.")
        return
    
    fetch_time = time.time() - start_time
    print(f"\nFetched {len(raw_data):,} violations in {fetch_time:.1f}s")
    
    # Process and enrich with coordinates + plates
    process_start = time.time()
    violations = process_violations(raw_data, coordinates)
    process_time = time.time() - process_start
    
    # Save to database
    print("\nSaving to database...")
    db_start = time.time()
    save_to_database(violations)
    db_time = time.time() - db_start
    
    total_time = time.time() - start_time
    
    print("\n" + "=" * 70)
    print(f"  DONE in {total_time:.1f}s!")
    print(f"  (Fetch: {fetch_time:.1f}s, Process: {process_time:.1f}s, DB: {db_time:.1f}s)")
    print("=" * 70)
    
    # Print data source summary
    print("\n📊 Data Summary:")
    print(f"  - Source: NY State Open Data (data.ny.gov)")
    print(f"  - Dataset: Traffic Tickets Issued (q4hy-kbtf)")
    print(f"  - Real fields: violation_code, description, year, month, day_of_week,")
    print(f"                 age, gender, state_of_license, police_agency, court, source")
    print(f"  - Synthetic fields: license_plate (random NY format), coordinates (from CSV)")


if __name__ == "__main__":
    main()
