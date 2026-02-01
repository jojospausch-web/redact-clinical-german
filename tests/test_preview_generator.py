"""Tests for preview generator."""

import pytest
import fitz  # PyMuPDF
from PIL import Image
import io
from src.preview_generator import create_preview_with_zones


class MockUploadedFile:
    """Mock Streamlit UploadedFile for testing."""
    
    def __init__(self, pdf_bytes):
        self.pdf_bytes = pdf_bytes
        self.position = 0
    
    def read(self):
        """Read PDF bytes."""
        return self.pdf_bytes
    
    def seek(self, position):
        """Seek to position."""
        self.position = position


def test_create_preview_with_zones():
    """Test that preview image is generated correctly."""
    # Create a simple test PDF
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 size
    page.insert_text((50, 100), "Test Header Area")
    page.insert_text((50, 400), "Test Content Area")
    page.insert_text((50, 800), "Test Footer Area")
    
    pdf_bytes = doc.tobytes()
    doc.close()
    
    # Create mock uploaded file
    mock_file = MockUploadedFile(pdf_bytes)
    
    # Generate preview
    preview = create_preview_with_zones(
        pdf_file=mock_file,
        header_height=150,
        footer_height=92
    )
    
    # Verify preview is a PIL Image
    assert isinstance(preview, Image.Image)
    
    # Verify image has dimensions
    assert preview.size[0] > 0
    assert preview.size[1] > 0
    
    # Verify it's RGB mode
    assert preview.mode == 'RGB'


def test_create_preview_no_zones():
    """Test preview generation with zero zone heights."""
    # Create a simple test PDF
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 400), "Test Content")
    
    pdf_bytes = doc.tobytes()
    doc.close()
    
    mock_file = MockUploadedFile(pdf_bytes)
    
    # Generate preview with no zones
    preview = create_preview_with_zones(
        pdf_file=mock_file,
        header_height=0,
        footer_height=0
    )
    
    assert isinstance(preview, Image.Image)
    assert preview.size[0] > 0


def test_create_preview_max_zones():
    """Test preview generation with maximum zone heights."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 400), "Test Content")
    
    pdf_bytes = doc.tobytes()
    doc.close()
    
    mock_file = MockUploadedFile(pdf_bytes)
    
    # Generate preview with maximum zones
    preview = create_preview_with_zones(
        pdf_file=mock_file,
        header_height=300,
        footer_height=200
    )
    
    assert isinstance(preview, Image.Image)
    assert preview.size[0] > 0
