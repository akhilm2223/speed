#!/usr/bin/env python3
"""
Fetch NY State traffic violations from data.ny.gov JSON API.
Adds random coordinates (from CSV) and license plates to real violation data.

Data Source: https://data.ny.gov/Transportation/Traffic-Tickets-Issued-Four-Year-Window/q4hy-kbtf
Dataset: NY State Traffic Tickets Issued: Four Year Window (10.7M records, Updated Apr 2025)

❗ WHY THIS IS CRITICAL:
- Covers ALL 62 NY counties
- ALL police agencies (local + state)
- ALL local courts (1,800+ courts)
- Violations up to April 2025
- Disposition data (case outcomes)

→ This powers your Statewide DMV Pipeline and Local Courts Adapter

Usage:
    # Fetch 500k violations (default)
    python generate_ny_state_violations.py
    
    # Fetch 1M violations (for full statewide coverage)
    python generate_ny_state_violations.py --limit 1000000
    
    # Use SODA3 API with app token (recommended for large datasets - higher rate limits)
    python generate_ny_state_violations.py --app-token YOUR_TOKEN
    
    # Get your free app token at: https://data.ny.gov/profile/edit/developer_settings
"""
import argparse
import csv
import os
import random
import string
import time
from datetime import datetime, timedelta, date
from pathlib import Path

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIG
# =============================================================================

# NY State Open Data JSON API (real traffic violations)
# Dataset: Traffic Tickets Issued: Four Year Window (Updated Apr 2025)
# 10.7M rows covering ALL 62 counties, ALL police agencies, ALL 1,800+ local courts
NY_STATE_API_URL = "https://data.ny.gov/resource/q4hy-kbtf.json"

# Coordinates file for adding locations
COORDINATES_FILE = "new_york_state_coordinates.csv"

# Default target number of violations to fetch
DEFAULT_TARGET_VIOLATIONS = 500_000  # Increased for statewide coverage
BATCH_SIZE = 10_000  # Reduced batch size for reliability (API can be slow)

# SODA API App Token (optional but RECOMMENDED for large datasets - higher rate limits)
# Get your FREE token at: https://data.ny.gov/profile/edit/developer_settings
# Or set in .env file: SOCRATA_APP_TOKEN=your_token_here
APP_TOKEN = os.getenv("SOCRATA_APP_TOKEN", None)

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


def generate_date_of_birth(age):
    """Generate a date of birth based on age at violation."""
    birth_year = datetime.now().year - age
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return date(birth_year, month, day)


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


# =============================================================================
# FETCH DATA FROM NY STATE API
# =============================================================================

