"""
License Plate OCR Module

Uses EasyOCR to extract license plate text from vehicle images.
Includes preprocessing, validation, and cleaning for US plates.
"""
import re
import cv2
import numpy as np
from typing import Optional, Tuple, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import EasyOCR
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    logger.warning("EasyOCR not installed. OCR functionality will be disabled.")


class PlateOCR:
    """
    License Plate OCR using EasyOCR.
    
    Features:
    - Automatic plate region detection from vehicle bbox
    - Image preprocessing for better OCR accuracy
    - US plate format validation (5-8 alphanumeric chars)
    - Confidence thresholding
    """
    
    # US plate regex patterns (common formats)
    US_PLATE_PATTERNS = [
        r'^[A-Z]{3}[0-9]{4}$',      # ABC1234 (7 chars)
        r'^[A-Z]{2}[0-9]{4}$',      # AB1234 (6 chars)
        r'^[0-9]{3}[A-Z]{3}$',      # 123ABC (6 chars)
        r'^[0-9]{3}[A-Z]{4}$',      # 123ABCD (7 chars)
        r'^[A-Z]{3}[0-9]{3}$',      # ABC123 (6 chars)
        r'^[A-Z][0-9]{3}[A-Z]{3}$', # A123BCD (7 chars)
        r'^[0-9][A-Z]{3}[0-9]{3}$', # 1ABC234 (7 chars)
        r'^[A-Z]{2}[0-9]{5}$',      # AB12345 (7 chars)
        r'^[A-Z]{3}[0-9]{2}[A-Z]$', # ABC12D (6 chars)
        r'^[0-9]{4}[A-Z]{3}$',      # 1234ABC (7 chars)
    ]
    
    def __init__(self, languages: List[str] = None, min_confidence: float = 0.3,
                 gpu: bool = False):
        """
        Initialize PlateOCR.
        
        Args:
            languages: List of languages for OCR (default: ['en'])
            min_confidence: Minimum OCR confidence threshold
            gpu: Whether to use GPU acceleration
        """
        self.min_confidence = min_confidence
        self.reader = None
        
        if EASYOCR_AVAILABLE:
            try:
                langs = languages or ['en']
                logger.info(f"Initializing EasyOCR with languages: {langs}")
                self.reader = easyocr.Reader(langs, gpu=gpu, verbose=False)
                logger.info("✓ EasyOCR initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
    
    def is_available(self) -> bool:
        """Check if OCR is available."""
        return self.reader is not None
    
    def extract_plate_region(self, frame: np.ndarray, 
                             vehicle_bbox: Tuple[int, int, int, int],
                             plate_position: str = 'bottom') -> np.ndarray:
        """
        Extract the likely license plate region from vehicle bounding box.
        
        Args:
            frame: Full frame image
            vehicle_bbox: Vehicle bounding box (x, y, w, h)
            plate_position: Where plate is likely to be ('bottom', 'top', 'center')
            
        Returns:
            Cropped plate region
        """
        x, y, w, h = vehicle_bbox
        
        # Expand bbox slightly for safety
        padding = 5
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(frame.shape[1] - x, w + 2 * padding)
        h = min(frame.shape[0] - y, h + 2 * padding)
        
        if plate_position == 'bottom':
            # License plate usually in bottom 30-40% of vehicle
            plate_y = int(y + h * 0.6)
            plate_h = int(h * 0.35)
            plate_x = int(x + w * 0.15)
            plate_w = int(w * 0.7)
        elif plate_position == 'top':
            # For front-facing vehicles
            plate_y = int(y + h * 0.1)
            plate_h = int(h * 0.3)
            plate_x = int(x + w * 0.2)
            plate_w = int(w * 0.6)
        else:  # center
            plate_y = int(y + h * 0.35)
            plate_h = int(h * 0.3)
            plate_x = int(x + w * 0.2)
            plate_w = int(w * 0.6)
        
        # Ensure within bounds
        plate_y = max(0, plate_y)
        plate_x = max(0, plate_x)
        plate_h = min(frame.shape[0] - plate_y, plate_h)
        plate_w = min(frame.shape[1] - plate_x, plate_w)
        
        # Crop the region
        plate_region = frame[plate_y:plate_y+plate_h, plate_x:plate_x+plate_w]
        
        return plate_region
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR accuracy.
        
        Applies:
        - Resize to optimal size
        - Grayscale conversion
        - Contrast enhancement
        - Noise reduction
        - Binarization
        """
        if image.size == 0:
            return image
        
        # Resize if too small
        min_height = 50
        if image.shape[0] < min_height:
            scale = min_height / image.shape[0]
            image = cv2.resize(image, None, fx=scale, fy=scale, 
                              interpolation=cv2.INTER_CUBIC)
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Enhance contrast using CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Denoise
        denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
        
        # Adaptive thresholding
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        
        return binary
    
    def clean_plate_text(self, text: str) -> str:
        """
        Clean and normalize OCR output to valid plate format.
        
        Removes special characters, normalizes spacing, fixes common OCR errors.
        """
        if not text:
            return ""
        
        # Convert to uppercase
        text = text.upper()
        
        # Remove all non-alphanumeric characters
        text = re.sub(r'[^A-Z0-9]', '', text)
        
        # Common OCR substitutions
        substitutions = {
            'O': '0',  # O -> 0 in number positions
            '0': 'O',  # 0 -> O in letter positions
            'I': '1',  # I -> 1
            'L': '1',  # L -> 1
            'S': '5',  # S -> 5
            'B': '8',  # B -> 8
            'G': '6',  # G -> 6
            'Z': '2',  # Z -> 2
        }
        
        # Try to identify format and apply appropriate substitutions
        # For now, just return the cleaned text
        return text
    
    def validate_plate(self, plate_text: str) -> bool:
        """
        Validate if the text looks like a valid US license plate.
        
        Checks:
        - Length (5-8 characters for most US plates)
        - Alphanumeric characters only
        - Matches common US plate patterns
        """
        if not plate_text:
            return False
        
        # Check length (US plates are typically 5-8 characters)
        if not (5 <= len(plate_text) <= 8):
            return False
        
        # Must be alphanumeric
        if not plate_text.isalnum():
            return False
        
        # Check against known patterns
        for pattern in self.US_PLATE_PATTERNS:
            if re.match(pattern, plate_text):
                return True
        
        # Allow if it has both letters and numbers and right length
        has_letters = any(c.isalpha() for c in plate_text)
        has_numbers = any(c.isdigit() for c in plate_text)
        
        return has_letters and has_numbers
    
    def read_plate(self, frame: np.ndarray, 
                   vehicle_bbox: Tuple[int, int, int, int] = None,
                   preprocess: bool = True) -> Tuple[Optional[str], float]:
        """
        Read license plate from image.
        
        Args:
            frame: Image (full frame or cropped plate region)
            vehicle_bbox: Optional vehicle bounding box to crop from
            preprocess: Whether to apply preprocessing
            
        Returns:
            Tuple of (plate_text, confidence) or (None, 0.0) if failed
        """
        if not self.is_available():
            return None, 0.0
        
        try:
            # Crop plate region if bbox provided
            if vehicle_bbox is not None:
                plate_region = self.extract_plate_region(frame, vehicle_bbox)
            else:
                plate_region = frame
            
            # Check if region is valid
            if plate_region.size == 0 or plate_region.shape[0] < 10 or plate_region.shape[1] < 10:
                return None, 0.0
            
            # Preprocess
            if preprocess:
                processed = self.preprocess_image(plate_region)
            else:
                processed = plate_region
            
            # Run OCR
            results = self.reader.readtext(processed, detail=1)
            
            if not results:
                # Try on unprocessed image
                results = self.reader.readtext(plate_region, detail=1)
            
            if not results:
                return None, 0.0
            
            # Process results
            best_plate = None
            best_confidence = 0.0
            
            for (bbox, text, confidence) in results:
                # Clean the text
                cleaned = self.clean_plate_text(text)
                
                # Skip if too short
                if len(cleaned) < 5:
                    continue
                
                # Validate
                if self.validate_plate(cleaned):
                    if confidence > best_confidence:
                        best_plate = cleaned
                        best_confidence = confidence
                elif confidence > self.min_confidence and confidence > best_confidence:
                    # Accept even if not matching pattern, if high confidence
                    best_plate = cleaned
                    best_confidence = confidence
            
            if best_plate and best_confidence >= self.min_confidence:
                return best_plate, best_confidence
            
            return None, 0.0
            
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return None, 0.0
    
    def read_plate_multi_position(self, frame: np.ndarray,
                                   vehicle_bbox: Tuple[int, int, int, int]
                                   ) -> Tuple[Optional[str], float]:
        """
        Try reading plate from multiple positions (front and rear).
        
        Args:
            frame: Full frame image
            vehicle_bbox: Vehicle bounding box
            
        Returns:
            Best (plate_text, confidence) found
        """
        positions = ['bottom', 'top', 'center']
        best_plate = None
        best_confidence = 0.0
        
        for position in positions:
            plate_region = self.extract_plate_region(frame, vehicle_bbox, position)
            plate_text, confidence = self.read_plate(plate_region)
            
            if plate_text and confidence > best_confidence:
                best_plate = plate_text
                best_confidence = confidence
        
        return best_plate, best_confidence
    
    def format_for_display(self, plate_text: str) -> str:
        """
        Format plate text for display (add common separators).
        
        Example: ABC1234 -> ABC-1234
        """
        if not plate_text or len(plate_text) < 5:
            return plate_text or ""
        
        # Find the transition between letters and numbers
        for i, char in enumerate(plate_text):
            if i > 0 and plate_text[i-1].isalpha() != char.isalpha():
                return f"{plate_text[:i]}-{plate_text[i:]}"
        
        return plate_text

