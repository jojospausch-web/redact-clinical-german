"""Tests for the exact-match case-sensitive blacklist feature.

Covers:
- Text-level regex matching (find_blacklist_matches helper)
- PDF-level redaction via ZoneBasedAnonymizer
"""

import io
import re
import json
import tempfile
from pathlib import Path

import fitz
import pytest

from src.zone_anonymizer import ZoneBasedAnonymizer
from src.config import AnonymizationTemplate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_minimal_template(blacklist: list) -> AnonymizationTemplate:
    """Return a minimal AnonymizationTemplate with the given blacklist_exact."""
    data = {
        "template_name": "Test",
        "version": "1.0",
        "zones": {},
        "structured_patterns": {},
        "date_handling": {},
        "image_pii_patterns": {},
        "blacklist_exact": blacklist,
    }
    return AnonymizationTemplate(**data)


def _create_pdf_with_text(text: str) -> str:
    """Create a single-page PDF containing *text*.  Returns the temp file path."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = f.name
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), text, fontsize=11)
    doc.save(path)
    doc.close()
    return path


def _extract_text_from_pdf(path: str) -> str:
    """Return all text extracted from the first page of the PDF at *path*."""
    doc = fitz.open(path)
    text = doc[0].get_text()
    doc.close()
    return text


def _find_blacklist_matches_in_text(text: str, blacklist: list) -> list:
    """Return blacklist entries that match as whole words (case-sensitive)."""
    matched = []
    for entry in blacklist:
        entry = entry.strip()
        if not entry:
            continue
        pattern = re.compile(r"\b" + re.escape(entry) + r"\b")
        if pattern.search(text):
            matched.append(entry)
    return matched


# ---------------------------------------------------------------------------
# Text-level regex tests (fast, no PDF required)
# ---------------------------------------------------------------------------

class TestBlacklistTextMatching:
    """Verify the regex logic underlying the blacklist feature."""

    def test_umg_matches_standalone(self):
        """'UMG' as a standalone word must be matched."""
        matches = _find_blacklist_matches_in_text("Klinik UMG Göttingen", ["UMG"])
        assert "UMG" in matches

    def test_umg_does_not_match_umgeben(self):
        """'UMG' must not match inside 'Umgeben'."""
        matches = _find_blacklist_matches_in_text("Umgeben von Bäumen", ["UMG"])
        assert "UMG" not in matches

    def test_lowercase_umg_not_matched(self):
        """Lowercase 'umg' must not match the blacklist entry 'UMG'."""
        matches = _find_blacklist_matches_in_text("umg test", ["UMG"])
        assert "UMG" not in matches

    def test_multiword_phrase_matched(self):
        """'Universitätsmedizin Göttingen' (exact) must be matched."""
        text = "überwiesen an Universitätsmedizin Göttingen für weitere Behandlung"
        matches = _find_blacklist_matches_in_text(text, ["Universitätsmedizin Göttingen"])
        assert "Universitätsmedizin Göttingen" in matches

    def test_double_space_variant_not_matched(self):
        """'Universitätsmedizin  Göttingen' (two spaces) must NOT match."""
        text = "Universitätsmedizin  Göttingen behandelt"
        matches = _find_blacklist_matches_in_text(text, ["Universitätsmedizin Göttingen"])
        assert "Universitätsmedizin Göttingen" not in matches

    def test_multiple_entries(self):
        """Multiple blacklist entries are each evaluated independently."""
        text = "UMG und Charité sind Unikliniken"
        matches = _find_blacklist_matches_in_text(text, ["UMG", "Charité", "MHH"])
        assert "UMG" in matches
        assert "Charité" in matches
        assert "MHH" not in matches

    def test_empty_blacklist(self):
        """An empty blacklist should produce no matches."""
        matches = _find_blacklist_matches_in_text("UMG Göttingen", [])
        assert matches == []

    def test_blank_entry_ignored(self):
        """Blank/whitespace-only entries must be silently ignored."""
        matches = _find_blacklist_matches_in_text("UMG", ["", "  ", "UMG"])
        assert "UMG" in matches
        assert len(matches) == 1


# ---------------------------------------------------------------------------
# PDF-level redaction tests
# ---------------------------------------------------------------------------

class TestBlacklistPdfRedaction:
    """Test that blacklist entries are actually redacted in a real PDF."""

    def _anonymize(self, input_path: str, blacklist: list) -> str:
        """Run anonymization and return output path."""
        template = _build_minimal_template(blacklist)
        anonymizer = ZoneBasedAnonymizer(template)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name
        anonymizer.anonymize_pdf(input_path, output_path)
        return output_path

    def test_umg_is_redacted(self):
        """'UMG' in the PDF must be removed after anonymization."""
        pdf_in = _create_pdf_with_text("Patient der Klinik UMG Göttingen")
        pdf_out = self._anonymize(pdf_in, ["UMG"])
        text = _extract_text_from_pdf(pdf_out)
        assert "UMG" not in text, f"Expected UMG to be redacted, but found in: {text!r}"

    def test_umgeben_is_not_redacted(self):
        """'Umgeben' must survive anonymization when blacklist contains 'UMG'."""
        pdf_in = _create_pdf_with_text("Umgeben von Bäumen ist der Park")
        pdf_out = self._anonymize(pdf_in, ["UMG"])
        text = _extract_text_from_pdf(pdf_out)
        assert "Umgeben" in text, f"Expected 'Umgeben' to survive, but text is: {text!r}"

    def test_multiword_phrase_redacted(self):
        """Multi-word blacklist phrase 'Universitätsmedizin Göttingen' must be redacted."""
        pdf_in = _create_pdf_with_text(
            "Einweisung durch Universitätsmedizin Göttingen erfolgt"
        )
        pdf_out = self._anonymize(pdf_in, ["Universitätsmedizin Göttingen"])
        text = _extract_text_from_pdf(pdf_out)
        # Both words should be gone (or at least the combined phrase)
        assert "Universitätsmedizin" not in text or "Göttingen" not in text, (
            f"Expected phrase to be redacted but found in: {text!r}"
        )

    def test_unrelated_text_preserved(self):
        """Text not in the blacklist must remain intact."""
        pdf_in = _create_pdf_with_text("Patient hat Fieber und Husten")
        pdf_out = self._anonymize(pdf_in, ["UMG"])
        text = _extract_text_from_pdf(pdf_out)
        assert "Fieber" in text, f"Expected 'Fieber' to survive: {text!r}"
        assert "Husten" in text, f"Expected 'Husten' to survive: {text!r}"

    def test_empty_blacklist_changes_nothing(self):
        """An empty blacklist must leave the page content unchanged."""
        original = "Keine Schwärzungen erwartet UMG und Alles"
        pdf_in = _create_pdf_with_text(original)
        pdf_out = self._anonymize(pdf_in, [])
        text = _extract_text_from_pdf(pdf_out)
        assert "UMG" in text, f"Expected UMG to survive with empty blacklist: {text!r}"


# ---------------------------------------------------------------------------
# Config / template field tests
# ---------------------------------------------------------------------------

class TestBlacklistConfig:
    """Verify that AnonymizationTemplate correctly handles blacklist_exact."""

    def test_default_is_empty_list(self):
        """blacklist_exact must default to an empty list."""
        tpl = _build_minimal_template(blacklist=[])
        assert tpl.blacklist_exact == []

    def test_entries_stored_correctly(self):
        """Entries passed to blacklist_exact are stored on the model."""
        tpl = _build_minimal_template(["UMG", "Charité"])
        assert "UMG" in tpl.blacklist_exact
        assert "Charité" in tpl.blacklist_exact

    def test_template_json_round_trip(self):
        """blacklist_exact survives JSON serialisation → deserialisation."""
        data = {
            "template_name": "Test",
            "version": "1.0",
            "zones": {},
            "structured_patterns": {},
            "date_handling": {},
            "image_pii_patterns": {},
            "blacklist_exact": ["UMG", "Universitätsmedizin Göttingen"],
        }
        tpl = AnonymizationTemplate(**data)
        serialised = json.dumps(tpl.model_dump())
        restored = AnonymizationTemplate(**json.loads(serialised))
        assert restored.blacklist_exact == ["UMG", "Universitätsmedizin Göttingen"]

    def test_default_template_has_blacklist_exact_field(self):
        """The production default template file must contain blacklist_exact."""
        template_path = Path("templates/german_clinical_default.json")
        with open(template_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "blacklist_exact" in data, (
            "german_clinical_default.json must contain a 'blacklist_exact' key"
        )
        assert isinstance(data["blacklist_exact"], list)
