#!/usr/bin/env python3
"""
Local Court CSV Ingestion Script
Ingests court violation CSV files into the DMV database.

Usage:
    python ingest_court_csv.py court_violations.csv
    python ingest_court_csv.py --file my_court_data.csv --batch-size 500
"""
import csv
import os
import sys
import argparse
from datetime import datetime

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

# Required CSV columns
REQUIRED_COLUMNS = [
    "driver_license_number", "driver_full_name", "date_of_birth", 
    "plate_id", "violation_code", "date_of_violation"
]

# Optional columns with defaults
OPTIONAL_COLUMNS = {
    "license_state": "NY",
    "plate_state": "NY",
    "disposition": "PENDING",
    "latitude": None,
    "longitude": None,
    "police_agency": "Local Police",
    "ticket_issuer": "Local Court",
}


def validate_csv(file_path):
    """Validate CSV file has required columns."""
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        
        missing = [col for col in REQUIRED_COLUMNS if col not in headers]
        if missing:
            print(f"❌ Error: Missing required columns: {', '.join(missing)}")
            print(f"   Required: {', '.join(REQUIRED_COLUMNS)}")
            return False
        
        return True


def get_value(row, column, default=None):
    """Get value from row with fallback to default."""
    value = row.get(column, "").strip()
    if not value or value.lower() == "null":
        return default
    return value


def ingest_csv(file_path, batch_size=1000):
    """Ingest CSV file into database."""
    print(f"\n{'='*60}")
    print(f"  LOCAL COURT CSV INGESTION")
    print(f"{'='*60}")
    print(f"\nFile: {file_path}")
    
    # Validate file exists
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        return False
    
    # Validate CSV structure
    if not validate_csv(file_path):
        return False
    
    print("✓ CSV structure validated")
    
    # Connect to database
    try:
        conn = psycopg.connect(**DB_CONFIG)
        cur = conn.cursor()
        print("✓ Connected to database")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    
    # Read and process CSV
    records_processed = 0
    records_inserted = 0
    records_failed = 0
    vehicles_created = 0
    
    start_time = datetime.now()
    
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        batch_vehicles = []
        batch_violations = []
        
        for row in reader:
            records_processed += 1
            
            try:
                # Extract values with defaults
                plate_id = get_value(row, "plate_id", "").upper()
                plate_state = get_value(row, "plate_state", "NY").upper()
                
                if not plate_id:
                    records_failed += 1
                    continue
                
                # Prepare vehicle tuple
                batch_vehicles.append((plate_id, plate_state))
                
                # Prepare violation tuple
                violation = (
                    get_value(row, "driver_license_number"),
                    get_value(row, "driver_full_name"),
                    get_value(row, "date_of_birth"),
                    get_value(row, "license_state", "NY"),
                    plate_id,
                    plate_state,
                    get_value(row, "violation_code"),
                    get_value(row, "date_of_violation"),
                    get_value(row, "disposition", "PENDING"),
                    get_value(row, "latitude") or None,
                    get_value(row, "longitude") or None,
                    get_value(row, "police_agency", "Local Police"),
                    get_value(row, "ticket_issuer", "Local Court"),
                    "local_court_upload",  # source_type
                )
                batch_violations.append(violation)
                
                # Process batch
                if len(batch_violations) >= batch_size:
                    inserted, v_created = process_batch(cur, conn, batch_vehicles, batch_violations)
                    records_inserted += inserted
                    vehicles_created += v_created
                    batch_vehicles = []
                    batch_violations = []
                    print(f"  Processed {records_processed:,} records...")
                    
            except Exception as e:
                records_failed += 1
                if records_failed <= 5:
                    print(f"  ⚠ Row {records_processed} error: {e}")
        
        # Process remaining batch
        if batch_violations:
            inserted, v_created = process_batch(cur, conn, batch_vehicles, batch_violations)
            records_inserted += inserted
            vehicles_created += v_created
    
    # Update driver summaries
    print("\nUpdating driver license summaries...")
    update_driver_summaries(cur, conn)
    
    # Close connection
    cur.close()
    conn.close()
    
    # Print summary
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n{'='*60}")
    print(f"  INGESTION COMPLETE")
    print(f"{'='*60}")
    print(f"  Records processed: {records_processed:,}")
    print(f"  Records inserted:  {records_inserted:,}")
    print(f"  Records failed:    {records_failed:,}")
    print(f"  Vehicles created:  {vehicles_created:,}")
    print(f"  Time elapsed:      {elapsed:.1f}s")
    print(f"{'='*60}\n")
    
    return True


def process_batch(cur, conn, vehicles, violations):
    """Process a batch of records."""
    vehicles_created = 0
    inserted = 0
    
    try:
        # Insert vehicles (ignore duplicates)
        unique_vehicles = list(set(vehicles))
        cur.executemany(
            "INSERT INTO vehicles (plate_id, registration_state) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            unique_vehicles
        )
        vehicles_created = cur.rowcount
        
        # Insert violations
        cur.executemany(
            """INSERT INTO violations (
                driver_license_number, driver_full_name, date_of_birth, license_state,
                plate_id, plate_state, violation_code, date_of_violation,
                disposition, latitude, longitude,
                police_agency, ticket_issuer, source_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            violations
        )
        inserted = len(violations)
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"  ⚠ Batch error: {e}")
    
    return inserted, vehicles_created


def update_driver_summaries(cur, conn):
    """Update driver license summary table with new violations."""
    try:
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
        print(f"  ✓ Updated {cur.rowcount:,} driver summaries")
    except Exception as e:
        print(f"  ⚠ Summary update error: {e}")
        conn.rollback()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest local court CSV into DMV database")
    parser.add_argument("file", nargs="?", default="court_violations.csv", help="CSV file to ingest")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for inserts")
    args = parser.parse_args()
    
    success = ingest_csv(args.file, args.batch_size)
    sys.exit(0 if success else 1)

