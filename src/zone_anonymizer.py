"""Zone-based PDF anonymization using PyMuPDF."""

import fitz  # PyMuPDF
from typing import Dict, List, Optional
from pathlib import Path
import logging

from src.config import ZoneConfig, AnonymizationTemplate, PIIEntity
from src.pii_extractor import StructuredPIIExtractor
from src.image_extractor import ImageExtractor
from src.date_shifter import DateShifter


class ZoneBasedAnonymizer:
    """Anonymizes PDFs using zone-based approach with structured PII extraction."""
    
    def __init__(
        self,
        template: AnonymizationTemplate,
        date_shifter: Optional[DateShifter] = None
    ):
        """Initialize the anonymizer.
        
        Args:
            template: Anonymization template with rules
            date_shifter: Optional date shifter for date anonymization
        """
        self.template = template
        self.pii_extractor = StructuredPIIExtractor(template.structured_patterns)
        self.image_extractor = ImageExtractor()
        self.date_shifter = date_shifter or DateShifter()
    
    def anonymize_pdf(
        self,
        pdf_path: str,
        output_path: str,
        extract_images_path: Optional[str] = None
    ) -> dict:
        """Anonymize a PDF using zone-based approach.
        
        Args:
            pdf_path: Path to input PDF
            output_path: Path for output anonymized PDF
            extract_images_path: Optional path to save extracted images
        
        Returns:
            Dictionary with anonymization statistics
        """
        doc = fitz.open(pdf_path)
        stats = {
            'total_pages': len(doc),
            'zones_redacted': 0,
            'pii_entities_found': 0,
            'images_extracted': 0,
            'dates_shifted': 0
        }
        
        # Process each page
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # 1. Apply zone-based redaction
            self._redact_zones(page, page_num, stats)
            
            # 2. Extract and analyze text for structured PII
            text = page.get_text()
            pii_entities = self.pii_extractor.extract_pii(text)
            stats['pii_entities_found'] += len(pii_entities)
            
            # 3. Redact PII entities
            self._redact_pii_entities(page, pii_entities, text, stats)
        
        # 4. Extract images if requested
        if extract_images_path:
            images = self.image_extractor.extract_images(pdf_path, extract_images_path)
            stats['images_extracted'] = len(images)
        
        # Apply all redactions
        for page_num in range(len(doc)):
            page = doc[page_num]
            page.apply_redactions()
        
        # Save anonymized PDF
        doc.save(output_path)
        doc.close()
        
        return stats
    
    def _redact_zones(self, page: fitz.Page, page_num: int, stats: dict):
        """Redact predefined zones on a page.
        
        Args:
            page: PDF page object
            page_num: Page number (0-indexed)
            stats: Statistics dictionary to update
        """
        for zone_name, zone_config in self.template.zones.items():
            # Check if this zone applies to this page
            if zone_config.page is not None and zone_config.page != page_num + 1:
                continue
            if zone_config.pages and zone_config.pages != "all":
                # Parse specific page numbers if needed
                continue
            
            page_height = page.rect.height
            
            # Create redaction rectangle
            redact_rect = fitz.Rect(
                0,
                zone_config.y_start,
                page.rect.width,
                zone_config.y_end
            )
            
            if zone_config.redaction == "full":
                # Full zone redaction
                if zone_config.preserve_logos:
                    # Get image positions to preserve logos
                    self._redact_with_logo_preservation(page, redact_rect, stats)
                else:
                    page.add_redact_annot(redact_rect, fill=(0, 0, 0))
                    stats['zones_redacted'] += 1
            
            elif zone_config.redaction == "keyword_based":
                # Keyword-based redaction
                self._redact_keywords(page, redact_rect, zone_config.keywords, stats)
    
    def _redact_with_logo_preservation(self, page: fitz.Page, zone_rect: fitz.Rect, stats: dict):
        """Redact a zone while preserving images (logos).
        
        Args:
            page: PDF page object
            zone_rect: Rectangle defining the zone
            stats: Statistics dictionary
        """
        # Get all images on the page
        image_list = page.get_images(full=True)
        logo_rects = []
        
        for img in image_list:
            xref = img[0]
            for img_rect in page.get_image_rects(xref):
                # Check if image is in the zone
                if zone_rect.intersects(img_rect):
                    logo_rects.append(img_rect)
        
        if not logo_rects:
            # No logos to preserve, redact entire zone
            page.add_redact_annot(zone_rect, fill=(0, 0, 0))
            stats['zones_redacted'] += 1
        else:
            # Create multiple redaction rectangles around logos
            # For simplicity, redact above and below the first logo
            if logo_rects:
                logo = logo_rects[0]
                
                # Redact above logo
                if zone_rect.y0 < logo.y0:
                    above_rect = fitz.Rect(zone_rect.x0, zone_rect.y0, zone_rect.x1, logo.y0)
                    page.add_redact_annot(above_rect, fill=(0, 0, 0))
                
                # Redact below logo
                if logo.y1 < zone_rect.y1:
                    below_rect = fitz.Rect(zone_rect.x0, logo.y1, zone_rect.x1, zone_rect.y1)
                    page.add_redact_annot(below_rect, fill=(0, 0, 0))
                
                # Redact to the left and right of logo
                if zone_rect.x0 < logo.x0:
                    left_rect = fitz.Rect(zone_rect.x0, logo.y0, logo.x0, logo.y1)
                    page.add_redact_annot(left_rect, fill=(0, 0, 0))
                
                if logo.x1 < zone_rect.x1:
                    right_rect = fitz.Rect(logo.x1, logo.y0, zone_rect.x1, logo.y1)
                    page.add_redact_annot(right_rect, fill=(0, 0, 0))
                
                stats['zones_redacted'] += 1
    
    def _redact_keywords(self, page: fitz.Page, zone_rect: fitz.Rect, keywords: List[str], stats: dict):
        """Redact text containing specific keywords within a zone.
        
        Args:
            page: PDF page object
            zone_rect: Rectangle defining the zone
            keywords: List of keywords to search for
            stats: Statistics dictionary
        """
        text_instances = page.get_text("dict")
        
        for keyword in keywords:
            # Search for keyword in the zone
            areas = page.search_for(keyword)
            for area in areas:
                # Check if the found area is within the zone
                if zone_rect.intersects(area):
                    page.add_redact_annot(area, fill=(0, 0, 0))
                    stats['zones_redacted'] += 1
    
    def _redact_pii_entities(self, page: fitz.Page, entities: List[PIIEntity], full_text: str, stats: dict):
        """Redact PII entities found by structured extraction.
        
        Args:
            page: PDF page object
            entities: List of PIIEntity objects to redact
            full_text: Full page text for context
            stats: Statistics dictionary
        """
        for entity in entities:
            # Search for the entity text on the page
            areas = page.search_for(entity.text)
            
            for area in areas:
                # Handle date shifting
                if entity.entity_type == "BIRTHDATE" or "DATE" in entity.entity_type:
                    # Shift the date
                    shifted_date = self.date_shifter.shift_date(entity.text)
                    # Redact and add shifted text
                    page.add_redact_annot(area, text=shifted_date, fill=(1, 1, 1), text_color=(0, 0, 0))
                    stats['dates_shifted'] += 1
                else:
                    # Standard black redaction
                    page.add_redact_annot(area, fill=(0, 0, 0))
