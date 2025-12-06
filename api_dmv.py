#!/usr/bin/env python3
"""
DMV ISA Enforcement API
Enhanced with severity, recency, time-of-day, and geography signals.
All data from real NYC Open Data violations.
"""
import os
from flask import Blueprint, jsonify, request
import psycopg
from dotenv import load_dotenv

load_dotenv()

dmv_bp = Blueprint('dmv', __name__, url_prefix='/api/dmv')

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "traffic_violations_db"),
    "user": os.getenv("DB_USER", "myuser"),
    "password": os.getenv("DB_PASSWORD", "mypassword"),
}

# DMV thresholds for ISA device requirement
# Two triggers: 11+ points on license OR 16+ speeding tickets
POINTS_THRESHOLD = 11        # 11+ points = ISA required
TICKETS_THRESHOLD = 16       # 16+ speeding tickets = ISA required
MONITOR_THRESHOLD = 6        # Start monitoring at 6 points


def get_db():
    return psycopg.connect(**DB_CONFIG)


def ensure_view_exists():
    """Create the enhanced risk view using ALL data."""
    conn = get_db()
    cur = conn.cursor()
    
    # Drop and recreate to avoid column order issues
    cur.execute("DROP VIEW IF EXISTS dmv_risk_view CASCADE")
    cur.execute("""
        CREATE VIEW dmv_risk_view AS
        SELECT 
            v.plate_id,
            v.registration_state,
            COUNT(*) AS violation_count,
            SUM(CASE 
                WHEN v.violation_code = '1180D' THEN 8
                WHEN v.violation_code = '1180C' THEN 5
                WHEN v.violation_code = '1180B' THEN 3
                WHEN v.violation_code IN ('1180E', '1180F') THEN 6
                ELSE 2
            END) AS risk_points,
            MAX(issue_date) AS last_violation,
            MIN(issue_date) AS first_violation,
            COUNT(*) FILTER (WHERE violation_code = '1180D') AS high_tier_count,
            COUNT(*) FILTER (WHERE violation_code = '1180A') AS low_tier_count,
            COUNT(*) FILTER (
                WHERE EXTRACT(HOUR FROM issue_date) >= 22 
                   OR EXTRACT(HOUR FROM issue_date) < 4
            ) AS night_violations,
            COALESCE(SPLIT_PART(MAX(v.violation_location), ',', 1), 'Unknown') AS primary_borough,
            COUNT(DISTINCT SPLIT_PART(v.violation_location, ',', 1)) AS borough_count,
            MAX(v.court) AS primary_court
        FROM violations v
        WHERE 
            v.plate_id NOT LIKE 'UNK%%'
            AND v.plate_id != 'NA'
            AND LENGTH(v.plate_id) >= 4
        GROUP BY 
            v.plate_id, v.registration_state
        HAVING 
            COUNT(*) >= 1
    """)
    conn.commit()
    cur.close()
    conn.close()


# NYC boroughs for determining ticket issuer
NYC_BOROUGHS = ['MANHATTAN', 'BROOKLYN', 'QUEENS', 'BRONX', 'STATEN ISLAND', 
                'NEW YORK', 'KINGS', 'RICHMOND', 'NYC']


def get_ticket_issuer(primary_borough, court):
    """Determine ticket issuer based on location.
    NYC = Department of Finance, Outside NYC = Local Court"""
    if primary_borough:
        borough_upper = primary_borough.upper().strip()
        # Check if it's an NYC borough
        for nyc in NYC_BOROUGHS:
            if nyc in borough_upper or borough_upper in nyc:
                return "NYC Dept of Finance"
        # Check if court name contains NYC TVB
        if court and 'TVB' in court.upper():
            return "NYC Dept of Finance"
    
    # Outside NYC - return the court name or default
    if court:
        return court
    return "Local Court"


try:
    ensure_view_exists()
except:
    pass


