"""Tests for false-positive prevention in phone/fax patterns.

These tests ensure that medical terms and common German words are NOT
partially or incorrectly redacted when phone/fax patterns are used.
"""

import json
import pytest
from src.pii_extractor import StructuredPIIExtractor
from src.config import PatternGroup, AnonymizationTemplate


# ---------------------------------------------------------------------------
# Shared patterns (loaded once to avoid duplication)
# ---------------------------------------------------------------------------

def _load_template_patterns():
    """Load structured patterns from the default clinical template."""
    with open("templates/german_clinical_default.json", "r", encoding="utf-8") as f:
        template_data = json.load(f)
    return AnonymizationTemplate(**template_data).structured_patterns


# Strict phone_landline pattern sourced from the template.  Stored as a
# module-level constant so tests can reference the canonical pattern without
# duplicating the string.
_TEMPLATE_PATTERNS = _load_template_patterns()
_PHONE_LANDLINE_PATTERN = _TEMPLATE_PATTERNS["phone_landline"].pattern
_FAX_PATTERN = _TEMPLATE_PATTERNS["fax"].pattern


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_phone_extractor():
    """Return an extractor with all patterns from the default template."""
    return StructuredPIIExtractor(_TEMPLATE_PATTERNS)


# ---------------------------------------------------------------------------
# Phone false-positive tests (medical terms that look phone-like)
# ---------------------------------------------------------------------------

class TestPhoneFalsePositives:
    """Phone patterns must not match partial words in medical text."""

    @pytest.fixture(autouse=True)
    def extractor(self):
        self._extractor = make_phone_extractor()

    def _phone_entities(self, text):
        return [e for e in self._extractor.extract_pii(text) if e.entity_type == "PHONE"]

    def test_ventrikel_not_matched(self):
        """'Ventrikel' must NOT be partially redacted."""
        assert self._phone_entities("Der linke Ventrikel zeigt normale Funktion.") == []

    def test_visuell_not_matched(self):
        """'visuell' must NOT be partially redacted."""
        assert self._phone_entities("Visuell keine Auffälligkeiten erkennbar.") == []

    def test_fistel_not_matched(self):
        """'Fistel' must NOT be partially redacted."""
        assert self._phone_entities("Es besteht eine Fistel zwischen Darm und Blase.") == []

    def test_telemetrie_not_matched(self):
        """'Telemetrie' must NOT be partially redacted."""
        assert self._phone_entities("EKG-Telemetrie wurde durchgeführt.") == []

    def test_relevant_not_matched(self):
        """'relevant' must NOT be partially redacted."""
        assert self._phone_entities("Keine klinisch relevanten Befunde.") == []

    def test_spiegel_not_matched(self):
        """'Spiegel' must NOT be partially redacted."""
        assert self._phone_entities("Blutzuckerspiegel im Normbereich.") == []

    def test_mittels_not_matched(self):
        """'mittels' must NOT be partially redacted."""
        assert self._phone_entities("Diagnose erfolgte mittels CT-Untersuchung.") == []

    def test_telefonnummer_word_not_matched(self):
        """'Telefonnummer' as a standalone word (no number) must NOT produce a match."""
        assert self._phone_entities("Bitte geben Sie Ihre Telefonnummer an.") == []

    def test_blood_pressure_not_matched(self):
        """Blood pressure value 'Mittel 120/80' must NOT be matched as a phone number."""
        assert self._phone_entities("Blutdruck: Mittel 120/80 mmHg.") == []


class TestPhoneFalsePositivesUmlauts:
    """Phone patterns must not match partial words involving German umlauts."""

    @pytest.fixture(autouse=True)
    def extractor(self):
        self._extractor = make_phone_extractor()

    def _phone_entities(self, text):
        return [e for e in self._extractor.extract_pii(text) if e.entity_type == "PHONE"]

    def test_haematologie_not_matched(self):
        """'Hämatologie' must NOT be partially redacted (umlaut word boundary)."""
        assert self._phone_entities("Konsil der Hämatologie erbeten.") == []

    def test_ueberweisung_not_matched(self):
        """'Überweisung' must NOT be partially redacted."""
        assert self._phone_entities("Die Überweisung liegt vor.") == []


# ---------------------------------------------------------------------------
# Valid phone numbers must still be detected
# ---------------------------------------------------------------------------

class TestValidPhoneNumbersStillMatched:
    """Valid phone numbers must still be matched after the pattern fix."""

    @pytest.fixture(autouse=True)
    def extractor(self):
        self._extractor = make_phone_extractor()

    def _phone_entities(self, text):
        return [e for e in self._extractor.extract_pii(text) if e.entity_type == "PHONE"]

    def test_tel_prefix(self):
        assert len(self._phone_entities("Tel.: 0561/937690")) >= 1

    def test_telefon_prefix(self):
        assert len(self._phone_entities("Telefon: 030-12345678")) >= 1

    def test_nummer_prefix(self):
        assert len(self._phone_entities("Nummer: 0173 1234567")) >= 1

    def test_international_prefix(self):
        assert len(self._phone_entities("+49 561 937690")) >= 1

    def test_national_prefix(self):
        assert len(self._phone_entities("0561/937690")) >= 1

    def test_phone_in_sentence(self):
        """Phone number embedded in a full sentence should be detected."""
        text = (
            "Bei Fragen wenden Sie sich bitte telefonisch an uns. "
            "Tel.: 0561/937690, Mo-Fr 8-17 Uhr."
        )
        assert len(self._phone_entities(text)) >= 1


