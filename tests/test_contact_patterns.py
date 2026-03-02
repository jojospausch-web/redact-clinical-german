"""Tests for contact information pattern recognition."""

import pytest
from src.pii_extractor import StructuredPIIExtractor
from src.config import PatternGroup


class TestPhonePatterns:
    """Test phone number detection patterns."""

    def test_phone_landline_basic(self):
        """Test basic landline phone detection."""
        patterns = {
            "phone_landline": PatternGroup(
                pattern=r"(?:Tel\.?:|Telefon:|Nummer:?)?\s*(?:\+49\s?)?(?:\(0\))?\s*(\d{2,5})[\s\-\/](\d{3,9})(?:[\s\-](\d{2,4}))?",
                type="PHONE",
            )
        }
        extractor = StructuredPIIExtractor(patterns)

        test_cases = [
            "0561/937690",
            "Tel.: 030-12345678",
            "Telefon: 0561 937690",
            "+49 561 937690",
        ]

        for text in test_cases:
            entities = extractor.extract_pii(text)
            assert len(entities) > 0, f"Should match: {text}"
            assert entities[0].entity_type == "PHONE"

    def test_phone_context_based(self):
        """Test context-based phone detection (user's example)."""
        patterns = {
            "phone_context": PatternGroup(
                pattern=r"(?:unter|über|Nummer)\s+(?:der\s+)?(?:Nummer\s+)?(\d{3,5}(?:[\s\-\/]\d{3,9})?(?:[\s\-]\d{2,4})?)\s+(?:erreichbar|telefonisch|zu erreichen|kontaktieren)",
                type="PHONE",
            )
        }
        extractor = StructuredPIIExtractor(patterns)

        text = "unter der Nummer 0561/937690 erreichbar"
        entities = extractor.extract_pii(text)

        assert len(entities) == 1
        assert entities[0].entity_type == "PHONE"
        assert "0561/937690" in entities[0].text

    def test_phone_full_sentence(self):
        """Test phone detection in full sentence (user's scenario)."""
        patterns = {
            "phone_context": PatternGroup(
                pattern=r"(?:unter|über|Nummer)\s+(?:der\s+)?(?:Nummer\s+)?(\d{3,5}(?:[\s\-\/]\d{3,9})?(?:[\s\-]\d{2,4})?)\s+(?:erreichbar|telefonisch|zu erreichen|kontaktieren)",
                type="PHONE",
            )
        }
        extractor = StructuredPIIExtractor(patterns)

        text = (
            "Sollte der Pat. den Termin nicht wahrnehmen können, ist das "
            "Ambulante Herzzentrum Kassel unter der Nummer 0561/937690 erreichbar."
        )
        entities = extractor.extract_pii(text)

        assert len(entities) >= 1
        phone_entities = [e for e in entities if e.entity_type == "PHONE"]
        assert len(phone_entities) >= 1
        assert any("0561/937690" in e.text for e in phone_entities)

    def test_phone_mobile(self):
        """Test mobile phone detection."""
        patterns = {
            "phone_mobile": PatternGroup(
                pattern=r"(?:Mobil:|Handy:)?\s*(?:\+49\s?)?(0?1[5-7][0-9])[\s\-\/]?(\d{7,8})",
                type="PHONE_MOBILE",
            )
        }
        extractor = StructuredPIIExtractor(patterns)

        test_cases = [
            "0173/1234567",
            "+49 173 12345678",
            "Mobil: 0151-98765432",
        ]

        for text in test_cases:
            entities = extractor.extract_pii(text)
            assert len(entities) > 0, f"Should match: {text}"
            assert entities[0].entity_type == "PHONE_MOBILE"


class TestEmailPatterns:
    """Test email detection patterns."""

    def test_email_basic(self):
        """Test basic email detection."""
        patterns = {
            "email": PatternGroup(
                pattern=r"\b([a-zA-Z0-9][a-zA-Z0-9._%+-]{0,63}@[a-zA-Z0-9][a-zA-Z0-9.-]{0,253}\.[a-zA-Z]{2,})",
                type="EMAIL",
            )
        }
        extractor = StructuredPIIExtractor(patterns)

        test_cases = [
            "max.mustermann@klinikum-kassel.de",
            "info@herzzentrum-goettingen.de",
            "dr.mueller@uniklinikum.com",
            "kontakt+info@mvz-hamburg.de",
        ]

        for text in test_cases:
            entities = extractor.extract_pii(text)
            assert len(entities) == 1, f"Should match exactly once: {text}"
            assert entities[0].entity_type == "EMAIL"


class TestFaxPatterns:
    """Test fax detection patterns."""

    def test_fax_basic(self):
        """Test basic fax detection."""
        patterns = {
            "fax": PatternGroup(
                pattern=r"(?:Fax:|Telefax:|Fax-Nr\.?:?)\s*(?:\+49\s?)?(?:\(0\))?\s*(\d{2,5})[\s\-\/](\d{3,9})",
                type="FAX",
            )
        }
        extractor = StructuredPIIExtractor(patterns)

        test_cases = [
            ("Fax: 0561/937691", "FAX"),
            ("Telefax: 030-12345679", "FAX"),
        ]

        for text, expected_type in test_cases:
            entities = extractor.extract_pii(text)
            assert len(entities) > 0, f"Should match: {text}"
            assert entities[0].entity_type == expected_type
