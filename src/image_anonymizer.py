"""Image anonymization using OCR and pattern detection."""

import re
from PIL import Image, ImageDraw
from typing import Dict, List, Tuple
import logging

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logging.warning("pytesseract not available. Image anonymization will be limited.")


class MedicalImageAnonymizer:
    """Anonymizes medical images using OCR to detect and redact PII."""
    
    def __init__(self, pii_patterns: Dict[str, str]):
        """Initialize with PII patterns to detect.
        
        Args:
            pii_patterns: Dictionary of pattern names and regex patterns
        """
        self.pii_patterns = pii_patterns
        self.compiled_patterns = {
            name: re.compile(pattern)
            for name, pattern in pii_patterns.items()
        }
    
    def anonymize_image(self, image: Image.Image) -> Tuple[Image.Image, List[dict]]:
        """Anonymize PII in an image using OCR.
        
        Args:
            image: PIL Image to anonymize
        
        Returns:
            Tuple of (anonymized_image, list of redacted regions)
        """
        if not TESSERACT_AVAILABLE:
            logging.warning("Tesseract not available, returning original image")
            return image, []
        
        # Create a copy to work with
        anonymized = image.copy()
        redacted_regions = []
        
        try:
            # Perform OCR with bounding box data
            ocr_data = pytesseract.image_to_data(
                image, 
                lang='deu',
                output_type=pytesseract.Output.DICT
            )
            
            # Process each detected text element
            n_boxes = len(ocr_data['text'])
            draw = ImageDraw.Draw(anonymized)
            
            for i in range(n_boxes):
                text = ocr_data['text'][i].strip()
                if not text:
                    continue
                
                # Check if text matches any PII pattern
                if self._is_pii(text):
                    # Get bounding box coordinates
                    x, y, w, h = (
                        ocr_data['left'][i],
                        ocr_data['top'][i],
                        ocr_data['width'][i],
                        ocr_data['height'][i]
                    )
                    
                    # Add some padding
                    padding = 2
                    bbox = (
                        x - padding,
                        y - padding,
                        x + w + padding,
                        y + h + padding
                    )
                    
                    # Redact with black rectangle
                    draw.rectangle(bbox, fill='black')
                    
                    redacted_regions.append({
                        'text': text,
                        'bbox': bbox,
                        'matched_pattern': self._get_matched_pattern(text)
                    })
        
        except Exception as e:
            logging.error(f"Error during OCR anonymization: {e}")
            return image, []
        
        return anonymized, redacted_regions
    
    def _is_pii(self, text: str) -> bool:
        """Check if text matches any PII pattern.
        
        Args:
            text: Text to check
        
        Returns:
            True if text matches a PII pattern
        """
        for pattern in self.compiled_patterns.values():
            if pattern.search(text):
                return True
        return False
    
    def _get_matched_pattern(self, text: str) -> str:
        """Get the name of the pattern that matched the text.
        
        Args:
            text: Text to check
        
        Returns:
            Name of the matched pattern or 'unknown'
        """
        for name, pattern in self.compiled_patterns.items():
            if pattern.search(text):
                return name
        return 'unknown'
    
    def anonymize_region(self, image: Image.Image, bbox: Tuple[int, int, int, int]) -> Image.Image:
        """Anonymize a specific region of an image.
        
        Args:
            image: PIL Image to anonymize
            bbox: Bounding box as (x0, y0, x1, y1)
        
        Returns:
            Anonymized image
        """
        anonymized = image.copy()
        draw = ImageDraw.Draw(anonymized)
        draw.rectangle(bbox, fill='black')
        return anonymized
