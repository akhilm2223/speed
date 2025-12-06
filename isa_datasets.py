#!/usr/bin/env python3
"""
ISA Datasets Module
Generates the two required hackathon deliverables:
  A. Drivers with 11+ points in 24-month trailing window
  B. Plates with 16+ tickets in 12-month trailing window
"""

from datetime import datetime, timedelta
import psycopg
import os
from dotenv import load_dotenv
from isa_policy import ISA_POLICY, get_points_for_code

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "traffic_violations_db"),
    "user": os.getenv("DB_USER", "myuser"),
    "password": os.getenv("DB_PASSWORD", "mypassword"),
}


def get_db_connection():
    """Get database connection."""
    return psycopg.connect(**DB_CONFIG)


# =============================================================================
# DATASET A: Drivers with 11+ points in 24-month trailing window
# =============================================================================
def get_drivers_11_plus_points(time_window_months: int = 24):
    """
    Get all drivers who have accumulated 11+ points in the trailing window.
    
    Returns list of dicts with:
      - driver_license_number
      - total_points
      - violation_count
      - violations (list of individual violations)
    """
    cutoff_date = datetime.now() - timedelta(days=time_window_months * 30)
    
    # Build points CASE statement from policy
    points_cases = []
    for code, points in ISA_POLICY["points_per_code"].items():
        points_cases.append(f"WHEN violation_code LIKE '{code}%%' THEN {points}")
    points_case_sql = "\n                ".join(points_cases)
    default_points = ISA_POLICY.get("default_points", 2)
    
    query = f"""
        WITH violation_points AS (
            SELECT 
                driver_license_number,
                driver_full_name,
                license_state,
                violation_code,
                date_of_violation,
                ticket_issuer,
                police_agency,
                plate_id,
                CASE 
                    {points_case_sql}
                    ELSE {default_points}
                END AS points
            FROM violations
            WHERE date_of_violation >= %s
        ),
        driver_totals AS (
            SELECT 
                driver_license_number,
                driver_full_name,
                license_state,
                SUM(points) AS total_points,
                COUNT(*) AS violation_count
            FROM violation_points
            GROUP BY driver_license_number, driver_full_name, license_state
            HAVING SUM(points) >= %s
        )
        SELECT 
            dt.driver_license_number,
            dt.driver_full_name,
            dt.license_state,
            dt.total_points,
            dt.violation_count,
            vp.violation_code,
            vp.date_of_violation,
            vp.ticket_issuer,
            vp.police_agency,
            vp.plate_id,
            vp.points
        FROM driver_totals dt
        JOIN violation_points vp ON dt.driver_license_number = vp.driver_license_number
        ORDER BY dt.total_points DESC, dt.driver_license_number, vp.date_of_violation DESC
    """
    
    results = []
    drivers_map = {}
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (cutoff_date, ISA_POLICY["isa_points_threshold"]))
            rows = cur.fetchall()
            
            for row in rows:
                license_num = row[0]
                
                if license_num not in drivers_map:
                    drivers_map[license_num] = {
                        "driver_license_number": row[0],
                        "driver_full_name": row[1],
                        "license_state": row[2],
                        "total_points": row[3],
                        "violation_count": row[4],
                        "violations": []
                    }
                
                drivers_map[license_num]["violations"].append({
                    "violation_code": row[5],
                    "date_of_violation": row[6].isoformat() if row[6] else None,
                    "ticket_issuer": row[7],
                    "police_agency": row[8],
                    "plate_id": row[9],
                    "points": row[10]
                })
    
    return list(drivers_map.values())


def get_drivers_flat_list(time_window_months: int = 24):
    """
    Get flat list of all violations for drivers with 11+ points.
    One row per violation (for table display).
    """
    cutoff_date = datetime.now() - timedelta(days=time_window_months * 30)
    
    # Build points CASE statement from policy
    points_cases = []
    for code, points in ISA_POLICY["points_per_code"].items():
        points_cases.append(f"WHEN violation_code LIKE '{code}%%' THEN {points}")
    points_case_sql = "\n                ".join(points_cases)
    default_points = ISA_POLICY.get("default_points", 2)
    
    query = f"""
        WITH violation_points AS (
            SELECT 
                driver_license_number,
                driver_full_name,
                license_state,
                violation_code,
                date_of_violation,
                ticket_issuer,
                police_agency,
                plate_id,
                CASE 
                    {points_case_sql}
                    ELSE {default_points}
                END AS points
            FROM violations
            WHERE date_of_violation >= %s
        ),
        driver_totals AS (
            SELECT 
                driver_license_number,
                SUM(points) AS total_points
            FROM violation_points
            GROUP BY driver_license_number
            HAVING SUM(points) >= %s
        )
        SELECT 
            vp.driver_license_number,
            vp.driver_full_name,
            vp.violation_code,
            vp.date_of_violation,
            vp.ticket_issuer,
            vp.police_agency,
            vp.plate_id,
            vp.points,
            dt.total_points
        FROM violation_points vp
        JOIN driver_totals dt ON vp.driver_license_number = dt.driver_license_number
        ORDER BY dt.total_points DESC, vp.driver_license_number, vp.date_of_violation DESC
    """
    
    results = []
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (cutoff_date, ISA_POLICY["isa_points_threshold"]))
            rows = cur.fetchall()
            
            for row in rows:
                results.append({
                    "driver_license_number": row[0],
                    "driver_full_name": row[1],
                    "violation_code": row[2],
                    "date_of_violation": row[3].isoformat() if row[3] else None,
                    "ticket_issuer": row[4],
                    "police_agency": row[5],
                    "plate_id": row[6],
                    "points": row[7],
                    "total_points": row[8]
                })
    
    return results


