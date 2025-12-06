#!/usr/bin/env python3
"""
Real-time Vehicle Detection & Speed Enforcement System
Uses YOLO for vehicle detection, tracking, and speed estimation.

Usage:
    python cv_detector_realtime.py --camera-id CAM-1 --video frontend-react/public/timesquare.mp4
    python cv_detector_realtime.py --camera-id CAM-2 --video frontend-react/public/wallstreet.mp4
"""
import cv2
import numpy as np
from pathlib import Path
import json
import time
import random
import requests
from datetime import datetime
from collections import defaultdict
import argparse

# Try to import ultralytics for YOLO
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("⚠ ultralytics not installed. Using simulated detection.")

# =============================================================================
# CAMERA CONFIGURATIONS
# =============================================================================
CAMERA_CONFIG = {
    "CAM-1": {
        "name": "Times Square",
        "location": "Times Square, Manhattan",
        "speed_limit_mph": 15,
        "pixels_per_meter": 10.0,
    },
    "CAM-2": {
        "name": "Wall Street",
        "location": "Wall Street, Manhattan",
        "speed_limit_mph": 30,
        "pixels_per_meter": 8.0,
    },
    "CAM-3": {
        "name": "Barclays Center",
        "location": "Barclays Center, Brooklyn",
        "speed_limit_mph": 30,
        "pixels_per_meter": 8.0,
    },
    "CAM-4": {
        "name": "Hudson Valley Albany",
        "location": "Hudson Valley, Albany",
        "speed_limit_mph": 55,
        "pixels_per_meter": 6.0,
    },
}

# Thresholds
MILD_OVER = 5   # mph over limit
SEVERE_OVER = 20

# Violation code mapping
def pick_violation_code(mph_over):
    """Map speed over limit to NY VTL 1180 violation code."""
    if mph_over <= 10:
        return "1180A"  # 1-10 over (2 pts)
    elif mph_over <= 20:
        return "1180B"  # 11-20 over (3 pts)
    elif mph_over <= 30:
        return "1180C"  # 21-30 over (5 pts)
    else:
        return "1180D"  # 31+ over (8 pts, severe)


# =============================================================================
# SIMPLE TRACKER
# =============================================================================
class SimpleTracker:
    """Simple nearest-neighbor tracker for vehicle IDs."""
    
    def __init__(self, max_distance=100):
        self.tracks = {}
        self.next_id = 1
        self.max_distance = max_distance
    
    def update(self, detections):
        """Update tracks with new detections."""
        if not detections:
            return []
        
        det_centers = [self._get_center(d['bbox']) for d in detections]
        
        matched_tracks = []
        unmatched_dets = list(range(len(detections)))
        
        if self.tracks:
            track_ids = list(self.tracks.keys())
            track_centers = [self.tracks[tid]['center'] for tid in track_ids]
            
            for i, det_center in enumerate(det_centers):
                min_dist = float('inf')
                best_track = None
                
                for j, track_center in enumerate(track_centers):
                    dist = np.linalg.norm(np.array(det_center) - np.array(track_center))
                    if dist < min_dist and dist < self.max_distance:
                        min_dist = dist
                        best_track = track_ids[j]
                
                if best_track is not None:
                    self.tracks[best_track]['bbox'] = detections[i]['bbox']
                    self.tracks[best_track]['center'] = det_center
                    self.tracks[best_track]['class'] = detections[i]['class']
                    self.tracks[best_track]['conf'] = detections[i]['conf']
                    matched_tracks.append(best_track)
                    unmatched_dets.remove(i)
        
        for i in unmatched_dets:
            track_id = self.next_id
            self.next_id += 1
            self.tracks[track_id] = {
                'id': track_id,
                'bbox': detections[i]['bbox'],
                'center': det_centers[i],
                'class': detections[i]['class'],
                'conf': detections[i]['conf'],
            }
            matched_tracks.append(track_id)
        
        return [self.tracks[tid] for tid in matched_tracks]
    
    def _get_center(self, bbox):
        x, y, w, h = bbox
        return (x + w/2, y + h/2)


