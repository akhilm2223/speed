#!/usr/bin/env python3
"""
Fetch speeding violations from NYC Open Data (max 100k records).
Stores data in PostgreSQL database with optimized batch inserts.

Usage:
    python ingest.py
"""
import os
import random
import string
from datetime import datetime, timedelta, date
from pathlib import Path

import psycopg
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# CONFIG
# =============================================================================

MAX_VALID_RECORDS = 100_000  # Target valid records (with coordinates)
FETCH_MULTIPLIER = 1.5       # Fetch extra to account for invalid records
BATCH_SIZE = 50_000          # API batch size
DB_BATCH_SIZE = 5000         # Database insert batch size

API_URL = "https://data.cityofnewyork.us/resource/57p3-pdcj.json"
API_SOURCE_NAME = "Moving Violation Summons"


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "traffic_violations_db"),
    "user": os.getenv("DB_USER", "myuser"),
    "password": os.getenv("DB_PASSWORD", "mypassword"),
}

# Output paths
PROJECT_ROOT = Path(__file__).parent
# Main DB schema now lives in sql/schema.sql
SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"


# =============================================================================
# DRIVER DATA GENERATION
# =============================================================================

def generate_driver_license_number():
    """Generate a random NY driver license number (format: 9 digits)."""
    return ''.join(random.choices(string.digits, k=9))


def generate_driver_name():
    """Generate a random driver name."""
    first_names = ["JOHN", "JANE", "MICHAEL", "SARAH", "DAVID", "EMILY", "ROBERT", "JESSICA",
                   "WILLIAM", "ASHLEY", "RICHARD", "AMANDA", "JOSEPH", "MELISSA", "THOMAS", "NICOLE",
                   "CHRISTOPHER", "MICHELLE", "CHARLES", "KIMBERLY", "DANIEL", "AMY", "MATTHEW", "ANGELA"]
    last_names = ["SMITH", "JOHNSON", "WILLIAMS", "BROWN", "JONES", "GARCIA", "MILLER", "DAVIS",
                  "RODRIGUEZ", "MARTINEZ", "HERNANDEZ", "LOPEZ", "WILSON", "ANDERSON", "THOMAS", "TAYLOR"]
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def generate_date_of_birth():
    """Generate a random date of birth (age 18-75)."""
    age = random.randint(18, 75)
    birth_year = datetime.now().year - age
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return date(birth_year, month, day)


# =============================================================================
# FETCH DATA FROM API
# =============================================================================

def fetch_violations_from_api(max_records):
    """Fetch speeding violations from NYC Open Data API endpoint."""
    all_data = []
    last_date = None
    batch = 1
    
    print(f"\nFetching from {API_SOURCE_NAME} (max {max_records:,})...")
    
    while len(all_data) < max_records:
        # Speeding codes start with 1180
        where = "violation_code LIKE '1180%'"
        if last_date:
            where += f" AND violation_date < '{last_date}'"
        
        # Select fields (API has plate fields)
        select_fields = ("evnt_key, reg_plate_num, reg_state_cd, violation_date, "
                         "violation_time, violation_code, city_nm, rpt_owning_cmd, "
                         "latitude, longitude")
        
        # Only fetch what we need
        remaining = max_records - len(all_data)
        limit = min(BATCH_SIZE, remaining)
        
        params = {
            "$select": select_fields,
            "$where": where,
            "$order": "violation_date DESC",
            "$limit": limit,
        }
        
        print(f"  Batch {batch}...", end=" ", flush=True)
        
        response = requests.get(API_URL, params=params, timeout=120)
        response.raise_for_status()
        rows = response.json()
        
        if not rows:
            print("Done!")
            break
        
        # Tag each row with its source
        for row in rows:
            row["_source"] = API_SOURCE_NAME
        
        all_data.extend(rows)
        print(f"got {len(rows):,} (total: {len(all_data):,})")
        
        last_date = rows[-1].get("violation_date")
        
        if len(rows) < limit:
            break
        
        batch += 1
    
    return all_data[:max_records]  # Ensure we don't exceed max


def fetch_all_violations():
    """Fetch speeding violations from NYC Open Data API endpoint."""
    # Fetch extra to account for ~30% invalid records (missing coordinates)
    fetch_target = int(MAX_VALID_RECORDS * FETCH_MULTIPLIER)
    print(f"\nFetching speeding violations from NYC Open Data (target {MAX_VALID_RECORDS:,} valid)...\n")
    
    data = fetch_violations_from_api(fetch_target)
    print(f"  Total from {API_SOURCE_NAME}: {len(data):,} violations\n")
    
    return data


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def is_valid_location(row):
    """Check if row has valid coordinates."""
    try:
        lat = float(row.get("latitude", 0))
        lon = float(row.get("longitude", 0))
        return lat != 0 and lon != 0
    except:
        return False