# =============================================================================
# DATASET B: Plates with 16+ tickets in 12-month trailing window
# =============================================================================
def get_plates_16_plus_tickets(time_window_months: int = 12):
    """
    Get all plates with 16+ speeding tickets in the trailing window.
    
    Returns list of dicts with:
      - plate_id
      - ticket_count
      - violations (list of individual violations)
    """
    # Use database NOW() to avoid timezone/clock skew issues
    query = f"""
        WITH plate_counts AS (
            SELECT 
                plate_id,
                plate_state,
                COUNT(*) AS ticket_count
            FROM violations
            WHERE date_of_violation >= NOW() - INTERVAL '{time_window_months} months'
            GROUP BY plate_id, plate_state
            HAVING COUNT(*) >= %s
        )
        SELECT 
            pc.plate_id,
            pc.plate_state,
            pc.ticket_count,
            v.driver_license_number,
            v.violation_code,
            v.date_of_violation,
            v.ticket_issuer,
            v.police_agency
        FROM plate_counts pc
        JOIN violations v ON pc.plate_id = v.plate_id AND pc.plate_state = v.plate_state
        WHERE v.date_of_violation >= NOW() - INTERVAL '{time_window_months} months'
        ORDER BY pc.ticket_count DESC, pc.plate_id, v.date_of_violation DESC
    """
    
    plates_map = {}
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (ISA_POLICY["isa_ticket_threshold"],))
            rows = cur.fetchall()
            
            for row in rows:
                plate_key = f"{row[0]}_{row[1]}"  # plate_id + state
                
                if plate_key not in plates_map:
                    plates_map[plate_key] = {
                        "plate_id": row[0],
                        "plate_state": row[1],
                        "ticket_count": row[2],
                        "violations": []
                    }
                
                plates_map[plate_key]["violations"].append({
                    "driver_license_number": row[3],
                    "violation_code": row[4],
                    "date_of_violation": row[5].isoformat() if row[5] else None,
                    "ticket_issuer": row[6],
                    "police_agency": row[7]
                })
    
    return list(plates_map.values())


def get_plates_flat_list(time_window_months: int = 12):
    """
    Get flat list of all violations for plates with 16+ tickets.
    One row per violation (for table display).
    """
    cutoff_date = datetime.now() - timedelta(days=time_window_months * 30)
    
    query = """
        WITH plate_counts AS (
            SELECT 
                plate_id,
                plate_state,
                COUNT(*) AS ticket_count
            FROM violations
            WHERE date_of_violation >= %s
            GROUP BY plate_id, plate_state
            HAVING COUNT(*) >= %s
        )
        SELECT 
            v.plate_id,
            v.plate_state,
            pc.ticket_count,
            v.driver_license_number,
            v.violation_code,
            v.date_of_violation,
            v.ticket_issuer,
            v.police_agency
        FROM violations v
        JOIN plate_counts pc ON v.plate_id = pc.plate_id AND v.plate_state = pc.plate_state
        WHERE v.date_of_violation >= %s
        ORDER BY pc.ticket_count DESC, v.plate_id, v.date_of_violation DESC
    """
    
    results = []
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (cutoff_date, ISA_POLICY["isa_ticket_threshold"], cutoff_date))
            rows = cur.fetchall()
            
            for row in rows:
                results.append({
                    "plate_id": row[0],
                    "plate_state": row[1],
                    "ticket_count": row[2],
                    "driver_license_number": row[3],
                    "violation_code": row[4],
                    "date_of_violation": row[5].isoformat() if row[5] else None,
                    "ticket_issuer": row[6],
                    "police_agency": row[7]
                })
    
    return results


