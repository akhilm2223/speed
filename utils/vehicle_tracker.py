"""
Vehicle Tracker using Centroid Tracking with Hungarian Algorithm

Provides stable vehicle IDs across frames for accurate speed calculation.
Uses scipy's linear_sum_assignment for optimal matching.
"""
import numpy as np
from collections import OrderedDict
from typing import List, Dict, Tuple, Optional

# Try scipy but gracefully handle version conflicts
SCIPY_AVAILABLE = False
try:
    from scipy.spatial import distance as dist
    from scipy.optimize import linear_sum_assignment
    SCIPY_AVAILABLE = True
except (ImportError, ValueError) as e:
    # ValueError catches numpy binary incompatibility
    print(f"⚠ scipy not available ({type(e).__name__}) - using basic tracking")


class CentroidTracker:
    """
    Track objects across frames using centroid-based tracking with Hungarian algorithm.
    
    Features:
    - Assigns unique IDs to each detected vehicle
    - Maintains position history for speed calculation
    - Handles object disappearance with configurable patience
    - Uses Hungarian algorithm for optimal assignment
    """
    
    def __init__(self, max_disappeared: int = 30, max_distance: int = 100):
        """
        Initialize the tracker.
        
        Args:
            max_disappeared: Number of frames to keep tracking after object disappears
            max_distance: Maximum pixel distance for matching objects between frames
        """
        self.next_object_id = 0
        self.objects: OrderedDict[int, np.ndarray] = OrderedDict()
        self.disappeared: Dict[int, int] = {}
        self.bboxes: Dict[int, Tuple[int, int, int, int]] = {}
        self.position_history: Dict[int, List[Tuple[np.ndarray, float]]] = {}
        
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
    
    def register(self, centroid: np.ndarray, bbox: Tuple[int, int, int, int], timestamp: float) -> int:
        """Register a new object with the next available ID."""
        object_id = self.next_object_id
        self.objects[object_id] = centroid
        self.bboxes[object_id] = bbox
        self.disappeared[object_id] = 0
        self.position_history[object_id] = [(centroid.copy(), timestamp)]
        self.next_object_id += 1
        return object_id
    
    def deregister(self, object_id: int) -> None:
        """Deregister an object ID."""
        del self.objects[object_id]
        del self.disappeared[object_id]
        del self.bboxes[object_id]
        if object_id in self.position_history:
            del self.position_history[object_id]
    
    def update(self, detections: List[Dict], timestamp: float) -> List[Dict]:
        """
        Update tracker with new detections.
        
        Args:
            detections: List of detection dicts with 'bbox' key (x, y, w, h)
            timestamp: Current frame timestamp in seconds
            
        Returns:
            List of tracked objects with IDs and position history
        """
        # No detections - mark all as disappeared
        if len(detections) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return self._get_tracked_objects()
        
        # Extract centroids and bboxes from detections
        input_centroids = np.zeros((len(detections), 2), dtype="int")
        input_bboxes = []
        
        for i, det in enumerate(detections):
            bbox = det['bbox']
            x, y, w, h = bbox
            cx = int(x + w / 2)
            cy = int(y + h / 2)
            input_centroids[i] = (cx, cy)
            input_bboxes.append(bbox)
        
        # If no existing objects, register all detections
        if len(self.objects) == 0:
            for i in range(len(input_centroids)):
                self.register(input_centroids[i], input_bboxes[i], timestamp)
            return self._get_tracked_objects()
        
        # Get existing object IDs and centroids
        object_ids = list(self.objects.keys())
        object_centroids = list(self.objects.values())
        
        # Compute distance matrix between existing and new centroids
        if SCIPY_AVAILABLE:
            D = dist.cdist(np.array(object_centroids), input_centroids)
        else:
            # Fallback: manual distance calculation
            D = np.zeros((len(object_centroids), len(input_centroids)))
            for i, oc in enumerate(object_centroids):
                for j, ic in enumerate(input_centroids):
                    D[i, j] = np.linalg.norm(oc - ic)
        
        # Use Hungarian algorithm for optimal assignment
        if SCIPY_AVAILABLE:
            rows, cols = linear_sum_assignment(D)
        else:
            # Greedy fallback
            rows = []
            cols = []
            D_copy = D.copy()
            for _ in range(min(D.shape)):
                min_idx = np.unravel_index(np.argmin(D_copy), D_copy.shape)
                if D_copy[min_idx] < self.max_distance:
                    rows.append(min_idx[0])
                    cols.append(min_idx[1])
                    D_copy[min_idx[0], :] = float('inf')
                    D_copy[:, min_idx[1]] = float('inf')
        
        # Track which rows/cols have been used
        used_rows = set()
        used_cols = set()
        
        # Match objects
        for row, col in zip(rows, cols):
            if D[row, col] > self.max_distance:
                continue
            
            object_id = object_ids[row]
            self.objects[object_id] = input_centroids[col]
            self.bboxes[object_id] = input_bboxes[col]
            self.disappeared[object_id] = 0
            
            # Add to position history
            self.position_history[object_id].append((input_centroids[col].copy(), timestamp))
            # Keep only last 30 positions
            if len(self.position_history[object_id]) > 30:
                self.position_history[object_id] = self.position_history[object_id][-30:]
            
            used_rows.add(row)
            used_cols.add(col)
        
        # Handle unmatched existing objects (disappeared)
        unused_rows = set(range(len(object_centroids))) - used_rows
        for row in unused_rows:
            object_id = object_ids[row]
            self.disappeared[object_id] += 1
            if self.disappeared[object_id] > self.max_disappeared:
                self.deregister(object_id)
        
        # Register unmatched new detections
        unused_cols = set(range(len(input_centroids))) - used_cols
        for col in unused_cols:
            self.register(input_centroids[col], input_bboxes[col], timestamp)
        
        return self._get_tracked_objects()
    
    def _get_tracked_objects(self) -> List[Dict]:
        """Convert internal state to list of tracked objects."""
        result = []
        for object_id in self.objects.keys():
            centroid = self.objects[object_id]
            bbox = self.bboxes[object_id]
            history = self.position_history.get(object_id, [])
            
            result.append({
                'id': object_id,
                'centroid': tuple(centroid),
                'bbox': bbox,
                'position_history': history,
            })
        return result
    
    def get_position_history(self, object_id: int) -> List[Tuple[np.ndarray, float]]:
        """Get position history for a specific object."""
        return self.position_history.get(object_id, [])
    
    def get_previous_position(self, object_id: int) -> Optional[Tuple[np.ndarray, float]]:
        """Get the previous position for speed calculation."""
        history = self.position_history.get(object_id, [])
        if len(history) >= 2:
            return history[-2]
        return None
    
    def get_current_position(self, object_id: int) -> Optional[Tuple[np.ndarray, float]]:
        """Get the current position."""
        history = self.position_history.get(object_id, [])
        if len(history) >= 1:
            return history[-1]
        return None

