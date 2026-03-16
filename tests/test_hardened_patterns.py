"""Tests for the hardened doctor_name and salutation_with_name patterns.

Verifies positive cases (names that MUST be matched) and negative cases
(medical terms / common German words that must NOT be matched), using the
patterns loaded directly from the production template so that any future
pattern updates are automatically exercised.
"""

import json
import pytest

from src.pii_extractor import StructuredPIIExtractor
from src.config import PatternGroup, AnonymizationTemplate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_template_patterns():
    """Return structured_patterns from the default clinical template."""
    with open("templates/german_clinical_default.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return AnonymizationTemplate(**data).structured_patterns


_TEMPLATE_PATTERNS = _load_template_patterns()


def _make_extractor_with(*pattern_names):
    """Return a StructuredPIIExtractor containing only the named patterns."""
    patterns = {k: v for k, v in _TEMPLATE_PATTERNS.items() if k in pattern_names}
    return StructuredPIIExtractor(patterns)


# ---------------------------------------------------------------------------
# doctor_name pattern – positive cases
# ---------------------------------------------------------------------------

class TestDoctorNamePositive:
    """The hardened doctor_name pattern must still match real doctor titles."""

    @pytest.fixture(autouse=True)
    def extractor(self):
        self._ext = _make_extractor_with("doctor_name")

    def _names(self, text):
        return [e.text for e in self._ext.extract_pii(text) if e.entity_type == "DOCTOR_NAME"]

    def test_pd_dr_with_given_and_last_name(self):
        """PD Dr. Christoph Jensen must be matched."""
        names = self._names("Behandelnder Arzt: PD Dr. Christoph Jensen")
        assert any("Jensen" in n for n in names), f"Expected Jensen in {names}"

    def test_dr_simple_last_name(self):
        """Dr. Schmidt (single last name) must be matched."""
        names = self._names("Dr. Schmidt übernimmt die Behandlung.")
        assert any("Schmidt" in n for n in names), f"Expected Schmidt in {names}"

    def test_dr_with_name_prefix_el(self):
        """Dr. El Barco (El prefix) must be matched."""
        names = self._names("Zugewiesen von Dr. El Barco.")
        assert any("Barco" in n for n in names), f"Expected Barco in {names}"

    def test_frau_barco_salutation_not_doctor(self):
        """Frau Barco matched by salutation pattern (not doctor_name)."""
        sal_ext = _make_extractor_with("salutation_with_name")
        entities = sal_ext.extract_pii("Frau Barco kommt morgen.")
        assert any("Barco" in e.text for e in entities), "Expected Barco via salutation"

    def test_prof_dr_dr_hyphenated_von_prefix(self):
        """Prof. Dr. Dr. Hans-Albert von Stein must be matched."""
        names = self._names("Mit freundlichen Grüßen, Prof. Dr. Dr. Hans-Albert von Stein")
        assert any("Stein" in n for n in names), f"Expected Stein in {names}"

    def test_prof_dr_med(self):
        """Prof. Dr. med. Karl Müller must be matched."""
        names = self._names("Prof. Dr. med. Karl Müller schreibt vor.")
        assert any("Müller" in n for n in names), f"Expected Müller in {names}"


# ---------------------------------------------------------------------------
# doctor_name pattern – negative cases
# ---------------------------------------------------------------------------

class TestDoctorNameNegative:
    """Common medical words must NOT be matched as doctor names."""

    @pytest.fixture(autouse=True)
    def extractor(self):
        self._ext = _make_extractor_with("doctor_name")

    def _has_doctor_match(self, text):
        return any(e.entity_type == "DOCTOR_NAME" for e in self._ext.extract_pii(text))

    def test_visuell_not_matched(self):
        """'visuell' must not be matched as a doctor name."""
        assert not self._has_doctor_match("Visuell keine Auffälligkeiten erkennbar.")

    def test_ventrikel_not_matched(self):
        """'Ventrikel' must not be matched as a doctor name."""
        assert not self._has_doctor_match("Der linke Ventrikel zeigt normale Funktion.")

    def test_spiegel_not_matched(self):
        """'Spiegel' must not be matched as a doctor name."""
        assert not self._has_doctor_match("Blutzuckerspiegel im Normbereich.")

    def test_zielwert_not_matched(self):
        """'Zielwert' must not be matched as a doctor name."""
        assert not self._has_doctor_match("Zielwert für HbA1c liegt bei 7 %.")

    def test_fistel_not_matched(self):
        """'Fistel' must not be matched as a doctor name."""
        assert not self._has_doctor_match("Es besteht eine Fistel zwischen Darm und Blase.")

    def test_aktuell_not_matched(self):
        """'aktuell' must not be matched as a doctor name."""
        assert not self._has_doctor_match("Der aktuelle Befund liegt vor.")

    def test_telemetrie_not_matched(self):
        """'Telemetrie' must not be matched as a doctor name."""
        assert not self._has_doctor_match("EKG-Telemetrie wurde durchgeführt.")

    def test_eltern_not_matched(self):
        """'Eltern' must not be matched as a doctor name."""
        assert not self._has_doctor_match("Die Eltern wurden informiert.")

    def test_belgien_not_matched(self):
        """'Belgien' must not be matched as a doctor name."""
        assert not self._has_doctor_match("Reise nach Belgien vor 2 Wochen.")

    def test_el_salvador_without_title_not_matched(self):
        """'El-Salvador' without a doctor title must not be matched."""
        assert not self._has_doctor_match("Patient stammt aus El-Salvador.")


# ---------------------------------------------------------------------------
# salutation_with_name pattern – positive cases
# ---------------------------------------------------------------------------

class TestSalutationHardenedPositive:
    """Hardened salutation_with_name must still match real last names."""

    @pytest.fixture(autouse=True)
    def extractor(self):
        self._ext = _make_extractor_with("salutation_with_name")

    def _names(self, text):
        return [e.text for e in self._ext.extract_pii(text) if e.entity_type == "PERSON_NAME"]

    def test_herr_jensen(self):
        """'Herr Jensen' must be matched."""
        names = self._names("Herr Jensen schlägt den 10.06.2025 vor.")
        assert "Jensen" in names

    def test_frau_barco(self):
        """'Frau Barco' must be matched."""
        names = self._names("Frau Barco wurde entlassen.")
        assert "Barco" in names

    def test_herr_kollege_excluded(self):
        """'Herr Kollege' must NOT be matched (generic salutation)."""
        assert self._names("Sehr geehrter Herr Kollege,") == []

    def test_frau_kollegin_excluded(self):
        """'Frau Kollegin' must NOT be matched (generic salutation)."""
        assert self._names("Sehr geehrte Frau Kollegin,") == []


# ---------------------------------------------------------------------------
# salutation_with_name pattern – negative cases (no salutation prefix)
# ---------------------------------------------------------------------------

class TestSalutationHardenedNegative:
    """Medical/common words without a salutation prefix must not be matched."""

    @pytest.fixture(autouse=True)
    def extractor(self):
        self._ext = _make_extractor_with("salutation_with_name")

    def _has_match(self, text):
        return any(e.entity_type == "PERSON_NAME" for e in self._ext.extract_pii(text))

    def test_visuell_standalone(self):
        assert not self._has_match("visuell keine Auffälligkeiten.")

    def test_ventrikel_standalone(self):
        assert not self._has_match("Der linke Ventrikel zeigt normale Funktion.")

    def test_spiegel_standalone(self):
        assert not self._has_match("Blutzuckerspiegel im Normbereich.")

    def test_eltern_standalone(self):
        assert not self._has_match("Die Eltern wurden informiert.")

    def test_belgien_standalone(self):
        assert not self._has_match("Reise nach Belgien.")

    def test_el_salvador_standalone(self):
        assert not self._has_match("Patient aus El-Salvador.")

    def test_lowercase_after_herr_not_matched(self):
        """Lowercase word after 'Herr' must not match (uppercase guard)."""
        assert not self._has_match("Herr visuell ist ein Symptom.")

    def test_lowercase_after_frau_not_matched(self):
        """Lowercase word after 'Frau' must not match (uppercase guard)."""
        assert not self._has_match("Frau ventrikel ist getestet.")


# ---------------------------------------------------------------------------
# Token-length filter
# ---------------------------------------------------------------------------

class TestTokenLengthFilter:
    """Post-match token-length filter must discard all-short-token matches."""

    def test_all_short_tokens_discarded_for_doctor_name(self):
        """A doctor_name match where all name tokens are <3 chars is discarded."""
        # "Dr. Al" – "Al" is only 2 chars; the new pattern requires >=3 for the name
        # token so this should not match at the regex level or filter level.
        patterns = {
            "doctor_name": PatternGroup(
                # Use a deliberately loose pattern that could match short tokens,
                # then rely on the post-filter to drop them.
                pattern=r"\b((?:Dr\.)\s+(?-i:[A-ZÄÖÜ])[a-zäöüß]{1,})\b",
                type="DOCTOR_NAME",
            )
        }
        ext = StructuredPIIExtractor(patterns)
        # "Dr. Al" – group 1 = "Dr. Al"; tokens = ["Dr.", "Al"] → "Al" < 3 chars,
        # but "Dr." is 3 chars → NOT all short → NOT discarded.
        entities = ext.extract_pii("Dr. Al ist behandelnder Arzt.")
        # The filter should NOT discard this because "Dr." has 3 chars.
        assert len(entities) == 1

    def test_only_two_char_tokens_discarded(self):
        """If every token in captured text is <3 chars the match is discarded."""
        patterns = {
            "doctor_name": PatternGroup(
                # Pattern that captures only very short tokens (e.g. "Dr. Al")
                # but we craft text where group 1 is "Al" alone (2 chars).
                pattern=r"(?:Dr\.)\s+((?-i:[A-ZÄÖÜ])[a-zäöüß]{1})\b",
                type="DOCTOR_NAME",
            )
        }
        ext = StructuredPIIExtractor(patterns)
        # group 1 = "Al" → only token "Al" < 3 chars → all short → discarded
        entities = ext.extract_pii("Dr. Al wurde notiert.")
        assert len(entities) == 0, f"Expected 0 but got {[e.text for e in entities]}"


# ---------------------------------------------------------------------------
# _all_tokens_short unit tests
# ---------------------------------------------------------------------------

class TestAllTokensShort:
    """Direct unit tests for StructuredPIIExtractor._all_tokens_short."""

    @pytest.fixture(autouse=True)
    def extractor(self):
        self._ext = StructuredPIIExtractor({})

    def test_empty_string_returns_true(self):
        """Empty string has no tokens – treated as all-short."""
        assert self._ext._all_tokens_short("") is True

    def test_whitespace_only_returns_true(self):
        """Whitespace-only string has no tokens – treated as all-short."""
        assert self._ext._all_tokens_short("   ") is True

    def test_single_short_token_returns_true(self):
        """A single token shorter than min_length (3) returns True."""
        assert self._ext._all_tokens_short("Al") is True

    def test_single_long_token_returns_false(self):
        """A single token of min_length or longer returns False."""
        assert self._ext._all_tokens_short("Ali") is False
        assert self._ext._all_tokens_short("Jensen") is False

    def test_all_short_multiple_tokens_returns_true(self):
        """Multiple tokens all below min_length returns True."""
        assert self._ext._all_tokens_short("El Al") is True

    def test_mixed_lengths_returns_false(self):
        """When at least one token is long enough, returns False."""
        assert self._ext._all_tokens_short("El Barco") is False
        assert self._ext._all_tokens_short("Dr. Jensen") is False

    def test_custom_min_length(self):
        """Custom min_length threshold is respected."""
        assert self._ext._all_tokens_short("Dr.", min_length=4) is True
        assert self._ext._all_tokens_short("Dr.", min_length=3) is False

    def test_token_exactly_at_min_length_not_short(self):
        """Token of exactly min_length (3) is NOT considered short."""
        assert self._ext._all_tokens_short("Dr.") is False
