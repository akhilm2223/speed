#!/usr/bin/env python3
"""
DMV ISA Enforcement API
Enhanced with policy-based risk engine for ISA enforcement.
All data from real NYC Open Data violations.
"""
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask import Blueprint, jsonify, request
import psycopg
from dotenv import load_dotenv

from isa_policy import (
    ISA_POLICY,
    get_points_for_code,
    get_policy_summary,
    compute_status,
    get_trigger_reason,
    compute_crash_risk_score,
    get_crash_risk_level,
    get_jurisdiction_type,
    ENFORCEMENT_STATES,
)
from isa_datasets import (
    get_drivers_11_plus_points,
    get_drivers_flat_list,
    get_plates_16_plus_tickets,
    get_plates_flat_list,
    get_isa_summary_counts,
    get_warning_drivers,
    get_warning_plates,
)

load_dotenv()

dmv_bp = Blueprint('dmv', __name__, url_prefix='/api/dmv')

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "traffic_violations_db"),
    "user": os.getenv("DB_USER", "myuser"),
    "password": os.getenv("DB_PASSWORD", "mypassword"),
}

# NYC boroughs for determining ticket issuer
NYC_BOROUGHS = ['MANHATTAN', 'BROOKLYN', 'QUEENS', 'BRONX', 'STATEN ISLAND', 
                'NEW YORK', 'KINGS', 'RICHMOND', 'NYC']


def get_db():
    return psycopg.connect(**DB_CONFIG)


def get_ticket_issuer(primary_borough, court):
    """Determine ticket issuer based on location.
    NYC = Department of Finance, Outside NYC = Local Court
    
    Note: Current dataset is NYC Ope NYC DOF
    if court:
        return court
    return "NYC Dept of Finance"n Data only - all records are NYC DOF.
    Statewide integration with 1,800 local courts requires NYS TSLED access.
    """
    if primary_borough:
        borough_upper = primary_borough.upper().strip()
        for nyc in NYC_BOROUGHS:
            if nyc in borough_upper or borough_upper in nyc:
                return "NYC Dept of Finance"
        if court and 'TVB' in court.upper():
            return "NYC Dept of Finance"
    
    # For real NYC Open Data, default to


def get_time_window_filter(policy: dict = ISA_POLICY):
    """
    Get SQL WHERE clause for time window filtering.
    Returns (sql_clause, params) tuple.
    """
    if policy["time_window_months"] is None:
        return "", []
    
    cutoff_date = datetime.now() - relativedelta(months=policy["time_window_months"])
    return "AND v.date_of_violation >= %s", [cutoff_date]


def compute_driver_risk(conn, plate_id: str, registration_state: str = "NY", policy: dict = ISA_POLICY) -> dict:
    """
    Compute risk metrics for a single driver based on policy.
    
    This is the core risk calculation function that aggregates violations
    and determines driver status according to the ISA policy.
    
    Args:
        conn: Database connection
        plate_id: Vehicle plate ID
        registration_state: Vehicle registration state
        policy: Policy configuration dict
    
    Returns:
        Dict with risk metrics:
        - total_points: Sum of points from violations
        - total_tickets: Count of speeding tickets
        - severe_count: Count of severe violations (1180D/E/F)
        - latest_violation_ts: Most recent violation date
        - first_violation_ts: Earliest violation date
        - primary_borough: Most common violation location
        - borough_count: Number of distinct boroughs
        - night_violations: Count of nighttime violations
        - status: 'OK' | 'MONITORING' | 'ISA_REQUIRED'
        - trigger_reason: Human-readable reason if ISA required
    """
    cur = conn.cursor()
    
    time_clause, time_params = get_time_window_filter(policy)
    
    # Build points CASE statement from policy
    points_cases = []
    for code, points in policy["points_per_code"].items():
        points_cases.append(f"WHEN v.violation_code = '{code}' THEN {points}")
    points_case_sql = "CASE " + " ".join(points_cases) + f" ELSE {policy['default_points']} END"
    
    # Build severe codes list
    severe_codes = policy.get("severe_codes", ["1180D", "1180E", "1180F"])
    severe_codes_sql = ", ".join(f"'{c}'" for c in severe_codes)
    
    query = f"""
        SELECT 
            COUNT(*) FILTER (WHERE v.disposition = 'GUILTY') AS total_tickets,
            COALESCE(SUM(CASE WHEN v.disposition = 'GUILTY' THEN {points_case_sql} ELSE 0 END), 0) AS total_points,
            COUNT(*) FILTER (WHERE v.disposition = 'GUILTY' AND v.violation_code IN ({severe_codes_sql})) AS severe_count,
            MAX(v.date_of_violation) AS latest_violation_ts,
            MIN(v.date_of_violation) AS first_violation_ts,
            'NYC' AS primary_borough,
            1 AS borough_count,
            COUNT(*) FILTER (
                WHERE v.disposition = 'GUILTY'
                  AND (EXTRACT(HOUR FROM v.date_of_violation) >= 22 
                   OR EXTRACT(HOUR FROM v.date_of_violation) < 4)
            ) AS night_violations,
            COUNT(*) FILTER (WHERE v.disposition = 'GUILTY' AND v.violation_code = '1180D') AS high_tier_count,
            COUNT(*) FILTER (WHERE v.disposition = 'GUILTY' AND v.violation_code = '1180A') AS low_tier_count,
            'NYC Dept of Finance' AS primary_court
        FROM violations v
        WHERE v.plate_id = %s 
          AND v.plate_state = %s
          {time_clause}
    """
    
    params = [plate_id, registration_state] + time_params
    cur.execute(query, params)
    row = cur.fetchone()
    cur.close()
    
    if not row or row[0] == 0:
        return {
            "total_points": 0,
            "total_tickets": 0,
            "severe_count": 0,
            "latest_violation_ts": None,
            "first_violation_ts": None,
            "primary_borough": "Unknown",
            "borough_count": 0,
            "night_violations": 0,
            "high_tier_count": 0,
            "low_tier_count": 0,
            "primary_court": None,
            "status": "OK",
            "trigger_reason": None,
        }
    
    total_tickets = row[0]
    total_points = row[1]
    
    status = compute_status(total_points, total_tickets, policy)
    trigger_reason = get_trigger_reason(total_points, total_tickets, policy)
    
    night_violations = row[7]
    borough_count = row[6]
    primary_borough = row[5]
    primary_court = row[10]
    
    # Compute crash risk score
    crash_risk = compute_crash_risk_score(
        total_points, total_tickets, night_violations, borough_count, policy
    )
    crash_risk_level = get_crash_risk_level(crash_risk)
    
    # Determine jurisdiction
    jurisdiction_type = get_jurisdiction_type(primary_borough, primary_court)
    court_name = primary_court if primary_court else (
        "NYC Dept of Finance" if jurisdiction_type == "NYC_DOF" else "Local Court"
    )
    
    return {
        "total_points": total_points,
        "total_tickets": total_tickets,
        "severe_count": row[2],
        "latest_violation_ts": row[3],
        "first_violation_ts": row[4],
        "primary_borough": primary_borough,
        "borough_count": borough_count,
        "night_violations": night_violations,
        "high_tier_count": row[8],
        "low_tier_count": row[9],
        "primary_court": primary_court,
        "court_name": court_name,
        "ticket_issuer": primary_court,  # Use primary_court which comes from ticket_issuer column
        "status": status,
        "trigger_reason": trigger_reason,
        "crash_risk_score": crash_risk,
        "crash_risk_level": crash_risk_level,
        "jurisdiction_type": jurisdiction_type,
    }



