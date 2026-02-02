"""Tests for template loading and validation."""

import pytest
import json
from pathlib import Path

from src.config import AnonymizationTemplate
from src.main import load_and_validate_template


class TestTemplateLoading:
    """Test cases for template loading and validation."""
    
    def test_default_template_loads(self):
        """Test that the default German clinical template loads successfully."""
        template_path = "templates/german_clinical_default.json"
        
        # Verify file exists
        assert Path(template_path).exists(), f"Template file not found: {template_path}"
        
        # Load and validate template
        config = load_and_validate_template(template_path)
        
        # Verify basic structure
        assert config.template_name == "German-Clinical-Structured-v2"
        assert config.version == "2.0.0"
        
    def test_template_has_required_fields(self):
        """Test that template has all required fields."""
        template_path = "templates/german_clinical_default.json"
        config = load_and_validate_template(template_path)
        
        # Check zones - new zone names
        assert "header_page_1" in config.zones
        assert "footer_page_1" in config.zones
        assert "footer_other_pages" in config.zones
        
        # Check date handling patterns
        assert "birthdate" in config.date_handling
        assert "german_full_date" in config.date_handling
        assert "german_abbr_date" in config.date_handling
        assert "numeric_date" in config.date_handling
        
        # Verify date patterns have required fields
        for pattern_name, pattern_config in config.date_handling.items():
            assert hasattr(pattern_config, 'pattern'), f"{pattern_name} missing 'pattern'"
            assert hasattr(pattern_config, 'action'), f"{pattern_name} missing 'action'"
        
        # Check structured patterns
        assert "patient_block" in config.structured_patterns
        assert "case_id" in config.structured_patterns
        
        # Check image PII patterns
        assert len(config.image_pii_patterns) > 0
        
    def test_template_date_handling_config(self):
        """Test that date handling configurations are valid."""
        template_path = "templates/german_clinical_default.json"
        config = load_and_validate_template(template_path)
        
        # Test birthdate pattern
        birthdate_config = config.date_handling["birthdate"]
        assert birthdate_config.pattern == r"\*(\d{2}\.\d{2}\.\d{4})"
        assert birthdate_config.action == "shift"
        assert birthdate_config.shift_days_range == (-30, 30)
        
        # Test german full date pattern
        german_full_config = config.date_handling["german_full_date"]
        assert "Januar" in german_full_config.pattern
        assert german_full_config.action == "shift"
        
    def test_template_optional_fields(self):
        """Test that optional fields are present and valid."""
        template_path = "templates/german_clinical_default.json"
        config = load_and_validate_template(template_path)
        
        # Check optional fields exist and are not empty
        assert config.location_anonymization is not None
        assert isinstance(config.location_anonymization, dict)
        assert config.location_anonymization.get("enabled") is not None
        
        assert config.pii_mechanisms is not None
        assert isinstance(config.pii_mechanisms, dict)
        assert len(config.pii_mechanisms) > 0
        
        assert config.info is not None
        assert isinstance(config.info, str)
        assert len(config.info) > 0
        
    def test_template_location_anonymization(self):
        """Test that location anonymization config is present."""
        template_path = "templates/german_clinical_default.json"
        config = load_and_validate_template(template_path)
        
        # Verify location anonymization is configured
        assert config.location_anonymization["enabled"] is True
        assert "city_database" in config.location_anonymization
        assert "facilities_database" in config.location_anonymization
        assert "location_blacklist" in config.location_anonymization
        
    def test_invalid_template_raises_error(self, tmp_path):
        """Test that invalid template raises helpful error."""
        # Create invalid template
        invalid_template = tmp_path / "invalid.json"
        invalid_template.write_text(json.dumps({
            "template_name": "Invalid",
            "version": "1.0.0",
            "zones": {},
            "structured_patterns": {},
            "date_handling": {
                "bad_date": {
                    "pattern": "some_pattern"
                    # Missing 'action' field
                }
            },
            "image_pii_patterns": {}
        }))
        
        # Should raise ValueError with helpful message
        with pytest.raises(ValueError) as exc_info:
            load_and_validate_template(str(invalid_template))
        
        assert "Validierungsfehler" in str(exc_info.value)
        
    def test_missing_template_raises_error(self):
        """Test that missing template file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_and_validate_template("nonexistent_template.json")
