"""Tests to verify date-shifting is disabled for regular dates but still works for birthdate."""

import pytest
import json
from src.pii_extractor import StructuredPIIExtractor
from src.config import AnonymizationTemplate


def load_template():
    """Load the german_clinical_default.json template."""
    with open("templates/german_clinical_default.json", "r", encoding="utf-8") as f:
        template_data = json.load(f)
    return AnonymizationTemplate(**template_data)


def test_regular_dates_not_extracted():
    """Test that regular dates (without *) are NOT extracted."""
    template = load_template()
    extractor = StructuredPIIExtractor(template.structured_patterns)
    
    # Text with various date formats that should NOT be extracted
    text = """
    Aufenthalt vom 05.08 bis zum 21.08.2023
    Herzkatheteruntersuchung vom 16.08.2023
    Patient aufgenommen am 5. November 2023
    Entlassung am 10. Nov. 2023
    Termin: 15.12.2024
    """
    
    entities = extractor.extract_pii(text)
    date_entities = [e for e in entities if e.entity_type == 'DATE']
    
    # Should NOT extract any DATE entities
    assert len(date_entities) == 0, f"Expected no DATE entities, but found: {date_entities}"


def test_birthdate_still_extracted():
    """Test that birthdate (with *) is STILL extracted."""
    template = load_template()
    extractor = StructuredPIIExtractor(template.structured_patterns)
    
    # Text with birthdate (asterisk prefix) - must match full patient_block pattern
    text = "Herr Müller, Max, *01.01.1960"
    
    entities = extractor.extract_pii(text)
    birthdate_entities = [e for e in entities if e.entity_type == 'BIRTHDATE']
    
    # Should extract the birthdate
    assert len(birthdate_entities) == 1, f"Expected 1 BIRTHDATE entity, but found {len(birthdate_entities)}: {entities}"
    assert '01.01.1960' in birthdate_entities[0].text


def test_date_not_in_pii_mechanisms():
    """Test that DATE is not in pii_mechanisms."""
    template = load_template()
    
    # DATE should not be in pii_mechanisms
    assert "DATE" not in template.pii_mechanisms, "DATE should be removed from pii_mechanisms"
    
    # BIRTHDATE should still be there
    assert "BIRTHDATE" in template.pii_mechanisms, "BIRTHDATE should remain in pii_mechanisms"
    assert template.pii_mechanisms["BIRTHDATE"] == "shift_date"


def test_date_patterns_removed_from_structured_patterns():
    """Test that date patterns are removed from structured_patterns."""
    template = load_template()
    patterns = template.structured_patterns
    
    # These patterns should NOT exist anymore
    date_pattern_names = [
        "date_range",
        "german_full_date",
        "german_abbr_date",
        "date_with_context_full",
        "date_with_context_short",
        "date_numeric_full"
    ]
    
    for pattern_name in date_pattern_names:
        assert pattern_name not in patterns, f"{pattern_name} should be removed from structured_patterns"


def test_patient_block_pattern_still_exists():
    """Test that patient_block pattern with BIRTHDATE still exists."""
    template = load_template()
    patterns = template.structured_patterns
    
    # patient_block should still exist
    assert "patient_block" in patterns, "patient_block pattern should still exist"
    
    # It should have BIRTHDATE in groups
    patient_block = patterns["patient_block"]
    assert patient_block.groups is not None
    assert "4" in patient_block.groups
    assert patient_block.groups["4"] == "BIRTHDATE"


def test_date_handling_block_still_exists():
    """Test that date_handling block still exists (for future use)."""
    template = load_template()
    
    # date_handling should still exist
    assert template.date_handling is not None, "date_handling should still exist in template"
    
    # birthdate handling should still exist
    assert "birthdate" in template.date_handling


def test_mixed_content_extraction():
    """Test extraction with mixed content (birthdate + regular dates)."""
    template = load_template()
    extractor = StructuredPIIExtractor(template.structured_patterns)
    
    text = """Frau Schmidt, Anna, *15.03.1975
Aufenthalt vom 05.08 bis zum 21.08.2023
Herzkatheteruntersuchung vom 16.08.2023"""
    
    entities = extractor.extract_pii(text)
    
    # Should only extract BIRTHDATE, not DATE
    birthdate_entities = [e for e in entities if e.entity_type == 'BIRTHDATE']
    date_entities = [e for e in entities if e.entity_type == 'DATE']
    
    assert len(birthdate_entities) == 1, f"Should extract exactly 1 BIRTHDATE, found {len(birthdate_entities)}: {entities}"
    assert len(date_entities) == 0, "Should NOT extract any DATE entities"
    assert '15.03.1975' in birthdate_entities[0].text
