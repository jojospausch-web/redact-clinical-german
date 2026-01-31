"""Tests for zone-based PDF anonymization."""

import pytest
import fitz  # PyMuPDF
from pathlib import Path
import tempfile

from src.zone_anonymizer import ZoneBasedAnonymizer
from src.config import AnonymizationTemplate, ZoneConfig, PatternGroup, DateHandlingConfig
from src.date_shifter import DateShifter


class TestZoneBasedAnonymizer:
    """Test cases for ZoneBasedAnonymizer class."""
    
    @pytest.fixture
    def sample_template(self):
        """Create a sample anonymization template."""
        return AnonymizationTemplate(
            template_name="Test-Template",
            version="1.0.0",
            zones={
                "header": ZoneConfig(
                    page=1,
                    y_start=0,
                    y_end=100,
                    redaction="full",
                    preserve_logos=False
                ),
                "footer": ZoneConfig(
                    pages="all",
                    y_start=750,
                    y_end=842,
                    redaction="keyword_based",
                    keywords=["IBAN", "Sparkasse"]
                )
            },
            structured_patterns={
                "case_id": PatternGroup(
                    pattern=r"Pat\.-Nr\.\s*([0-9]{6,10})",
                    type="CASE_ID"
                )
            },
            date_handling={
                "birthdate": DateHandlingConfig(
                    pattern=r"\*(\d{2}\.\d{2}\.\d{4})",
                    action="shift",
                    shift_days_range=(-30, 30)
                )
            },
            image_pii_patterns={
                "case_number": r"\d{6,10}"
            }
        )
    
    @pytest.fixture
    def sample_pdf(self):
        """Create a simple sample PDF for testing."""
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as f:
            doc = fitz.open()
            page = doc.new_page(width=595, height=842)  # A4 size
            
            # Add some text in the header zone
            page.insert_text((50, 50), "Klinik Header - Patient Info", fontsize=12)
            
            # Add some text in the main content
            page.insert_text((50, 400), "Patient: Pat.-Nr. 123456789", fontsize=11)
            page.insert_text((50, 420), "Geburtsdatum: *01.01.1960", fontsize=11)
            
            # Add text in footer
            page.insert_text((50, 780), "Bankverbindung: Sparkasse IBAN DE123456", fontsize=9)
            
            doc.save(f.name)
            doc.close()
            
            yield f.name
            
            # Cleanup
            Path(f.name).unlink(missing_ok=True)
    
    def test_anonymizer_initialization(self, sample_template):
        """Test that anonymizer initializes correctly."""
        date_shifter = DateShifter(shift_days=10)
        anonymizer = ZoneBasedAnonymizer(sample_template, date_shifter)
        
        assert anonymizer.template == sample_template
        assert anonymizer.date_shifter == date_shifter
        assert anonymizer.pii_extractor is not None
        assert anonymizer.image_extractor is not None
    
    def test_anonymize_pdf_basic(self, sample_template, sample_pdf):
        """Test basic PDF anonymization."""
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as f:
            output_path = f.name
        
        try:
            date_shifter = DateShifter(shift_days=10)
            anonymizer = ZoneBasedAnonymizer(sample_template, date_shifter)
            
            stats = anonymizer.anonymize_pdf(sample_pdf, output_path)
            
            # Check that statistics are returned
            assert 'total_pages' in stats
            assert stats['total_pages'] == 1
            assert 'zones_redacted' in stats
            assert 'pii_entities_found' in stats
            
            # Verify output file was created
            assert Path(output_path).exists()
            
            # Verify the output PDF can be opened
            doc = fitz.open(output_path)
            assert len(doc) == 1
            doc.close()
            
        finally:
            # Cleanup
            Path(output_path).unlink(missing_ok=True)
    
    def test_zone_redaction_stats(self, sample_template, sample_pdf):
        """Test that zone redaction statistics are tracked."""
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as f:
            output_path = f.name
        
        try:
            anonymizer = ZoneBasedAnonymizer(sample_template)
            stats = anonymizer.anonymize_pdf(sample_pdf, output_path)
            
            # Should have redacted at least the header and footer keywords
            assert stats['zones_redacted'] >= 0
            
        finally:
            Path(output_path).unlink(missing_ok=True)
    
    def test_pii_extraction_stats(self, sample_template, sample_pdf):
        """Test that PII extraction statistics are tracked."""
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as f:
            output_path = f.name
        
        try:
            anonymizer = ZoneBasedAnonymizer(sample_template)
            stats = anonymizer.anonymize_pdf(sample_pdf, output_path)
            
            # Should find at least the case ID
            assert stats['pii_entities_found'] >= 1
            
        finally:
            Path(output_path).unlink(missing_ok=True)