# ---------------------------------------------------------------------------
# Fax false-positive tests
# ---------------------------------------------------------------------------

class TestFaxFalsePositives:
    """Fax patterns must not cause false positives in medical text."""

    @pytest.fixture(autouse=True)
    def extractor(self):
        self._extractor = make_phone_extractor()

    def _fax_entities(self, text):
        return [e for e in self._extractor.extract_pii(text) if e.entity_type == "FAX"]

    def test_random_numbers_not_fax(self):
        """Numbers without Fax: prefix must NOT be matched as fax."""
        assert self._fax_entities("0561/937691") == []

    def test_valid_fax_detected(self):
        """Valid fax with explicit prefix must be detected."""
        assert len(self._fax_entities("Fax: 0561/937691")) >= 1

    def test_telefax_detected(self):
        """Valid fax with Telefax: prefix must be detected."""
        assert len(self._fax_entities("Telefax: 030-12345679")) >= 1


# ---------------------------------------------------------------------------
# Word boundary umlaut tests via the extractor
# ---------------------------------------------------------------------------

class TestWordBoundaryUmlautsViaExtractor:
    """Word boundary checks must correctly handle German umlauts in pattern matching."""

    def test_phone_pattern_does_not_match_inside_umlaut_word(self):
        """A phone-type pattern must not match inside a word that contains umlauts."""
        patterns = {
            "phone_landline": PatternGroup(
                pattern=_PHONE_LANDLINE_PATTERN,
                type="PHONE",
            )
        }
        extractor = StructuredPIIExtractor(patterns)

        # "Hämatologie" must not trigger any match
        text = "Hämatologie der Uniklinik"
        entities = extractor.extract_pii(text)
        assert len(entities) == 0

    def test_salutation_pattern_not_triggered_by_umlaut_word(self):
        """Salutation pattern must not match inside a compound word with umlauts."""
        patterns = {
            "salutation_with_name": PatternGroup(
                pattern=r"(?:Herr|Frau)\s+(?!(?:Kollege|Kollegin)\b)([A-ZÄÖÜ][a-zäöüß-]{2,})",
                type="PERSON_NAME",
            )
        }
        extractor = StructuredPIIExtractor(patterns)

        # "Herrschaft" must not match (would extract "schaft" after "Herr")
        text = "Die Herrschaft des Patienten über eigene Daten"
        entities = extractor.extract_pii(text)
        assert len(entities) == 0


# ---------------------------------------------------------------------------
# Pattern deactivation tests
# ---------------------------------------------------------------------------

class TestPatternDeactivation:
    """Disabled patterns (active_patterns=False) must not produce any entities."""

    def test_disabled_phone_pattern_not_applied(self):
        """phone_landline set to False must not extract any phone entities."""
        patterns = {
            "phone_landline": PatternGroup(
                pattern=_PHONE_LANDLINE_PATTERN,
                type="PHONE",
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        text = "Tel.: 0561/937690"

        # Enabled
        entities = extractor.extract_pii(text, active_patterns={"phone_landline": True})
        assert len(entities) == 1

        # Disabled
        entities = extractor.extract_pii(text, active_patterns={"phone_landline": False})
        assert len(entities) == 0

    def test_disabled_fax_pattern_not_applied(self):
        """fax set to False must not extract any fax entities."""
        patterns = {
            "fax": PatternGroup(
                pattern=_FAX_PATTERN,
                type="FAX",
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        text = "Fax: 0561/937691"

        assert len(extractor.extract_pii(text, active_patterns={"fax": True})) == 1
        assert len(extractor.extract_pii(text, active_patterns={"fax": False})) == 0

    def test_default_enabled_when_active_patterns_is_none(self):
        """Patterns must default to enabled when active_patterns is None."""
        patterns = {
            "phone_landline": PatternGroup(
                pattern=_PHONE_LANDLINE_PATTERN,
                type="PHONE",
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        text = "Tel.: 0561/937690"

        assert len(extractor.extract_pii(text, active_patterns=None)) == 1
        assert len(extractor.extract_pii(text, active_patterns={})) == 1


# ---------------------------------------------------------------------------
# Template version test
# ---------------------------------------------------------------------------

class TestTemplateVersion:
    """Template version should reflect the bug-fix release."""

    def test_template_version_is_2_2_0(self):
        """Template version must be bumped to 2.2.0 after the fix."""
        with open("templates/german_clinical_default.json", "r", encoding="utf-8") as f:
            template_data = json.load(f)
        assert template_data["version"] == "2.2.0"
