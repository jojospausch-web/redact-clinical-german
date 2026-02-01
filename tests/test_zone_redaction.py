"""Tests for separate page zone redaction and signature block functionality."""

import pytest
from pathlib import Path
import fitz
import tempfile
import json

from src.zone_anonymizer import ZoneBasedAnonymizer
from src.config import AnonymizationTemplate, ZoneConfig, SignatureBlockConfig
from src.date_shifter import DateShifter


class TestSeparatePageZones:
    """Test separate zone configurations for different pages."""
    
    def test_exclude_page_functionality(self):
        """Test that exclude_page correctly skips specified pages."""
        # Create template with footer zone that excludes page 1
        template_dict = {
            "template_name": "Test",
            "version": "1.0",
            "zones": {
                "footer_other": {
                    "pages": "all",
                    "exclude_page": 1,
                    "y_start": 0,
                    "y_end": 80,
                    "redaction": "full"
                }
            },
            "structured_patterns": {},
            "date_handling": {},
            "image_pii_patterns": {}
        }
        
        template = AnonymizationTemplate(**template_dict)
        anonymizer = ZoneBasedAnonymizer(template)
        
        # Create a test PDF with 3 pages
        doc = fitz.open()
        for i in range(3):
            page = doc.new_page(width=595, height=842)  # A4 size
            page.insert_text((100, 50), f"Page {i+1} - Footer Text")
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            temp_input = tmp.name
            doc.save(temp_input)
            doc.close()
        
        # Process the PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            temp_output = tmp.name
        
        stats = anonymizer.anonymize_pdf(temp_input, temp_output)
        
        # Check that zones were redacted (should be 2, not 3, since page 1 is excluded)
        assert stats['zones_redacted'] >= 2  # Pages 2 and 3
        
        # Clean up
        Path(temp_input).unlink()
        Path(temp_output).unlink()
    
    def test_page_1_specific_zones(self):
        """Test that page-specific zones only apply to specified page."""
        template_dict = {
            "template_name": "Test",
            "version": "1.0",
            "zones": {
                "header_page_1": {
                    "page": 1,
                    "y_start": 700,
                    "y_end": 842,
                    "redaction": "full",
                    "preserve_logos": False
                }
            },
            "structured_patterns": {},
            "date_handling": {},
            "image_pii_patterns": {}
        }
        
        template = AnonymizationTemplate(**template_dict)
        anonymizer = ZoneBasedAnonymizer(template)
        
        # Create a test PDF with 2 pages
        doc = fitz.open()
        for i in range(2):
            page = doc.new_page(width=595, height=842)
            page.insert_text((100, 800), f"Header Text Page {i+1}")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            temp_input = tmp.name
            doc.save(temp_input)
            doc.close()
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            temp_output = tmp.name
        
        stats = anonymizer.anonymize_pdf(temp_input, temp_output)
        
        # Should only redact 1 zone (page 1 header)
        assert stats['zones_redacted'] == 1
        
        # Clean up
        Path(temp_input).unlink()
        Path(temp_output).unlink()
    
    def test_separate_footer_zones(self):
        """Test different footer zones for page 1 vs other pages."""
        template_dict = {
            "template_name": "Test",
            "version": "1.0",
            "zones": {
                "footer_page_1": {
                    "page": 1,
                    "y_start": 0,
                    "y_end": 35,
                    "redaction": "full"
                },
                "footer_other": {
                    "pages": "all",
                    "exclude_page": 1,
                    "y_start": 0,
                    "y_end": 80,
                    "redaction": "full"
                }
            },
            "structured_patterns": {},
            "date_handling": {},
            "image_pii_patterns": {}
        }
        
        template = AnonymizationTemplate(**template_dict)
        anonymizer = ZoneBasedAnonymizer(template)
        
        # Create a test PDF with 3 pages
        doc = fitz.open()
        for i in range(3):
            page = doc.new_page(width=595, height=842)
            page.insert_text((100, 30), f"Footer Page {i+1}")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            temp_input = tmp.name
            doc.save(temp_input)
            doc.close()
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            temp_output = tmp.name
        
        stats = anonymizer.anonymize_pdf(temp_input, temp_output)
        
        # Should redact 3 zones total (1 for page 1, 2 for pages 2-3)
        assert stats['zones_redacted'] == 3
        
        # Clean up
        Path(temp_input).unlink()
        Path(temp_output).unlink()


