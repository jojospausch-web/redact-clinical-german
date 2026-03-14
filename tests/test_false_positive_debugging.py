"""Tests to reproduce and debug false-positive redactions in German clinical text.

These tests assert that known medical terms are NOT (partially) redacted
by any of the configured patterns.  When a test fails the debug-level log
output (enable with ``logging.basicConfig(level=logging.DEBUG)``) will show
the exact pattern and position responsible.
"""

import json
import logging
import pytest
from src.pii_extractor import StructuredPIIExtractor
from src.config import AnonymizationTemplate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_extractor() -> StructuredPIIExtractor:
    """Load extractor with all patterns from the default clinical template."""
    with open("templates/german_clinical_default.json", "r", encoding="utf-8") as f:
        template_data = json.load(f)
    template = AnonymizationTemplate(**template_data)
    return StructuredPIIExtractor(template.structured_patterns)


def _redacted_texts(extractor: StructuredPIIExtractor, text: str) -> list[str]:
    """Return list of entity texts extracted from *text*."""
    return [e.text for e in extractor.extract_pii(text)]


# ---------------------------------------------------------------------------
# Individual false-positive tests
# ---------------------------------------------------------------------------

class TestFalsePositiveDebugging:
    """Each known false-positive has its own test method for clear failure messages."""

    @pytest.fixture(autouse=True)
    def extractor(self):
        self._extractor = _load_extractor()

    # ── Ventrikel ────────────────────────────────────────────────────────────

    def test_ventrikel_not_partially_redacted(self):
        """'Ventrikel' must not be partially redacted (e.g. 'kel' removed)."""
        text = "Linker Ventrikel: Normale systolische LV-Funktion (LV-EF visuell 60 %)."
        matched = _redacted_texts(self._extractor, text)
        for forbidden in ("kel", "Ventrikel"):
            assert forbidden not in matched, (
                f"False positive: '{forbidden}' was matched in: {text}\n"
                f"All matches: {matched}"
            )

    # ── visuell ──────────────────────────────────────────────────────────────

    def test_visuell_not_partially_redacted(self):
        """'visuell' must not be partially redacted (e.g. 'uell' removed)."""
        text = "LV-EF visuell 60 %"
        matched = _redacted_texts(self._extractor, text)
        for forbidden in ("uell", "visuell"):
            assert forbidden not in matched, (
                f"False positive: '{forbidden}' was matched in: {text}\n"
                f"All matches: {matched}"
            )

    # ── Fistel ───────────────────────────────────────────────────────────────

    def test_fistel_not_partially_redacted(self):
        """'Fistel' must not be partially redacted (e.g. 'tel' removed)."""
        text = "AV-Fistel oder Aneurysma"
        matched = _redacted_texts(self._extractor, text)
        for forbidden in ("tel", "Fistel"):
            assert forbidden not in matched, (
                f"False positive: '{forbidden}' was matched in: {text}\n"
                f"All matches: {matched}"
            )

    # ── Telemetrie ───────────────────────────────────────────────────────────

    def test_telemetrie_not_partially_redacted(self):
        """'Telemetrie' must not be partially redacted (e.g. 'Tele' removed)."""
        text = "Telemetrie wurden keine relevanten Rhythmusstörungen dokumentiert."
        matched = _redacted_texts(self._extractor, text)
        for forbidden in ("Tele", "Telemetrie"):
            assert forbidden not in matched, (
                f"False positive: '{forbidden}' was matched in: {text}\n"
                f"All matches: {matched}"
            )

    # ── Spiegel ──────────────────────────────────────────────────────────────

    def test_spiegel_not_partially_redacted(self):
        """'Spiegel' must not be partially redacted (e.g. 'gel' removed)."""
        text = "LDL-Spiegel begannen wir eine Medikation"
        matched = _redacted_texts(self._extractor, text)
        for forbidden in ("gel", "Spiegel"):
            assert forbidden not in matched, (
                f"False positive: '{forbidden}' was matched in: {text}\n"
                f"All matches: {matched}"
            )

    # ── Zielwert ─────────────────────────────────────────────────────────────

    def test_zielwert_not_partially_redacted(self):
        """'Zielwert' must not be partially redacted (e.g. 'ielw' removed)."""
        text = "Zielwert <70 mg/dl bei KHK"
        matched = _redacted_texts(self._extractor, text)
        for forbidden in ("ielw", "Zielwert"):
            assert forbidden not in matched, (
                f"False positive: '{forbidden}' was matched in: {text}\n"
                f"All matches: {matched}"
            )

    # ── atemreagibel ─────────────────────────────────────────────────────────

    def test_atemreagibel_not_partially_redacted(self):
        """'atemreagibel' must not be partially redacted (e.g. 'bel' removed)."""
        text = "nicht gestaut und >50% atemreagibel. Perikard:"
        matched = _redacted_texts(self._extractor, text)
        for forbidden in ("bel", "atemreagibel", "reagibel"):
            assert forbidden not in matched, (
                f"False positive: '{forbidden}' was matched in: {text}\n"
                f"All matches: {matched}"
            )

    # ── relevanten ───────────────────────────────────────────────────────────

    def test_relevanten_not_partially_redacted(self):
        """'relevanten' must not be partially redacted (e.g. 'rele', 'vant', 'vanten' removed)."""
        text = "keine relevanten Rhythmusstörungen dokumentiert."
        matched = _redacted_texts(self._extractor, text)
        for forbidden in ("rele", "vant", "vanten", "relevanten"):
            assert forbidden not in matched, (
                f"False positive: '{forbidden}' was matched in: {text}\n"
                f"All matches: {matched}"
            )

    # ── Postinterventionell ──────────────────────────────────────────────────

    def test_postinterventionell_not_partially_redacted(self):
        """'Postinterventionell' must not be partially redacted (e.g. 'nell' removed)."""
        text = "Postinterventionell zeigte die Leistensonographie einen unauffälligen Befund."
        matched = _redacted_texts(self._extractor, text)
        for forbidden in ("nell", "interventionell", "Postinterventionell"):
            assert forbidden not in matched, (
                f"False positive: '{forbidden}' was matched in: {text}\n"
                f"All matches: {matched}"
            )

    # ── aktuellen ────────────────────────────────────────────────────────────

    def test_aktuellen_not_partially_redacted(self):
        """'aktuellen' must not be partially redacted (e.g. 'uellen' removed)."""
        text = "gemäß den aktuellen ESC-Leitlinien"
        matched = _redacted_texts(self._extractor, text)
        for forbidden in ("uellen", "aktuellen"):
            assert forbidden not in matched, (
                f"False positive: '{forbidden}' was matched in: {text}\n"
                f"All matches: {matched}"
            )


