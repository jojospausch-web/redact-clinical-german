"""Tests for pacemaker ID pattern and cut-off after keyword feature."""

import pytest
import fitz  # PyMuPDF
from pathlib import Path
import tempfile

from src.pii_extractor import StructuredPIIExtractor
from src.config import (
    AnonymizationTemplate,
    ZoneConfig,
    PatternGroup,
    CutAfterKeyword,
)
from src.zone_anonymizer import ZoneBasedAnonymizer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_template(**extra):
    """Return the minimal AnonymizationTemplate needed for tests."""
    return AnonymizationTemplate(
        template_name="Test",
        version="1.0.0",
        zones={},
        structured_patterns={},
        image_pii_patterns={},
        **extra,
    )


# ---------------------------------------------------------------------------
# Pacemaker ID pattern tests
# ---------------------------------------------------------------------------

class TestPacemakerIdPattern:
    """Tests for the pacemaker_id structured pattern."""

    PACEMAKER_PATTERN = PatternGroup(
        pattern=r"\b(?:DR|VR|PM|SM|ICD|CRT)\s+\d{6}\b",
        type="DEVICE_ID",
    )

    @pytest.fixture
    def extractor(self):
        return StructuredPIIExtractor({"pacemaker_id": self.PACEMAKER_PATTERN})

    @pytest.mark.parametrize("serial", [
        "DR 268880",
        "VR 123456",
        "PM 111222",
        "SM 333444",
        "ICD 987654",
        "CRT 456789",
    ])
    def test_known_prefixes_are_matched(self, extractor, serial):
        """All known device prefixes should be detected."""
        entities = extractor.extract_pii(f"Device: {serial} implanted.")
        assert len(entities) >= 1
        assert any(e.entity_type == "DEVICE_ID" for e in entities)

    def test_full_text_match(self, extractor):
        """Test detection inside a realistic clinical sentence."""
        text = "Z.n. DDD-Schrittmacherimplantation (ACME G70A2 DR 268880)"
        entities = extractor.extract_pii(text)
        device_ids = [e for e in entities if e.entity_type == "DEVICE_ID"]
        assert len(device_ids) == 1
        assert "DR" in device_ids[0].text
        assert "268880" in device_ids[0].text

    def test_unknown_prefix_not_matched(self, extractor):
        """Unknown 2-letter prefixes should NOT be matched to avoid false positives."""
        entities = extractor.extract_pii("Reference AB 123456 and CT 789012.")
        device_ids = [e for e in entities if e.entity_type == "DEVICE_ID"]
        assert len(device_ids) == 0

    def test_wrong_digit_count_not_matched(self, extractor):
        """Serials with wrong digit count should not match."""
        entities = extractor.extract_pii("Code DR 12345 and DR 1234567.")
        device_ids = [e for e in entities if e.entity_type == "DEVICE_ID"]
        assert len(device_ids) == 0

    def test_hk_format_not_matched(self, extractor):
        """HK-Nr. format (4 digits / 2 digits) must not be picked up."""
        entities = extractor.extract_pii("HK-Nr.: 5423/25")
        device_ids = [e for e in entities if e.entity_type == "DEVICE_ID"]
        assert len(device_ids) == 0


# ---------------------------------------------------------------------------
# CutAfterKeyword config model tests
# ---------------------------------------------------------------------------

class TestCutAfterKeywordModel:
    """Unit tests for the CutAfterKeyword Pydantic model."""

    def test_defaults(self):
        config = CutAfterKeyword()
        assert config.enabled is False
        assert config.trigger == ""
        assert config.redact_all_following_pages is True

    def test_custom_values(self):
        config = CutAfterKeyword(
            enabled=True,
            trigger="HÄMOSTASEOLOGIE Roche",
            redact_all_following_pages=False,
        )
        assert config.enabled is True
        assert config.trigger == "HÄMOSTASEOLOGIE Roche"
        assert config.redact_all_following_pages is False

    def test_template_accepts_cut_after_keyword(self):
        tmpl = _make_minimal_template(
            cut_after_keyword=CutAfterKeyword(
                enabled=True, trigger="HÄMOSTASEOLOGIE Roche"
            )
        )
        assert tmpl.cut_after_keyword is not None
        assert tmpl.cut_after_keyword.enabled is True

    def test_template_without_cut_after_keyword(self):
        tmpl = _make_minimal_template()
        assert tmpl.cut_after_keyword is None