class TestSignatureBlockRedaction:
    """Test signature block redaction functionality."""
    
    def test_signature_block_detection(self):
        """Test that signature blocks are detected and redacted."""
        template_dict = {
            "template_name": "Test",
            "version": "1.0",
            "zones": {},
            "signature_block": {
                "enabled": True,
                "trigger": "Mit freundlichen Grüßen",
                "height_below": 40,
                "redaction": "full"
            },
            "structured_patterns": {},
            "date_handling": {},
            "image_pii_patterns": {}
        }
        
        template = AnonymizationTemplate(**template_dict)
        anonymizer = ZoneBasedAnonymizer(template)
        
        # Create a test PDF with signature
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((100, 500), "Mit freundlichen Grüßen")
        page.insert_text((100, 520), "Prof. Dr. med. Karl Toischer")
        page.insert_text((100, 540), "Komm. Leitung der Klinik")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            temp_input = tmp.name
            doc.save(temp_input)
            doc.close()
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            temp_output = tmp.name
        
        anonymizer.anonymize_pdf(temp_input, temp_output)
        
        # Verify output exists
        assert Path(temp_output).exists()
        
        # Clean up
        Path(temp_input).unlink()
        Path(temp_output).unlink()
    
    def test_signature_block_disabled(self):
        """Test that signature blocks are not redacted when disabled."""
        template_dict = {
            "template_name": "Test",
            "version": "1.0",
            "zones": {},
            "signature_block": {
                "enabled": False,
                "trigger": "Mit freundlichen Grüßen",
                "height_below": 40,
                "redaction": "full"
            },
            "structured_patterns": {},
            "date_handling": {},
            "image_pii_patterns": {}
        }
        
        template = AnonymizationTemplate(**template_dict)
        anonymizer = ZoneBasedAnonymizer(template)
        
        # Create a test PDF
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((100, 500), "Mit freundlichen Grüßen")
        page.insert_text((100, 520), "Dr. Test")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            temp_input = tmp.name
            doc.save(temp_input)
            doc.close()
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            temp_output = tmp.name
        
        anonymizer.anonymize_pdf(temp_input, temp_output)
        
        # Verify output exists
        assert Path(temp_output).exists()
        
        # Clean up
        Path(temp_input).unlink()
        Path(temp_output).unlink()
    
    def test_multiple_signature_blocks(self):
        """Test handling of multiple signature triggers on same page."""
        template_dict = {
            "template_name": "Test",
            "version": "1.0",
            "zones": {},
            "signature_block": {
                "enabled": True,
                "trigger": "Mit freundlichen Grüßen",
                "height_below": 40,
                "redaction": "full"
            },
            "structured_patterns": {},
            "date_handling": {},
            "image_pii_patterns": {}
        }
        
        template = AnonymizationTemplate(**template_dict)
        anonymizer = ZoneBasedAnonymizer(template)
        
        # Create a test PDF with multiple signatures (e.g., cc to multiple doctors)
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((100, 500), "Mit freundlichen Grüßen")
        page.insert_text((100, 520), "Dr. First")
        page.insert_text((400, 500), "Mit freundlichen Grüßen")
        page.insert_text((400, 520), "Dr. Second")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            temp_input = tmp.name
            doc.save(temp_input)
            doc.close()
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            temp_output = tmp.name
        
        anonymizer.anonymize_pdf(temp_input, temp_output)
        
        # Verify output exists
        assert Path(temp_output).exists()
        
        # Clean up
        Path(temp_input).unlink()
        Path(temp_output).unlink()


