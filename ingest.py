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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
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

API_URLS = [
    ("https://data.cityofnewyork.us/resource/57p3-pdcj.json", "Moving Violation Summons", True),
    ("https://data.cityofnewyork.us/resource/bme5-7ty4.json", "Moving Violation B Summons Historic", False),
]

# Pool of plates for generating repeat offenders (small chance of reuse)
REPEAT_OFFENDER_PLATES = []
REPEAT_OFFENDER_CHANCE = 0.05  # 5% chance to reuse an existing plate


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
# PLATE GENERATION (for APIs without plate data)
# =============================================================================

def generate_random_plate():
    """Generate a random NY-style license plate (ABC1234 format)."""
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    numbers = ''.join(random.choices(string.digits, k=4))
    return f"{letters}{numbers}"


def get_or_generate_plate():
    """Get a plate - either reuse an existing one (repeat offender) or generate new."""
    global REPEAT_OFFENDER_PLATES
    
    # Small chance to reuse an existing plate (repeat offender)
    if REPEAT_OFFENDER_PLATES and random.random() < REPEAT_OFFENDER_CHANCE:
        return random.choice(REPEAT_OFFENDER_PLATES)
    
    # Generate new plate
    new_plate = generate_random_plate()
    
    # Add to pool for potential future reuse
    REPEAT_OFFENDER_PLATES.append(new_plate)
    
    # Keep pool manageable (last 500 plates)
    if len(REPEAT_OFFENDER_PLATES) > 500:
        REPEAT_OFFENDER_PLATES = REPEAT_OFFENDER_PLATES[-500:]
    
    return new_plate


def get_random_state():
    """Get a random state - mostly NY, occasionally others."""
    # 85% NY, 15% other nearby states
    if random.random() < 0.85:
        return "NY"
    else:
        return random.choice(["NJ", "CT", "PA", "MA", "FL", "CA", "TX"])


# =============================================================================
# FETCH DATA FROM API
# =============================================================================

def fetch_violations_from_api(api_url, source_name, has_plate_fields, max_records):
    """Fetch speeding violations from a single NYC Open Data API endpoint."""
    all_data = []
    last_date = None
    batch = 1
    
    print(f"\nFetching from {source_name} (max {max_records:,})...")
    
    while len(all_data) < max_records:
        # Speeding codes start with 1180
        where = "violation_code LIKE '1180%'"
        if last_date:
            where += f" AND violation_date < '{last_date}'"
        
        # Select fields based on what's available
        if has_plate_fields:
            select_fields = ("evnt_key, reg_plate_num, reg_state_cd, violation_date, "
                           "violation_time, violation_code, city_nm, rpt_owning_cmd, "
                           "latitude, longitude")
        else:
            select_fields = ("evnt_key, violation_date, violation_time, violation_code, "
                           "city_nm, rpt_owning_cmd, latitude, longitude")
        
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
        
        response = requests.get(api_url, params=params, timeout=120)
        response.raise_for_status()
        rows = response.json()
        
        if not rows:
            print("Done!")
            break
        
        # Generate plate/state for records that don't have them
        # Also tag each row with its source
        for row in rows:
            row["_source"] = source_name
            if not has_plate_fields:
                row["reg_plate_num"] = get_or_generate_plate()
                row["reg_state_cd"] = get_random_state()
        
        all_data.extend(rows)
        print(f"got {len(rows):,} (total: {len(all_data):,})")
        
        last_date = rows[-1].get("violation_date")
        
        if len(rows) < limit:
            break
        
        batch += 1
    
    return all_data[:max_records]  # Ensure we don't exceed max


def fetch_all_violations():
    """Fetch speeding violations from all NYC Open Data API endpoints (parallel)."""
    # Fetch extra to account for ~30% invalid records (missing coordinates)
    fetch_target = int(MAX_VALID_RECORDS * FETCH_MULTIPLIER)
    print(f"\nFetching speeding violations from NYC Open Data (target {MAX_VALID_RECORDS:,} valid)...\n")
    
    all_data = []
    
    # Fetch from all sources in parallel
    with ThreadPoolExecutor(max_workers=len(API_URLS)) as executor:
        futures = {}
        for api_url, source_name, has_plate_fields in API_URLS:
            future = executor.submit(
                fetch_violations_from_api, 
                api_url, source_name, has_plate_fields, fetch_target
            )
            futures[future] = source_name
        
        for future in as_completed(futures):
            source_name = futures[future]
            try:
                data = future.result()
                all_data.extend(data)
                print(f"  Total from {source_name}: {len(data):,} violations\n")
            except Exception as e:
                print(f"  Error from {source_name}: {e}")
    
    return all_data


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_violation_description(violation_code):
    """Map violation code to human-readable description."""
    code = str(violation_code or "").strip().upper()
    
    # NYC Speeding Violation Codes
    descriptions = {
        "1180A": "Speeding 1-10 mph over limit",
        "1180B": "Speeding 11-20 mph over limit",
        "1180C": "Speeding 21-30 mph over limit",
        "1180D": "Speeding 31+ mph over limit (Excessive Speed)",
        "1180E": "Speeding in school zone",
        "1180F": "Speeding in work zone",
    }
    
    # Return specific description or generic one
    if code in descriptions:
        return descriptions[code]
    elif code.startswith("1180"):
        return "Speeding violation"
    else:
        return "Traffic violation"

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


def format_location(row):
    """Format location as readable string."""
    parts = []
    if row.get("city_nm"):
        parts.append(row["city_nm"])
    if row.get("latitude") and row.get("longitude"):
        parts.append(f"({row['latitude']}, {row['longitude']})")
    if row.get("rpt_owning_cmd"):
        parts.append(f"Precinct: {row['rpt_owning_cmd']}")
    return ", ".join(parts) if parts else None


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
            print("Tables dropped.")
    
    # Apply schema
    if SCHEMA_PATH.exists():
        print("Applying schema...")
        with psycopg.connect(**DB_CONFIG, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_PATH.read_text())
                print("Tables created.")


def prepare_record(row):
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
    
    issue_date = parse_datetime(row.get("violation_date"), row.get("violation_time"))
    violation_code = row.get("violation_code")
    
    vehicle = (plate, state)
    violation = (
        plate, state, "police_stop",
        violation_code,
        get_violation_description(violation_code),
        issue_date,
        format_location(row),
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
    
    for row in violations:
        source = row.get("_source", "Unknown")
        if source not in source_stats:
            source_stats[source] = {"valid": 0, "invalid": 0}
        
        result = prepare_record(row)
        if result is None:
            source_stats[source]["invalid"] += 1
            continue
        
        source_stats[source]["valid"] += 1
        vehicle, violation = result
        vehicles.add(vehicle)
        violation_records.append(violation)
    
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
        # Rebuild vehicles set from limited violations
        vehicles = set((v[0], v[1]) for v in violation_records)
    
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
                plate_id, registration_state, source_type,
                violation_code, violation_description, issue_date, violation_location
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            batch
        )
        inserted += len(batch)
        if (i + DB_BATCH_SIZE) % 20000 == 0 or i + DB_BATCH_SIZE >= len(violation_records):
            print(f"    Progress: {inserted:,}/{len(violation_records):,}")
        conn.commit()
    
    cur.close()
    conn.close()
    
    print(f"\nDatabase: Inserted {inserted:,} violations")


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
    
    # 1. Fetch data from API (parallel, limited)
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