def parse_datetime(date_str, time_str):
    """Parse date and time into datetime object."""
    if not date_str:
        return None
    try:
        date = date_str.split("T")[0]
        if time_str:
            if len(time_str) == 5:
                time_str += ":00"
            return datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %H:%M:%S")
        return datetime.strptime(date, "%Y-%m-%d")
    except:
        return None


# =============================================================================
# SAVE TO DATABASE
# =============================================================================

def setup_database():
    """Create database and tables. Drops existing tables for fresh start."""
    db_name = DB_CONFIG["dbname"]
    
    # Create database if it doesn't exist
    admin_config = {**DB_CONFIG, "dbname": "postgres"}
    with psycopg.connect(**admin_config, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if not cur.fetchone():
                print(f"Creating database '{db_name}'...")
                cur.execute(f'CREATE DATABASE "{db_name}"')
    
    # Drop and recreate tables
    print("Dropping existing tables...")
    with psycopg.connect(**DB_CONFIG, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS violations CASCADE")
            cur.execute("DROP TABLE IF EXISTS vehicles CASCADE")
            cur.execute("DROP TABLE IF EXISTS dmv_alerts CASCADE")
            cur.execute("DROP TABLE IF EXISTS ai_violations CASCADE")
            cur.execute("DROP TABLE IF EXISTS ai_detections CASCADE")  # Cleanup old table
            cur.execute("DROP TABLE IF EXISTS cameras CASCADE")
            print("Tables dropped.")
    
    # Apply schema
    if SCHEMA_PATH.exists():
        print("Applying schema...")
        with psycopg.connect(**DB_CONFIG, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_PATH.read_text())
                print("Tables created.")


def prepare_record(row, driver_pool=None):
    """Prepare a single record for batch insert. Returns (vehicle_tuple, violation_tuple) or None if invalid."""
    # Require valid coordinates
    if not is_valid_location(row):
        return None
    
    plate = (row.get("reg_plate_num") or "").strip()
    state = (row.get("reg_state_cd") or "").strip()
    
    # Skip if plate or state is empty or null
    plate_upper = plate.upper().replace("(", "").replace(")", "")
    state_upper = state.upper().replace("(", "").replace(")", "")
    if not plate or not state or plate_upper == "NULL" or state_upper == "NULL":
        return None
    
    # Truncate to match schema limits
    state = state[:10]
    plate = plate[:16]
    
    date_of_violation = parse_datetime(row.get("violation_date"), row.get("violation_time"))
    violation_code = row.get("violation_code")
    
    # Generate or reuse driver information (5% chance to reuse existing driver)
    if driver_pool and random.random() < 0.05:
        # Reuse existing driver (repeat offender)
        driver_license_number, driver_full_name, date_of_birth = random.choice(driver_pool)
    else:
        # Generate new driver
        driver_license_number = generate_driver_license_number()
        driver_full_name = generate_driver_name()
        date_of_birth = generate_date_of_birth()
        # Add to pool for potential reuse
        if driver_pool is not None:
            driver_pool.append((driver_license_number, driver_full_name, date_of_birth))
            if len(driver_pool) > 1000:
                driver_pool[:] = driver_pool[-500:]  # Keep last 500
    
    # Generate disposition
    disposition_options = ["GUILTY", "NOT GUILTY","DISMISSED"]
    disposition = random.choice(disposition_options)
    
    # Get coordinates
    lat = float(row.get("latitude", 0))
    lon = float(row.get("longitude", 0))
    
    vehicle = (plate, state)
    
    # Always use "NYC Police Department" for police_agency
    police_agency = "NYC Police Department"
    ticket_issuer = "NYC Dept of Finance"  # NYC Open Data is all NYC
    source_type = "nyc_open_data"
    
    violation = (
        driver_license_number,
        driver_full_name,
        date_of_birth,
        state,  # license_state
        plate,  # plate_id
        state,  # plate_state
        violation_code,
        date_of_violation,
        disposition,
        lat,
        lon,
        police_agency,
        ticket_issuer,
        source_type,
    )
    
    return vehicle, violation


def save_to_database(violations):
    """Save violations to PostgreSQL database using fast batch inserts."""
    print(f"\nSaving {len(violations):,} records to database...")
    
    setup_database()
    
    # Pre-process all records and track per-source stats
    print("  Preparing records...")
    vehicles = set()
    violation_records = []
    source_stats = {}  # {source_name: {"valid": 0, "invalid": 0}}
    driver_pool = []  # For repeat offender drivers: [(license, name, dob), ...]
    
    for row in violations:
        source = row.get("_source", "Unknown")
        if source not in source_stats:
            source_stats[source] = {"valid": 0, "invalid": 0}
        
        result = prepare_record(row, driver_pool)
        if result is None:
            source_stats[source]["invalid"] += 1
            continue
        
        source_stats[source]["valid"] += 1
        vehicle, violation = result
        vehicles.add(vehicle)
        violation_records.append(violation)
        
    # Rebuild vehicles set from violations (plate_id is at index 4, plate_state is at index 5)
    vehicles = set((v[4], v[5]) for v in violation_records)
    
    # Print per-source stats
    print("\n  Per-source breakdown:")
    for source, stats in source_stats.items():
        total = stats["valid"] + stats["invalid"]
        pct = (stats["valid"] / total * 100) if total > 0 else 0
        print(f"    {source}: {stats['valid']:,} valid, {stats['invalid']:,} invalid ({pct:.1f}% valid)")
    
    # Limit to target
    total_valid = len(violation_records)
    total_invalid = sum(s["invalid"] for s in source_stats.values())
    if len(violation_records) > MAX_VALID_RECORDS:
        violation_records = violation_records[:MAX_VALID_RECORDS]
        # Rebuild vehicles set from limited violations (plate_id is at index 4, plate_state is at index 5)
        vehicles = set((v[4], v[5]) for v in violation_records)
    
    print(f"\n  Total valid: {len(violation_records):,}, Total invalid: {total_invalid:,}")
    
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Batch insert vehicles using executemany with COPY-like performance
    print(f"  Inserting {len(vehicles):,} vehicles...")
    vehicle_list = list(vehicles)
    for i in range(0, len(vehicle_list), DB_BATCH_SIZE):
        batch = vehicle_list[i:i + DB_BATCH_SIZE]
        cur.executemany(
            "INSERT INTO vehicles (plate_id, registration_state) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            batch
        )
    conn.commit()
    
    # Batch insert violations
    print(f"  Inserting {len(violation_records):,} violations...")
    inserted = 0
    for i in range(0, len(violation_records), DB_BATCH_SIZE):
        batch = violation_records[i:i + DB_BATCH_SIZE]
        cur.executemany(
            """INSERT INTO violations (
                driver_license_number, driver_full_name, date_of_birth, license_state,
                plate_id, plate_state, violation_code, date_of_violation,
                disposition, latitude, longitude,
                police_agency, ticket_issuer, source_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            batch
        )
        inserted += len(batch)
        if (i + DB_BATCH_SIZE) % 20000 == 0 or i + DB_BATCH_SIZE >= len(violation_records):
            print(f"    Progress: {inserted:,}/{len(violation_records):,}")
        conn.commit()
    
    # Populate driver_license_summary table
    print("  Updating driver_license_summary...")
    cur.execute("""
        INSERT INTO driver_license_summary (driver_license_number, license_state, total_speeding_tickets, points_on_license)
        SELECT 
            driver_license_number,
            license_state,
            COUNT(*),
            SUM(CASE 
                WHEN disposition = 'GUILTY' THEN
                    CASE 
                        WHEN violation_code = '1180A' THEN 3
                        WHEN violation_code = '1180B' THEN 4
                        WHEN violation_code = '1180C' THEN 6
                        WHEN violation_code = '1180D' THEN 8
                        WHEN violation_code IN ('1180E', '1180F') THEN 7
                        ELSE 0
                    END
                ELSE 0
            END)
        FROM violations
        WHERE violation_code LIKE '1180%'
        GROUP BY driver_license_number, license_state
        ON CONFLICT (driver_license_number, license_state) DO UPDATE SET
            total_speeding_tickets = EXCLUDED.total_speeding_tickets,
            points_on_license = EXCLUDED.points_on_license,
            updated_at = NOW()
    """)
    conn.commit()
    
    cur.execute("SELECT COUNT(*) FROM driver_license_summary")
    summary_count = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    print(f"\nDatabase: Inserted {inserted:,} violations")
    print(f"Database: Updated {summary_count:,} driver license summaries")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import time
    
    print("=" * 50)
    print("  STOP SUPER SPEEDERS - DATA INGESTION")
    print(f"  Target: {MAX_VALID_RECORDS:,} valid records")
    print("=" * 50)
    
    start_time = time.time()
    
    print("\nDropping existing data and fetching fresh from API...")
    
    # 1. Fetch data from API
    data = fetch_all_violations()
    
    if not data:
        print("No data fetched.")
        exit(1)
    
    fetch_time = time.time() - start_time
    print(f"\nFetched {len(data):,} total violations in {fetch_time:.1f}s")
    
    # 2. Save to database (batch inserts)
    db_start = time.time()
    save_to_database(data)
    db_time = time.time() - db_start
    
    total_time = time.time() - start_time
    
    print("\n" + "=" * 50)
    print(f"  DONE in {total_time:.1f}s!")
    print(f"  (Fetch: {fetch_time:.1f}s, DB: {db_time:.1f}s)")
    print("=" * 50)