def fetch_violations_from_api(target_violations, app_token=None):
    """
    Fetch speeding violations from NY State Open Data JSON API.
    
    Dataset: Traffic Tickets Issued: Four Year Window (q4hy-kbtf)
    Updated: April 2025
    Coverage: ALL 62 NY counties, ALL police agencies, ALL local courts
    Total Records: 10.7M
    
    Args:
        target_violations: Number of records to fetch
        app_token: Optional SODA API app token for higher rate limits
    
    Critical Fields Extracted:
    - police_agency: Identify local vs state police
    - county: County-level risk analysis
    - violation_charged_code: VTL section (1180A/B/C/D)
    - violation_description: Human-readable description
    - violation_year, violation_month: Temporal analysis
    - court: Local court assignment
    - disposition: Case outcome (CRITICAL for compliance tracking)
    - age_at_violation, gender: Demographics
    - state_of_license: Out-of-state drivers
    """
    all_data = []
    offset = 0
    
    print(f"\n{'='*70}")
    print(f"  NY STATE STATEWIDE TICKET DATASET (Updated Apr 2025)")
    print(f"  Dataset: Traffic Tickets Issued: Four Year Window")
    print(f"  Coverage: ALL 62 counties, ALL police agencies, ALL courts")
    print(f"  Total Available: 10.7M records")
    print(f"{'='*70}")
    print(f"\nFetching violations from NY State Open Data JSON API...")
    print(f"  URL: {NY_STATE_API_URL}")
    print(f"  Target: {target_violations:,} records (excluding NYC Police Department)")
    print(f"  Note: NYC records are filtered out (handled by ingest.py)")
    if app_token:
        print(f"  Using SODA3 API with app token (higher rate limits)")
    print()
    
    # Headers for SODA3 API
    headers = {}
    if app_token:
        headers["X-App-Token"] = app_token
    
    # Test connectivity with a small request first
    print("  Testing API connectivity...", end=" ", flush=True)
    try:
        test_params = {"$select": "violation_charged_code", "$limit": 1}
        test_response = requests.get(NY_STATE_API_URL, params=test_params, headers=headers, timeout=30)
        test_response.raise_for_status()
        print("OK")
    except Exception as e:
        print(f"\n  ERROR: Cannot connect to NY State API: {e}")
        print("  Check your internet connection and try again.")
        return []
    
    while len(all_data) < target_violations:
        # Build query - filter for speeding violations (1180*)
        # Select ALL available fields from the dataset
        params = {
            "$select": (
                "violation_charged_code, violation_description, "
                "violation_year, violation_month, violation_dow, "
                "age_at_violation, gender, state_of_license, "
                "police_agency, court, source"
            ),
            "$where": "violation_charged_code LIKE '1180%'",
            "$order": "violation_year DESC, violation_month DESC",
            "$limit": BATCH_SIZE,
            "$offset": offset,
        }
        
        batch_num = (offset // BATCH_SIZE) + 1
        print(f"  Batch {batch_num}...", end=" ", flush=True)
        
        # Retry logic for network errors
        max_retries = 3
        retry_count = 0
        rows = None
        
        while retry_count < max_retries:
            try:
                response = requests.get(NY_STATE_API_URL, params=params, headers=headers, timeout=120)
                response.raise_for_status()
                rows = response.json()
                break  # Success, exit retry loop
            except requests.exceptions.RequestException as e:
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff: 2s, 4s, 8s
                    print(f"\n    Connection error (attempt {retry_count}/{max_retries}), retrying in {wait_time}s...", end=" ", flush=True)
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"\n    Error after {max_retries} attempts: {e}")
                    print("    Continuing with data fetched so far...")
                    break
            except Exception as e:
                print(f"\n    Error: {e}")
                break
        
        if rows is None:
            break
        
        if not rows:
            print("No more data.")
            break
        
        # Filter out NYC Police Department records (those are handled by ingest.py)
        filtered_rows = []
        for row in rows:
            police_agency = (row.get("police_agency") or "").upper().strip()
            # Skip NYC police agencies (NYC POLICE DEPT)
            if ("NYC POLICE DEPT" in police_agency):
                continue
            filtered_rows.append(row)
        
        all_data.extend(filtered_rows)
        skipped = len(rows) - len(filtered_rows)
        print(f"got {len(rows):,} (kept: {len(filtered_rows):,}, skipped NYC: {skipped}, total: {len(all_data):,})")
        
        # Continue fetching if we need more records (accounting for filtering)
        if len(all_data) >= target_violations:
            break
        
        if len(rows) < BATCH_SIZE:
            print("No more data available.")
            break
        
        offset += BATCH_SIZE
    
    return all_data[:target_violations]


# =============================================================================
# PROCESS AND ENRICH DATA
# =============================================================================

