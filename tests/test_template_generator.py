"""Tests for custom template generator."""

import pytest
from src.template_generator import create_custom_template


def test_create_custom_template_first_page_only():
    """Test creating custom template with header on first page only."""
    template = create_custom_template(
        header_height=150,
        header_page="1",
        footer_height=92,
        footer_keywords=["IBAN", "Bankverbindung"]
    )
    
    # Check template structure
    assert "zones" in template
    assert "header" in template["zones"]
    assert "footer" in template["zones"]
    
    # Check header configuration
    header = template["zones"]["header"]
    assert header["page"] == 1
    assert header["pages"] is None
    assert header["y_start"] == 842 - 150  # A4 height - header height
    assert header["y_end"] == 842
    assert header["redaction"] == "full"
    
    # Check footer configuration
    footer = template["zones"]["footer"]
    assert footer["pages"] == "all"
    assert footer["y_start"] == 0
    assert footer["y_end"] == 92
    assert footer["redaction"] == "keyword_based"
    assert footer["keywords"] == ["IBAN", "Bankverbindung"]


def test_create_custom_template_all_pages():
    """Test creating custom template with header on all pages."""
    template = create_custom_template(
        header_height=200,
        header_page="all",
        footer_height=100,
        footer_keywords=[]
    )
    
    # Check header applies to all pages
    header = template["zones"]["header"]
    assert header["page"] is None
    assert header["pages"] == "all"
    assert header["y_start"] == 842 - 200
    assert header["y_end"] == 842
    
    # Check footer without keywords uses full redaction
    footer = template["zones"]["footer"]
    assert footer["redaction"] == "full"
    assert "keywords" not in footer or footer.get("keywords") == []


def test_create_custom_template_zero_heights():
    """Test creating custom template with zero zone heights."""
    template = create_custom_template(
        header_height=0,
        header_page="1",
        footer_height=0,
        footer_keywords=[]
    )
    
    # Check zones are created even with zero height
    assert "zones" in template
    header = template["zones"]["header"]
    assert header["y_start"] == 842  # No header zone
    assert header["y_end"] == 842
    
    footer = template["zones"]["footer"]
    assert footer["y_start"] == 0
    assert footer["y_end"] == 0


def test_create_custom_template_max_heights():
    """Test creating custom template with maximum zone heights."""
    template = create_custom_template(
        header_height=300,
        header_page="all",
        footer_height=200,
        footer_keywords=["IBAN", "BIC", "Sparkasse"]
    )
    
    header = template["zones"]["header"]
    assert header["y_start"] == 842 - 300
    assert header["y_end"] == 842
    
    footer = template["zones"]["footer"]
    assert footer["y_start"] == 0
    assert footer["y_end"] == 200
    assert len(footer["keywords"]) == 3


def test_create_custom_template_preserves_base_template():
    """Test that custom template preserves other fields from base template."""
    template = create_custom_template(
        header_height=150,
        header_page="1",
        footer_height=92,
        footer_keywords=["IBAN"]
    )
    
    # Check that other template fields are preserved
    assert "template_name" in template
    assert "version" in template
    assert "structured_patterns" in template
    assert "date_handling" in template
    assert "image_pii_patterns" in template
    
    # Check that postal code patterns are present
    assert "postal_code_with_city" in template["structured_patterns"]
    assert "postal_code_standalone" in template["structured_patterns"]
