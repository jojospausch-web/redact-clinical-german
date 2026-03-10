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