# =============================================================================
# TRAFFIC DETECTOR
# =============================================================================
class TrafficDetector:
    """Detects vehicles, tracks them, estimates speed, flags violations."""
    
    VEHICLE_CLASSES = {2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}
    MAX_VIOLATIONS = 5  # Maximum violations to capture per session
    
    def __init__(self, camera_id, config, api_base='http://localhost:5001'):
        self.camera_id = camera_id
        self.config = config
        self.api_base = api_base
        self.violations_captured = 0  # Track how many we've captured
        
        # Initialize YOLO
        self.model = None
        if YOLO_AVAILABLE:
            try:
                self.model = YOLO('yolov8n.pt')
                print(f"✓ YOLO model loaded")
            except Exception as e:
                print(f"⚠ YOLO load failed: {e}")
        
        self.tracker = SimpleTracker(max_distance=150)
        
        self.vehicle_state = defaultdict(lambda: {
            'speed_mph': 0,
            'last_center': None,
            'last_time': None,
            'has_violated': False,
            'plate': self._generate_plate(),
            'color': 'green',
        })
        
        # Track plates we've already captured to prevent duplicates
        self.captured_plates = set()
        
        self.snapshot_dir = Path('snapshots')
        self.snapshot_dir.mkdir(exist_ok=True)
        
        self.frame_count = 0
        self.fps = 30
    
    def _generate_plate(self):
        letters = ''.join(random.choices('ABCDEFGHJKLMNPRSTUVWXYZ', k=3))
        numbers = ''.join(random.choices('0123456789', k=4))
        return f"{letters}-{numbers}"
    
    def detect_vehicles(self, frame):
        """Detect vehicles using YOLO or simulation."""
        if self.model:
            results = self.model(frame, verbose=False, classes=[2, 3, 5, 7])
            detections = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    detections.append({
                        'bbox': (x1, y1, x2-x1, y2-y1),
                        'class': int(box.cls[0]),
                        'conf': float(box.conf[0]),
                    })
            return detections
        else:
            # Simulated detection
            return self._simulate_detections(frame)
    
    def _simulate_detections(self, frame):
        """Simulate vehicle detections."""
        h, w = frame.shape[:2]
        num_vehicles = random.randint(2, 4)
        detections = []
        
        for i in range(num_vehicles):
            x = random.randint(w//10, w - w//5)
            y = random.randint(h//3, h - h//5)
            width = random.randint(80, 150)
            height = random.randint(60, 100)
            
            detections.append({
                'bbox': (x, y, width, height),
                'class': 2,  # car
                'conf': random.uniform(0.7, 0.95),
            })
        
        return detections
    
    def estimate_speed(self, track_id, center, current_time):
        """Estimate speed based on movement."""
        state = self.vehicle_state[track_id]
        
        if state['last_center'] is None or state['last_time'] is None:
            state['last_center'] = center
            state['last_time'] = current_time
            return 0
        
        # Calculate distance in pixels
        dx = center[0] - state['last_center'][0]
        dy = center[1] - state['last_center'][1]
        d_px = np.sqrt(dx**2 + dy**2)
        
        # Convert to meters
        d_m = d_px / self.config['pixels_per_meter']
        
        # Time difference
        dt = current_time - state['last_time']
        if dt == 0:
            return state['speed_mph']
        
        # Speed in m/s then mph
        v_ms = d_m / dt
        v_mph = v_ms * 2.23694
        
        # Smooth speed (moving average)
        alpha = 0.3
        speed_mph = alpha * v_mph + (1 - alpha) * state['speed_mph']
        
        # Add realistic variation
        speed_mph += random.uniform(-2, 2)
        speed_mph = max(0, speed_mph)
        
        state['speed_mph'] = speed_mph
        state['last_center'] = center
        state['last_time'] = current_time
        
        return speed_mph
    
    def check_violation(self, track_id, speed_mph):
        """Check if vehicle is speeding and handle violation."""
        state = self.vehicle_state[track_id]
        speed_limit = self.config['speed_limit_mph']
        over = speed_mph - speed_limit
        
        # Only flag SEVERE violations (20+ mph over limit)
        # This ensures we only capture real dangerous speeders
        if over <= 0:
            state['color'] = 'green'
            return None
        elif over < SEVERE_OVER:  # Less than 20 mph over - just warn
            state['color'] = 'yellow' if over > MILD_OVER else 'green'
            return None
        else:
            state['color'] = 'red'
            
            plate = state['plate']
            
            # Skip if we already captured this plate OR this vehicle already violated
            if state['has_violated'] or plate in self.captured_plates:
                return None
            
            # Mark as violated and add to captured plates
            state['has_violated'] = True
            self.captured_plates.add(plate)
            
            return {
                'track_id': track_id,
                'plate': plate,
                'speed_mph': int(speed_mph),
                'speed_limit': speed_limit,
                'mph_over': int(over),
                'violation_code': pick_violation_code(over),
            }
    
    def save_screenshot(self, frame, track, violation):
        """Save detailed screenshot of violation with comprehensive info overlay."""
        x, y, w, h = track['bbox']
        frame_h, frame_w = frame.shape[:2]
        
        # Create a copy of the full frame
        screenshot = frame.copy()
        
        # Draw red rectangle around the violating vehicle (thicker border)
        cv2.rectangle(screenshot, (x, y), (x+w, y+h), (0, 0, 255), 4)
        
        # Draw corner brackets for emphasis
        bracket_len = 20
        # Top-left
        cv2.line(screenshot, (x, y), (x + bracket_len, y), (0, 0, 255), 6)
        cv2.line(screenshot, (x, y), (x, y + bracket_len), (0, 0, 255), 6)
        # Top-right
        cv2.line(screenshot, (x + w, y), (x + w - bracket_len, y), (0, 0, 255), 6)
        cv2.line(screenshot, (x + w, y), (x + w, y + bracket_len), (0, 0, 255), 6)
        # Bottom-left
        cv2.line(screenshot, (x, y + h), (x + bracket_len, y + h), (0, 0, 255), 6)
        cv2.line(screenshot, (x, y + h), (x, y + h - bracket_len), (0, 0, 255), 6)
        # Bottom-right
        cv2.line(screenshot, (x + w, y + h), (x + w - bracket_len, y + h), (0, 0, 255), 6)
        cv2.line(screenshot, (x + w, y + h), (x + w, y + h - bracket_len), (0, 0, 255), 6)
        
        # Create info panel at the bottom
        panel_height = 180
        panel = np.zeros((panel_height, frame_w, 3), dtype=np.uint8)
        panel[:] = (40, 40, 40)  # Dark gray background
        
        # Red header bar
        cv2.rectangle(panel, (0, 0), (frame_w, 45), (0, 0, 180), -1)
        
        # Header text
        cv2.putText(panel, "SPEED VIOLATION DETECTED", (20, 32), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        cv2.putText(panel, f"NY DMV ISA ENFORCEMENT", (frame_w - 350, 32), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        
        # Violation details - Left column
        y_offset = 75
        line_height = 28
        
        cv2.putText(panel, f"LICENSE PLATE:", (20, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        cv2.putText(panel, f"{violation['plate']}", (180, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        
        y_offset += line_height
        cv2.putText(panel, f"SPEED DETECTED:", (20, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        cv2.putText(panel, f"{violation['speed_mph']} MPH", (180, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        y_offset += line_height
        cv2.putText(panel, f"SPEED LIMIT:", (20, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        cv2.putText(panel, f"{violation['speed_limit']} MPH", (180, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        y_offset += line_height
        cv2.putText(panel, f"OVER LIMIT:", (20, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        cv2.putText(panel, f"+{violation['mph_over']} MPH", (180, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # Right column
        y_offset = 75
        col2_x = frame_w // 2 + 50
        
        cv2.putText(panel, f"VIOLATION CODE:", (col2_x, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        cv2.putText(panel, f"{violation['violation_code']}", (col2_x + 170, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 165, 0), 2)
        
        y_offset += line_height
        cv2.putText(panel, f"CAMERA:", (col2_x, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        cv2.putText(panel, f"{self.camera_id}", (col2_x + 170, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        y_offset += line_height
        cv2.putText(panel, f"LOCATION:", (col2_x, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        cv2.putText(panel, f"{self.config['location'][:25]}", (col2_x + 170, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        y_offset += line_height
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(panel, f"TIMESTAMP:", (col2_x, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        cv2.putText(panel, f"{timestamp}", (col2_x + 170, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Violation reason at bottom
        reason = self._get_violation_reason(violation)
        cv2.putText(panel, f"REASON: {reason}", (20, panel_height - 15), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 200, 100), 1)
        
        # Combine frame and panel
        final_image = np.vstack([screenshot, panel])
        
        # Save
        filename = f"{self.camera_id}_{violation['plate']}_{int(time.time())}.jpg"
        filepath = self.snapshot_dir / filename
        cv2.imwrite(str(filepath), final_image)
        
        return str(filepath)
    
    def _get_violation_reason(self, violation):
        """Generate detailed violation reason text."""
        mph_over = violation['mph_over']
        code = violation['violation_code']
        
        if code == '1180D':
            return f"SEVERE SPEEDING: {mph_over} MPH over limit. 8 points. ISA device may be required."
        elif code == '1180C':
            return f"EXCESSIVE SPEEDING: {mph_over} MPH over limit. 5 points on license."
        elif code == '1180B':
            return f"SPEEDING: {mph_over} MPH over limit. 3 points on license."
        else:
            return f"SPEEDING: {mph_over} MPH over posted speed limit. 2 points on license."
    
    def send_violation_to_backend(self, violation, screenshot_path):
        """Send violation to backend API."""
        payload = {
            "camera_id": self.camera_id,
            "plate_id": violation['plate'],
            "speed_detected": violation['speed_mph'],
            "speed_limit": violation['speed_limit'],
            "mph_over": violation['mph_over'],
            "violation_code": violation['violation_code'],
            "location": self.config['location'],
            "timestamp": datetime.now().isoformat(),
            "screenshot_path": screenshot_path,
        }
        
        try:
            url = f"{self.api_base}/api/cameras/{self.camera_id}/detect"
            response = requests.post(url, json=payload, timeout=5)
            if response.ok:
                print(f"✓ Violation logged: {violation['plate']} - {violation['speed_mph']} MPH")
                return response.json()
            else:
                print(f"⚠ API error: {response.status_code}")
        except Exception as e:
            print(f"⚠ Failed to send violation: {e}")
        
        return None
    
    def draw_overlay(self, frame, tracks):
        """Draw detection boxes and info on frame."""
        for track in tracks:
            track_id = track['id']
            state = self.vehicle_state[track_id]
            x, y, w, h = track['bbox']
            
            # Color based on speed
            color_map = {'green': (0, 255, 0), 'yellow': (0, 255, 255), 'red': (0, 0, 255)}
            color = color_map.get(state['color'], (0, 255, 0))
            
            # Draw box
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
            
            # Draw plate and speed
            plate_text = f"{state['plate']}"
            speed_text = f"{int(state['speed_mph'])} MPH | LIMIT {self.config['speed_limit_mph']}"
            
            cv2.putText(frame, plate_text, (x, y-25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            cv2.putText(frame, speed_text, (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        return frame
    
    def process_frame(self, frame):
        """Process single frame: detect, track, estimate speed, check violations."""
        self.frame_count += 1
        current_time = self.frame_count / self.fps
        
        # Stop processing if we've captured enough violations
        if self.violations_captured >= self.MAX_VIOLATIONS:
            return frame, []
        
        # Detect vehicles
        detections = self.detect_vehicles(frame)
        
        # Update tracker
        tracks = self.tracker.update(detections)
        
        # Process each track
        violations = []
        for track in tracks:
            track_id = track['id']
            center = track['center']
            
            # Estimate speed
            speed_mph = self.estimate_speed(track_id, center, current_time)
            
            # Check for violation (only severe ones: 20+ mph over)
            violation = self.check_violation(track_id, speed_mph)
            if violation and self.violations_captured < self.MAX_VIOLATIONS:
                screenshot_path = self.save_screenshot(frame, track, violation)
                self.send_violation_to_backend(violation, screenshot_path)
                violations.append(violation)
                self.violations_captured += 1
                
                # Stop if we've reached the limit
                if self.violations_captured >= self.MAX_VIOLATIONS:
                    print(f"\n✓ Captured {self.MAX_VIOLATIONS} violations - stopping detection")
                    break
        
        # Draw overlay
        frame = self.draw_overlay(frame, tracks)
        
        return frame, violations


# =============================================================================
# MAIN PROCESSING FUNCTION
# =============================================================================
def process_camera_video(camera_id, video_path, display=True):
    """Process camera video with real-time detection and violation logging."""
    if camera_id not in CAMERA_CONFIG:
        print(f"❌ Unknown camera: {camera_id}")
        return
    
    config = CAMERA_CONFIG[camera_id]
    print(f"\n{'='*60}")
    print(f"  Processing: {config['name']}")
    print(f"  Location: {config['location']}")
    print(f"  Speed Limit: {config['speed_limit_mph']} MPH")
    print(f"{'='*60}\n")
    
    detector = TrafficDetector(camera_id, config)
    
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"❌ Cannot open video: {video_path}")
        return
    
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    detector.fps = fps
    
    total_violations = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Process frame
        frame, violations = detector.process_frame(frame)
        total_violations += len(violations)
        
        # Display
        if display:
            cv2.imshow(f'{config["name"]} - Press Q to quit', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    cap.release()
    if display:
        try:
            cv2.destroyAllWindows()
        except:
            pass  # Ignore if window system not available
    
    print(f"\n{'='*60}")
    print(f"  Processing Complete")
    print(f"  Total Violations: {total_violations}")
    print(f"{'='*60}\n")


# =============================================================================
# CLI
# =============================================================================
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Real-time Traffic Violation Detection')
    parser.add_argument('--camera-id', required=True, help='Camera ID (CAM-1, CAM-2, etc.)')
    parser.add_argument('--video', required=True, help='Path to video file')
    parser.add_argument('--no-display', action='store_true', help='Disable video display')
    
    args = parser.parse_args()
    
    process_camera_video(args.camera_id, args.video, display=not args.no_display)
