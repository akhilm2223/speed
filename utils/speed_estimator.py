"""
Speed Estimation Module

Calculates vehicle speed based on pixel displacement across frames
using camera calibration (meters_per_pixel).
"""
import numpy as np
from typing import Tuple, Optional, List
from collections import deque


class SpeedEstimator:
    """
    Estimate vehicle speed from frame-to-frame pixel displacement.
    
    Uses:
    - Pixel displacement between frames
    - Camera FPS for time calculation
    - Camera-specific calibration (meters_per_pixel)
    - Moving average smoothing for stable readings
    """
    
    def __init__(self, meters_per_pixel: float = 0.05, fps: float = 30.0, 
                 smoothing_window: int = 5, min_movement: float = 2.0):
        """
        Initialize speed estimator.
        
        Args:
            meters_per_pixel: Camera calibration - real-world meters per pixel
            fps: Video frames per second
            smoothing_window: Number of readings to average for smoothing
            min_movement: Minimum pixel movement to register (noise filter)
        """
        self.meters_per_pixel = meters_per_pixel
        self.fps = fps
        self.smoothing_window = smoothing_window
        self.min_movement = min_movement
        
        # Speed history per vehicle ID for smoothing
        self.speed_history: dict[int, deque] = {}
    
    def estimate_speed(self, 
                       previous_xy: Tuple[float, float], 
                       current_xy: Tuple[float, float],
                       time_delta: Optional[float] = None) -> float:
        """
        Calculate speed from position change.
        
        Args:
            previous_xy: Previous position (x, y) in pixels
            current_xy: Current position (x, y) in pixels
            time_delta: Time between positions in seconds (uses 1/fps if None)
            
        Returns:
            Speed in MPH
        """
        # Calculate pixel displacement
        dx = current_xy[0] - previous_xy[0]
        dy = current_xy[1] - previous_xy[1]
        pixel_distance = np.sqrt(dx**2 + dy**2)
        
        # Filter out noise (tiny movements)
        if pixel_distance < self.min_movement:
            return 0.0
        
        # Convert to meters
        meters = pixel_distance * self.meters_per_pixel
        
        # Calculate time delta
        if time_delta is None or time_delta <= 0:
            time_delta = 1.0 / self.fps
        
        # Calculate speed in m/s
        speed_mps = meters / time_delta
        
        # Convert to MPH
        speed_mph = speed_mps * 2.23694
        
        return speed_mph
    
    def estimate_speed_smoothed(self, 
                                 vehicle_id: int,
                                 previous_xy: Tuple[float, float], 
                                 current_xy: Tuple[float, float],
                                 time_delta: Optional[float] = None) -> float:
        """
        Calculate smoothed speed using moving average.
        
        Args:
            vehicle_id: Unique vehicle ID for tracking history
            previous_xy: Previous position (x, y) in pixels
            current_xy: Current position (x, y) in pixels
            time_delta: Time between positions in seconds
            
        Returns:
            Smoothed speed in MPH
        """
        # Get raw speed
        raw_speed = self.estimate_speed(previous_xy, current_xy, time_delta)
        
        # Initialize history if needed
        if vehicle_id not in self.speed_history:
            self.speed_history[vehicle_id] = deque(maxlen=self.smoothing_window)
        
        # Add to history
        self.speed_history[vehicle_id].append(raw_speed)
        
        # Calculate moving average
        if len(self.speed_history[vehicle_id]) == 0:
            return 0.0
        
        return float(np.mean(self.speed_history[vehicle_id]))
    
    def estimate_from_history(self, 
                              position_history: List[Tuple[np.ndarray, float]],
                              vehicle_id: Optional[int] = None) -> float:
        """
        Estimate speed from full position history.
        
        Uses multiple frames for more accurate estimation.
        
        Args:
            position_history: List of (position, timestamp) tuples
            vehicle_id: Optional vehicle ID for smoothing
            
        Returns:
            Estimated speed in MPH
        """
        if len(position_history) < 2:
            return 0.0
        
        # Use last few positions for estimation
        num_samples = min(5, len(position_history))
        recent = position_history[-num_samples:]
        
        speeds = []
        for i in range(1, len(recent)):
            prev_pos, prev_time = recent[i-1]
            curr_pos, curr_time = recent[i]
            
            time_delta = curr_time - prev_time
            if time_delta <= 0:
                continue
            
            speed = self.estimate_speed(
                (prev_pos[0], prev_pos[1]),
                (curr_pos[0], curr_pos[1]),
                time_delta
            )
            speeds.append(speed)
        
        if not speeds:
            return 0.0
        
        # Return median for robustness
        return float(np.median(speeds))
    
    def update_calibration(self, meters_per_pixel: float) -> None:
        """Update the calibration value."""
        self.meters_per_pixel = meters_per_pixel
    
    def update_fps(self, fps: float) -> None:
        """Update the FPS value."""
        self.fps = fps
    
    def clear_history(self, vehicle_id: Optional[int] = None) -> None:
        """Clear speed history for a vehicle or all vehicles."""
        if vehicle_id is not None:
            if vehicle_id in self.speed_history:
                del self.speed_history[vehicle_id]
        else:
            self.speed_history.clear()
    
    @staticmethod
    def mph_to_kmh(mph: float) -> float:
        """Convert MPH to KM/H."""
        return mph * 1.60934
    
    @staticmethod
    def mps_to_mph(mps: float) -> float:
        """Convert m/s to MPH."""
        return mps * 2.23694