# ---------------------------------------------------------------------------
# Comprehensive test with the full clinical note excerpt
# ---------------------------------------------------------------------------

class TestFullClinicalNoteExcerpt:
    """Run the complete clinical note excerpt and assert no spurious matches."""

    FULL_TEXT = (
        "Linker Ventrikel: Normale systolische LV-Funktion (LV-EF visuell 60 %). "
        "2.97 m/s Rechter Ventrikel: RV > LV. Metrisch jedoch nur leichtgradig dilatiert. "
        "Leichtgradig eingeschränkte RV-Funktion (TAPSE 15 mm). "
        "Rechter Vorhof: sysPAP 38 mmHg. "
        "Aortenklappe: Biologischer Aortenklappenersatz in situ "
        "mit AV Vmax 2,05 m/s, AV PGmean 9 mmHg ohne Inuffizienz. "
        "Vena cava inferior: Vena cava inferior nicht gestaut und >50% atemreagibel. "
        "Perikard: Kein Perikarderguss. "
        "Über den Zugängen der Leiste kein Hinweis auf AV-Fistel oder Aneurysma. "
        "Der transfemorale kathetergestützte Aortenklappenersatz konnte komplikationslos durchgeführt "
        "werden. Postinterventionell zeigte die Leistensonographie einen unauffälligen Befund, die "
        "Echokardiographie präsentierte die Aortenklappenbioprothese in situ und mit guter Funktion. "
        "Im EKG und in der Telemetrie wurden keine relevanten Rhythmusstörungen dokumentiert. "
        "Bei erhöhtem LDL-Spiegel begannen wir eine Medikation mittels Rosuvastatin und Ezetimib "
        "und bitten im ambulanten Verlauf um Kontrolle des LDL-Spiegels (Zielwert <70 mg/dl bei KHK). "
        "Endokarditis-Prophylaxe gemäß den aktuellen ESC-Leitlinien"
    )

    # Terms that must NOT appear in the extracted entities under any circumstances.
    FORBIDDEN = [
        "kel", "Ventrikel",
        "uell", "visuell",
        "bel", "atemreagibel", "reagibel",
        "tel", "Fistel",
        "nell", "interventionell", "Postinterventionell",
        "Tele", "Telemetrie",
        "vant", "vanten", "relevanten",        "gel", "Spiegel",
        "ielw", "Zielwert",
        "uellen", "aktuellen",
        "mit",   # partial match of "mittels" (substring "mit" must not be extracted from "mittels")
    ]

    @pytest.fixture(autouse=True)
    def extractor(self):
        self._extractor = _load_extractor()

    def test_no_false_positives_in_full_excerpt(self):
        """None of the known false-positive fragments must appear in extracted entities."""
        matched = _redacted_texts(self._extractor, self.FULL_TEXT)
        failures = [f for f in self.FORBIDDEN if f in matched]
        assert not failures, (
            f"False positives detected: {failures}\n"
            f"All extracted entities: {matched}"
        )