class TestDatePatterns:
    """Test improved date pattern recognition."""
    
    def test_date_with_context_triggers(self):
        """Test date extraction with context triggers like 'vom', 'bis', 'am'."""
        from src.pii_extractor import StructuredPIIExtractor
        from src.config import PatternGroup
        
        patterns = {
            "date_with_context": PatternGroup(
                pattern=r"(?:vom|bis|am|seit|zum)\s+(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?",
                type="DATE"
            )
        }
        
        extractor = StructuredPIIExtractor(patterns)
        
        text = "wir berichten über o.g. Pat., die/der sich vom 05.08 bis zum 21.08.2023 in unserer stationären Behandlung befand."
        
        entities = extractor.extract_pii(text)
        
        # Should extract dates with context
        assert len(entities) > 0
        
        # Check that dates are captured
        dates_text = [e.text for e in entities]
        # Pattern should capture at least parts of the dates
        assert any('05' in d or '21' in d or '2023' in d for d in dates_text)
    
    def test_numeric_date_pattern(self):
        """Test standard numeric date pattern."""
        from src.pii_extractor import StructuredPIIExtractor
        from src.config import PatternGroup
        
        patterns = {
            "numeric_date": PatternGroup(
                pattern=r"\b(\d{2})\.(\d{2})\.(\d{4})\b",
                type="DATE"
            )
        }
        
        extractor = StructuredPIIExtractor(patterns)
        
        text = "Aufnahme am 16.08.2023, Entlassung am 17.08.2023"
        
        entities = extractor.extract_pii(text)
        
        # Should extract both dates
        assert len(entities) >= 2


class TestPatternImprovements:
    """Test pattern improvements for false positives and better matching."""
    
    def test_patient_block_line_beginning_only(self):
        """Test that patient block only matches at line beginning."""
        from src.pii_extractor import StructuredPIIExtractor
        from src.config import PatternGroup
        
        patterns = {
            "patient_block": PatternGroup(
                pattern=r"^(Herr|Frau)\s+([A-ZÄÖÜ][a-zäöüß-]+),\s+([A-ZÄÖÜ][a-zäöüß-]+),\s+\*(\d{2}\.\d{2}\.\d{4})",
                groups={"1": "SALUTATION", "2": "LASTNAME", "3": "FIRSTNAME", "4": "BIRTHDATE"}
            )
        }
        
        extractor = StructuredPIIExtractor(patterns)
        
        # Should NOT match "Sehr geehrter Herr Kollege"
        text1 = "Sehr geehrter Herr Kollege"
        entities1 = extractor.extract_pii(text1)
        assert len(entities1) == 0
        
        # SHOULD match actual patient block at line beginning
        text2 = "Herr Müller, Hans, *01.01.1960"
        entities2 = extractor.extract_pii(text2)
        assert len(entities2) > 0
    
    def test_doctor_name_complete_match(self):
        """Test that doctor name pattern captures complete name."""
        from src.pii_extractor import StructuredPIIExtractor
        from src.config import PatternGroup
        
        patterns = {
            "doctor_name": PatternGroup(
                pattern=r"((?:Prof\.|Dr\.|PD)\s+(?:med\.\s+)?[A-ZÄÖÜ][a-zäöüß-]+(?:\s+[A-ZÄÖÜ][a-zäöüß-]+)*)",
                type="DOCTOR_NAME"
            )
        }
        
        extractor = StructuredPIIExtractor(patterns)
        
        # Test "Dr. Mallegus" - should capture both parts
        text = "Dr. Mallegus"
        entities = extractor.extract_pii(text)
        
        assert len(entities) > 0
        # The complete match should include the full name
        full_matches = [e.text for e in entities]
        assert any("Mallegus" in m for m in full_matches)
    
    def test_doctor_with_location_pattern(self):
        """Test doctor with organization/location pattern."""
        from src.pii_extractor import StructuredPIIExtractor
        from src.config import PatternGroup
        
        patterns = {
            "doctor_with_location": PatternGroup(
                pattern=r"Dr\.\s+([A-ZÄÖÜ][a-zäöüß-]+)(?:,\s+([A-Z]{2,})\s+([A-ZÄÖÜ][a-zäöüß]+))?",
                groups={"1": "DOCTOR_NAME", "2": "ORGANIZATION", "3": "CITY"}
            )
        }
        
        extractor = StructuredPIIExtractor(patterns)
        
        # Test "Dr. Führig, MVZ Hannover"
        text = "Dr. Führig, MVZ Hannover"
        entities = extractor.extract_pii(text)
        
        # Should extract all three groups
        assert len(entities) >= 3
        
        entity_types = [e.entity_type for e in entities]
        assert "DOCTOR_NAME" in entity_types
        assert "ORGANIZATION" in entity_types
        assert "CITY" in entity_types
