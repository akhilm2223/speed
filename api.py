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

MONITOR_THRESHOLD = 5
ISA_REQUIRED_THRESHOLD = 10


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
        limit = request.args.get('limit', 300000, type=int)
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT violation_location, violation_code, violation_description, 
                   issue_date, plate_id, registration_state
            FROM violations
            WHERE violation_location IS NOT NULL LIMIT %s
        """, (limit,))

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
            location = row[0]
            violation_code = row[1]
            violation_description = row[2]
            issue_date = row[3]
            plate_id = row[4]
            registration_state = row[5]
            if not location:
                continue
            match = re.search(r'\(\s*(-?\d+\.?\d*),\s*(-?\d+\.?\d*)\s*\)', location)
            if match:
                try:
                    lat, lon = float(match.group(1)), float(match.group(2))
                    if lat != 0 and lon != 0:
                        severity = get_severity_from_code(violation_code)
                        # Return as object with all details
                        points.append({
                            'lat': lat,
                            'lon': lon,
                            'severity': severity,
                            'code': violation_code,
                            'description': violation_description,
                            'date': issue_date.isoformat() if issue_date else None,
                            'plate': plate_id,
                            'state': registration_state,
                            'location': location
                        })
                except ValueError:
                    continue

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
    """Get all camera locations."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT camera_id, name, latitude, longitude, borough, zone_type,
                   description, video_url, is_active
            FROM cameras ORDER BY camera_id
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


@app.route('/api/cameras/<camera_id>/detect', methods=['POST'])
def run_detection(camera_id):
    """
    Process a dynamically detected violation from the frontend YOLO simulation.
    Creates drivers on-the-fly when first detected - no pre-seeded data.
    """
    try:
        data = request.json
        plate_id = data.get('plate_id')
        speed_detected = data.get('speed_detected')
        speed_limit = data.get('speed_limit', 30)
        violation_type = data.get('violation_type', 'speeding')
        points = data.get('points', 3)
        corridor_name = data.get('corridor_name')
        
        if not plate_id:
            return jsonify({"error": "plate_id required"}), 400
        
        conn = get_db()
        cur = conn.cursor()
        
        # Get camera info
        cur.execute("""
            SELECT latitude, longitude, zone_type, name 
            FROM cameras WHERE camera_id = %s
        """, (camera_id,))
        cam_row = cur.fetchone()
        if not cam_row:
            cur.close()
            conn.close()
            return jsonify({"error": "Camera not found"}), 404
        
        cam_lat, cam_lng, zone_type, cam_name = float(cam_row[0]), float(cam_row[1]), cam_row[2], cam_row[3]
        corridor = corridor_name or cam_name
        
        # Check if driver exists - if not, CREATE them (dynamic discovery!)
        cur.execute("SELECT plate_id FROM drivers WHERE plate_id = %s", (plate_id,))
        driver_exists = cur.fetchone()
        
        if not driver_exists:
            # First time seeing this plate - create driver record
            cur.execute("""
                INSERT INTO drivers (plate_id, registration_state, total_violations, 
                    current_risk_points, isa_status, first_violation_date, last_violation_date)
                VALUES (%s, 'NY', 0, 0, 'NONE', NOW(), NOW())
            """, (plate_id,))
        
        # Insert the AI violation
        cur.execute("""
            INSERT INTO ai_violations 
            (camera_id, plate_id, registration_state, violation_type, points, 
             speed_detected, speed_limit, corridor_name, latitude, longitude, confidence)
            VALUES (%s, %s, 'NY', %s, %s, %s, %s, %s, %s, %s, 0.95)
            RETURNING violation_id
        """, (camera_id, plate_id, violation_type, points, speed_detected, speed_limit, 
              corridor, cam_lat, cam_lng))
        
        violation_id = cur.fetchone()[0]
        
        # Update driver risk score
        cur.execute("""
            UPDATE drivers SET
                total_violations = total_violations + 1,
                current_risk_points = current_risk_points + %s,
                last_violation_date = NOW(),
                first_violation_date = COALESCE(first_violation_date, NOW())
            WHERE plate_id = %s
            RETURNING total_violations, current_risk_points, isa_status
        """, (points, plate_id))
        
        driver_row = cur.fetchone()
        total_v, risk_pts, isa_status = driver_row
        new_status = isa_status
        alert_created = None
        
        # Check thresholds and update status
        if risk_pts >= ISA_REQUIRED_THRESHOLD and isa_status not in ('ISA_REQUIRED', 'COMPLIANT'):
            new_status = 'ISA_REQUIRED'
            cur.execute("""
                UPDATE drivers SET isa_status = 'ISA_REQUIRED'
                WHERE plate_id = %s
            """, (plate_id,))
            alert_created = {
                "type": "ISA_REQUIRED",
                "message": f"Driver {plate_id} crossed ISA threshold ({risk_pts} points)"
            }
        elif risk_pts >= MONITOR_THRESHOLD and isa_status == 'NONE':
            new_status = 'MONITOR'
            cur.execute("""
                UPDATE drivers SET isa_status = 'MONITOR'
                WHERE plate_id = %s
            """, (plate_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "violation_id": violation_id,
            "plate_id": plate_id,
            "violation_type": violation_type,
            "points": points,
            "speed_detected": speed_detected,
            "speed_limit": speed_limit,
            "corridor": corridor,
            "driver": {
                "plate_id": plate_id,
                "total_violations": total_v,
                "risk_points": risk_pts,
                "isa_status": new_status,
                "is_new": not driver_exists
            },
            "alert": alert_created
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
    print("    POST /api/cameras/<id>/simulate")
    print("\n  Driver & Alert Endpoints:")
    print("    GET  /api/drivers")
    print("    GET  /api/drivers/<plate_id>")
    print("    GET  /api/alerts")
    print("    GET  /api/ai-heatmap")
    print("    POST /api/reset-demo")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5001)