# ---------------------------------------------------------------------------
# New tests for PR #22 regex tightening fixes
# ---------------------------------------------------------------------------

class TestPostalCodeLookbehindFix:
    """Postal-code patterns must not match 5-digit sequences that appear inside
    phone numbers (preceded by '/' or another digit)."""

    @pytest.fixture(autouse=True)
    def extractor(self):
        self._extractor = _load_extractor()

    def test_postal_code_not_extracted_after_slash(self):
        """5 digits after '/' in a phone number must NOT be matched as postal code."""
        text = "Tel: 0561/93769 Kassel"
        matched = _redacted_texts(self._extractor, text)
        assert "93769" not in matched, (
            f"False positive: '93769' after '/' extracted as postal code.\n"
            f"All matches: {matched}"
        )

    def test_real_postal_code_still_extracted(self):
        """A genuine standalone postal code+city must still be extracted."""
        text = "37075 Göttingen"
        matched = _redacted_texts(self._extractor, text)
        assert "37075" in matched or "Göttingen" in matched, (
            f"True positive missed: expected postal code or city in '{text}'.\n"
            f"All matches: {matched}"
        )

    def test_postal_code_in_address_still_extracted(self):
        """Postal code inside an address block must still be extracted."""
        text = "Meierweg 123, 34117 Kassel"
        matched = _redacted_texts(self._extractor, text)
        assert "34117" in matched or "Kassel" in matched, (
            f"True positive missed: postal code/city in address not found.\n"
            f"All matches: {matched}"
        )

    def test_phone_digits_not_postal_code(self):
        """Digits inside a multi-segment phone number must not leak as postal code."""
        # "0561/937690" contains "93769" as a 5-digit substring after the slash.
        # With (?<![/\d]) lookbehind, "93769" preceded by "/" must not match.
        text = "Rückfragen unter 0561/937690."
        matched = _redacted_texts(self._extractor, text)
        assert "93769" not in matched, (
            f"False positive: phone digit segment extracted as postal code.\n"
            f"All matches: {matched}"
        )


