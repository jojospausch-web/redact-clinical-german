"""Tests for structured PII extraction."""

import pytest
from src.pii_extractor import StructuredPIIExtractor
from src.config import PatternGroup


class TestStructuredPIIExtractor:
    """Test cases for StructuredPIIExtractor class."""
    
    def test_extract_case_id(self):
        """Test extraction of case/patient ID."""
        patterns = {
            "case_id": PatternGroup(
                pattern=r"Pat\.?-?Nr\.?:?\s*([0-9]{6,10})",
                type="CASE_ID"
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = "Patient information: Pat.-Nr. 123456789"
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 1
        assert entities[0].entity_type == "CASE_ID"
        assert entities[0].text == "123456789"
    
    def test_extract_patient_block_with_groups(self):
        """Test extraction of patient block with multiple groups."""
        patterns = {
            "patient_block": PatternGroup(
                pattern=r"(Herr|Frau)\s+([A-ZÄÖÜ][a-zäöüß-]+),\s+([A-ZÄÖÜ][a-zäöüß-]+),\s+\*(\d{2}\.\d{2}\.\d{4})",
                groups={
                    "1": "SALUTATION",
                    "2": "LASTNAME",
                    "3": "FIRSTNAME",
                    "4": "BIRTHDATE"
                }
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = "Herr Müller, Max, *01.01.1960"
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 4
        
        # Check each entity type
        types = {e.entity_type for e in entities}
        assert types == {"SALUTATION", "LASTNAME", "FIRSTNAME", "BIRTHDATE"}
        
        # Check specific values
        lastname = next(e for e in entities if e.entity_type == "LASTNAME")
        assert lastname.text == "Müller"
        
        firstname = next(e for e in entities if e.entity_type == "FIRSTNAME")
        assert firstname.text == "Max"
        
        birthdate = next(e for e in entities if e.entity_type == "BIRTHDATE")
        assert birthdate.text == "01.01.1960"
    
    def test_extract_address(self):
        """Test extraction of address."""
        patterns = {
            "address": PatternGroup(
                pattern=r"([A-ZÄÖÜ][a-zäöüß]+(?:straße|str\.|weg|platz|allee))\s+(\d+[a-z]?),?\s+(\d{5})\s+([A-ZÄÖÜ][a-zäöüß]+)",
                type="ADDRESS"
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = "Wohnhaft in Hauptstraße 123, 37075 Göttingen"
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 1
        assert entities[0].entity_type == "ADDRESS"
        assert "Hauptstraße" in entities[0].text
    
    def test_extract_doctor_signature_with_context(self):
        """Test extraction of doctor name with context trigger."""
        patterns = {
            "doctor_signature": PatternGroup(
                context_trigger="Mit freundlichen Grüßen",
                pattern=r"(Prof\.|Dr\.|PD)\s+(med\.\s+)?([A-ZÄÖÜ][a-zäöüß-]+(?:\s+[A-ZÄÖÜ][a-zäöüß-]+)+)",
                type="DOCTOR_NAME",
                lookahead=200
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = """
        Vielen Dank für Ihre Überweisung.
        
        Mit freundlichen Grüßen
        
        Prof. Dr. med. Karl Müller
        """
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 1
        assert entities[0].entity_type == "DOCTOR_NAME"
        assert "Karl Müller" in entities[0].text
        assert entities[0].context == "Mit freundlichen Grüßen"
    
    def test_no_extraction_without_context(self):
        """Test that extraction doesn't happen without proper context."""
        patterns = {
            "doctor_signature": PatternGroup(
                context_trigger="Mit freundlichen Grüßen",
                pattern=r"Prof\.\s+Dr\.\s+med\.\s+([A-ZÄÖÜ][a-zäöüß-]+)",
                type="DOCTOR_NAME",
                lookahead=100
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        # Text without the context trigger
        text = "Prof. Dr. med. Müller ist der Chefarzt."
        entities = extractor.extract_pii(text)
        
        # Should not extract because context trigger is missing
        assert len(entities) == 0
    
    def test_multiple_patterns(self):
        """Test extraction with multiple different patterns."""
        patterns = {
            "case_id": PatternGroup(
                pattern=r"Pat\.-Nr\.\s*([0-9]{6,10})",
                type="CASE_ID"
            ),
            "birthdate": PatternGroup(
                pattern=r"\*(\d{2}\.\d{2}\.\d{4})",
                type="BIRTHDATE"
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = "Patient Pat.-Nr. 987654321, geboren *15.05.1975"
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 2
        
        case_id = next(e for e in entities if e.entity_type == "CASE_ID")
        assert case_id.text == "987654321"
        
        birthdate = next(e for e in entities if e.entity_type == "BIRTHDATE")
        assert birthdate.text == "15.05.1975"
    
    def test_german_umlauts(self):
        """Test that German umlauts are properly handled."""
        patterns = {
            "patient_block": PatternGroup(
                pattern=r"(Herr|Frau)\s+([A-ZÄÖÜ][a-zäöüß-]+)",
                groups={
                    "1": "SALUTATION",
                    "2": "NAME"
                }
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = "Frau Müßiggang"
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 2
        name = next(e for e in entities if e.entity_type == "NAME")
        assert name.text == "Müßiggang"
    
    def test_extract_postal_code_with_city(self):
        """Test extraction of postal code with city name."""
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
        
        text = "Wohnhaft in 37075 Göttingen"
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 2
        
        postal_code = next(e for e in entities if e.entity_type == "POSTAL_CODE")
        assert postal_code.text == "37075"
        
        city = next(e for e in entities if e.entity_type == "CITY")
        assert city.text == "Göttingen"
    
    def test_extract_postal_code_standalone(self):
        """Test extraction of standalone postal code."""
        patterns = {
            "postal_code_standalone": PatternGroup(
                pattern=r"(?:PLZ:?\s*)?(\d{5})(?!\d)",
                type="POSTAL_CODE"
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = "PLZ: 20246"
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 1
        assert entities[0].entity_type == "POSTAL_CODE"
        assert entities[0].text == "20246"
    
    def test_extract_multiple_postal_codes(self):
        """Test extraction of multiple postal codes in text."""
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
        
        text = "Patient von 37075 Göttingen nach 20246 Hamburg verlegt"
        entities = extractor.extract_pii(text)
        
        # Should find 2 postal codes and 2 cities
        assert len(entities) == 4
        
        postal_codes = [e for e in entities if e.entity_type == "POSTAL_CODE"]
        assert len(postal_codes) == 2
        assert postal_codes[0].text == "37075"
        assert postal_codes[1].text == "20246"
        
        cities = [e for e in entities if e.entity_type == "CITY"]
        assert len(cities) == 2
        assert cities[0].text == "Göttingen"
        assert cities[1].text == "Hamburg"
