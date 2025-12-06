#!/usr/bin/env python3
"""
Fetch all speeding violations from NYC Open Data.
Stores data in PostgreSQL database.

Usage:
    python ingest.py
"""
import os
import re
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

API_URL = "https://data.cityofnewyork.us/resource/57p3-pdcj.json"

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "traffic_violations_db"),
    "user": os.getenv("DB_USER", "myuser"),
    "password": os.getenv("DB_PASSWORD", "mypassword"),
}

# Output paths
PROJECT_ROOT = Path(__file__).parent
SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"


# =============================================================================
# FETCH DATA FROM API
# =============================================================================

def fetch_all_violations():
    """Fetch ALL speeding violations from NYC Open Data API."""
    all_data = []
    last_date = None
    batch = 1
    
    print("\nFetching all speeding violations from NYC Open Data...\n")
    
    while True:
        # Speeding codes start with 1180
        where = "violation_code LIKE '1180%'"
        if last_date:
            where += f" AND violation_date < '{last_date}'"
        
        params = {
            "$select": "evnt_key, reg_plate_num, reg_state_cd, violation_date, "
                       "violation_time, violation_code, city_nm, rpt_owning_cmd, "
                       "latitude, longitude",
            "$where": where,
            "$order": "violation_date DESC",
            "$limit": 50000,
        }
        
        print(f"Batch {batch}...", end=" ", flush=True)
        
        response = requests.get(API_URL, params=params, timeout=60)
        response.raise_for_status()
        rows = response.json()
        
        if not rows:
            print("Done!")
            break
        
        all_data.extend(rows)
        print(f"got {len(rows):,} (total: {len(all_data):,})")
        
        last_date = rows[-1].get("violation_date")
        
        if len(rows) < 50000:
            break
        
        batch += 1
    
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


def save_to_database(violations):
    """Save violations to PostgreSQL database. Skips duplicates."""
    print(f"\nSaving to database...")
    
    setup_database()
    
    inserted = 0
    skipped_invalid = 0
    skipped_duplicate = 0
    
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    for i, row in enumerate(violations, 1):
        # Skip invalid data
        if not is_valid_location(row):
            skipped_invalid += 1
            continue
        
        plate = (row.get("reg_plate_num") or "").strip()
        state = (row.get("reg_state_cd") or "").strip()
        
        # Skip if plate or state is empty or null (including variations like "(null)", "NULL", etc.)
        plate_upper = plate.upper().replace("(", "").replace(")", "")
        state_upper = state.upper().replace("(", "").replace(")", "")
        if not plate or not state or plate_upper == "NULL" or state_upper == "NULL":
            skipped_invalid += 1
            continue
        
        # Truncate state to max 10 characters (matching schema)
        if len(state) > 10:
            state = state[:10]
        
        # Truncate plate to max 16 characters (matching schema)
        if len(plate) > 16:
            plate = plate[:16]
        
        # Insert vehicle (ignore if exists)
        cur.execute("""
            INSERT INTO vehicles (plate_id, registration_state)
            VALUES (%s, %s) ON CONFLICT DO NOTHING
        """, (plate, state))
        
        # Insert violation - use evnt_key to prevent duplicates
        evnt_key = row.get("evnt_key")
        issue_date = parse_datetime(row.get("violation_date"), row.get("violation_time"))
        
        # Check if this violation already exists (by evnt_key if available, or by plate+date+code)
        if evnt_key:
            cur.execute("""
                SELECT 1 FROM violations 
                WHERE plate_id = %s AND registration_state = %s 
                  AND violation_code = %s AND issue_date = %s
                LIMIT 1
            """, (plate, state, row.get("violation_code"), issue_date))
            if cur.fetchone():
                skipped_duplicate += 1
                continue
        
        # Insert new violation
        violation_code = row.get("violation_code")
        violation_description = get_violation_description(violation_code)
        
        cur.execute("""
            INSERT INTO violations (
                plate_id, registration_state, source_type,
                violation_code, violation_description, issue_date, violation_location
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            plate, state, "police_stop",
            violation_code,
            violation_description,
            issue_date,
            format_location(row),
        ))
        
        inserted += 1
        
        # Commit every 1000 rows
        if i % 1000 == 0:
            conn.commit()
            print(f"  Progress: {i:,}/{len(violations):,} (new: {inserted:,}, duplicates: {skipped_duplicate:,})")
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\nDatabase: Inserted {inserted:,} new violations")
    print(f"          Skipped {skipped_invalid:,} invalid")
    print(f"          Skipped {skipped_duplicate:,} duplicates")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("  STOP SUPER SPEEDERS - DATA INGESTION")
    print("=" * 50)
    
    print("\nDropping existing data and fetching fresh from API...")
    
    # 1. Fetch all data from API
    data = fetch_all_violations()
    
    if not data:
        print("No data fetched.")
        exit(1)
    
    print(f"\nFetched {len(data):,} total violations from API")
    
    # 2. Save to database (fresh start - tables are dropped)
    save_to_database(data)
    
    print("\n" + "=" * 50)
    print("  DONE!")
    print("=" * 50)