class TestDoctorNameTighteningFix:
    """Doctor-name pattern must handle combined titles and stop at lowercase words."""

    @pytest.fixture(autouse=True)
    def extractor(self):
        self._extractor = _load_extractor()

    def test_pd_dr_combined_title_matched(self):
        """'PD Dr. Jensen' must be matched as a single DOCTOR_NAME entity."""
        from src.pii_extractor import StructuredPIIExtractor
        text = "PD Dr. Jensen übernahm die weitere kardiologische Betreuung."
        entities = self._extractor.extract_pii(text)
        doctor_names = [e.text for e in entities if e.entity_type == "DOCTOR_NAME"]
        assert any("Jensen" in n for n in doctor_names), (
            f"True positive missed: 'PD Dr. Jensen' not found as DOCTOR_NAME.\n"
            f"DOCTOR_NAME entities: {doctor_names}"
        )

    def test_doctor_name_stops_before_lowercase_continuation(self):
        """Doctor name must not consume lowercase words that follow it."""
        text = "Dr. Jensen übernahm die weitere kardiologische Betreuung."
        entities = self._extractor.extract_pii(text)
        doctor_names = [e.text for e in entities if e.entity_type == "DOCTOR_NAME"]
        # Must not match the whole sentence fragment beyond the name
        for name in doctor_names:
            assert "übernahm" not in name, (
                f"Over-match: 'übernahm' included in DOCTOR_NAME '{name}'."
            )
            assert "kardiologische" not in name, (
                f"Over-match: 'kardiologische' included in DOCTOR_NAME '{name}'."
            )

    def test_prof_dr_med_matched(self):
        """'Prof. Dr. med. Müller' must be matched."""
        text = "Prof. Dr. med. Müller wurde als Konsiliarius hinzugezogen."
        entities = self._extractor.extract_pii(text)
        doctor_names = [e.text for e in entities if e.entity_type == "DOCTOR_NAME"]
        assert any("Müller" in n for n in doctor_names), (
            f"True positive missed: 'Prof. Dr. med. Müller' not found.\n"
            f"DOCTOR_NAME entities: {doctor_names}"
        )

    def test_doctor_name_max_three_parts(self):
        """Doctor name should capture at most 3 name parts after the title."""
        # 4-word sequence after title - pattern should stop at max 3 parts.
        # Combined title 'Dr.' = 1 token; up to 3 name tokens → ≤4 tokens total.
        text = "Dr. Max Ernst Schulze Braun wurde informiert."
        entities = self._extractor.extract_pii(text)
        doctor_names = [e.text for e in entities if e.entity_type == "DOCTOR_NAME"]
        for name in doctor_names:
            words = name.split()
            # title (1 token: 'Dr.') + up to 3 name parts = max 4 tokens
            assert len(words) <= 4, (
                f"Over-match: doctor name '{name}' has {len(words)} tokens (expected ≤4)."
            )


class TestMedicalFacilityPrepositionFix:
    """medical_facility pattern must not capture prepositions/articles as the city name."""

    @pytest.fixture(autouse=True)
    def extractor(self):
        self._extractor = _load_extractor()

    def test_preposition_not_matched_as_city(self):
        """'Herzzentrum für Kardiologie' must not yield 'für' as the city."""
        text = "Herzzentrum für Kardiologie"
        entities = self._extractor.extract_pii(text)
        city_texts = [e.text for e in entities if e.entity_type in ("CITY", "FACILITY_TYPE")]
        assert "für" not in city_texts, (
            f"False positive: 'für' matched as city in '{text}'.\n"
            f"All entities: {[(e.text, e.entity_type) for e in entities]}"
        )

    def test_preposition_in_not_matched_as_city(self):
        """'Rehaklinik in Kassel' must not yield 'in' as the city (only 'Kassel')."""
        text = "Rehaklinik in Kassel"
        entities = self._extractor.extract_pii(text)
        city_texts = [e.text for e in entities]
        assert "in" not in city_texts, (
            f"False positive: 'in' matched as city in '{text}'.\n"
            f"All entities: {[(e.text, e.entity_type) for e in entities]}"
        )

    def test_real_city_after_facility_still_matched(self):
        """'Ambulantes Herzzentrum Kassel' must still yield Kassel as city."""
        text = "Ambulantes Herzzentrum Kassel"
        entities = self._extractor.extract_pii(text)
        texts = [e.text for e in entities]
        assert "Kassel" in texts or "Herzzentrum" in texts, (
            f"True positive missed: facility+city not found.\n"
            f"All entities: {[(e.text, e.entity_type) for e in entities]}"
        )

    def test_facility_bad_city_matched(self):
        """'Herzzentrum Bad Nauheim' (compound city) must still be recognised."""
        text = "Herzzentrum Bad Nauheim"
        entities = self._extractor.extract_pii(text)
        texts = [e.text for e in entities]
        assert "Bad Nauheim" in texts or "Herzzentrum" in texts, (
            f"True positive missed: 'Herzzentrum Bad Nauheim' not found.\n"
            f"All entities: {[(e.text, e.entity_type) for e in entities]}"
        )


