#!/usr/bin/env python3
"""
Flask server for Stop Super Speeders - All API endpoints.
Includes heatmap, cameras, drivers, and ISA enforcement.

Usage:
    python api.py

Then access API at: http://localhost:5001
"""
import os
import re
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Register DMV blueprint
from api_dmv import dmv_bp
app.register_blueprint(dmv_bp)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "traffic_violations_db"),
    "user": os.getenv("DB_USER", "myuser"),
    "password": os.getenv("DB_PASSWORD", "mypassword"),
}

# Real DMV thresholds for ISA device requirement
# Two triggers: 11+ points on license OR 16+ speeding tickets
POINTS_THRESHOLD = 11        # 11+ points = ISA required
TICKETS_THRESHOLD = 16       # 16+ speeding tickets = ISA required
MONITOR_THRESHOLD = 6        # Start monitoring at 6 points


def get_db():
    return psycopg.connect(**DB_CONFIG)


# =============================================================================
# HEATMAP ENDPOINTS
# =============================================================================

@app.route('/api/stats')
def get_stats():
    """Get database statistics including top violators."""
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM violations")
        violations = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM vehicles")
        vehicles = cur.fetchone()[0]

        cur.execute("""
            SELECT v.plate_id, v.registration_state, COUNT(vio.violation_id) as violation_count
            FROM vehicles v
            LEFT JOIN violations vio ON v.plate_id = vio.plate_id AND v.registration_state = vio.registration_state
            GROUP BY v.plate_id, v.registration_state
            HAVING COUNT(vio.violation_id) > 0
            ORDER BY violation_count DESC LIMIT 200
        """)
        top_violators = [{"plate_id": r[0], "registration_state": r[1], "count": r[2]} for r in cur]

        cur.execute("""
            SELECT violation_code, COUNT(*) as count
            FROM violations GROUP BY violation_code ORDER BY count DESC LIMIT 10
        """)
        violations_by_code = [{"code": r[0], "count": r[1]} for r in cur]

        cur.close()
        conn.close()

        return jsonify({
            "total_violations": violations,
            "total_vehicles": vehicles,
            "top_violators": top_violators,
            "violations_by_code": violations_by_code
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/heatmap')
def get_heatmap():
    """Get heatmap points from violations with coordinates and severity."""
    try:
        limit = request.args.get('limit', 50000, type=int)
        region = request.args.get('region', 'all')  # 'all', 'nyc', 'suffolk'
        
        conn = get_db()
        cur = conn.cursor()

        # Region bounds
        # NYC: 40.49-40.92 lat, -74.26 to -73.70 lon
        # Suffolk County: 40.66-41.16 lat, -73.50 to -71.85 lon
        
        if region == 'nyc':
            cur.execute("""
                SELECT latitude, longitude, violation_code, 
                       date_of_violation, plate_id, plate_state, police_agency
                FROM violations
                WHERE latitude BETWEEN 40.49 AND 40.92
                  AND longitude BETWEEN -74.26 AND -73.70
                LIMIT %s
            """, (limit,))
        elif region == 'suffolk':
            cur.execute("""
                SELECT latitude, longitude, violation_code, 
                       date_of_violation, plate_id, plate_state, police_agency
                FROM violations
                WHERE latitude BETWEEN 40.66 AND 41.16
                  AND longitude BETWEEN -73.50 AND -71.85
                LIMIT %s
            """, (limit,))
        else:
            # Statewide: Get balanced sample from NYC + rest of state
            # First get NYC points, then fill with rest of state
            nyc_limit = limit // 2  # Half from NYC
            other_limit = limit - nyc_limit  # Half from rest of state
            
            cur.execute("""
                (SELECT latitude, longitude, violation_code, 
                        date_of_violation, plate_id, plate_state, police_agency
                 FROM violations
                 WHERE latitude BETWEEN 40.49 AND 40.92
                   AND longitude BETWEEN -74.26 AND -73.70
                 LIMIT %s)
                UNION ALL
                (SELECT latitude, longitude, violation_code, 
                        date_of_violation, plate_id, plate_state, police_agency
                 FROM violations
                 WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                   AND NOT (latitude BETWEEN 40.49 AND 40.92 AND longitude BETWEEN -74.26 AND -73.70)
                 LIMIT %s)
            """, (nyc_limit, other_limit))

        def get_severity_from_code(code):
            """Map violation code to severity intensity (0.0-1.0)."""
            if not code:
                return 0.3
            code_str = str(code).strip().upper()
            # 1180A = 1-10 mph (low) -> 0.3
            # 1180B = 11-20 mph (moderate) -> 0.5
            # 1180C = 21-30 mph (high) -> 0.7
            # 1180D = 31+ mph (severe) -> 0.9
            if code_str == '1180A':
                return 0.3
            elif code_str == '1180B':
                return 0.5
            elif code_str == '1180C':
                return 0.7
            elif code_str == '1180D':
                return 0.9
            elif code_str in ('1180E', '1180F'):  # School/Work zones
                return 0.8
            else:
                return 0.4  # Default for other 1180 codes

        points = []
        for row in cur:
            lat, lon, violation_code, date_of_violation, plate_id, plate_state, police_agency = row
            
            if lat is not None and lon is not None and lat != 0 and lon != 0:
                severity = get_severity_from_code(violation_code)
                points.append({
                    'lat': float(lat),
                    'lon': float(lon),
                    'severity': severity,
                    'code': violation_code,
                    'description': f"Violation {violation_code}", # Placeholder as description col missing
                    'date': date_of_violation.isoformat() if date_of_violation else None,
                    'plate': plate_id,
                    'state': plate_state,
                    'location': f"({lat}, {lon})",
                    'police_agency': police_agency or "Unknown"
                })

        cur.close()
        conn.close()
        return jsonify(points)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# CAMERA ENDPOINTS
# =============================================================================

@app.route('/api/cameras')
def get_cameras():
    """Get all active camera locations."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT camera_id, name, latitude, longitude, borough, zone_type,
                   description, video_url, is_active
            FROM cameras 
            WHERE is_active = true
            ORDER BY camera_id
        """)

        cameras = [{
            "camera_id": r[0], "name": r[1], "latitude": float(r[2]), "longitude": float(r[3]),
            "borough": r[4], "zone_type": r[5], "description": r[6], "video_url": r[7], "is_active": r[8]
        } for r in cur]

        cur.close()
        conn.close()
        return jsonify(cameras)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/cameras/<camera_id>')
def get_camera(camera_id):
    """Get single camera details."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT camera_id, name, latitude, longitude, borough, zone_type,
                   description, video_url, is_active
            FROM cameras WHERE camera_id = %s
        """, (camera_id,))

        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Camera not found"}), 404

        camera = {
            "camera_id": row[0], "name": row[1], "latitude": float(row[2]), "longitude": float(row[3]),
            "borough": row[4], "zone_type": row[5], "description": row[6], "video_url": row[7], "is_active": row[8]
        }

        cur.close()
        conn.close()
        return jsonify(camera)
    except Exception as e:
        return jsonify({"error": str(e)}), 500





