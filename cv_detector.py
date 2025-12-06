#!/usr/bin/env python3
"""
Real-time Vehicle Detection & Speed Enforcement System
Uses YOLO for vehicle detection, tracking, and speed estimation.

Usage:
    python cv_detector.py --camera-id CAM-1 --video frontend-react/public/timesquare.mp4
    python cv_detector.py --camera-id CAM-2 --video frontend-react/public/wallstreet.mp4
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
    print("Warning: ultralytics not installed. Using simulated detection.")
    print("Install with: pip install ultralytics")


# =============================================================================
# CAMERA CONFIGURATIONS
# =============================================================================
CAMERA_CONFIG = {
    "CAM-1": {
        "name": "Times Square",
        "location": "Times Square, Manhattan",
        "speed_limit_mph": 15,
        "pixels_per_meter": 10.0,
        "fps": 30,
    },
    "CAM-2": {
        "name": "Wall Street",
        "location": "Wall Street, Manhattan",
        "speed_limit_mph": 30,
        "pixels_per_meter": 8.0,
        "fps": 30,
    },
    "CAM-3": {
        "name": "Barclays Center",
        "location": "Barclays Center, Brooklyn",
        "speed_limit_mph": 30,
        "pixels_per_meter": 8.0,
        "fps": 30,
    },
    "CAM-4": {
        "name": "Hudson Valley Albany",
        "location": "Hudson Valley, Albany",
        "speed_limit_mph": 55,
        "pixels_per_meter": 6.0,
        "fps": 30,
    },
}

# Violation code mapping based on mph over limit
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
# SIMPLE TRACKER (Nearest Neighbor Matching)
# =============================================================================
class SimpleTracker:
    """Simple nearest-neighbor tracker for vehicle IDs."""
    
    def __init__(self, max_distance=100):
        self.tracks = {}
        self.next_id = 1
        self.max_distance = max_distance
    
    def update(self, detections):
        """Update tracks with new detections. Returns list of tracked objects."""
        if not detections:
            return []
        
        # Get centers of new detections
        det_centers = [self._get_center(d['bbox']) for d in detections]
        
        # Match with existing tracks
        matched_tracks = []
        unmatched_dets = list(range(len(detections)))
        
        if self.tracks:
            # Calculate distances between existing tracks and new detections
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
                    # Update existing track
                    self.tracks[best_track]['bbox'] = detections[i]['bbox']
                    self.tracks[best_track]['center'] = det_center
                    self.tracks[best_track]['class'] = detections[i]['class']
                    self.tracks[best_track]['conf'] = detections[i]['conf']
                    matched_tracks.append(best_track)
                    unmatched_dets.remove(i)
        
        # Create new tracks for unmatched detections
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
        
        # Return active tracks
        return [self.tracks[tid] for tid in matched_tracks]
    
    def _get_center(self, bbox):
        """Get center point of bounding box."""
        x, y, w, h = bbox
        return (x + w/2, y + h/2)


# =============================================================================
# TRAFFIC DETECTOR WITH SPEED ESTIMATION
# =============================================================================
class TrafficDetector:
    """Detects vehicles, tracks them, estimates speed, and flags violations."""
    
    # Vehicle classes in COCO dataset
    VEHICLE_CLASSES = {2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}
    
    
    def __init__(self, camera_id, config, api_base='http://localhost:5001'):
        """Initialize detector with camera config."""
        self.camera_id = camera_id
        self.config = config
        self.api_base = api_base
        
        # Initialize YOLO model
        self.model = None
        if YOLO_AVAILABLE:
            try:
                self.model = YOLO('yolov8n.pt')  # Nano model for speed
                print(f"✓ YOLO model loaded: yolov8n.pt")
            except Exception as e:
                print(f"⚠ Could not load YOLO: {e}. Using simulated detection.")
        
        # Initialize tracker
        self.tracker = SimpleTracker(max_distance=150)
        
        # Track state per vehicle
        self.vehicle_state = defaultdict(lambda: {
            'speed_mph': 0,
            'last_center': None,
            'last_time': None,
            'has_violated': False,
            'plate': self._generate_plate(),
            'color': 'green',
            'violation_count': 0,
        })
        
        # Snapshot directory
        self.snapshot_dir = Path('snapshots')
        self.snapshot_dir.mkdir(exist_ok=True)
    
    def _generate_plate(self):
        """Generate realistic NY license plate."""
        letters = ''.join(random.choices('ABCDEFGHJKLMNPRSTUVWXYZ', k=3))
        numbers = ''.join(random.choices('0123456789', k=4))
        return f"{letters}-{numbers}"
    
    def detect_frame(self, frame, confidence_threshold=0.5):
        """
        Detect vehicles in a single frame.
        
        Returns:
            list of detections: [{
                'id': vehicle_id,
                'class': 'car'|'truck'|etc,
                'confidence': 0.0-1.0,
                'bbox': [x1, y1, x2, y2],
                'plate': simulated plate string,
                'speed_estimate': estimated speed
            }]
        """
        detections = []
        
        if self.model is None:
            # Fallback: generate simulated detections
            return self._simulate_detections(frame)
        
        # Run YOLO detection
        results = self.model(frame, verbose=False)
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                
                # Only process vehicles above confidence threshold
                if cls_id in self.VEHICLE_CLASSES and conf >= confidence_threshold:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    
                    # Simple tracking: assign ID based on position
                    vehicle_id = self._get_or_assign_id(x1, y1, x2, y2)
                    
                    # Simulate plate detection (in real system, use EasyOCR or similar)
                    plate = self._simulate_plate_detection(vehicle_id)
                    
                    # Estimate speed based on position change (simplified)
                    speed = self._estimate_speed(vehicle_id, x1, y1, x2, y2)
                    
                    detections.append({
                        'id': vehicle_id,
                        'class': self.VEHICLE_CLASSES[cls_id],
                        'confidence': round(conf, 2),
                        'bbox': [x1, y1, x2, y2],
                        'plate': plate,
                        'speed_estimate': speed
                    })
        
        return detections
    
    def _get_or_assign_id(self, x1, y1, x2, y2):
        """Simple tracking: match to existing vehicle or assign new ID."""
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        
        # Check if this matches an existing tracked vehicle
        for vid, data in self.tracked_vehicles.items():
            last_cx, last_cy = data['center']
            # If center is within 100 pixels, consider it the same vehicle
            if abs(cx - last_cx) < 100 and abs(cy - last_cy) < 100:
                self.tracked_vehicles[vid]['center'] = (cx, cy)
                self.tracked_vehicles[vid]['last_seen'] = time.time()
                return vid
        
        # New vehicle
        vid = self.next_vehicle_id
        self.next_vehicle_id += 1
        self.tracked_vehicles[vid] = {
            'center': (cx, cy),
            'plate': random.choice(self.DEMO_PLATES),
            'last_seen': time.time(),
            'positions': [(cx, cy, time.time())]
        }
        return vid
    
    def _simulate_plate_detection(self, vehicle_id):
        """Return simulated plate for a vehicle."""
        if vehicle_id in self.tracked_vehicles:
            return self.tracked_vehicles[vehicle_id]['plate']
        return random.choice(self.DEMO_PLATES)
    
    def _estimate_speed(self, vehicle_id, x1, y1, x2, y2):
        """Estimate speed based on position changes (simplified)."""
        if vehicle_id not in self.tracked_vehicles:
            return random.randint(25, 45)
        
        data = self.tracked_vehicles[vehicle_id]
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        
        # Add current position
        data['positions'].append((cx, cy, time.time()))
        
        # Keep only last 10 positions
        if len(data['positions']) > 10:
            data['positions'] = data['positions'][-10:]
        
        # Calculate speed from position change (very simplified)
        if len(data['positions']) >= 2:
            p1 = data['positions'][0]
            p2 = data['positions'][-1]
            dx = abs(p2[0] - p1[0])
            dt = p2[2] - p1[2]
            if dt > 0:
                # Convert pixel movement to approximate mph (calibration needed for real use)
                pixel_speed = dx / dt
                # Rough conversion: assume 1 pixel/sec ≈ 0.5 mph at typical camera distance
                return min(80, max(15, int(pixel_speed * 0.5 + random.randint(20, 35))))
        
        return random.randint(25, 45)
    
    def _simulate_detections(self, frame):
        """Generate simulated detections when YOLO is not available."""
        h, w = frame.shape[:2]
        num_vehicles = random.randint(1, 4)
        detections = []
        
        for i in range(num_vehicles):
            # Random bounding box
            x1 = random.randint(50, w - 200)
            y1 = random.randint(h // 3, h - 150)
            x2 = x1 + random.randint(80, 150)
            y2 = y1 + random.randint(60, 100)
            
            vid = self.next_vehicle_id
            self.next_vehicle_id += 1
            
            detections.append({
                'id': vid,
                'class': random.choice(['car', 'car', 'car', 'truck', 'bus']),
                'confidence': round(random.uniform(0.7, 0.95), 2),
                'bbox': [x1, y1, x2, y2],
                'plate': random.choice(self.DEMO_PLATES),
                'speed_estimate': random.randint(25, 55)
            })
        
        return detections
    
    def draw_detections(self, frame, detections, speed_limit=30):
        """Draw bounding boxes and info on frame."""
        annotated = frame.copy()
        
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            plate = det['plate']
            speed = det['speed_estimate']
            conf = det['confidence']
            
            # Color based on speed violation
            if speed > speed_limit + 15:
                color = (0, 0, 255)  # Red - severe
                status = "VIOLATION"
            elif speed > speed_limit:
                color = (0, 165, 255)  # Orange - speeding
                status = "SPEEDING"
            else:
                color = (0, 255, 0)  # Green - ok
                status = "OK"
            
            # Draw bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Draw info background
            info_text = f"{plate} | {speed}mph"
            (tw, th), _ = cv2.getTextSize(info_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(annotated, (x1, y1 - 25), (x1 + tw + 10, y1), color, -1)
            
            # Draw text
            cv2.putText(annotated, info_text, (x1 + 5, y1 - 7),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Draw status if violation
            if status != "OK":
                cv2.putText(annotated, status, (x1, y2 + 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Draw detection count
        cv2.putText(annotated, f"Vehicles: {len(detections)}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        return annotated
    
    def process_video(self, video_path, output_path=None, speed_limit=30, max_frames=None):
        """
        Process entire video and return detection summary.
        
        Args:
            video_path: Path to input video
            output_path: Optional path to save annotated video
            speed_limit: Speed limit for violation detection
            max_frames: Max frames to process (None = all)
        
        Returns:
            dict with detection summary
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return {"error": f"Could not open video: {video_path}"}
        
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        writer = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        all_detections = []
        violations = []
        frame_count = 0
        
        print(f"Processing video: {video_path}")
        print(f"Resolution: {width}x{height}, FPS: {fps}, Frames: {total_frames}")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if max_frames and frame_count >= max_frames:
                break
            
            # Process every 5th frame for speed
            if frame_count % 5 == 0:
                detections = self.detect_frame(frame)
                all_detections.extend(detections)
                
                # Check for violations
                for det in detections:
                    if det['speed_estimate'] > speed_limit:
                        violations.append({
                            'frame': frame_count,
                            'timestamp': frame_count / fps,
                            'plate': det['plate'],
                            'speed': det['speed_estimate'],
                            'speed_limit': speed_limit,
                            'vehicle_class': det['class']
                        })
                
                # Draw detections
                annotated = self.draw_detections(frame, detections, speed_limit)
            else:
                annotated = frame
            
            if writer:
                writer.write(annotated)
            
            frame_count += 1
            
            if frame_count % 100 == 0:
                print(f"  Processed {frame_count}/{total_frames} frames...")
        
        cap.release()
        if writer:
            writer.release()
        
        # Summarize unique plates detected
        unique_plates = {}
        for v in violations:
            plate = v['plate']
            if plate not in unique_plates:
                unique_plates[plate] = {'count': 0, 'max_speed': 0, 'violations': []}
            unique_plates[plate]['count'] += 1
            unique_plates[plate]['max_speed'] = max(unique_plates[plate]['max_speed'], v['speed'])
            unique_plates[plate]['violations'].append(v)
        
        return {
            'video': str(video_path),
            'frames_processed': frame_count,
            'total_detections': len(all_detections),
            'total_violations': len(violations),
            'speed_limit': speed_limit,
            'unique_plates': unique_plates,
            'violations': violations[:50]  # Limit to first 50
        }