@dmv_bp.route('/dashboard')
def get_dashboard():
    """Get DMV dashboard with enhanced KPIs and enforcement queue."""
    try:
        ensure_view_exists()
        conn = get_db()
        cur = conn.cursor()
        
        # Get top 5000 drivers from enhanced risk view (ALL data)
        cur.execute("""
            SELECT 
                plate_id, registration_state, violation_count, risk_points,
                last_violation, high_tier_count, low_tier_count,
                night_violations, primary_borough, borough_count, primary_court
            FROM dmv_risk_view
            ORDER BY risk_points DESC
            LIMIT 5000
        """)
        
        all_drivers = []
        for row in cur:
            # Columns: 0:plate_id, 1:state, 2:violation_count, 3:risk_points, 4:last_violation,
            #          5:high_tier_count, 6:low_tier_count, 7:night_violations, 8:primary_borough, 9:borough_count, 10:primary_court
            risk = row[3]
            violation_count = row[2]
            night_violations = row[7]
            borough_count = row[9]
            primary_borough = row[8]
            primary_court = row[10]
            
            # ISA required if: 11+ points OR 16+ speeding tickets
            isa_required = (risk >= POINTS_THRESHOLD) or (violation_count >= TICKETS_THRESHOLD)
            
            # Determine trigger reason
            trigger_reason = None
            if isa_required:
                if risk >= POINTS_THRESHOLD and violation_count >= TICKETS_THRESHOLD:
                    trigger_reason = f"{risk} points AND {violation_count} tickets"
                elif risk >= POINTS_THRESHOLD:
                    trigger_reason = f"{risk} points (threshold: {POINTS_THRESHOLD})"
                else:
                    trigger_reason = f"{violation_count} tickets (threshold: {TICKETS_THRESHOLD})"
            
            if isa_required:
                status = 'ISA_REQUIRED'
                action_state = 'READY_FOR_ALERT'
            elif risk >= MONITOR_THRESHOLD:
                status = 'MONITORING'
                action_state = 'BELOW_THRESHOLD'
            else:
                status = 'OK'
                action_state = 'BELOW_THRESHOLD'
            
            is_cross_borough = borough_count >= 2
            is_night_heavy = (night_violations / violation_count) >= 0.5 if violation_count > 0 else False
            
            all_drivers.append({
                "plate_id": row[0],
                "state": row[1],
                "violation_count": violation_count,
                "risk_points": risk,
                "last_violation": row[4].isoformat() if row[4] else None,
                "high_tier_count": row[5],
                "low_tier_count": row[6],
                "night_violations": night_violations,
                "primary_borough": primary_borough,
                "borough_count": borough_count,
                "primary_court": primary_court,
                "ticket_issuer": get_ticket_issuer(primary_borough, primary_court),
                "status": status,
                "action_state": action_state,
                "is_cross_borough": is_cross_borough,
                "is_night_heavy": is_night_heavy,
                "trigger_reason": trigger_reason,
            })
        
        # Check for existing alerts
        cur.execute("SELECT plate_id, status FROM dmv_alerts WHERE status IN ('SENT', 'COMPLIANT')")
        alert_statuses = {row[0]: row[1] for row in cur}
        
        for driver in all_drivers:
            if driver['plate_id'] in alert_statuses:
                alert_status = alert_statuses[driver['plate_id']]
                if alert_status == 'SENT':
                    driver['action_state'] = 'ALERT_SENT'
                elif alert_status == 'COMPLIANT':
                    driver['action_state'] = 'COMPLIANT'
                    driver['status'] = 'COMPLIANT'
        
        # KPIs
        isa_required = len([d for d in all_drivers if d['status'] == 'ISA_REQUIRED'])
        monitoring = len([d for d in all_drivers if d['status'] == 'MONITORING'])
        # "Super Speeders" = drivers with 3+ violations (high risk pattern)
        super_speeders = len([d for d in all_drivers if d['violation_count'] >= 3])
        cross_borough_count = len([d for d in all_drivers if d['is_cross_borough'] and d['risk_points'] >= MONITOR_THRESHOLD])
        
        # Latest violation
        cur.execute("SELECT MAX(issue_date) FROM violations")
        latest = cur.fetchone()[0]
        
        # Highest risk corridor
        cur.execute("""
            SELECT SPLIT_PART(violation_location, ',', 1) as borough, COUNT(*) as cnt
            FROM violations
            WHERE violation_location IS NOT NULL AND registration_state = 'NY'
            GROUP BY borough ORDER BY cnt DESC LIMIT 1
        """)
        row = cur.fetchone()
        highest_corridor = row[0] if row else "N/A"
        corridor_count = row[1] if row else 0
        
        # Enforcement queue (risk >= 5)
        queue = [d for d in all_drivers if d['risk_points'] >= MONITOR_THRESHOLD]
        
        cur.close()
        conn.close()
        
        return jsonify({
            "kpis": {
                "isa_required": isa_required,
                "monitoring": monitoring,
                "super_speeders": super_speeders,
                "cross_borough_violators": cross_borough_count,
                "latest_violation": latest.isoformat() if latest else None,
                "highest_corridor": highest_corridor,
                "corridor_violations": corridor_count,
            },
            "queue": queue,  # Return all drivers in queue (up to LIMIT from query)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dmv_bp.route('/drivers/<plate_id>')
def get_driver(plate_id):
    """Get driver profile with full violation timeline and risk signals."""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Get driver from risk view
        cur.execute("""
            SELECT 
                plate_id, registration_state, violation_count, risk_points,
                last_violation, first_violation, high_tier_count, low_tier_count,
                night_violations, primary_borough, borough_count
            FROM dmv_risk_view
            WHERE plate_id = %s
        """, (plate_id,))
        
        driver_row = cur.fetchone()
        if not driver_row:
            return jsonify({"error": "Driver not found"}), 404
        
        # Columns: 0:plate_id, 1:state, 2:violation_count, 3:risk_points, 4:last_violation,
        #          5:first_violation, 6:high_tier_count, 7:low_tier_count, 8:night_violations, 9:primary_borough, 10:borough_count
        risk = driver_row[3]
        violation_count = driver_row[2]
        night_violations = driver_row[8]
        borough_count = driver_row[10]
        
        # ISA required if: 11+ points OR 16+ speeding tickets
        isa_required = (risk >= POINTS_THRESHOLD) or (violation_count >= TICKETS_THRESHOLD)
        
        # Determine trigger reason
        trigger_reason = None
        if isa_required:
            if risk >= POINTS_THRESHOLD and violation_count >= TICKETS_THRESHOLD:
                trigger_reason = f"{risk} points AND {violation_count} tickets"
            elif risk >= POINTS_THRESHOLD:
                trigger_reason = f"{risk} points (threshold: {POINTS_THRESHOLD})"
            else:
                trigger_reason = f"{violation_count} tickets (threshold: {TICKETS_THRESHOLD})"
        
        if isa_required:
            status = 'ISA_REQUIRED'
            action_state = 'READY_FOR_ALERT'
        elif risk >= MONITOR_THRESHOLD:
            status = 'MONITORING'
            action_state = 'BELOW_THRESHOLD'
        else:
            status = 'OK'
            action_state = 'BELOW_THRESHOLD'
        
        driver = {
            "plate_id": driver_row[0],
            "state": driver_row[1],
            "violation_count": violation_count,
            "risk_points": risk,
            "last_violation": driver_row[4].isoformat() if driver_row[4] else None,
            "first_violation": driver_row[5].isoformat() if driver_row[5] else None,
            "high_tier_count": driver_row[6],
            "low_tier_count": driver_row[7],
            "night_violations": night_violations,
            "night_percentage": round((night_violations / violation_count) * 100) if violation_count > 0 else 0,
            "primary_borough": driver_row[9],
            "borough_count": borough_count,
            "is_cross_borough": borough_count >= 2,
            "status": status,
            "trigger_reason": trigger_reason,
            "points_threshold": POINTS_THRESHOLD,
            "tickets_threshold": TICKETS_THRESHOLD,
        }
        
        # Get all violations
        cur.execute("""
            SELECT 
                violation_id, violation_code, violation_description, issue_date, violation_location,
                EXTRACT(HOUR FROM issue_date) as hour
            FROM violations
            WHERE plate_id = %s AND registration_state = 'NY'
            ORDER BY issue_date DESC
        """, (plate_id,))
        
        violations = []
        boroughs_seen = set()
        for row in cur:
            location = row[4] or ""
            borough = location.split(",")[0] if location else "Unknown"
            boroughs_seen.add(borough)
            
            # Parse lat/lng
            lat, lng = None, None
            if "(" in location and ")" in location:
                try:
                    coords = location.split("(")[1].split(")")[0]
                    lat, lng = [float(x.strip()) for x in coords.split(",")]
                except:
                    pass
            
            hour = int(row[5]) if row[5] else 0
            is_night = hour >= 22 or hour < 4
            is_high_tier = row[1] == '1180D'
            
            violations.append({
                "id": row[0],
                "code": row[1],
                "description": row[2] or "",
                "date": row[3].isoformat() if row[3] else None,
                "location": location,
                "borough": borough,
                "lat": lat,
                "lng": lng,
                "is_night": is_night,
                "is_high_tier": is_high_tier,
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
            if alerts[0]['status'] == 'SENT':
                action_state = 'ALERT_SENT'
            elif alerts[0]['status'] == 'COMPLIANT':
                action_state = 'COMPLIANT'
                driver['status'] = 'COMPLIANT'
        
        cur.close()
        conn.close()
        
        return jsonify({
            "driver": driver,
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
    """Send ISA Notice."""
    try:
        data = request.json
        plate_id = data.get('plate_id')
        triggered_by = data.get('triggered_by', 'DMV Officer')
        
        if not plate_id:
            return jsonify({"error": "plate_id required"}), 400
        
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("SELECT violation_count, risk_points FROM dmv_risk_view WHERE plate_id = %s", (plate_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Driver not found"}), 404
        
        violations, risk = row[0], row[1]
        
        cur.execute("""
            INSERT INTO dmv_alerts (plate_id, alert_type, status, risk_score_at_alert, total_violations_at_alert, reason)
            VALUES (%s, 'ISA_REQUIRED', 'SENT', %s, %s, %s)
            RETURNING alert_id, created_at
        """, (plate_id, risk, violations, f"ISA notice sent by {triggered_by}. Risk: {risk} pts from {violations} violations."))
        
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "alert_id": result[0],
            "plate_id": plate_id,
            "status": "SENT",
            "risk": risk,
            "created_at": result[1].isoformat(),
            "message": f"ISA Notice sent for {plate_id}",
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dmv_bp.route('/alerts/<int:alert_id>/comply', methods=['POST'])
def mark_compliant(alert_id):
    """Mark driver as compliant."""
    try:
        data = request.json
        triggered_by = data.get('triggered_by', 'DMV Officer')
        
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE dmv_alerts SET status = 'COMPLIANT', reason = %s, resolved_at = NOW()
            WHERE alert_id = %s RETURNING plate_id
        """, (f"Marked compliant by {triggered_by}. ISA device installed.", alert_id))
        
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Alert not found"}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"success": True, "alert_id": alert_id, "plate_id": row[0], "status": "COMPLIANT"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
