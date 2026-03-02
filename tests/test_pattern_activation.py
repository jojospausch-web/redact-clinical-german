"""Tests for pattern activation (active_patterns) feature."""

import pytest
from src.pii_extractor import StructuredPIIExtractor
from src.config import PatternGroup


class TestPatternActivation:
    """Test cases for active_patterns filtering in StructuredPIIExtractor."""

    @pytest.fixture
    def postal_patterns(self):
        return {
            "postal_code_standalone": PatternGroup(
                pattern=r"(?:PLZ:?\s*)?(\d{5})(?!\d)",
                type="POSTAL_CODE",
            ),
            "case_id": PatternGroup(
                pattern=r"Pat\.?-?Nr\.?:?\s*([0-9]{6,10})",
                type="CASE_ID",
            ),
        }

    def test_all_patterns_active_when_none(self, postal_patterns):
        """When active_patterns is None all patterns run (backwards compat)."""
        extractor = StructuredPIIExtractor(postal_patterns)
        text = "PLZ: 10000 Pat.-Nr. 123456789"
        entities = extractor.extract_pii(text, active_patterns=None)
        types = {e.entity_type for e in entities}
        assert "POSTAL_CODE" in types
        assert "CASE_ID" in types

    def test_disabled_pattern_is_skipped(self, postal_patterns):
        """A pattern set to False in active_patterns is not applied."""
        extractor = StructuredPIIExtractor(postal_patterns)
        text = "PLZ: 10000"
        entities = extractor.extract_pii(
            text, active_patterns={"postal_code_standalone": False}
        )
        assert len(entities) == 0

    def test_missing_pattern_key_defaults_to_enabled(self, postal_patterns):
        """A pattern not listed in active_patterns defaults to enabled."""
        extractor = StructuredPIIExtractor(postal_patterns)
        text = "Pat.-Nr. 123456789"
        # case_id not in dict → should still be applied
        entities = extractor.extract_pii(
            text, active_patterns={"postal_code_standalone": False}
        )
        assert len(entities) == 1
        assert entities[0].entity_type == "CASE_ID"

    def test_empty_active_patterns_defaults_to_all_enabled(self, postal_patterns):
        """An empty dict has no overrides, so all patterns default to enabled."""
        extractor = StructuredPIIExtractor(postal_patterns)
        text = "PLZ: 10000 Pat.-Nr. 123456789"
        # empty dict → every pattern defaults to True (no key → enabled)
        entities = extractor.extract_pii(text, active_patterns={})
        types = {e.entity_type for e in entities}
        assert "POSTAL_CODE" in types
        assert "CASE_ID" in types

    def test_explicitly_false_disables_pattern(self, postal_patterns):
        """Only patterns explicitly set to False are skipped."""
        extractor = StructuredPIIExtractor(postal_patterns)
        text = "PLZ: 10000 Pat.-Nr. 123456789"
        entities = extractor.extract_pii(
            text,
            active_patterns={
                "postal_code_standalone": False,
                "case_id": False,
            },
        )
        assert len(entities) == 0

    def test_partial_activation(self, postal_patterns):
        """Only the enabled pattern produces results."""
        extractor = StructuredPIIExtractor(postal_patterns)
        text = "PLZ: 10000 Pat.-Nr. 123456789"
        entities = extractor.extract_pii(
            text,
            active_patterns={
                "postal_code_standalone": False,
                "case_id": True,
            },
        )
        assert all(e.entity_type == "CASE_ID" for e in entities)
        assert len(entities) >= 1