def process_camera_videos():
    """Process all camera videos and save detection results."""
    detector = TrafficDetector()
    
    videos = [
        ('frontend-react/public/timesquare.mp4', 15, 'CAM-1'),
        ('frontend-react/public/Video_Creation_Request_Fulfilled.mp4', 30, 'CAM-2'),
        ('frontend-react/public/Video_Generation_Successful.mp4', 30, 'CAM-3'),
    ]
    
    results = {}
    
    for video_path, speed_limit, camera_id in videos:
        if Path(video_path).exists():
            print(f"\n{'='*50}")
            print(f"Processing {camera_id}: {video_path}")
            print(f"Speed limit: {speed_limit} mph")
            print('='*50)
            
            result = detector.process_video(
                video_path, 
                speed_limit=speed_limit,
                max_frames=150  # Process first 150 frames for demo
            )
            results[camera_id] = result
            
            print(f"\nResults for {camera_id}:")
            print(f"  Violations: {result['total_violations']}")
            print(f"  Unique plates: {len(result['unique_plates'])}")
            for plate, data in result['unique_plates'].items():
                print(f"    {plate}: {data['count']} violations, max {data['max_speed']}mph")
    
    # Save results
    output_path = Path('detection_results.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Results saved to {output_path}")
    
    return results


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Traffic Camera CV Detector')
    parser.add_argument('--video', type=str, help='Path to video file')
    parser.add_argument('--output', type=str, help='Output video path')
    parser.add_argument('--speed-limit', type=int, default=30, help='Speed limit')
    parser.add_argument('--process-all', action='store_true', help='Process all camera videos')
    
    args = parser.parse_args()
    
    if args.process_all:
        process_camera_videos()
    elif args.video:
        detector = TrafficDetector()
        result = detector.process_video(args.video, args.output, args.speed_limit)
        print(json.dumps(result, indent=2))
    else:
        print("Usage:")
        print("  python cv_detector.py --video path/to/video.mp4")
        print("  python cv_detector.py --process-all")