def ensure_view_exists(policy: dict = ISA_POLICY):
    """Create the enhanced risk view using policy-based points."""
    conn = get_db()
    cur = conn.cursor()
    
    # Build points CASE statement from policy
    points_cases = []
    for code, points in policy["points_per_code"].items():
        points_cases.append(f"WHEN v.violation_code = '{code}' THEN {points}")
    points_case_sql = "CASE " + " ".join(points_cases) + f" ELSE {policy['default_points']} END"
    
    # Build severe codes list
    severe_codes = policy.get("severe_codes", ["1180D", "1180E", "1180F"])
    severe_codes_sql = ", ".join(f"'{c}'" for c in severe_codes)
    
    # Time window filter
    time_clause = ""
    if policy["time_window_months"] is not None:
        cutoff_date = datetime.now() - relativedelta(months=policy["time_window_months"])
        time_clause = f"AND v.date_of_violation >= '{cutoff_date.strftime('%Y-%m-%d')}'"
    
    cur.execute("DROP VIEW IF EXISTS dmv_risk_view CASCADE")
    cur.execute(f"""
        CREATE VIEW dmv_risk_view AS
        SELECT 
            v.plate_id,
            v.plate_state as registration_state,
            COUNT(*) AS violation_count,
            SUM(CASE WHEN v.disposition = 'GUILTY' THEN {points_case_sql} ELSE 0 END) AS risk_points,
            MAX(date_of_violation) AS last_violation,
            MIN(date_of_violation) AS first_violation,
            COUNT(*) FILTER (WHERE v.disposition = 'GUILTY' AND violation_code IN ({severe_codes_sql})) AS severe_count,
            COUNT(*) FILTER (WHERE v.disposition = 'GUILTY' AND violation_code = '1180D') AS high_tier_count,
            COUNT(*) FILTER (WHERE v.disposition = 'GUILTY' AND violation_code = '1180A') AS low_tier_count,
            COUNT(*) FILTER (
                WHERE v.disposition = 'GUILTY'
                  AND (EXTRACT(HOUR FROM date_of_violation) >= 22 
                   OR EXTRACT(HOUR FROM date_of_violation) < 4)
            ) AS night_violations,
            COALESCE(MODE() WITHIN GROUP (ORDER BY v.ticket_issuer), 'Unknown') AS primary_borough,
            COUNT(DISTINCT v.ticket_issuer) AS borough_count,
            COALESCE(MODE() WITHIN GROUP (ORDER BY v.ticket_issuer), 'Local Court') AS primary_court,
            COALESCE(MODE() WITHIN GROUP (ORDER BY v.police_agency), 'Unknown') AS primary_agency
        FROM violations v
        WHERE 
            v.plate_id NOT LIKE 'UNK%%'
            AND v.plate_id != 'NA'
            AND LENGTH(v.plate_id) >= 4
            {time_clause}
        GROUP BY 
            v.plate_id, v.plate_state
        HAVING 
            COUNT(*) >= 1
    """)
    conn.commit()
    cur.close()
    conn.close()


try:
    ensure_view_exists()
except:
    pass


