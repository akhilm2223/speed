#!/usr/bin/env python3
"""
Camera API endpoints for the ISA enforcement demo.
Handles camera data, simulated detections, and DMV alerts.

Run alongside api.py or integrate into it.
"""
import os
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "traffic_violations_db"),
    "user": os.getenv("DB_USER", "myuser"),
    "password": os.getenv("DB_PASSWORD", "mypassword"),
}

# Pre-computed detections for each camera (simulates CV results)
# In real system, this would come from YOLO + EasyOCR processing
CAMERA_DETECTIONS = {
    "CAM-1": [
        {"plate_id": "NYC-SAFE-01", "violation_type": "school_zone_speeding", "points": 3, 
         "speed_detected": 32, "speed_limit": 20, "is_school_zone": True, "video_timestamp": "00:05"},
        {"plate_id": "NYC-SAFE-01", "violation_type": "school_zone_speeding", "points": 3,
         "speed_detected": 35, "speed_limit": 20, "is_school_zone": True, "video_timestamp": "00:18"},
    ],
    "CAM-2": [
        {"plate_id": "NYC-SAFE-02", "violation_type": "excessive_speed", "points": 3,
         "speed_detected": 52, "speed_limit": 30, "is_school_zone": False, "video_timestamp": "00:03"},
        {"plate_id": "NYC-SAFE-02", "violation_type": "excessive_speed", "points": 4,
         "speed_detected": 58, "speed_limit": 30, "is_school_zone": False, "video_timestamp": "00:12"},
        {"plate_id": "NYC-SAFE-02", "violation_type": "reckless_speed", "points": 4,
         "speed_detected": 65, "speed_limit": 30, "is_school_zone": False, "video_timestamp": "00:22"},
    ],
    "CAM-3": [
        {"plate_id": "NYC-SAFE-01", "violation_type": "school_zone_speeding", "points": 3,
         "speed_detected": 28, "speed_limit": 15, "is_school_zone": True, "video_timestamp": "00:04"},
        {"plate_id": "BK-FAST-77", "violation_type": "school_zone_speeding", "points": 3,
         "speed_detected": 30, "speed_limit": 15, "is_school_zone": True, "video_timestamp": "00:09"},
    ],
    "CAM-4": [
        {"plate_id": "BK-FAST-77", "violation_type": "excessive_speed", "points": 4,
         "speed_detected": 55, "speed_limit": 30, "is_school_zone": False, "video_timestamp": "00:06"},
        {"plate_id": "BK-FAST-77", "violation_type": "reckless_speed", "points": 4,
         "speed_detected": 62, "speed_limit": 30, "is_school_zone": False, "video_timestamp": "00:15"},
    ],
    "CAM-5": [
        {"plate_id": "QNS-1234", "violation_type": "speeding", "points": 2,
         "speed_detected": 38, "speed_limit": 30, "is_school_zone": False, "video_timestamp": "00:03"},
        {"plate_id": "NYC-SAFE-01", "violation_type": "excessive_speed", "points": 4,
         "speed_detected": 55, "speed_limit": 30, "is_school_zone": False, "video_timestamp": "00:11"},
    ],
    # NEW MANHATTAN CAMERAS
    "CAM-6": [  # Times Square
        {"plate_id": "TS-SPEED-99", "violation_type": "pedestrian_zone_speeding", "points": 4,
         "speed_detected": 35, "speed_limit": 15, "is_school_zone": False, "video_timestamp": "00:04"},
        {"plate_id": "NYC-SAFE-01", "violation_type": "pedestrian_zone_speeding", "points": 4,
         "speed_detected": 40, "speed_limit": 15, "is_school_zone": False, "video_timestamp": "00:12"},
        {"plate_id": "MN-TAXI-42", "violation_type": "excessive_speed", "points": 3,
         "speed_detected": 32, "speed_limit": 15, "is_school_zone": False, "video_timestamp": "00:18"},
    ],
    "CAM-7": [  # East Harlem - 125th St
        {"plate_id": "EH-DARK-01", "violation_type": "excessive_speed", "points": 4,
         "speed_detected": 52, "speed_limit": 25, "is_school_zone": False, "video_timestamp": "00:03"},
        {"plate_id": "NYC-SAFE-02", "violation_type": "reckless_speed", "points": 5,
         "speed_detected": 60, "speed_limit": 25, "is_school_zone": False, "video_timestamp": "00:09"},
        {"plate_id": "BK-FAST-77", "violation_type": "excessive_speed", "points": 4,
         "speed_detected": 55, "speed_limit": 25, "is_school_zone": False, "video_timestamp": "00:15"},
    ],
    "CAM-8": [  # Washington Heights
        {"plate_id": "WH-NIGHT-33", "violation_type": "excessive_speed", "points": 4,
         "speed_detected": 48, "speed_limit": 25, "is_school_zone": False, "video_timestamp": "00:05"},
        {"plate_id": "NYC-SAFE-01", "violation_type": "reckless_speed", "points": 5,
         "speed_detected": 58, "speed_limit": 25, "is_school_zone": False, "video_timestamp": "00:11"},
        {"plate_id": "EH-DARK-01", "violation_type": "excessive_speed", "points": 4,
         "speed_detected": 50, "speed_limit": 25, "is_school_zone": False, "video_timestamp": "00:19"},
    ],
}