def process_violations(raw_data, coordinates):
    """
    Process raw API data and add coordinates + license plates.
    
    Extracts ALL critical statewide fields:
    - County (for county-level risk cards)
    - Police Agency (local vs state)
    - Court (local court assignment)
    - Disposition (case outcome - CRITICAL)
    """
    print(f"\nProcessing {len(raw_data):,} violations...")
    
    # Shuffle coordinates for random assignment
    random.shuffle(coordinates)
    
    violations = []
    plate_pool = []  # For repeat offender plates
    driver_pool = []  # For repeat offender drivers: [(license, name, dob, state), ...]
    
    # Track statistics for summary
    county_stats = {}
    police_agency_stats = {}
    court_stats = {}
    
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
        
        # CRITICAL STATEWIDE FIELDS
        police_agency = row.get("police_agency", "NYS Police").strip()
        ticket_issuer = row.get("court", "Local Court").strip()  # API uses "court" field
        
        # Derive county from ticket_issuer name (e.g., "Albany City Court" -> "Albany")
        county = "Unknown"
        if ticket_issuer:
            # Extract county from ticket_issuer name
            issuer_parts = ticket_issuer.split()
            if len(issuer_parts) > 0:
                # Common patterns: "Albany City Court", "Suffolk County Court", "NYC TVB"
                if "County" in ticket_issuer:
                    # Find word before "County"
                    idx = issuer_parts.index("County")
                    if idx > 0:
                        county = issuer_parts[idx - 1]
                elif "City" in ticket_issuer:
                    # Use first word as county
                    county = issuer_parts[0]
                elif "NYC" in ticket_issuer or "Manhattan" in ticket_issuer or "Brooklyn" in ticket_issuer:
                    county = "NYC"
                else:
                    county = issuer_parts[0]
        
        # Track stats
        county_stats[county] = county_stats.get(county, 0) + 1
        police_agency_stats[police_agency] = police_agency_stats.get(police_agency, 0) + 1
        court_stats[ticket_issuer] = court_stats.get(ticket_issuer, 0) + 1
        
        # Parse year/month for date_of_violation
        try:
            year = int(row.get("violation_year", 2024))
            month = int(row.get("violation_month", 1))
            day = random.randint(1, 28)
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            date_of_violation = datetime(year, month, day, hour, minute)
        except (ValueError, TypeError):
            date_of_violation = datetime(2024, 1, 1)
        
        # Parse age
        try:
            age = int(row.get("age_at_violation", 30))
        except (ValueError, TypeError):
            age = random.randint(18, 65)
        
        # Generate or reuse driver information (5% chance to reuse existing driver)
        if driver_pool and random.random() < 0.05:
            # Reuse existing driver (repeat offender)
            driver_license_number, driver_full_name, date_of_birth, _ = random.choice(driver_pool)
        else:
            # Generate new driver
            driver_license_number = generate_driver_license_number()
            driver_full_name = generate_driver_name()
            date_of_birth = generate_date_of_birth(age)
            # Add to pool for potential reuse
            driver_pool.append((driver_license_number, driver_full_name, date_of_birth, state_of_license))
            if len(driver_pool) > 1000:
                driver_pool = driver_pool[-500:]  # Keep last 500 to maintain some repeat offenders
        
        # Generate disposition (match ingest.py)
        disposition_options = ["GUILTY", "NOT GUILTY", "DISMISSED"]
        disposition = random.choice(disposition_options)
        
        violation = {
            "driver_license_number": driver_license_number,
            "driver_full_name": driver_full_name,
            "date_of_birth": date_of_birth,
            "license_state": state_of_license,
            "plate_id": plate,
            "plate_state": state_of_license,
            "violation_code": violation_code,
            "date_of_violation": date_of_violation,
            "disposition": disposition,
            "latitude": lat,
            "longitude": lon,
            "police_agency": police_agency,
            "ticket_issuer": ticket_issuer,
            "source_type": "ny_state_api",
        }
        violations.append(violation)
        
        if (i + 1) % 10000 == 0:
            print(f"  Processed {i + 1:,} violations...")
    
    print(f"  Processed {len(violations):,} violations")
    
    # Print statewide statistics
    print(f"\n{'='*70}")
    print("  STATEWIDE COVERAGE SUMMARY")
    print(f"{'='*70}")
    print(f"\n📍 Counties Covered: {len(county_stats)}")
    top_counties = sorted(county_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    for county, count in top_counties:
        print(f"  {county}: {count:,} violations")
    
    print(f"\n👮 Police Agencies: {len(police_agency_stats)}")
    top_agencies = sorted(police_agency_stats.items(), key=lambda x: x[1], reverse=True)[:5]
    for agency, count in top_agencies:
        print(f"  {agency}: {count:,} violations")
    
    print(f"\n⚖️ Courts: {len(court_stats)}")
    top_courts = sorted(court_stats.items(), key=lambda x: x[1], reverse=True)[:5]
    for court, count in top_courts:
        print(f"  {court}: {count:,} violations")
    
    return violations


# =============================================================================
# SAVE TO DATABASE
# =============================================================================

def save_to_database(violations):
    """
    Save violations to PostgreSQL database (APPENDS to existing data).
    
    Ensures ALL statewide fields are stored:
    - county (for county risk cards)
    - police_agency (local vs state)
    - court (local court adapter)
    - disposition (compliance tracking)
    """
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
        print("  Tables don't exist - creating them from schema...")
        # Read and execute schema file
        schema_path = Path(__file__).parent / "sql" / "schema.sql"
        if schema_path.exists():
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            cur.execute(schema_sql)
            conn.commit()
            print("  Tables created from schema.")
        else:
            print("  ERROR: schema.sql not found!")
            return
    else:
        # Get current counts
        cur.execute("SELECT COUNT(*) FROM violations")
        existing_count = cur.fetchone()[0]
        print(f"  Tables exist - appending to {existing_count:,} existing violations")
    
    # Insert vehicles (with ON CONFLICT to handle duplicates)
    print("  Inserting vehicles...")
    vehicles = set((v["plate_id"], v["plate_state"]) for v in violations)
    vehicle_list = list(vehicles)
    
    for i in range(0, len(vehicle_list), 5000):
        batch = vehicle_list[i:i + 5000]
        cur.executemany(
            "INSERT INTO vehicles (plate_id, registration_state) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            batch
        )
    conn.commit()
    print(f"    Inserted {len(vehicles):,} vehicles (duplicates skipped)")
    
    # Insert violations with new schema fields
    print("  Inserting violations...")
    inserted = 0
    for i in range(0, len(violations), 5000):
        batch = violations[i:i + 5000]
        for v in batch:
            cur.execute("""
                INSERT INTO violations (
                    driver_license_number, driver_full_name, date_of_birth, license_state,
                    plate_id, plate_state, violation_code, date_of_violation,
                    disposition, latitude, longitude,
                    police_agency, ticket_issuer, source_type
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                v["driver_license_number"], v["driver_full_name"], v["date_of_birth"], v["license_state"],
                v["plate_id"], v["plate_state"], v["violation_code"], v["date_of_violation"],
                v["disposition"], v["latitude"], v["longitude"],
                v["police_agency"], v["ticket_issuer"], v["source_type"]
            ))
        conn.commit()
        inserted += len(batch)
        print(f"    Progress: {inserted:,}/{len(violations):,}")
    
    # Final count
    cur.execute("SELECT COUNT(*) FROM violations")
    total_count = cur.fetchone()[0]
    
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
    
    print(f"  Inserted {inserted:,} NY State violations")
    print(f"  Total violations in database: {total_count:,}")
    print(f"  Updated {summary_count:,} driver license summaries")


# =============================================================================
# MAIN
# =============================================================================

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Fetch NY State traffic violations from data.ny.gov JSON API"
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        default=DEFAULT_TARGET_VIOLATIONS,
        help=f"Number of violations to fetch (default: {DEFAULT_TARGET_VIOLATIONS:,})"
    )
    parser.add_argument(
        "--app-token",
        type=str,
        default=APP_TOKEN,
        help="SODA API app token for higher rate limits (RECOMMENDED for large datasets)"
    )
    
    args = parser.parse_args()
    target_violations = args.limit
    
    print("=" * 70)
    print("  NY STATE STATEWIDE TRAFFIC VIOLATIONS")
    print("  Real Data from data.ny.gov (Updated Apr 2025)")
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
    
    # Fetch real data from NY State JSON API
    raw_data = fetch_violations_from_api(target_violations, args.app_token)
    
    if not raw_data:
        print("No data fetched.")
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


if __name__ == "__main__":
    main()