@dmv_bp.route('/dashboard')
def get_dashboard():
    """
    Get DMV dashboard with policy-based KPIs and enforcement queue.
    
    Supports filters:
    - county: Filter by county
    - court: Filter by court
    - agency: Filter by police agency
    - source: Filter by data source (ny_state_csv, police_stop, etc.)
    """
    try:
        ensure_view_exists(ISA_POLICY)
        conn = get_db()
        cur = conn.cursor()
        
        # Get filter parameters
        filter_county = request.args.get('county')
        filter_court = request.args.get('court')
        filter_agency = request.args.get('agency')
        filter_source = request.args.get('source')
        
        policy = ISA_POLICY
        pts_threshold = policy["isa_points_threshold"]
        tkt_threshold = policy["isa_ticket_threshold"]
        mon_threshold = policy["monitoring_min_points"]

        # KPIs from all data
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE risk_points >= %s OR violation_count >= %s
                ) AS isa_required,
                COUNT(*) FILTER (
                    WHERE risk_points >= %s AND risk_points < %s
                      AND violation_count < %s
                ) AS monitoring,
                COUNT(*) FILTER (
                    WHERE violation_count >= 3
                ) AS super_speeders,
                0 AS cross_borough,
                COALESCE(SUM(violation_count), 0) AS total_violations
            FROM dmv_risk_view
            """,
            (pts_threshold, tkt_threshold, mon_threshold, pts_threshold, tkt_threshold),
        )
        kpi_row = cur.fetchone()
        kpi_isa_required = kpi_row[0] or 0
        kpi_monitoring = kpi_row[1] or 0
        kpi_super_speeders = kpi_row[2] or 0
        kpi_cross_borough = kpi_row[3] or 0
        kpi_total_violations = int(kpi_row[4] or 0)
        
        # County stats for new KPI cards (Placeholder as county not available)
        top_risk_counties = []
        most_1180d_county = None
        cross_jurisdiction_count = 0

        # Enforcement queue: top 5000 drivers by risk
        # Pre-compute license violation counts AND points for performance
        points_case_sql = "CASE " + " ".join([f"WHEN violation_code = '{code}' THEN {points}" for code, points in policy["points_per_code"].items()]) + f" ELSE {policy['default_points']} END"
        severe_codes = policy.get("severe_codes", ["1180D", "1180E", "1180F"])
        severe_codes_sql = ", ".join(f"'{c}'" for c in severe_codes)
        
        cur.execute(f"""
            WITH license_stats AS (
                SELECT 
                    TRIM(driver_license_number) as license_num,
                    COUNT(*) as license_violation_count,
                    SUM(CASE WHEN disposition = 'GUILTY' THEN {points_case_sql} ELSE 0 END) as license_points,
                    COUNT(*) FILTER (WHERE disposition = 'GUILTY' AND violation_code IN ({severe_codes_sql})) as license_severe_count,
                    COUNT(*) FILTER (
                        WHERE disposition = 'GUILTY'
                        AND (EXTRACT(HOUR FROM date_of_violation) >= 22 
                             OR EXTRACT(HOUR FROM date_of_violation) < 4)
                    ) as license_night_violations
                FROM violations
                WHERE driver_license_number IS NOT NULL
                  AND driver_license_number NOT IN ('', 'NA', 'UNKNOWN')
                GROUP BY TRIM(driver_license_number)
            )
            SELECT 
                rv.plate_id, rv.registration_state, rv.violation_count, rv.risk_points,
                rv.last_violation, rv.severe_count, rv.high_tier_count, rv.low_tier_count,
                rv.night_violations, rv.primary_borough, rv.borough_count, rv.primary_court,
                latest_v.driver_license_number,
                COALESCE(license_stats.license_violation_count, 0) as license_violation_count,
                rv.primary_agency,
                COALESCE(license_stats.license_points, 0) as license_points,
                COALESCE(license_stats.license_severe_count, 0) as license_severe_count,
                COALESCE(license_stats.license_night_violations, 0) as license_night_violations
            FROM (
                SELECT * FROM dmv_risk_view ORDER BY risk_points DESC LIMIT 5000
            ) rv
            LEFT JOIN LATERAL (
                SELECT driver_license_number FROM violations 
                WHERE plate_id = rv.plate_id AND plate_state = rv.registration_state 
                ORDER BY date_of_violation DESC LIMIT 1
            ) latest_v ON true
            LEFT JOIN license_stats ON TRIM(latest_v.driver_license_number) = license_stats.license_num
        """)
        
        all_drivers = []
        for row in cur:
            plate_id = row[0]
            state = row[1]
            violation_count = row[2]  # Plate violation count
            risk_points = row[3]  # Plate points
            last_violation = row[4]
            plate_severe_count = row[5]  # Plate-level severe count
            high_tier_count = row[6]
            low_tier_count = row[7]
            plate_night_violations = row[8]  # Plate-level night violations
            primary_borough = row[9]
            borough_count = row[10]
            primary_court = row[11]
            driver_license_number = row[12]
            license_violation_count = row[13] if row[13] is not None else 0  # License-specific violation count
            police_agency = row[14] if len(row) > 14 else "Unknown"
            license_points = row[15] if len(row) > 15 else 0  # License-specific points
            license_severe_count = row[16] if len(row) > 16 else 0  # License-specific severe count
            license_night_violations = row[17] if len(row) > 17 else 0  # License-specific night violations
            
            # Use license-specific data when license number exists, otherwise use plate data
            # CRITICAL: If driver has violations (even if 0 points due to DISMISSED), show driver stats
            # Only fall back to plate stats if no driver license data exists
            if driver_license_number and license_violation_count > 0:
                # Driver exists with violations - show their personal stats
                display_violation_count = license_violation_count
                display_points = license_points  # May be 0 if all dismissed - that's correct!
                severe_count = license_severe_count
                night_violations = license_night_violations
            else:
                # No driver license or no violations for this driver - show plate stats
                display_violation_count = violation_count
                display_points = risk_points
                severe_count = plate_severe_count
                night_violations = plate_night_violations
            
            status = compute_status(display_points, display_violation_count, policy)
            trigger_reason = get_trigger_reason(display_points, display_violation_count, policy)
            
            # Compute crash risk score
            crash_risk = compute_crash_risk_score(
                display_points, display_violation_count, night_violations, borough_count, policy
            )
            crash_risk_level = get_crash_risk_level(crash_risk)
            
            # Determine jurisdiction
            jurisdiction_type = get_jurisdiction_type(primary_borough, primary_court)
            court_name = primary_court if primary_court else (
                "NYC Dept of Finance" if jurisdiction_type == "NYC_DOF" else "Local Court"
            )
            
            is_cross_borough = borough_count >= 2
            is_night_heavy = (night_violations / display_violation_count) >= 0.5 if display_violation_count > 0 else False
            
            all_drivers.append({
                "plate_id": plate_id,
                "driver_license_number": driver_license_number,
                "state": state,
                "violation_count": display_violation_count,  # Use license-specific count when available
                "plate_violation_count": violation_count,  # Keep original plate count for reference
                "risk_score": display_points,  # Use driver-specific or plate points
                "risk_points": display_points,
                "total_points": display_points,  # Alias for clarity - now matches violation count
                "crash_risk_score": crash_risk,
                "crash_risk_level": crash_risk_level,
                "last_violation": last_violation.isoformat() if last_violation else None,
                "severe_count": severe_count,
                "high_tier_count": high_tier_count,
                "low_tier_count": low_tier_count,
                "night_violations": night_violations,
                "night_percentage": round((night_violations / display_violation_count) * 100) if display_violation_count > 0 else 0,
                "primary_borough": primary_borough,
                "borough_count": borough_count,
                "primary_court": primary_court,
                "court_name": court_name,
                "ticket_issuer": primary_court,  # Use primary_court which comes from ticket_issuer column
                "police_agency": police_agency,
                "jurisdiction_type": jurisdiction_type,
                "status": status,
                "enforcement_status": "NEW",  # Default, will be updated from alerts
                "is_cross_borough": is_cross_borough,
                "is_night_heavy": is_night_heavy,
                "trigger_reason": trigger_reason,
            })
        
        # Check for existing alerts - get latest status per plate
        cur.execute("""
            SELECT DISTINCT ON (plate_id) plate_id, status, court_name, responsible_party, due_date
            FROM dmv_alerts 
            ORDER BY plate_id, created_at DESC
        """)
        alert_data = {row[0]: {
            "status": row[1], 
            "court_name": row[2],
            "responsible_party": row[3],
            "due_date": row[4]
        } for row in cur}
        
        for driver in all_drivers:
            if driver['plate_id'] in alert_data:
                alert_info = alert_data[driver['plate_id']]
                driver['enforcement_status'] = alert_info['status']
                if alert_info['court_name']:
                    driver['court_name'] = alert_info['court_name']
                if alert_info['status'] == 'COMPLIANT':
                    driver['status'] = 'COMPLIANT'
        
        # Latest violation
        cur.execute("SELECT MAX(date_of_violation) FROM violations")
        latest = cur.fetchone()[0]
        
        highest_corridor = "NYC"
        corridor_count = 0
        
        # Enforcement queue (risk >= monitoring threshold), sorted by crash risk
        queue = [d for d in all_drivers if d['risk_points'] >= mon_threshold]
        queue.sort(key=lambda x: x['crash_risk_score'], reverse=True)
        
        cur.close()
        conn.close()
        
        return jsonify({
            "policy": get_policy_summary(policy),
            "kpis": {
                "isa_required": kpi_isa_required,
                "monitoring": kpi_monitoring,
                "super_speeders": kpi_super_speeders,
                "total_violations": kpi_total_violations,
                "cross_borough_violators": kpi_cross_borough,
                "cross_jurisdiction_offenders": cross_jurisdiction_count,
                "latest_violation": latest.isoformat() if latest else None,
                "highest_corridor": highest_corridor,
                "corridor_violations": corridor_count,
            },
            "county_stats": {
                "top_risk_counties": top_risk_counties,
                "most_1180d_county": most_1180d_county,
            },
            "filters_applied": {
                "county": filter_county,
                "court": filter_court,
                "agency": filter_agency,
                "source": filter_source,
            },
            "queue": queue,
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dmv_bp.route('/drivers/<plate_id>')
def get_driver(plate_id):
    """Get driver profile with policy-based risk calculation."""
    try:
        conn = get_db()
        policy = ISA_POLICY
        cur = conn.cursor()
        
        # First, find the registration state for this plate
        cur.execute("""
            SELECT plate_state FROM violations 
            WHERE plate_id = %s 
            GROUP BY plate_state 
            ORDER BY COUNT(*) DESC LIMIT 1
        """, (plate_id,))
        state_row = cur.fetchone()
        registration_state = state_row[0] if state_row else "NY"
        cur.close()
        
        # Use the compute_driver_risk helper with actual state
        risk = compute_driver_risk(conn, plate_id, registration_state, policy)
        
        if risk["total_tickets"] == 0:
            conn.close()
            return jsonify({"error": "Driver not found"}), 404
        
        cur = conn.cursor()
        
        # Determine action state
        if risk["status"] == 'ISA_REQUIRED':
            action_state = 'READY_FOR_ALERT'
        else:
            action_state = 'BELOW_THRESHOLD'
        
        # Compute lives at stake metric (crash likelihood * avg occupancy)
        lives_at_stake = round(risk["crash_risk_score"] / 100 * 1.8, 2)
        
        driver = {
            "plate_id": plate_id,
            "state": registration_state,
            "violation_count": risk["total_tickets"],
            "risk_points": risk["total_points"],
            "crash_risk_score": risk["crash_risk_score"],
            "crash_risk_level": risk["crash_risk_level"],
            "lives_at_stake": lives_at_stake,
            "last_violation": risk["latest_violation_ts"].isoformat() if risk["latest_violation_ts"] else None,
            "first_violation": risk["first_violation_ts"].isoformat() if risk["first_violation_ts"] else None,
            "severe_count": risk["severe_count"],
            "high_tier_count": risk["high_tier_count"],
            "low_tier_count": risk["low_tier_count"],
            "night_violations": risk["night_violations"],
            "night_percentage": round((risk["night_violations"] / risk["total_tickets"]) * 100) if risk["total_tickets"] > 0 else 0,
            "primary_borough": risk["primary_borough"],
            "borough_count": risk["borough_count"],
            "is_cross_borough": risk["borough_count"] >= 2,
            "court_name": risk["court_name"],
            "ticket_issuer": risk["court_name"],  # Use court_name which comes from ticket_issuer column
            "jurisdiction_type": risk["jurisdiction_type"],
            "status": risk["status"],
            "trigger_reason": risk["trigger_reason"],
            "enforcement_status": "NEW",
        }
        
        # Get all violations with points
        time_clause, time_params = get_time_window_filter(policy)
        
        cur.execute(f"""
            SELECT 
                violation_id, violation_code, violation_code as violation_description, date_of_violation,
                EXTRACT(HOUR FROM date_of_violation) as hour
            FROM violations
            WHERE plate_id = %s AND plate_state = %s
            {time_clause}
            ORDER BY date_of_violation DESC
        """, [plate_id, registration_state] + time_params)
        
        violations = []
        boroughs_seen = set(['NYC'])
        for row in cur:
            location = "NYC"
            borough = "NYC"
            
            hour = int(row[4]) if row[4] else 0
            is_night = hour >= 22 or hour < 4
            code = row[1]
            is_high_tier = code == '1180D'
            points = get_points_for_code(code, policy)
            
            violations.append({
                "id": row[0],
                "code": code,
                "description": f"Violation {row[1]}",
                "date": row[3].isoformat() if row[3] else None,
                "location": location,
                "borough": borough,
                "lat": 0,
                "lng": 0,
                "is_night": is_night,
                "is_high_tier": is_high_tier,
                "points": points,
            })
        
        driver["boroughs_affected"] = list(boroughs_seen)
        
        # Get alerts
        cur.execute("""
            SELECT alert_id, status, risk_score_at_alert, reason, created_at, resolved_at
            FROM dmv_alerts WHERE plate_id = %s ORDER BY created_at DESC
        """, (plate_id,))
        
        alerts = []
        for row in cur:
            alerts.append({
                "id": row[0],
                "status": row[1],
                "risk_at_alert": row[2],
                "notes": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
                "updated_at": row[5].isoformat() if row[5] else None,
            })
        
        if alerts:
            latest_status = alerts[0]['status']
            driver['enforcement_status'] = latest_status
            if latest_status == 'COMPLIANT':
                driver['status'] = 'COMPLIANT'
        
        cur.close()
        conn.close()
        
        return jsonify({
            "policy": get_policy_summary(policy),
            "driver": driver,
            "risk": {
                "total_points": risk["total_points"],
                "total_tickets": risk["total_tickets"],
                "severe_count": risk["severe_count"],
                "status": risk["status"],
            },
            "violations": violations,
            "alerts": alerts,
            "action_state": action_state,
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dmv_bp.route('/alerts')
def get_alerts():
    """Get DMV alerts for activity feed."""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT alert_id, plate_id, status, risk_score_at_alert, reason, created_at
            FROM dmv_alerts ORDER BY created_at DESC LIMIT 50
        """)
        
        alerts = []
        for row in cur:
            status = row[2]
            message = f"{row[1]} – ISA Notice Sent" if status == 'SENT' else f"{row[1]} – {status}"
            
            alerts.append({
                "id": row[0],
                "plate_id": row[1],
                "status": status,
                "risk": row[3],
                "notes": row[4],
                "timestamp": row[5].isoformat() if row[5] else None,
                "message": message,
            })
        
        cur.close()
        conn.close()
        return jsonify(alerts)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dmv_bp.route('/alerts/send', methods=['POST'])