# ISA thresholds
MONITOR_THRESHOLD = 5
ISA_REQUIRED_THRESHOLD = 10


def get_db():
    return psycopg.connect(**DB_CONFIG)


@app.route('/api/cameras')
def get_cameras():
    """Get all camera locations."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT camera_id, name, latitude, longitude, borough, zone_type, 
                   description, video_url, is_active
            FROM cameras
            ORDER BY camera_id
        """)
        
        cameras = []
        for row in cur:
            cameras.append({
                "camera_id": row[0],
                "name": row[1],
                "latitude": float(row[2]),
                "longitude": float(row[3]),
                "borough": row[4],
                "zone_type": row[5],
                "description": row[6],
                "video_url": row[7],
                "is_active": row[8]
            })
        
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
            "camera_id": row[0],
            "name": row[1],
            "latitude": float(row[2]),
            "longitude": float(row[3]),
            "borough": row[4],
            "zone_type": row[5],
            "description": row[6],
            "video_url": row[7],
            "is_active": row[8]
        }
        
        cur.close()
        conn.close()
        return jsonify(camera)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/cameras/<camera_id>/simulate', methods=['POST'])
def simulate_detection(camera_id):
    """
    Simulate CV detection for a camera click.
    This processes pre-computed detections and updates driver risk scores.
    """
    try:
        detections = CAMERA_DETECTIONS.get(camera_id, [])
        if not detections:
            return jsonify({"error": "No detections configured for this camera"}), 404
        
        conn = get_db()
        cur = conn.cursor()
        
        # Get camera info
        cur.execute("SELECT latitude, longitude, zone_type FROM cameras WHERE camera_id = %s", (camera_id,))
        cam_row = cur.fetchone()
        if not cam_row:
            return jsonify({"error": "Camera not found"}), 404
        
        cam_lat, cam_lng, zone_type = float(cam_row[0]), float(cam_row[1]), cam_row[2]
        
        results = []
        drivers_updated = []
        alerts_created = []
        
        for det in detections:
            plate_id = det["plate_id"]
            reg_state = "NY"
            
            # Insert violation
            cur.execute("""
                INSERT INTO ai_violations 
                (camera_id, plate_id, registration_state, violation_type, points, 
                 speed_detected, speed_limit, is_school_zone, latitude, longitude, video_timestamp, confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING violation_id
            """, (camera_id, plate_id, reg_state, det["violation_type"], det["points"],
                  det.get("speed_detected"), det.get("speed_limit"), det.get("is_school_zone", False),
                  cam_lat, cam_lng, det.get("video_timestamp"), 0.95))
            
            violation_id = cur.fetchone()[0]
            
            # Update driver risk
            cur.execute("""
                UPDATE drivers SET
                    total_violations = total_violations + 1,
                    current_risk_points = current_risk_points + %s,
                    last_violation_date = NOW(),
                    first_violation_date = COALESCE(first_violation_date, NOW()),
                    updated_at = NOW()
                WHERE plate_id = %s AND registration_state = %s
                RETURNING total_violations, current_risk_points, isa_status
            """, (det["points"], plate_id, reg_state))
            
            driver_row = cur.fetchone()
            if driver_row:
                total_v, risk_pts, isa_status = driver_row
                new_status = isa_status
                
                # Check thresholds
                if risk_pts >= ISA_REQUIRED_THRESHOLD and isa_status != "ISA_REQUIRED":
                    new_status = "ISA_REQUIRED"
                    cur.execute("""
                        UPDATE drivers SET isa_status = 'ISA_REQUIRED', updated_at = NOW()
                        WHERE plate_id = %s AND registration_state = %s
                    """, (plate_id, reg_state))
                    
                    # Create DMV alert
                    cur.execute("""
                        INSERT INTO dmv_alerts 
                        (plate_id, registration_state, alert_type, reason, risk_score_at_alert, total_violations_at_alert)
                        VALUES (%s, %s, 'ISA_REQUIRED', %s, %s, %s)
                        RETURNING alert_id
                    """, (plate_id, reg_state, 
                          f"Driver exceeded risk threshold ({risk_pts} points) - ISA installation required",
                          risk_pts, total_v))
                    alert_id = cur.fetchone()[0]
                    alerts_created.append({
                        "alert_id": alert_id,
                        "plate_id": plate_id,
                        "alert_type": "ISA_REQUIRED",
                        "risk_score": risk_pts
                    })
                    
                elif risk_pts >= MONITOR_THRESHOLD and isa_status == "NONE":
                    new_status = "MONITOR"
                    cur.execute("""
                        UPDATE drivers SET isa_status = 'MONITOR', updated_at = NOW()
                        WHERE plate_id = %s AND registration_state = %s
                    """, (plate_id, reg_state))
                
                drivers_updated.append({
                    "plate_id": plate_id,
                    "total_violations": total_v,
                    "risk_points": risk_pts,
                    "isa_status": new_status,
                    "isa_required": new_status == "ISA_REQUIRED"
                })
            
            results.append({
                "violation_id": violation_id,
                "plate_id": plate_id,
                "violation_type": det["violation_type"],
                "points": det["points"],
                "speed_detected": det.get("speed_detected"),
                "speed_limit": det.get("speed_limit"),
                "is_school_zone": det.get("is_school_zone", False)
            })
        
        # Update road segment risk
        cur.execute("""
            UPDATE road_segments SET
                total_violations = total_violations + %s,
                risk_score = risk_score + %s,
                last_violation_date = NOW()
            WHERE latitude = %s AND longitude = %s
        """, (len(detections), sum(d["points"] for d in detections), cam_lat, cam_lng))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "camera_id": camera_id,
            "violations_logged": len(results),
            "detections": results,
            "drivers_updated": drivers_updated,
            "alerts_created": alerts_created
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/drivers')
def get_drivers():
    """Get all tracked drivers with risk scores."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT plate_id, registration_state, total_violations, current_risk_points,
                   isa_status, first_violation_date, last_violation_date
            FROM drivers
            WHERE total_violations > 0
            ORDER BY current_risk_points DESC
        """)
        
        drivers = []
        for row in cur:
            drivers.append({
                "plate_id": row[0],
                "registration_state": row[1],
                "total_violations": row[2],
                "risk_points": row[3],
                "isa_status": row[4],
                "first_violation_date": row[5].isoformat() if row[5] else None,
                "last_violation_date": row[6].isoformat() if row[6] else None,
                "isa_required": row[4] == "ISA_REQUIRED"
            })
        
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
        
        # Get driver info
        cur.execute("""
            SELECT plate_id, registration_state, total_violations, current_risk_points,
                   isa_status, first_violation_date, last_violation_date
            FROM drivers WHERE plate_id = %s
        """, (plate_id,))
        
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Driver not found"}), 404
        
        driver = {
            "plate_id": row[0],
            "registration_state": row[1],
            "total_violations": row[2],
            "risk_points": row[3],
            "isa_status": row[4],
            "first_violation_date": row[5].isoformat() if row[5] else None,
            "last_violation_date": row[6].isoformat() if row[6] else None,
            "isa_required": row[4] == "ISA_REQUIRED"
        }
        
        # Get violation history
        cur.execute("""
            SELECT violation_id, camera_id, violation_type, points, speed_detected,
                   speed_limit, is_school_zone, detected_at
            FROM ai_violations
            WHERE plate_id = %s
            ORDER BY detected_at DESC
        """, (plate_id,))
        
        violations = []
        for v in cur:
            violations.append({
                "violation_id": v[0],
                "camera_id": v[1],
                "violation_type": v[2],
                "points": v[3],
                "speed_detected": v[4],
                "speed_limit": v[5],
                "is_school_zone": v[6],
                "detected_at": v[7].isoformat() if v[7] else None
            })
        
        driver["violations"] = violations
        
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
            FROM dmv_alerts
            ORDER BY created_at DESC
        """)
        
        alerts = []
        for row in cur:
            alerts.append({
                "alert_id": row[0],
                "plate_id": row[1],
                "registration_state": row[2],
                "alert_type": row[3],
                "reason": row[4],
                "risk_score": row[5],
                "total_violations": row[6],
                "status": row[7],
                "created_at": row[8].isoformat() if row[8] else None
            })
        
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
        
        points = []
        for row in cur:
            lat, lng, pts = float(row[0]), float(row[1]), row[2]
            points.append([lat, lng, pts / 4.0])  # Normalize intensity
        
        cur.close()
        conn.close()
        return jsonify(points)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/reset-demo', methods=['POST'])
def reset_demo():
    """Reset all demo data for a fresh start."""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("DELETE FROM ai_violations")
        cur.execute("DELETE FROM dmv_alerts")
        cur.execute("""
            UPDATE drivers SET 
                total_violations = 0, 
                current_risk_points = 0,
                isa_status = 'NONE',
                first_violation_date = NULL,
                last_violation_date = NULL
            WHERE plate_id LIKE 'NYC-%' OR plate_id LIKE 'BK-%' OR plate_id LIKE 'QNS-%'
        """)
        cur.execute("UPDATE road_segments SET total_violations = 0, risk_score = 0")
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"message": "Demo reset successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("=" * 50)
    print("  Camera API Server Starting...")
    print("  Endpoints:")
    print("    GET  /api/cameras")
    print("    GET  /api/cameras/<id>")
    print("    POST /api/cameras/<id>/simulate")
    print("    GET  /api/drivers")
    print("    GET  /api/drivers/<plate_id>")
    print("    GET  /api/alerts")
    print("    GET  /api/ai-heatmap")
    print("    POST /api/reset-demo")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5002)