# =============================================================================
# DRIVER & ALERT ENDPOINTS
# =============================================================================

@app.route('/api/drivers')
def get_drivers():
    """Get all tracked drivers with risk scores."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT plate_id, registration_state, total_violations, current_risk_points,
                   isa_status, first_violation_date, last_violation_date
            FROM drivers WHERE total_violations > 0
            ORDER BY current_risk_points DESC
        """)

        drivers = [{
            "plate_id": r[0], "registration_state": r[1], "total_violations": r[2],
            "risk_points": r[3], "isa_status": r[4],
            "first_violation_date": r[5].isoformat() if r[5] else None,
            "last_violation_date": r[6].isoformat() if r[6] else None,
            "isa_required": r[4] == "ISA_REQUIRED"
        } for r in cur]

        cur.close()
        conn.close()
        return jsonify(drivers)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/drivers/<plate_id>')
def get_driver(plate_id):
    """Get single driver details with violation history."""
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT plate_id, registration_state, total_violations, current_risk_points,
                   isa_status, first_violation_date, last_violation_date
            FROM drivers WHERE plate_id = %s
        """, (plate_id,))

        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Driver not found"}), 404

        driver = {
            "plate_id": row[0], "registration_state": row[1], "total_violations": row[2],
            "risk_points": row[3], "isa_status": row[4],
            "first_violation_date": row[5].isoformat() if row[5] else None,
            "last_violation_date": row[6].isoformat() if row[6] else None,
            "isa_required": row[4] == "ISA_REQUIRED"
        }

        cur.execute("""
            SELECT violation_id, camera_id, violation_type, points, speed_detected,
                   speed_limit, is_school_zone, detected_at
            FROM ai_violations WHERE plate_id = %s ORDER BY detected_at DESC
        """, (plate_id,))

        driver["violations"] = [{
            "violation_id": v[0], "camera_id": v[1], "violation_type": v[2],
            "points": v[3], "speed_detected": v[4], "speed_limit": v[5],
            "is_school_zone": v[6], "detected_at": v[7].isoformat() if v[7] else None
        } for v in cur]

        cur.close()
        conn.close()
        return jsonify(driver)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/license/<license_number>/violations')
def get_violations_by_license(license_number):
    """Get all violations for a driver license number."""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Normalize license number (trim whitespace, ensure string)
        license_number = str(license_number).strip()
        
        # Get all violations for this license
        # Use TRIM on both sides to handle any whitespace issues in the database
        cur.execute("""
            SELECT DISTINCT
                v.violation_id,
                v.driver_license_number,
                v.driver_full_name,
                v.date_of_birth,
                v.license_state,
                v.plate_id,
                v.plate_state,
                v.violation_code,
                v.date_of_violation,
                v.disposition,
                v.latitude,
                v.longitude,
                v.police_agency,
                v.ticket_issuer,
                v.source_type,
                ai.speed_detected,
                ai.speed_limit,
                ai.screenshot_path,
                ai.ocr_confidence,
                ai.camera_id
            FROM violations v
            LEFT JOIN ai_violations ai ON v.violation_id = ai.violation_id
            WHERE TRIM(v.driver_license_number) = TRIM(%s)
            ORDER BY v.date_of_violation DESC
        """, (license_number,))
        
        violations = []
        driver_info = None
        
        for row in cur:
            if not driver_info and row[1]:
                driver_info = {
                    "driver_license_number": row[1],
                    "driver_full_name": row[2],
                    "date_of_birth": row[3].isoformat() if row[3] else None,
                    "license_state": row[4]
                }
            
            screenshot_path = row[17]
            screenshot_url = f'/snapshots/{Path(screenshot_path).name}' if screenshot_path else None
            
            violations.append({
                "violation_id": row[0],
                "plate_id": row[5],
                "plate_state": row[6],
                "violation_code": row[7],
                "date_of_violation": row[8].isoformat() if row[8] else None,
                "disposition": row[9],
                "latitude": float(row[10]) if row[10] else None,
                "longitude": float(row[11]) if row[11] else None,
                "police_agency": row[12],
                "ticket_issuer": row[13],
                "source_type": row[14],
                "speed_detected": float(row[15]) if row[15] else None,
                "speed_limit": row[16],
                "screenshot_url": screenshot_url,
                "ocr_confidence": float(row[18]) if row[18] else None,
                "camera_id": row[19]
            })
        
        # Get driver license summary (using TRIM for consistency)
        cur.execute("""
            SELECT total_speeding_tickets, points_on_license
            FROM driver_license_summary
            WHERE TRIM(driver_license_number) = TRIM(%s)
        """, (license_number,))
        
        summary_row = cur.fetchone()
        summary = None
        if summary_row:
            summary = {
                "total_speeding_tickets": summary_row[0],
                "points_on_license": summary_row[1]
            }
        
        cur.close()
        conn.close()
        
        if not violations:
            return jsonify({"error": "No violations found for this license"}), 404
        
        # Use the actual count from the violations array
        actual_count = len(violations)
        
        return jsonify({
            "success": True,
            "driver": driver_info,
            "summary": summary,
            "violations": violations,
            "total_violations": actual_count
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/alerts')
def get_alerts():
    """Get all DMV alerts."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT alert_id, plate_id, registration_state, alert_type, reason,
                   risk_score_at_alert, total_violations_at_alert, status, created_at
            FROM dmv_alerts ORDER BY created_at DESC
        """)

        alerts = [{
            "alert_id": r[0], "plate_id": r[1], "registration_state": r[2],
            "alert_type": r[3], "reason": r[4], "risk_score": r[5],
            "total_violations": r[6], "status": r[7],
            "created_at": r[8].isoformat() if r[8] else None
        } for r in cur]

        cur.close()
        conn.close()
        return jsonify(alerts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/ai-heatmap')
def get_ai_heatmap():
    """Get heatmap points from AI-detected violations."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT latitude, longitude, points
            FROM ai_violations
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """)

        points = [[float(r[0]), float(r[1]), r[2] / 4.0] for r in cur]

        cur.close()
        conn.close()
        return jsonify(points)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Store recent detections for SSE streaming
RECENT_DETECTIONS = []
MAX_RECENT_DETECTIONS = 50


@app.route('/api/cameras/<camera_id>/detect', methods=['POST'])
def run_detection(camera_id):
    """
    Process a detected violation from the CV pipeline.
    Uses REAL OCR plates and REAL speed estimation.
    Creates violation records and DMV alerts for high-risk drivers.
    Links to existing drivers or creates stable synthetic drivers.
    """
    try:
        data = request.json
        print(f"DEBUG: Received data: {data}")  # Debug log
        
        plate_id = data.get('plate_id')
        speed_detected = data.get('speed_detected')
        speed_limit = data.get('speed_limit', 30)
        violation_type = data.get('violation_type', 'speeding')
        corridor_name = data.get('corridor_name')
        ocr_confidence = data.get('ocr_confidence', 0.0)
        
        if not plate_id:
            return jsonify({"error": "plate_id required"}), 400
        
        # Validate plate format (OCR result or tracking-based ID)
        if not re.match(r'^[A-Z0-9\-]{5,12}$', plate_id):
            return jsonify({"error": "Invalid plate format"}), 400
        
        conn = get_db()
        cur = conn.cursor()
        
        # Get camera info
        cur.execute("""
            SELECT latitude, longitude, zone_type, name, borough, speed_limit
            FROM cameras WHERE camera_id = %s
        """, (camera_id,))
        cam_row = cur.fetchone()
        if not cam_row:
            cur.close()
            conn.close()
            return jsonify({"error": "Camera not found"}), 404
        
        cam_lat, cam_lng, zone_type, cam_name, borough = (
            float(cam_row[0]), float(cam_row[1]), cam_row[2], cam_row[3], cam_row[4] or "NYC"
        )
        # Use camera's configured speed limit if not provided
        if speed_limit == 30 and cam_row[5]:
            speed_limit = cam_row[5]
        
        corridor = corridor_name or cam_name
        
        # Calculate violation code based on speed over limit
        speed_over = speed_detected - speed_limit
        if speed_over >= 31:
            violation_code = "1180D"
            points = 8
        elif speed_over >= 21:
            violation_code = "1180C"
            points = 5
        elif speed_over >= 11:
            violation_code = "1180B"
            points = 3
        else:
            violation_code = "1180A"
            points = 2
        
        # School/work zone bonus
        if zone_type in ('school_zone', 'work_zone'):
            violation_code = "1180E" if zone_type == 'school_zone' else "1180F"
            points = 6
        
        # === REAL PLATE MATCHING & DRIVER LINKAGE ===
        
        # Check if this plate already exists in our system
        cur.execute("""
            SELECT v.driver_license_number, v.driver_full_name, v.date_of_birth
            FROM violations v
            WHERE v.plate_id = %s AND v.plate_state = 'NY'
            ORDER BY v.date_of_violation DESC
            LIMIT 1
        """, (plate_id,))
        existing_driver = cur.fetchone()
        
        if existing_driver:
            # Use existing driver info - this plate was seen before
            driver_license_number = existing_driver[0]
            driver_full_name = existing_driver[1]
            date_of_birth = existing_driver[2]
            print(f"  → Linked to existing driver: {driver_license_number}")
        else:
            # Create stable synthetic driver for this NEW plate
            # Generate deterministic ID from plate (so same plate = same driver)
            import hashlib
            plate_hash = hashlib.md5(plate_id.encode()).hexdigest()[:9].upper()
            driver_license_number = plate_hash
            
            # Generate stable name from plate hash
            first_names = ["JOHN", "JANE", "MICHAEL", "SARAH", "DAVID", "EMILY", "ROBERT", "JESSICA"]
            last_names = ["SMITH", "JOHNSON", "WILLIAMS", "BROWN", "JONES", "GARCIA", "MILLER", "DAVIS"]
            name_idx = int(plate_hash[:2], 16) % len(first_names)
            surname_idx = int(plate_hash[2:4], 16) % len(last_names)
            driver_full_name = f"{first_names[name_idx]} {last_names[surname_idx]}"
            
            # Generate stable DOB from plate hash
            from datetime import date
            year = 1950 + (int(plate_hash[4:6], 16) % 50)
            month = 1 + (int(plate_hash[6:7], 16) % 12)
            day = 1 + (int(plate_hash[7:8], 16) % 28)
            date_of_birth = date(year, month, day)
            
            print(f"  → Created new synthetic driver: {driver_license_number} ({driver_full_name})")
        
        # Ensure vehicle exists
        cur.execute("""
            INSERT INTO vehicles (plate_id, registration_state) 
            VALUES (%s, 'NY') ON CONFLICT DO NOTHING
        """, (plate_id,))
        
        # Get screenshot path if provided
        screenshot_path = data.get('screenshot_path')
        
        # Create violation record with REAL driver linkage
        cur.execute("""
            INSERT INTO violations (
                driver_license_number, driver_full_name, date_of_birth, license_state,
                plate_id, plate_state, violation_code, date_of_violation,
                disposition, latitude, longitude,
                police_agency, ticket_issuer, source_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s)
            RETURNING violation_id
        """, (
            driver_license_number, driver_full_name, date_of_birth, 'NY',
            plate_id, 'NY', violation_code, 'GUILTY',
            cam_lat, cam_lng,
            f"Camera {camera_id}", corridor, 'camera'
        ))
        violation_id = cur.fetchone()[0]
        
        # Store AI violation with screenshot and OCR confidence
        cur.execute("""
            INSERT INTO ai_violations (
                violation_id, camera_id, plate_id, violation_type,
                points, speed_detected, speed_limit, latitude, longitude,
                screenshot_path, ocr_confidence
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            violation_id, camera_id, plate_id, violation_type,
            points, speed_detected, speed_limit, cam_lat, cam_lng,
            screenshot_path, ocr_confidence
        ))
        
        # Update driver license summary
        cur.execute("""
            INSERT INTO driver_license_summary (driver_license_number, license_state, total_speeding_tickets, points_on_license)
            VALUES (%s, 'NY', 1, %s)
            ON CONFLICT (driver_license_number, license_state) DO UPDATE SET
                total_speeding_tickets = driver_license_summary.total_speeding_tickets + 1,
                points_on_license = driver_license_summary.points_on_license + %s,
                updated_at = NOW()
        """, (driver_license_number, points, points))
        
        # Get updated driver stats from violations table (using driver_license_number for accurate tracking)
        cur.execute("""
            SELECT 
                COUNT(*) as total_tickets,
                SUM(CASE 
                    WHEN violation_code = '1180D' THEN 8
                    WHEN violation_code = '1180C' THEN 5
                    WHEN violation_code = '1180B' THEN 3
                    WHEN violation_code IN ('1180E', '1180F') THEN 6
                    ELSE 2
                END) as total_points,
                COUNT(*) FILTER (WHERE violation_code IN ('1180D', '1180E', '1180F')) as severe_count,
                COUNT(*) FILTER (
                    WHERE EXTRACT(HOUR FROM date_of_violation) >= 22 
                       OR EXTRACT(HOUR FROM date_of_violation) < 4
                ) as night_violations,
                COUNT(DISTINCT police_agency) as borough_count
            FROM violations
            WHERE driver_license_number = %s AND license_state = 'NY'
        """, (driver_license_number,))
        
        stats = cur.fetchone()
        total_tickets = stats[0]
        total_points = stats[1]
        severe_count = stats[2]
        night_violations = stats[3]
        borough_count = stats[4]
        
        # Calculate crash risk score
        severity_factor = min(total_points / 11, 2.0) / 2.0
        nighttime_factor = (night_violations / total_tickets) if total_tickets > 0 else 0
        cross_borough_factor = 1.0 if borough_count > 1 else 0.0
        crash_risk = round((severity_factor * 0.6 + nighttime_factor * 0.3 + cross_borough_factor * 0.1) * 100, 1)
        
        # Determine status
        isa_required = (total_points >= POINTS_THRESHOLD) or (total_tickets >= TICKETS_THRESHOLD)
        status = "ISA_REQUIRED" if isa_required else ("MONITORING" if total_points >= MONITOR_THRESHOLD else "OK")
        
        # Create DMV alert if ISA required
        alert_created = None
        if isa_required:
            # Check if alert already exists
            cur.execute("""
                SELECT alert_id FROM dmv_alerts 
                WHERE plate_id = %s AND status NOT IN ('COMPLIANT', 'ESCALATED')
                ORDER BY created_at DESC LIMIT 1
            """, (plate_id,))
            existing_alert = cur.fetchone()
            
            if not existing_alert:
                # Create new alert with driver linkage
                cur.execute("""
                    INSERT INTO dmv_alerts (
                        plate_id, driver_license_number, alert_type, status, risk_score_at_alert, crash_risk_at_alert,
                        total_violations_at_alert, reason, responsible_party, court_name
                    ) VALUES (%s, %s, 'ISA_REQUIRED', 'NEW', %s, %s, %s, %s, 'DMV', 'NYC Dept of Finance')
                    RETURNING alert_id
                """, (
                    plate_id, driver_license_number, total_points, crash_risk, total_tickets,
                    f"CV Detection: {speed_detected} MPH at {corridor}. Crash Risk: {crash_risk}%"
                ))
                alert_id = cur.fetchone()[0]
                alert_created = {
                    "alert_id": alert_id,
                    "type": "ISA_REQUIRED",
                    "crash_risk": crash_risk,
                    "message": f"🚨 HIGH RISK: {plate_id} requires ISA device"
                }
        
        conn.commit()
        
        # Build detection result
        detection_result = {
            "success": True,
            "violation_id": violation_id,
            "plate_id": plate_id,
            "camera_id": camera_id,
            "camera_name": cam_name,
            "borough": borough,
            "speed_detected": speed_detected,
            "speed_limit": speed_limit,
            "violation_code": violation_code,
            "points": points,
            "ocr_confidence": ocr_confidence,
            "driver": {
                "plate_id": plate_id,
                "driver_license_number": driver_license_number,
                "driver_name": driver_full_name,
                "total_tickets": total_tickets,
                "total_points": total_points,
                "crash_risk_score": crash_risk,
                "status": status,
                "severe_count": severe_count,
            },
            "alert": alert_created,
            "is_high_risk": crash_risk >= 50,
        }
        
        # Store for SSE streaming
        RECENT_DETECTIONS.insert(0, {
            **detection_result,
            "timestamp": datetime.now().isoformat()
        })
        if len(RECENT_DETECTIONS) > MAX_RECENT_DETECTIONS:
            RECENT_DETECTIONS.pop()
        
        cur.close()
        conn.close()
        
        return jsonify(detection_result)
        
    except Exception as e:
        import traceback
        print(f"ERROR in run_detection: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/api/detections/recent')
def get_recent_detections():
    """Get recent CV detections for live feed."""
    limit = request.args.get('limit', 20, type=int)
    return jsonify(RECENT_DETECTIONS[:limit])


@app.route('/api/stats/lives-saved')
def get_lives_saved():
    """Calculate estimated lives saved based on ISA compliance."""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Count compliant drivers (ISA installed)
        cur.execute("""
            SELECT COUNT(DISTINCT plate_id) 
            FROM dmv_alerts WHERE status = 'COMPLIANT'
        """)
        compliant_count = cur.fetchone()[0] or 0
        
        # Each ISA device reduces crash risk by ~50%, avg 1.8 lives per fatal crash
        # Conservative estimate: 0.1 lives saved per ISA device per year
        lives_saved = round(compliant_count * 0.1, 1)
        
        # Count high-risk drivers identified
        cur.execute("""
            SELECT COUNT(*) FROM dmv_risk_view WHERE risk_points >= 11
        """)
        high_risk_identified = cur.fetchone()[0] or 0
        
        cur.close()
        conn.close()
        
        return jsonify({
            "lives_saved_estimate": lives_saved,
            "isa_devices_installed": compliant_count,
            "high_risk_identified": high_risk_identified,
            "methodology": "Based on NHTSA crash reduction data for speed limiters"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500





@app.route('/api/reset-demo', methods=['POST'])
def reset_demo():
    """Reset all demo data for a fresh start - clears all AI-detected drivers."""
    try:
        conn = get_db()
        cur = conn.cursor()

        # Clear all AI violations
        cur.execute("DELETE FROM ai_violations")
        
        # Clear all DMV alerts
        cur.execute("DELETE FROM dmv_alerts")
        
        # Delete all dynamically created drivers (those with our generated plate patterns)
        cur.execute("""
            DELETE FROM drivers 
            WHERE plate_id ~ '^[A-Z]{2,3}-[0-9]{4}$'
        """)
        
        # Reset road segments
        cur.execute("UPDATE road_segments SET total_violations = 0, risk_score = 0")

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Demo reset - all AI-detected drivers cleared"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Serve screenshots
from flask import send_from_directory
import os

SNAPSHOTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'snapshots')

@app.route('/snapshots/<path:filename>')
def serve_snapshot(filename):
    """Serve violation screenshots."""
    print(f"Serving snapshot: {filename} from {SNAPSHOTS_DIR}")
    return send_from_directory(SNAPSHOTS_DIR, filename)


@app.route('/api/cameras/screenshot', methods=['POST'])
def upload_screenshot():
    """Upload and save a screenshot from camera detection."""
    try:
        from werkzeug.utils import secure_filename
        import os
        
        if 'screenshot' not in request.files:
            return jsonify({"error": "No screenshot file"}), 400
        
        file = request.files['screenshot']
        camera_id = request.form.get('camera_id')
        plate_id = request.form.get('plate_id')
        
        if file.filename == '':
            return jsonify({"error": "Empty filename"}), 400
        
        # Create snapshots directory if it doesn't exist
        snapshots_dir = 'snapshots'
        if not os.path.exists(snapshots_dir):
            os.makedirs(snapshots_dir)
        
        # Save file
        filename = secure_filename(file.filename)
        filepath = os.path.join(snapshots_dir, filename)
        file.save(filepath)
        
        return jsonify({
            "success": True,
            "screenshot_path": filepath,
            "filename": filename
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/cameras/<camera_id>/violations', methods=['GET'])
def get_camera_violations(camera_id):
    """Get existing violations with screenshots for a camera."""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Query ai_violations directly (works with seeded snapshots)
        cur.execute("""
            SELECT 
                ai.violation_id,
                ai.plate_id,
                ai.violation_type,
                ai.detected_at,
                ai.speed_detected,
                ai.speed_limit,
                ai.camera_id,
                ai.screenshot_path,
                ai.ocr_confidence
            FROM ai_violations ai
            WHERE ai.camera_id = %s
              AND ai.screenshot_path IS NOT NULL
            ORDER BY ai.detected_at DESC
            LIMIT 10
        """, (camera_id,))
        
        violations = []
        for row in cur:
            screenshot_path = row[7]
            screenshot_url = f'/snapshots/{Path(screenshot_path).name}' if screenshot_path else None
            
            violations.append({
                'violation_id': row[0],
                'plate_id': row[1],
                'violation_code': row[2],
                'date': row[3].isoformat() if row[3] else None,
                'speed_detected': float(row[4]) if row[4] else 0,
                'speed_limit': row[5],
                'camera_id': row[6],
                'screenshot_url': screenshot_url,
                'ocr_confidence': float(row[8]) if row[8] else None,
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "camera_id": camera_id,
            "violations": violations
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/cameras/<camera_id>/run-detection', methods=['POST'])
def run_cv_detection(camera_id):
    """Run Python CV detector and return violations with screenshots."""
    import subprocess
    from datetime import datetime, timedelta
    
    # Map camera IDs to video files
    video_map = {
        'CAM-1': 'frontend-react/public/timesquare.mp4',
        'CAM-2': 'frontend-react/public/wallstreet.mp4',
        'CAM-3': 'frontend-react/public/brooklyn.mp4',
        'CAM-4': 'frontend-react/public/hudson valley albany.mp4',
        'CAM-5': 'frontend-react/public/JFK_Airport_Speeding_Camry_Video.mp4',
    }
    
    if camera_id not in video_map:
        return jsonify({"error": f"Unknown camera: {camera_id}"}), 404
    
    video_path = video_map[camera_id]
    
    # Record start time to only get NEW violations
    detection_start = datetime.now()
    
    try:
        # Run the Python CV detector
        print(f"🎥 Running CV detection for {camera_id}...")
        result = subprocess.run(
            ['python', 'cv_detector_realtime.py', '--camera-id', camera_id, '--video', video_path, '--no-display'],
            capture_output=True,
            text=True,
            timeout=60
        )
        print(f"CV output: {result.stdout}")
        if result.stderr:
            print(f"CV stderr: {result.stderr}")
        
        # Get ONLY the violations created during THIS detection session
        conn = get_db()
        cur = conn.cursor()
        
        # Get violations created in the last 2 minutes (this session only)
        cur.execute("""
            SELECT 
                v.violation_id,
                v.plate_id,
                v.violation_code,
                v.date_of_violation,
                ai.speed_detected,
                ai.speed_limit,
                ai.camera_id,
                ai.screenshot_path
            FROM violations v
            JOIN ai_violations ai ON v.violation_id = ai.violation_id
            WHERE ai.camera_id = %s
              AND v.date_of_violation >= %s
            ORDER BY v.date_of_violation DESC
            LIMIT 5
        """, (camera_id, detection_start - timedelta(seconds=10)))
        
        violations = []
        seen_plates = set()  # Prevent duplicate plates
        
        for row in cur:
            plate_id = row[1]
            # Skip if we already have this plate (prevent duplicates)
            if plate_id in seen_plates:
                continue
            seen_plates.add(plate_id)
            
            screenshot_path = row[7]
            screenshot_url = None
            if screenshot_path:
                # Get just the filename from the path
                screenshot_filename = Path(screenshot_path).name
                screenshot_url = f'/snapshots/{screenshot_filename}'
                print(f"  Screenshot URL: {screenshot_url}")
            
            violations.append({
                'violation_id': row[0],
                'plate_id': plate_id,
                'violation_code': row[2],
                'date': row[3].isoformat() if row[3] else None,
                'speed_detected': row[4],
                'speed_limit': row[5],
                'camera_id': row[6],
                'screenshot_url': screenshot_url,
            })
        
        cur.close()
        conn.close()
        
        print(f"✓ Returning {len(violations)} violations with screenshots")
        
        return jsonify({
            "success": True,
            "camera_id": camera_id,
            "violations_count": len(violations),
            "violations": violations,
            "message": f"Detection complete. Found {len(violations)} violations."
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Detection timed out"}), 500
    except Exception as e:
        print(f"Error running CV detection: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/recent-violations')
def get_recent_violations():
    """Get recent violations with screenshots for map display and activity log."""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        limit = request.args.get('limit', 50, type=int)
        
        # Get recent AI violations (include all camera violations, not just those with screenshots)
        cur.execute("""
            SELECT 
                v.violation_id,
                v.plate_id,
                v.plate_state,
                v.latitude,
                v.longitude,
                v.violation_code,
                v.date_of_violation,
                v.police_agency,
                ai.speed_detected,
                ai.speed_limit,
                ai.camera_id,
                ai.screenshot_path,
                ai.ocr_confidence,
                v.driver_license_number,
                v.driver_full_name
            FROM violations v
            LEFT JOIN ai_violations ai ON v.violation_id = ai.violation_id
            WHERE v.source_type = 'camera' OR ai.camera_id IS NOT NULL
            ORDER BY v.date_of_violation DESC
            LIMIT %s
        """, (limit,))
        
        violations = []
        for row in cur:
            violations.append({
                'violation_id': row[0],
                'plate_id': row[1],
                'plate_state': row[2],
                'latitude': float(row[3]) if row[3] else None,
                'longitude': float(row[4]) if row[4] else None,
                'violation_code': row[5],
                'date': row[6].isoformat() if row[6] else None,
                'date_of_violation': row[6].isoformat() if row[6] else None,  # Alias for compatibility
                'police_agency': row[7],
                'speed_detected': float(row[8]) if row[8] else None,
                'speed_limit': row[9],
                'camera_id': row[10],
                'screenshot_url': f'/snapshots/{Path(row[11]).name}' if row[11] else None,
                'ocr_confidence': float(row[12]) if row[12] else None,
                'driver_license_number': row[13],
                'driver_name': row[14],
            })
        
        cur.close()
        conn.close()
        
        return jsonify(violations)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("  Stop Super Speeders - API Server")
    print("=" * 60)
    print("\n  Heatmap Endpoints:")
    print("    GET  /api/stats")
    print("    GET  /api/heatmap")
    print("\n  Camera Endpoints:")
    print("    GET  /api/cameras")
    print("    GET  /api/cameras/<id>")
    print("    POST /api/cameras/<id>/detect")
    print("\n  Driver & Alert Endpoints:")
    print("    GET  /api/drivers")
    print("    GET  /api/drivers/<plate_id>")
    print("    GET  /api/alerts")
    print("    GET  /api/ai-heatmap")
    print("    GET  /api/recent-violations")
    print("\n  Screenshots:")
    print("    GET  /snapshots/<filename>")
    print("\n  Demo:")
    print("    POST /api/reset-demo")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5001)