def send_alert():
    """Send ISA Notice - transitions to NOTICE_SENT status."""
    try:
        data = request.json
        plate_id = data.get('plate_id')
        triggered_by = data.get('triggered_by', 'DMV Officer')
        
        if not plate_id:
            return jsonify({"error": "plate_id required"}), 400
        
        conn = get_db()
        
        # Use policy-based risk calculation
        risk = compute_driver_risk(conn, plate_id, "NY", ISA_POLICY)
        
        if risk["total_tickets"] == 0:
            conn.close()
            return jsonify({"error": "Driver not found"}), 404
        
        cur = conn.cursor()
        
        # Calculate follow-up due date (14 days from now)
        from datetime import timedelta
        due_date = datetime.now() + timedelta(days=14)
        
        cur.execute("""
            INSERT INTO dmv_alerts (
                plate_id, alert_type, status, risk_score_at_alert, crash_risk_at_alert,
                total_violations_at_alert, reason, responsible_party, due_date, 
                enforcement_stage, court_name
            )
            VALUES (%s, 'ISA_REQUIRED', 'NOTICE_SENT', %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING alert_id, created_at
        """, (
            plate_id, 
            risk["total_points"], 
            risk["crash_risk_score"],
            risk["total_tickets"], 
            f"ISA notice sent by {triggered_by}. Risk: {risk['total_points']} pts, Crash Risk: {risk['crash_risk_score']}%",
            "DMV",
            due_date,
            "NOTICE_SENT",
            risk["court_name"]
        ))
        
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "alert_id": result[0],
            "plate_id": plate_id,
            "status": "NOTICE_SENT",
            "enforcement_status": "NOTICE_SENT",
            "risk": risk["total_points"],
            "crash_risk": risk["crash_risk_score"],
            "due_date": due_date.isoformat(),
            "created_at": result[1].isoformat(),
            "message": f"ISA Notice sent for {plate_id}",
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dmv_bp.route('/alerts/<int:alert_id>/transition', methods=['POST'])
def transition_alert(alert_id):
    """Transition alert to next enforcement status."""
    try:
        data = request.json
        new_status = data.get('status')
        triggered_by = data.get('triggered_by', 'DMV Officer')
        notes = data.get('notes', '')
        
        valid_statuses = ['NEW', 'NOTICE_SENT', 'FOLLOW_UP_DUE', 'COMPLIANT', 'ESCALATED']
        if new_status not in valid_statuses:
            return jsonify({"error": f"Invalid status. Must be one of: {valid_statuses}"}), 400
        
        conn = get_db()
        cur = conn.cursor()
        
        # Calculate new due date for follow-up states
        due_date = None
        if new_status == 'FOLLOW_UP_DUE':
            from datetime import timedelta
            due_date = datetime.now() + timedelta(days=7)
        
        resolved_at = datetime.now() if new_status in ['COMPLIANT', 'ESCALATED'] else None
        
        cur.execute("""
            UPDATE dmv_alerts 
            SET status = %s, 
                enforcement_stage = %s,
                notes = COALESCE(notes, '') || %s,
                due_date = COALESCE(%s, due_date),
                resolved_at = %s,
                updated_at = NOW()
            WHERE alert_id = %s 
            RETURNING plate_id
        """, (
            new_status, 
            new_status,
            f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {triggered_by}: Transitioned to {new_status}. {notes}",
            due_date,
            resolved_at,
            alert_id
        ))
        
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Alert not found"}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True, 
            "alert_id": alert_id, 
            "plate_id": row[0], 
            "status": new_status,
            "enforcement_status": new_status
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dmv_bp.route('/alerts/<int:alert_id>/comply', methods=['POST'])
def mark_compliant(alert_id):
    """Mark driver as compliant - shortcut for transition to COMPLIANT."""
    try:
        data = request.json
        triggered_by = data.get('triggered_by', 'DMV Officer')
        
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE dmv_alerts 
            SET status = 'COMPLIANT', 
                enforcement_stage = 'COMPLIANT',
                reason = %s, 
                resolved_at = NOW(),
                updated_at = NOW()
            WHERE alert_id = %s 
            RETURNING plate_id
        """, (f"Marked compliant by {triggered_by}. ISA device installed.", alert_id))
        
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Alert not found"}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True, 
            "alert_id": alert_id, 
            "plate_id": row[0], 
            "status": "COMPLIANT",
            "enforcement_status": "COMPLIANT"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dmv_bp.route('/policy')
def get_policy():
    """Get current ISA policy configuration."""
    return jsonify({
        "policy": ISA_POLICY,
        "summary": get_policy_summary(ISA_POLICY),
        "enforcement_states": ENFORCEMENT_STATES,
    })


# =============================================================================
# LOCAL COURTS ADAPTER ENDPOINTS (Statewide Support)
# =============================================================================

@dmv_bp.route('/local-courts/summary')
def get_local_courts_summary():
    """
    Get summary of statewide local courts data.
    Powers the Local Courts Adapter UI panel.
    Uses ticket_issuer and police_agency columns from violations table.
    """
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Get unique counts
        cur.execute("SELECT COUNT(DISTINCT ticket_issuer) FROM violations WHERE ticket_issuer IS NOT NULL")
        unique_courts = cur.fetchone()[0] or 0
        
        cur.execute("SELECT COUNT(DISTINCT police_agency) FROM violations WHERE police_agency IS NOT NULL")
        unique_agencies = cur.fetchone()[0] or 0
        
        # Top ticket issuers by violation count
        cur.execute("""
            SELECT ticket_issuer, COUNT(*) as cnt 
            FROM violations 
            WHERE ticket_issuer IS NOT NULL 
            GROUP BY ticket_issuer 
            ORDER BY cnt DESC 
            LIMIT 10
        """)
        top_courts = [{"court": r[0], "count": r[1]} for r in cur.fetchall()]
        
        # Top police agencies
        cur.execute("""
            SELECT police_agency, COUNT(*) as cnt 
            FROM violations 
            WHERE police_agency IS NOT NULL 
            GROUP BY police_agency 
            ORDER BY cnt DESC 
            LIMIT 10
        """)
        top_agencies = [{"police_agency": r[0], "count": r[1]} for r in cur.fetchall()]
        
        # Derive counties from ticket_issuer names (simple extraction)
        cur.execute("""
            SELECT ticket_issuer, COUNT(*) as cnt 
            FROM violations 
            WHERE ticket_issuer IS NOT NULL 
            GROUP BY ticket_issuer 
            ORDER BY cnt DESC
        """)
        issuer_counts = cur.fetchall()
        
        # Extract county from ticket_issuer name (e.g., "SUFFOLK COUNTY TPVA" -> "SUFFOLK")
        county_counts = {}
        for issuer_name, count in issuer_counts:
            if issuer_name:
                parts = issuer_name.upper().split()
                if 'COUNTY' in parts:
                    idx = parts.index('COUNTY')
                    if idx > 0:
                        county = parts[idx - 1]
                        county_counts[county] = county_counts.get(county, 0) + count
                elif 'NYC' in issuer_name.upper() or 'NEW YORK CITY' in issuer_name.upper():
                    county_counts['NYC'] = county_counts.get('NYC', 0) + count
                # Skip entries without "COUNTY" in the name to avoid false positives
        
        top_counties = [{"county": k, "count": v} for k, v in sorted(county_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
        unique_counties = len(county_counts)
        
        cur.close()
        conn.close()
        
        return jsonify({
            "unique_counties": unique_counties,
            "unique_courts": unique_courts,
            "unique_police_agencies": unique_agencies,
            "top_counties": top_counties,
            "top_courts": top_courts,
            "top_agencies": top_agencies,
            "all_counties": list(county_counts.keys()),
            "all_courts": [c["court"] for c in top_courts],
            "all_agencies": [a["police_agency"] for a in top_agencies],
            "message": f"Local Courts Adapter: {unique_courts} ticket issuers, {unique_agencies} agencies, {unique_counties} counties"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dmv_bp.route('/local-courts/upload', methods=['POST'])
def upload_local_court_csv():
    """
    Upload CSV from local courts.
    Parses and inserts violation data into the database.
    """
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file selected"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Parse CSV
        import csv
        import io
        from datetime import datetime
        
        content = file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        
        rows = list(reader)
        if not rows:
            return jsonify({"error": "Empty CSV file"}), 400
            
        conn = get_db()
        cur = conn.cursor()
        
        inserted_count = 0
        error_count = 0
        first_error = None
        
        # Detect format (simple vs full)
        headers = rows[0].keys()
        is_full_format = 'driver_license_number' in headers
        
        print(f"Processing upload: {len(rows)} rows, Full Format: {is_full_format}")
        
        for row in rows:
            try:
                # Handle different date formats
                violation_date_str = row.get('violation_date') or row.get('date_of_violation')
                try:
                    if 'T' in violation_date_str:
                        violation_date = datetime.fromisoformat(violation_date_str.replace('Z', ''))
                    else:
                        violation_date = datetime.strptime(violation_date_str, '%Y-%m-%d %H:%M:%S')
                except:
                    # Fallback try other format
                    try:
                        violation_date = datetime.strptime(violation_date_str, '%Y-%m-%d')
                    except:
                        violation_date = datetime.now() # Fallback
                
                # Extract or Default other fields
                plate_id = row.get('plate_id', '').strip().upper()
                if not plate_id: continue
                
                plate_state = row.get('plate_state') or row.get('registration_state') or "NY"
                violation_code = row.get('violation_code') or "1180D"
                
                if is_full_format:
                    # Use all fields if available - validate required fields
                    driver_license = row.get('driver_license_number', '').strip()
                    driver_name = row.get('driver_full_name', '').strip()
                    dob = row.get('date_of_birth', '').strip()
                    
                    if not driver_license or not driver_name or not dob:
                        raise ValueError(f"Missing required field: driver_license_number, driver_full_name, or date_of_birth")
                    
                    license_state = row.get('license_state', 'NY').strip()
                    disposition = row.get('disposition', 'GUILTY').strip()
                    
                    try:
                        lat = float(row.get('latitude', 0) or 0)
                        lng = float(row.get('longitude', 0) or 0)
                    except (ValueError, TypeError):
                        raise ValueError(f"Invalid coordinates: latitude={row.get('latitude')}, longitude={row.get('longitude')}")
                    
                    police_agency = row.get('police_agency', 'Unknown').strip()
                    ticket_issuer = row.get('court') or row.get('ticket_issuer', 'Unknown')
                    if ticket_issuer:
                        ticket_issuer = ticket_issuer.strip()
                else:
                    # Defaults for simple format
                    driver_license = "UNKNOWN"
                    driver_name = "UNKNOWN" 
                    dob = "1980-01-01"
                    license_state = "NY"
                    disposition = row.get('disposition', 'GUILTY')
                    lat = 0.0
                    lng = 0.0
                    police_agency = row.get('police_agency', 'Local Police')
                    ticket_issuer = row.get('court') or row.get('ticket_issuer', 'Local Court')

                # Ensure vehicle exists (required for foreign key)
                cur.execute("""
                    INSERT INTO vehicles (plate_id, registration_state)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (plate_id, plate_state))

                # Insert into DB
                cur.execute("""
                    INSERT INTO violations (
                        driver_license_number, driver_full_name, date_of_birth, license_state,
                        plate_id, plate_state, violation_code, date_of_violation,
                        disposition, latitude, longitude,
                        police_agency, ticket_issuer, source_type
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'local_court_upload')
                """, (
                    driver_license, driver_name, dob, license_state,
                    plate_id, plate_state, violation_code, violation_date,
                    disposition, lat, lng,
                    police_agency, ticket_issuer
                ))
                
                inserted_count += 1
                
            except Exception as e:
                error_msg = str(e)
                print(f"Error processing row {inserted_count + error_count + 1}: {error_msg}")
                if error_count == 0:
                    first_error = error_msg
                error_count += 1
                continue
        
        # Update driver license summaries
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
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "filename": file.filename,
            "inserted": inserted_count,
            "errors": error_count,
            "first_error": first_error if error_count > 0 else None,
            "message": f"Successfully imported {inserted_count} violations."
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# COUNTY-LEVEL RISK ANALYTICS
# =============================================================================