# =============================================================================
# SUMMARY COUNTS (for dashboard KPIs)
# =============================================================================
def get_isa_summary_counts():
    """
    Get summary counts for ISA thresholds.
    Returns:
      - drivers_11_plus: count of unique drivers with 11+ points (24m)
      - plates_16_plus: count of unique plates with 16+ tickets (12m)
    """
    cutoff_24m = datetime.now() - timedelta(days=730)  # 24 months
    cutoff_12m = datetime.now() - timedelta(days=365)  # 12 months
    
    # Build points CASE for driver count
    points_cases = []
    for code, points in ISA_POLICY["points_per_code"].items():
        points_cases.append(f"WHEN violation_code LIKE '{code}%%' THEN {points}")
    points_case_sql = "\n                ".join(points_cases)
    default_points = ISA_POLICY.get("default_points", 2)
    
    drivers_query = f"""
        SELECT COUNT(DISTINCT driver_license_number)
        FROM (
            SELECT 
                driver_license_number,
                SUM(CASE 
                    {points_case_sql}
                    ELSE {default_points}
                END) AS total_points
            FROM violations
            WHERE date_of_violation >= %s
            GROUP BY driver_license_number
            HAVING SUM(CASE 
                {points_case_sql}
                ELSE {default_points}
            END) >= %s
        ) AS drivers_over_threshold
    """
    
    plates_query = """
        SELECT COUNT(DISTINCT plate_id)
        FROM (
            SELECT plate_id, COUNT(*) AS ticket_count
            FROM violations
            WHERE date_of_violation >= %s
            GROUP BY plate_id
            HAVING COUNT(*) >= %s
        ) AS plates_over_threshold
    """
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(drivers_query, (cutoff_24m, ISA_POLICY["isa_points_threshold"]))
            drivers_count = cur.fetchone()[0] or 0
            
            cur.execute(plates_query, (cutoff_12m, ISA_POLICY["isa_ticket_threshold"]))
            plates_count = cur.fetchone()[0] or 0
    
    return {
        "drivers_11_plus_points_24m": drivers_count,
        "plates_16_plus_tickets_12m": plates_count,
        "points_threshold": ISA_POLICY["isa_points_threshold"],
        "ticket_threshold": ISA_POLICY["isa_ticket_threshold"],
        "driver_window_months": 24,
        "plate_window_months": 12
    }


# =============================================================================
# WARNING BAND: Near-threshold drivers and plates
# =============================================================================
def get_warning_drivers(time_window_months: int = 24, min_points: int = 8, max_points: int = 10):
    """
    Get drivers in the warning band (approaching ISA threshold).
    Default: 8-10 points in 24-month window.
    """
    cutoff_date = datetime.now() - timedelta(days=time_window_months * 30)
    
    # Build points CASE statement from policy
    points_cases = []
    for code, points in ISA_POLICY["points_per_code"].items():
        points_cases.append(f"WHEN violation_code LIKE '{code}%%' THEN {points}")
    points_case_sql = "\n                ".join(points_cases)
    default_points = ISA_POLICY.get("default_points", 2)
    
    query = f"""
        SELECT 
            driver_license_number,
            driver_full_name,
            license_state,
            SUM(CASE 
                {points_case_sql}
                ELSE {default_points}
            END) AS total_points,
            COUNT(*) AS violation_count
        FROM violations
        WHERE date_of_violation >= %s
        GROUP BY driver_license_number, driver_full_name, license_state
        HAVING SUM(CASE 
            {points_case_sql}
            ELSE {default_points}
        END) BETWEEN %s AND %s
        ORDER BY total_points DESC
        LIMIT 100
    """
    
    results = []
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (cutoff_date, min_points, max_points))
            rows = cur.fetchall()
            
            for row in rows:
                results.append({
                    "driver_license_number": row[0],
                    "driver_full_name": row[1],
                    "license_state": row[2],
                    "total_points": row[3],
                    "violation_count": row[4],
                    "points_to_threshold": ISA_POLICY["isa_points_threshold"] - row[3]
                })
    
    return results


def get_warning_plates(time_window_months: int = 12, min_tickets: int = 12, max_tickets: int = 15):
    """
    Get plates in the warning band (approaching ISA threshold).
    Default: 12-15 tickets in 12-month window.
    """
    cutoff_date = datetime.now() - timedelta(days=time_window_months * 30)
    
    query = """
        SELECT 
            plate_id,
            plate_state,
            COUNT(*) AS ticket_count
        FROM violations
        WHERE date_of_violation >= %s
        GROUP BY plate_id, plate_state
        HAVING COUNT(*) BETWEEN %s AND %s
        ORDER BY ticket_count DESC
        LIMIT 100
    """
    
    results = []
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (cutoff_date, min_tickets, max_tickets))
            rows = cur.fetchall()
            
            for row in rows:
                results.append({
                    "plate_id": row[0],
                    "plate_state": row[1],
                    "ticket_count": row[2],
                    "tickets_to_threshold": ISA_POLICY["isa_ticket_threshold"] - row[2]
                })
    
    return results


if __name__ == "__main__":
    # Test the functions
    print("=" * 60)
    print("ISA DATASETS TEST")
    print("=" * 60)
    
    print("\n--- Summary Counts ---")
    summary = get_isa_summary_counts()
    print(f"Drivers with 11+ points (24m): {summary['drivers_11_plus_points_24m']}")
    print(f"Plates with 16+ tickets (12m): {summary['plates_16_plus_tickets_12m']}")
    
    print("\n--- Drivers 11+ Points (first 5) ---")
    drivers = get_drivers_11_plus_points()
    for d in drivers[:5]:
        print(f"  {d['driver_license_number']}: {d['total_points']} points, {d['violation_count']} violations")
    
    print("\n--- Plates 16+ Tickets (first 5) ---")
    plates = get_plates_16_plus_tickets()
    for p in plates[:5]:
        print(f"  {p['plate_id']}: {p['ticket_count']} tickets")
    
    print("\nDone!")

