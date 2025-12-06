#!/usr/bin/env python3
"""
Query database for a specific license number
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

def query_license(license_number):
    """Query database for violations by license number."""
    try:
        conn = psycopg.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        license_number = str(license_number).strip()
        
        print(f"\n{'='*80}")
        print(f"  QUERYING DATABASE FOR LICENSE: {license_number}")
        print(f"{'='*80}\n")
        
        # First, check exact match
        print("1. Checking EXACT match (no TRIM):")
        cur.execute("""
            SELECT COUNT(*) 
            FROM violations 
            WHERE driver_license_number = %s
        """, (license_number,))
        exact_count = cur.fetchone()[0]
        print(f"   Found: {exact_count} violations\n")
        
        # Check with TRIM
        print("2. Checking with TRIM on both sides:")
        cur.execute("""
            SELECT COUNT(*) 
            FROM violations 
            WHERE TRIM(driver_license_number) = TRIM(%s)
        """, (license_number,))
        trim_count = cur.fetchone()[0]
        print(f"   Found: {trim_count} violations\n")
        
        # Get all violations with details
        print("3. Fetching all violations (with TRIM):")
        cur.execute("""
            SELECT 
                v.violation_id,
                v.driver_license_number,
                v.driver_full_name,
                v.license_state,
                v.plate_id,
                v.plate_state,
                v.violation_code,
                v.date_of_violation,
                v.disposition,
                v.police_agency,
                v.source_type
            FROM violations v
            WHERE TRIM(v.driver_license_number) = TRIM(%s)
            ORDER BY v.date_of_violation DESC
        """, (license_number,))
        
        violations = cur.fetchall()
        print(f"   Retrieved {len(violations)} violations:\n")
        
        if violations:
            for i, row in enumerate(violations, 1):
                print(f"   Violation {i}:")
                print(f"      ID: {row[0]}")
                print(f"      License: '{row[1]}' (length: {len(str(row[1]))})")
                print(f"      Name: {row[2]}")
                print(f"      State: {row[3]}")
                print(f"      Plate: {row[4]} ({row[5]})")
                print(f"      Code: {row[6]}")
                print(f"      Date: {row[7]}")
                print(f"      Disposition: {row[8]}")
                print(f"      Agency: {row[9]}")
                print(f"      Source: {row[10]}")
                print()
        else:
            print("   No violations found!\n")
        
        # Check for similar license numbers (in case of formatting issues)
        print("4. Checking for similar license numbers (first 6 digits match):")
        prefix = license_number[:6] if len(license_number) >= 6 else license_number
        cur.execute("""
            SELECT DISTINCT driver_license_number, COUNT(*) as count
            FROM violations 
            WHERE driver_license_number LIKE %s
            GROUP BY driver_license_number
            ORDER BY count DESC
            LIMIT 10
        """, (f"{prefix}%",))
        
        similar = cur.fetchall()
        if similar:
            print(f"   Found {len(similar)} similar license numbers:\n")
            for lic, count in similar:
                print(f"      '{lic}' (length: {len(str(lic))}) - {count} violations")
        else:
            print("   No similar license numbers found\n")
        
        # Check driver license summary
        print("5. Checking driver_license_summary table:")
        cur.execute("""
            SELECT total_speeding_tickets, points_on_license, license_state
            FROM driver_license_summary
            WHERE TRIM(driver_license_number) = TRIM(%s)
        """, (license_number,))
        
        summary = cur.fetchone()
        if summary:
            print(f"   Total speeding tickets: {summary[0]}")
            print(f"   Points on license: {summary[1]}")
            print(f"   License state: {summary[2]}\n")
        else:
            print("   No summary found\n")
        
        cur.close()
        conn.close()
        
        print(f"{'='*80}\n")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    query_license("863715880")