# ---------------------------------------------------------------------------
# CutAfterKeyword integration tests (PDF-level)
# ---------------------------------------------------------------------------

def _create_pdf_with_text(pages_text: list[str]) -> str:
    """Create a temporary multi-page PDF with given text per page.

    Returns the path to the temporary file. The caller is responsible for
    deleting it, preferably in a ``finally`` block using
    ``Path(path).unlink(missing_ok=True)``.
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = f.name

    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page(width=595, height=842)
        # Insert text line by line so vertical positions are predictable
        y = 100
        for line in text.splitlines():
            if line.strip():
                page.insert_text((50, y), line.strip(), fontsize=11)
                y += 20
    doc.save(path)
    doc.close()
    return path


def _create_pdf_with_positioned_items(pages_items: list[list[tuple]]) -> str:
    """Create a temporary multi-page PDF with text at explicit y positions.

    Args:
        pages_items: List of pages; each page is a list of (text, y) tuples.

    Returns the path to the temporary file.
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = f.name

    doc = fitz.open()
    for items in pages_items:
        page = doc.new_page(width=595, height=842)
        for text, y in items:
            page.insert_text((50, y), text, fontsize=11)
    doc.save(path)
    doc.close()
    return path


class TestCutAfterKeywordIntegration:
    """Integration tests that anonymize real (temporary) PDFs."""

    def _anonymizer_with_cutoff(self, enabled: bool = True, trigger: str = "HÄMOSTASEOLOGIE Roche"):
        tmpl = _make_minimal_template(
            cut_after_keyword=CutAfterKeyword(
                enabled=enabled,
                trigger=trigger,
                redact_all_following_pages=True,
            )
        )
        return ZoneBasedAnonymizer(tmpl)

    def test_text_below_trigger_is_redacted(self):
        """Content on the same page below the trigger keyword must be blacked out.

        'Anamnese' is placed well above the 200 px window so it should survive;
        lab content below the trigger must be gone.
        """
        # Trigger at y=400 (baseline); redact_start_y ≈ 400 - 7 - 200 = 193.
        # 'Anamnese' at y=50 is clearly above that and must be preserved.
        pdf_path = _create_pdf_with_positioned_items([
            [
                ("Anamnese:", 50),
                ("Die Behandlung verlief komplikationslos.", 70),
                ("HÄMOSTASEOLOGIE Roche", 400),
                ("TPZ (Quick) 74-120 %", 420),
            ]
        ])
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                out_path = f.name
            try:
                anonymizer = self._anonymizer_with_cutoff()
                anonymizer.anonymize_pdf(pdf_path, out_path)

                out_doc = fitz.open(out_path)
                page_text = out_doc[0].get_text()
                out_doc.close()

                # Text well above the 200 px window should still be present
                assert "Anamnese" in page_text
                # Lab table content below trigger should be gone
                assert "TPZ" not in page_text
            finally:
                Path(out_path).unlink(missing_ok=True)
        finally:
            Path(pdf_path).unlink(missing_ok=True)

    def test_following_pages_fully_redacted(self):
        """All pages after the trigger page must be fully blacked out."""
        pdf_path = _create_pdf_with_text([
            "Page one content.\n\nHÄMOSTASEOLOGIE Roche\nLab row 1",
            "Page two lab continuation.",
        ])
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                out_path = f.name
            try:
                anonymizer = self._anonymizer_with_cutoff()
                anonymizer.anonymize_pdf(pdf_path, out_path)

                out_doc = fitz.open(out_path)
                page2_text = out_doc[1].get_text()
                out_doc.close()

                # The entire second page should be redacted (no readable text)
                assert "Page two" not in page2_text
            finally:
                Path(out_path).unlink(missing_ok=True)
        finally:
            Path(pdf_path).unlink(missing_ok=True)

    def test_no_cutoff_when_trigger_absent(self):
        """When the trigger keyword is not present, all page content must be preserved."""
        pdf_path = _create_pdf_with_text([
            "Normal clinical text without trigger.",
            "Second page also normal.",
        ])
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                out_path = f.name
            try:
                anonymizer = self._anonymizer_with_cutoff()
                anonymizer.anonymize_pdf(pdf_path, out_path)

                out_doc = fitz.open(out_path)
                p1 = out_doc[0].get_text()
                p2 = out_doc[1].get_text()
                out_doc.close()

                assert "Normal clinical text" in p1
                assert "Second page" in p2
            finally:
                Path(out_path).unlink(missing_ok=True)
        finally:
            Path(pdf_path).unlink(missing_ok=True)

    def test_no_cutoff_when_feature_disabled(self):
        """When cut_after_keyword.enabled is False, content must not be removed."""
        pdf_path = _create_pdf_with_text([
            "Text before.\n\nHÄMOSTASEOLOGIE Roche\nLab data.",
        ])
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                out_path = f.name
            try:
                anonymizer = self._anonymizer_with_cutoff(enabled=False)
                anonymizer.anonymize_pdf(pdf_path, out_path)

                out_doc = fitz.open(out_path)
                page_text = out_doc[0].get_text()
                out_doc.close()

                assert "Lab data" in page_text
            finally:
                Path(out_path).unlink(missing_ok=True)
        finally:
            Path(pdf_path).unlink(missing_ok=True)

    def test_content_200px_before_trigger_is_redacted(self):
        """Content within 200 px above the trigger must also be redacted."""
        # Trigger at y=400 baseline => y0 ~392.
        # Content at y=300 baseline => y0 ~292, which is within the 200 px window
        # (392 - 200 = 192 < 292), so it must be redacted.
        pdf_path = _create_pdf_with_positioned_items([
            [
                ("Safe content", 50),
                ("NearTriggerContent", 300),
                ("HAEMOSTASEOLOGIE Roche", 400),
                ("LabRow", 420),
            ]
        ])
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                out_path = f.name
            try:
                anonymizer = self._anonymizer_with_cutoff(trigger="HAEMOSTASEOLOGIE Roche")
                anonymizer.anonymize_pdf(pdf_path, out_path)

                out_doc = fitz.open(out_path)
                page_text = out_doc[0].get_text()
                out_doc.close()

                # Content within 200 px window must be gone
                assert "NearTriggerContent" not in page_text
                # Content below trigger must also be gone
                assert "LabRow" not in page_text
            finally:
                Path(out_path).unlink(missing_ok=True)
        finally:
            Path(pdf_path).unlink(missing_ok=True)

    def test_content_beyond_200px_before_trigger_is_preserved(self):
        """Content more than 200 px above the trigger must be preserved."""
        # Trigger at y=400 baseline => y0 ~392.
        # redact_start_y ~ 192.
        # Content at y=50 => y0 ~42, well above the redact boundary -> preserved.
        pdf_path = _create_pdf_with_positioned_items([
            [
                ("SafeContent", 50),
                ("HAEMOSTASEOLOGIE Roche", 400),
                ("LabRow", 420),
            ]
        ])
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                out_path = f.name
            try:
                anonymizer = self._anonymizer_with_cutoff(trigger="HAEMOSTASEOLOGIE Roche")
                anonymizer.anonymize_pdf(pdf_path, out_path)

                out_doc = fitz.open(out_path)
                page_text = out_doc[0].get_text()
                out_doc.close()

                # Content more than 200 px above the trigger must survive
                assert "SafeContent" in page_text
                # Lab content must be gone
                assert "LabRow" not in page_text
            finally:
                Path(out_path).unlink(missing_ok=True)
        finally:
            Path(pdf_path).unlink(missing_ok=True)
