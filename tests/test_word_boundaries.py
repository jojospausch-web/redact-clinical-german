"""Tests for word boundary checking and facility pattern recognition."""

import json
import pytest
from src.pii_extractor import StructuredPIIExtractor
from src.config import PatternGroup, AnonymizationTemplate


class TestWordBoundaries:
    """Test cases for word boundary checking."""
    
    def test_whole_word_boundary_hamburg(self):
        """Test that only whole words are recognized, not substrings."""
        patterns = {
            "postal_code_with_city": PatternGroup(
                pattern=r"(\d{5})\s+([A-ZÄÖÜ][a-zäöüß]+)",
                groups={
                    "1": "POSTAL_CODE",
                    "2": "CITY"
                }
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        # Positive: Whole word
        text1 = "Patient wurde in Hamburg behandelt"
        entities = extractor.extract_pii(text1)
        hamburg_entities = [e for e in entities if e.text == 'Hamburg']
        assert len(hamburg_entities) == 0  # No postal code, so Hamburg not matched by this pattern
        
        # With postal code
        text2 = "Patient wohnt in 20246 Hamburg"
        entities = extractor.extract_pii(text2)
        hamburg_entities = [e for e in entities if e.text == 'Hamburg' and e.entity_type == 'CITY']
        assert len(hamburg_entities) == 1
        
        # Negative: Substring in compound word
        text3 = "OP-Methode nach Roshamburger"
        entities = extractor.extract_pii(text3)
        # "Hamburg" should NOT be extracted from "Roshamburger"
        hamburg_entities = [e for e in entities if 'Hamburg' in e.text]
        assert len(hamburg_entities) == 0
    
    def test_substring_not_matched(self):
        """Test that substrings like 'Klappe' in 'Aortenklappenbioprothese' are not matched."""
        patterns = {
            "test_pattern": PatternGroup(
                pattern=r"(Klappe)",
                type="TEST_ENTITY"
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        # Negative: Medical term
        text = "Aortenklappenbioprothese implantiert"
        entities = extractor.extract_pii(text)
        # "Klappe" should NOT be extracted from "Aortenklappenbioprothese"
        assert len(entities) == 0
        
        # Positive: Standalone word
        text2 = "Die Klappe wurde ersetzt"
        entities = extractor.extract_pii(text2)
        assert len(entities) == 1
        assert entities[0].text == "Klappe"


class TestFacilityPatterns:
    """Test cases for facility pattern recognition."""
    
    @pytest.fixture
    def template(self):
        """Load the template with facility patterns."""
        with open('templates/german_clinical_default.json', 'r', encoding='utf-8') as f:
            template_data = json.load(f)
        return AnonymizationTemplate(**template_data)
    
    def test_city_facility_simple(self, template):
        """Test simple city + facility patterns."""
        patterns = template.structured_patterns
        extractor = StructuredPIIExtractor(patterns)
        
        test_cases = [
            ("Einbecker Krankenhaus", True, "CITY_ADJECTIVE"),
            ("Hamburger Klinikum", True, "CITY_ADJECTIVE"),
            ("Göttinger MVZ", True, "CITY_ADJECTIVE"),
            ("Roshamburger OP", False, None),  # Should NOT match
        ]
        
        for text, should_match, expected_type in test_cases:
            entities = extractor.extract_pii(text)
            if should_match:
                # Check if we found the city adjective or facility
                city_adj_entities = [e for e in entities if e.entity_type in ['CITY_ADJECTIVE', 'FACILITY_TYPE']]
                assert len(city_adj_entities) > 0, f"Should match: {text}"
            else:
                # Should NOT match any Hamburg-related entity
                hamburg_entities = [e for e in entities if 'Hamburg' in e.text or 'hamburg' in e.text.lower()]
                assert len(hamburg_entities) == 0, f"Should NOT match: {text}"
    
    def test_university_hospital(self, template):
        """Test university hospital patterns."""
        patterns = template.structured_patterns
        extractor = StructuredPIIExtractor(patterns)
        
        text = "Universitätsklinikum Göttingen"
        entities = extractor.extract_pii(text)
        
        # Should find facility type and city
        facility_entities = [e for e in entities if e.entity_type == 'FACILITY_TYPE']
        city_entities = [e for e in entities if e.entity_type == 'CITY']
        
        assert len(facility_entities) >= 1
        assert len(city_entities) >= 1
        assert any('Universitätsklinikum' in e.text for e in facility_entities)
        assert any('Göttingen' in e.text for e in city_entities)
    
    def test_medical_facility_with_city(self, template):
        """Test generic medical facility with city adjective."""
        patterns = template.structured_patterns
        extractor = StructuredPIIExtractor(patterns)
        
        test_cases = [
            "Hamburger Herzzentrum",
            "Berliner Tumorzentrum",
            "Münchner Lungenzentrum",
        ]
        
        for text in test_cases:
            entities = extractor.extract_pii(text)
            # Should find city adjective or facility
            has_facility = any(e.entity_type in ['CITY_ADJECTIVE', 'FACILITY_FULL_NAME', 'MEDICAL_FACILITY'] 
                             for e in entities)
            assert has_facility, f"Should match facility in: {text}"


class TestHeaderFooterCoordinates:
    """Test that template has correct zone coordinates."""
    
    def test_header_footer_coordinates(self):
        """Test that template has correct zone coordinates."""
        with open('templates/german_clinical_default.json', 'r', encoding='utf-8') as f:
            template = json.load(f)
        
        # Header Seite 1 (at top of page)
        assert 'header_page_1' in template['zones']
        header = template['zones']['header_page_1']
        assert header['y_start'] == 562, "Header should start at y=562 (top of page - 280px)"
        assert header['y_end'] == 842, "Header should end at y=842 (top of page)"
        assert header['page'] == 1
        assert header['preserve_logos'] is False, "Logo preservation should be disabled"
        
        # Footer Seite 1 (at bottom of page)
        assert 'footer_page_1' in template['zones']
        footer1 = template['zones']['footer_page_1']
        assert footer1['y_start'] == 0, "Footer should start at y=0 (bottom of page)"
        assert footer1['y_end'] == 35, "Footer should end at y=35 (35px high)"
        assert footer1['page'] == 1
        assert footer1['redaction'] == 'full', "Footer should have full redaction"
        
        # Footer andere Seiten (at bottom of page)
        assert 'footer_other_pages' in template['zones']
        footer_other = template['zones']['footer_other_pages']
        assert footer_other['y_start'] == 0, "Footer should start at y=0 (bottom of page)"
        assert footer_other['y_end'] == 80, "Footer should end at y=80 (80px high)"
        assert footer_other['exclude_page'] == 1, "Should exclude page 1"
        assert footer_other['pages'] == 'all', "Should apply to all pages"


class TestWhitelistFramework:
    """Test that whitelist framework exists in config."""
    
    def test_whitelist_config_exists(self):
        """Test that WhitelistConfig class exists."""
        from src.config import WhitelistConfig
        
        # Test that we can create an empty whitelist
        whitelist = WhitelistConfig()
        assert whitelist.medical_terms == []
        assert whitelist.anatomical_terms == []
        assert whitelist.device_names == []
    
    def test_whitelist_in_template(self):
        """Test that template supports whitelist field."""
        from src.config import AnonymizationTemplate, WhitelistConfig
        
        # Load template
        with open('templates/german_clinical_default.json', 'r', encoding='utf-8') as f:
            template_data = json.load(f)
        
        template = AnonymizationTemplate(**template_data)
        
        # Whitelist should be None (not specified in template)
        assert template.whitelist is None


class TestIsWholeWordMethod:
    """Test the _is_whole_word helper method."""
    
    def test_is_whole_word_basic(self):
        """Test basic word boundary detection."""
        patterns = {}
        extractor = StructuredPIIExtractor(patterns)
        
        text = "in Hamburg behandelt"
        
        # "Hamburg" is a whole word
        start = text.index("Hamburg")
        end = start + len("Hamburg")
        assert extractor._is_whole_word(text, start, end) is True
        
        # Test at beginning
        text2 = "Hamburg ist eine Stadt"
        start2 = 0
        end2 = len("Hamburg")
        assert extractor._is_whole_word(text2, start2, end2) is True
        
        # Test at end
        text3 = "Ich wohne in Hamburg"
        start3 = text3.index("Hamburg")
        end3 = len(text3)
        assert extractor._is_whole_word(text3, start3, end3) is True
    
    def test_is_whole_word_substring(self):
        """Test that substrings are not considered whole words."""
        patterns = {}
        extractor = StructuredPIIExtractor(patterns)
        
        text = "Roshamburger"
        
        # "Hamburg" inside "Roshamburger" is NOT a whole word
        # Search case-insensitively
        start = text.lower().index("hamburg")
        end = start + len("hamburg")
        assert extractor._is_whole_word(text, start, end) is False
        
        # Test with medical term
        text2 = "Aortenklappenbioprothese"
        # Find "klappen" substring
        start2 = text2.lower().index("klappen")
        end2 = start2 + len("klappen")
        assert extractor._is_whole_word(text2, start2, end2) is False