class TestPhoneWordBoundaryFix:
    """Phone and fax patterns must not match inside longer digit sequences
    or produce partial matches in lab-row number strings."""

    @pytest.fixture(autouse=True)
    def extractor(self):
        self._extractor = _load_extractor()

    def test_lab_reference_range_not_phone(self):
        """Lab reference ranges like '135-145' must not be matched as phones."""
        text = "Natrium 138 mmol/L (135-145) Kalium 4.2 mmol/L (3.5-5.0)"
        entities = self._extractor.extract_pii(text)
        phones = [e for e in entities if e.entity_type in ("PHONE", "PHONE_MOBILE", "FAX")]
        assert len(phones) == 0, (
            f"False positive: lab reference range matched as phone: "
            f"{[(e.text, e.entity_type) for e in phones]}"
        )

    def test_measurement_values_not_phone(self):
        """Measurement values with slashes (e.g. '4/6') must not match as phones."""
        text = "CRP 4.5 mg/L Leukozyten 7200 /µL Thrombozyten 180000 /µL"
        entities = self._extractor.extract_pii(text)
        phones = [e for e in entities if e.entity_type in ("PHONE", "PHONE_MOBILE", "FAX")]
        assert len(phones) == 0, (
            f"False positive: measurement matched as phone: "
            f"{[(e.text, e.entity_type) for e in phones]}"
        )

    def test_real_phone_with_prefix_still_matched(self):
        """An explicit 'Tel.: XXXX' phone number must still be extracted."""
        text = "Rückfragen: Tel.: 0561/9376-0"
        entities = self._extractor.extract_pii(text)
        phones = [e for e in entities if e.entity_type in ("PHONE", "PHONE_MOBILE")]
        assert len(phones) >= 1, (
            f"True positive missed: phone number not found in '{text}'.\n"
            f"All entities: {[(e.text, e.entity_type) for e in entities]}"
        )

    def test_fax_with_explicit_prefix_matched(self):
        """A 'Fax: XXXX' number must still be extracted."""
        text = "Fax: 0561/9376-99"
        entities = self._extractor.extract_pii(text)
        faxes = [e for e in entities if e.entity_type == "FAX"]
        assert len(faxes) >= 1, (
            f"True positive missed: fax number not found in '{text}'.\n"
            f"All entities: {[(e.text, e.entity_type) for e in entities]}"
        )


# ---------------------------------------------------------------------------
# Standalone execution for quick manual debugging
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    extractor = _load_extractor()

    test_cases = [
        ("Linker Ventrikel: Normale systolische LV-Funktion (LV-EF visuell 60 %).", ["kel", "Ventrikel"]),
        ("LV-EF visuell 60 %", ["uell", "visuell"]),
        ("AV-Fistel oder Aneurysma", ["tel", "Fistel"]),
        ("Telemetrie wurden keine relevanten Rhythmusstörungen dokumentiert.", ["Tele", "Telemetrie"]),
        ("LDL-Spiegel begannen", ["gel", "Spiegel"]),
        ("Zielwert <70 mg/dl", ["ielw", "Zielwert"]),
        ("atemreagibel. Perikard:", ["bel", "reagibel"]),
        ("keine relevanten Rhythmusstörungen", ["rele", "relevanten"]),
        ("Postinterventionell zeigte", ["nell", "interventionell"]),
        ("gemäß den aktuellen ESC-Leitlinien", ["uellen", "aktuellen"]),
    ]

    failures = []
    for text, forbidden_matches in test_cases:
        entities = extractor.extract_pii(text)
        for entity in entities:
            if entity.text in forbidden_matches:
                failures.append(
                    {
                        "text": text,
                        "matched": entity.text,
                        "type": entity.entity_type,
                        "position": f"{entity.start_pos}-{entity.end_pos}",
                    }
                )

    print("\n" + "=" * 80)
    if failures:
        print("FALSE POSITIVES DETECTED:")
        print("=" * 80)
        for failure in failures:
            print(f"\nText: {failure['text']}")
            print(f"  Matched: '{failure['matched']}' as {failure['type']}")
            print(f"  Position: {failure['position']}")
        raise SystemExit(1)
    else:
        print("✅ All false-positive tests passed!")