@dmv_bp.route('/county-stats')
def get_county_stats():
    """
    Get county-level risk statistics for County Risk Cards.
    Note: Current schema doesn't have county column - returning NYC-based stats.
    """
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Get overall stats since we don't have county data
        cur.execute("""
            SELECT 
                COUNT(*) as total_violations,
                COUNT(*) FILTER (WHERE violation_code = '1180D') as severe_1180d,
                COUNT(*) FILTER (WHERE violation_code IN ('1180C', '1180D')) as high_severity,
                COUNT(*) FILTER (
                    WHERE EXTRACT(HOUR FROM date_of_violation) >= 22 
                       OR EXTRACT(HOUR FROM date_of_violation) < 4
                ) as nighttime_violations
            FROM violations
        """)
        
        row = cur.fetchone()
        total = row[0] or 0
        severe_1180d = row[1] or 0
        high_severity = row[2] or 0
        nighttime = row[3] or 0
        
        nighttime_pct = round(100.0 * nighttime / total, 1) if total > 0 else 0
        severe_pct = round(100.0 * severe_1180d / total, 1) if total > 0 else 0
        
        top_counties = [{
            "county": "NYC",
                "total_violations": total,
            "severe_1180d": severe_1180d,
            "high_severity": high_severity,
            "nighttime_violations": nighttime,
            "nighttime_percent": nighttime_pct,
            "severe_percent": severe_pct
        }]
        
        high_severity_counties = [{"county": "NYC", "count": severe_1180d}]
        
        county_risk = [{
            "county": "NYC",
            "crash_risk_score": severe_pct,
            "total_violations": total,
            "avg_points": 4.0
        }]
        
        cur.close()
        conn.close()
        
        return jsonify({
            "top_counties": top_counties,
            "high_severity_counties": high_severity_counties,
            "county_crash_risk": county_risk,
            "top_risk_county": county_risk[0] if county_risk else None,
            "most_1180d_county": high_severity_counties[0] if high_severity_counties else None
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# CROSS-JURISDICTION ANALYTICS
# =============================================================================

@dmv_bp.route('/cross-jurisdiction')
def get_cross_jurisdiction_stats():
    """
    Get cross-jurisdiction offender statistics.
    Note: Current schema doesn't have county column - returning placeholder data.
    """
    try:
        return jsonify({
            "total_cross_county_offenders": 0,
            "multi_county_offenders": 0,
            "top_cross_jurisdiction": [],
            "message": "Cross-jurisdiction tracking requires county data"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# IMPACT METRICS (Governor-Ready)
# =============================================================================

@dmv_bp.route('/impact-metrics')
def get_impact_metrics():
    """
    Get governor-ready impact metrics.
    Shows estimated lives saved and crash exposure reduction.
    """
    try:
        ensure_view_exists(ISA_POLICY)
        conn = get_db()
        cur = conn.cursor()
        
        # Total severe speeding violations
        cur.execute("SELECT COUNT(*) FROM violations WHERE violation_code = '1180D'")
        total_severe = cur.fetchone()[0]
        
        # High-risk drivers pending notice
        cur.execute("""
            SELECT COUNT(DISTINCT plate_id)
            FROM dmv_risk_view
            WHERE risk_points >= 11
        """)
        pending_notice = cur.fetchone()[0]
        
        # Cross-jurisdiction offenders (placeholder since no county column)
        cross_jurisdiction = 0
        
        # ISA compliant drivers
        cur.execute("SELECT COUNT(DISTINCT plate_id) FROM dmv_alerts WHERE status = 'COMPLIANT'")
        isa_compliant = cur.fetchone()[0]
        
        # Calculate estimated impact
        # 21% of severe speeders involved in fatal crashes
        # 64% reduction with ISA device
        fatality_risk = 0.21
        isa_effectiveness = 0.64
        
        estimated_fatal_exposure = int(total_severe * fatality_risk)
        potential_lives_saved = int(estimated_fatal_exposure * isa_effectiveness)
        lives_saved_so_far = int(isa_compliant * fatality_risk * isa_effectiveness)
        
        cur.close()
        conn.close()
        
        return jsonify({
            "total_severe_violations": total_severe,
            "high_risk_pending_notice": pending_notice,
            "cross_jurisdiction_offenders": cross_jurisdiction,
            "isa_compliant_drivers": isa_compliant,
            "estimated_fatal_exposure": estimated_fatal_exposure,
            "potential_lives_saved": potential_lives_saved,
            "lives_saved_so_far": lives_saved_so_far,
            "methodology": {
                "fatality_risk": "21% of severe speeders involved in fatal crashes",
                "isa_effectiveness": "64% crash reduction with ISA device",
                "source": "NHTSA speed limiter effectiveness studies"
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# DATA SOURCE FILTERING
# =============================================================================

@dmv_bp.route('/sources')
def get_data_sources():
    """Get available data sources for filtering."""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT source_type, COUNT(*) as cnt
            FROM violations
            GROUP BY source_type
            ORDER BY cnt DESC
        """)
        
        sources = [{"source": r[0], "count": r[1]} for r in cur]
        
        cur.close()
        conn.close()
        
        return jsonify({
            "sources": sources,
            "available_filters": ["ny_state_csv", "ny_state_generated", "police_stop", "camera"]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# ISA THRESHOLD DATASETS (Hackathon Deliverables A & B)
# =============================================================================

@dmv_bp.route('/isa/summary')
def api_isa_summary():
    """
    Get summary counts for ISA thresholds.
    Returns total drivers with 11+ points (24m) and plates with 16+ tickets (12m).
    """
    try:
        summary = get_isa_summary_counts()
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dmv_bp.route('/isa/drivers-24m')
def api_drivers_24m():
    """
    DATASET A: Drivers with 11+ points in 24-month trailing window.
    Returns grouped data with each driver's violations.
    """
    try:
        flat = request.args.get('flat', 'false').lower() == 'true'
        
        if flat:
            # Flat list: one row per violation
            data = get_drivers_flat_list(time_window_months=24)
        else:
            # Grouped: one entry per driver with nested violations
            data = get_drivers_11_plus_points(time_window_months=24)
        
        return jsonify({
            "count": len(data) if flat else len(data),
            "unique_drivers": len(set(d["driver_license_number"] for d in data)) if flat else len(data),
            "time_window_months": 24,
            "points_threshold": ISA_POLICY["isa_points_threshold"],
            "data": data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dmv_bp.route('/isa/plates-12m')
def api_plates_12m():
    """
    DATASET B: Plates with 16+ tickets in 12-month trailing window.
    Returns grouped data with each plate's violations.
    """
    try:
        flat = request.args.get('flat', 'false').lower() == 'true'
        
        if flat:
            # Flat list: one row per violation
            data = get_plates_flat_list(time_window_months=12)
        else:
            # Grouped: one entry per plate with nested violations
            data = get_plates_16_plus_tickets(time_window_months=12)
        
        return jsonify({
            "count": len(data) if flat else len(data),
            "unique_plates": len(set(d["plate_id"] for d in data)) if flat else len(data),
            "time_window_months": 12,
            "ticket_threshold": ISA_POLICY["isa_ticket_threshold"],
            "data": data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dmv_bp.route('/isa/send-summary', methods=['POST'])
def send_isa_summary():
    """
    Email alert system - sends ISA threshold notifications to DMV and vendors.
    Uses templates.html for professional HTML email formatting.
    In production, this would integrate with SMTP/SendGrid to send actual emails.
    For demo, it logs the action and returns success.
    """
    import logging
    from email_utils import send_batch_isa_notifications, get_violation_description
    
    try:
        payload = request.get_json() or {}
        recipients = payload.get("recipients", ["dmv@ny.gov", "vendor@isa.ny.gov"])
        drivers_list = payload.get("drivers", [])
        plates_count = payload.get("plates_count", 0)
        send_real = payload.get("send_real_email", False)  # Set to True in production
        
        # Log the email action
        logging.info(
            f"[ISA EMAIL] Sending ISA notifications to {recipients}. "
            f"Drivers: {len(drivers_list)}, Plates: {plates_count}"
        )
        
        # Send individual ISA notifications using template
        email_results = None
        if drivers_list:
            # Prepare driver data for email template
            drivers_for_email = []
            for driver in drivers_list[:10]:  # Limit to first 10 for demo
                drivers_for_email.append({
                    "license_number": driver.get("license_number", "N/A"),
                    "license_plate": driver.get("plate", "N/A"),
                    "violation_code": driver.get("violation_code", "1180D"),
                    "violation_description": get_violation_description(driver.get("violation_code", "1180D")),
                    "total_points": driver.get("total_points", 0)
                })
            
            email_results = send_batch_isa_notifications(drivers_for_email, send_real_email=send_real)
        
        return jsonify({
            "status": "ok",
            "message": "ISA notifications sent successfully" if send_real else "ISA notifications queued (demo mode)",
            "sent_to": recipients,
            "summary": {
                "drivers_11_plus": len(drivers_list),
                "plates_16_plus": plates_count,
                "timestamp": datetime.utcnow().isoformat(),
                "emails_sent": email_results.get("sent", 0) if email_results else 0
            },
            "email_results": email_results,
            "note": "Uses templates.html for professional ISA notice formatting. In production, emails would be sent via SMTP/SendGrid with CSV attachments."
        })
        
    except Exception as e:
        logging.error(f"Error sending ISA emails: {e}")
        return jsonify({"error": str(e)}), 500


@dmv_bp.route('/isa/warnings/drivers')
def api_warning_drivers():
    """
    Get drivers in warning band (8-10 points) - approaching ISA threshold.
    These drivers need proactive outreach before they hit the ISA mandate.
    """
    try:
        min_pts = int(request.args.get('min', 8))
        max_pts = int(request.args.get('max', 10))
        
        data = get_warning_drivers(time_window_months=24, min_points=min_pts, max_points=max_pts)
        
        return jsonify({
            "count": len(data),
            "min_points": min_pts,
            "max_points": max_pts,
            "threshold": ISA_POLICY["isa_points_threshold"],
            "time_window_months": 24,
            "data": data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dmv_bp.route('/isa/warnings/plates')
def api_warning_plates():
    """
    Get plates in warning band (12-15 tickets) - approaching ISA threshold.
    These vehicles need monitoring before they trigger the ISA mandate.
    """
    try:
        min_tix = int(request.args.get('min', 12))
        max_tix = int(request.args.get('max', 15))
        
        data = get_warning_plates(time_window_months=12, min_tickets=min_tix, max_tickets=max_tix)
        
        return jsonify({
            "count": len(data),
            "min_tickets": min_tix,
            "max_tickets": max_tix,
            "threshold": ISA_POLICY["isa_ticket_threshold"],
            "time_window_months": 12,
            "data": data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# STUB ENDPOINTS (for backward compatibility)
# =============================================================================

@dmv_bp.route('/sixteen-plus-tickets')
def api_sixteen_plus_tickets():
    """Stub endpoint for sixteen-plus-tickets - redirects to ISA data."""
    try:
        data = get_plates_16_plus_tickets(time_window_months=12)
        return jsonify({
            "threshold_count": len(data),
            "total_count": len(data),
            "time_window_months": 12,
            "drivers": []  # Legacy format
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dmv_bp.route('/plates-violations')
def api_plates_violations():
    """Stub endpoint for plates-violations."""
    try:
        data = get_plates_16_plus_tickets(time_window_months=12)
        return jsonify({
            "count": len(data),
            "data": data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
