"""Tests for image anonymization functionality."""

import pytest
from PIL import Image, ImageDraw, ImageFont
import tempfile
from pathlib import Path

from src.image_anonymizer import MedicalImageAnonymizer


class TestMedicalImageAnonymizer:
    """Test cases for MedicalImageAnonymizer class."""
    
    @pytest.fixture
    def sample_patterns(self):
        """Sample PII patterns for testing."""
        return {
            "case_number": r"\d{6,10}",
            "name": r"^[A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+$",
            "birthdate": r"\d{2}\.\d{2}\.\d{4}"
        }
    
    @pytest.fixture
    def simple_image(self):
        """Create a simple test image."""
        # Create a white image
        img = Image.new('RGB', (400, 200), color='white')
        return img
    
    def test_anonymizer_initialization(self, sample_patterns):
        """Test that anonymizer initializes correctly."""
        anonymizer = MedicalImageAnonymizer(sample_patterns)
        
        assert len(anonymizer.pii_patterns) == 3
        assert len(anonymizer.compiled_patterns) == 3
    
    def test_is_pii_detection(self, sample_patterns):
        """Test PII detection logic."""
        anonymizer = MedicalImageAnonymizer(sample_patterns)
        
        # Test case number detection
        assert anonymizer._is_pii("123456789") is True
        
        # Test date detection
        assert anonymizer._is_pii("01.01.2023") is True
        
        # Test non-PII
        assert anonymizer._is_pii("Normal text") is False
    
    def test_get_matched_pattern(self, sample_patterns):
        """Test pattern matching identification."""
        anonymizer = MedicalImageAnonymizer(sample_patterns)
        
        # Test case number
        assert anonymizer._get_matched_pattern("123456789") == "case_number"
        
        # Test birthdate
        assert anonymizer._get_matched_pattern("15.03.1980") == "birthdate"
        
        # Test unknown
        assert anonymizer._get_matched_pattern("random text") == "unknown"
    
    def test_anonymize_region(self, sample_patterns, simple_image):
        """Test region anonymization."""
        anonymizer = MedicalImageAnonymizer(sample_patterns)
        
        # Define a region to anonymize
        bbox = (50, 50, 150, 100)
        
        anonymized = anonymizer.anonymize_region(simple_image, bbox)
        
        # Verify image was modified (check a pixel in the redacted area)
        pixel = anonymized.getpixel((100, 75))
        assert pixel == (0, 0, 0)  # Should be black
    
    def test_anonymize_image_without_tesseract(self, sample_patterns, simple_image):
        """Test image anonymization when tesseract is not available."""
        anonymizer = MedicalImageAnonymizer(sample_patterns)
        
        # This should not fail even if tesseract is unavailable
        anonymized, redactions = anonymizer.anonymize_image(simple_image)
        
        # Should return the image (possibly unchanged if tesseract unavailable)
        assert anonymized is not None
        assert isinstance(redactions, list)
