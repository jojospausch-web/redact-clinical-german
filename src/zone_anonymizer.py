"""Zone-based PDF anonymization using PyMuPDF."""

import fitz  # PyMuPDF
from typing import Dict, List, Optional
from pathlib import Path
import logging

from src.config import ZoneConfig, AnonymizationTemplate, PIIEntity
from src.pii_extractor import StructuredPIIExtractor
from src.image_extractor import ImageExtractor


class ZoneBasedAnonymizer:
    """Anonymizes PDFs using zone-based approach with structured PII extraction."""
    
    def __init__(
        self,
        template: AnonymizationTemplate
    ):
        """Initialize the anonymizer.
        
        Args:
            template: Anonymization template with rules
        """
        self.template = template
        # Pass whitelist to the PII extractor
        whitelist = template.whitelist if hasattr(template, 'whitelist') else None
        self.pii_extractor = StructuredPIIExtractor(template.structured_patterns, whitelist)
        self.image_extractor = ImageExtractor()
    
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
            'images_extracted': 0
        }
        
        # Process each page
        cut_off_page = None

        for page_num in range(len(doc)):
            page = doc[page_num]

            # If we are past the cut-off page, redact the entire page and skip
            # normal processing.
            if cut_off_page is not None and page_num > cut_off_page:
                if (
                    self.template.cut_after_keyword
                    and self.template.cut_after_keyword.redact_all_following_pages
                ):
                    full_page_rect = fitz.Rect(0, 0, page.rect.width, page.rect.height)
                    page.add_redact_annot(full_page_rect, fill=(0, 0, 0))
                    logging.getLogger(__name__).info(
                        f"Redacted full page {page_num + 1} (following cut-off)"
                    )
                    page.apply_redactions()
                    continue

            # 1. Apply zone-based redaction (union system: all zones applied independently)
            self._redact_zones(page, page_num, stats)
            
            # 2. Apply signature block redaction
            self._redact_signature_blocks(page)
            
            # 2b. Apply personal block redaction
            self._redact_personal_blocks(page)
            
            # 2c. Apply header redaction on pages 2+
            self._redact_header_next_pages(page, page_num + 1)
            
            # 2d. Apply header-until-keyword redaction
            self._redact_header_until_keyword(page)

            # 2e. Check for cut-off trigger on this page (before PII extraction so
            #     any redaction annotation is applied in the same pass)
            if cut_off_page is None:
                cut_off_page = self._check_cutoff_trigger(page, page_num)
            
            # 3. Extract and analyze text for structured PII
            text = page.get_text()
            active_patterns = getattr(self.template, 'active_patterns', None)
            pii_entities = self.pii_extractor.extract_pii(text, active_patterns)
            stats['pii_entities_found'] += len(pii_entities)
            
            # 4. Redact PII entities
            self._redact_pii_entities(page, pii_entities, text, stats)
            
            # Apply redactions per page
            page.apply_redactions()
        
        # Extract images if requested
        if extract_images_path:
            images = self.image_extractor.extract_images(pdf_path, extract_images_path)
            stats['images_extracted'] = len(images)
        
        # Save anonymized PDF
        doc.save(output_path)
        doc.close()
        
        return stats
    
    def _redact_zones(self, page: fitz.Page, page_num: int, stats: dict):
        """Redact predefined zones on a page with exclude_page support.
        
        Args:
            page: PDF page object
            page_num: Page number (0-indexed)
            stats: Statistics dictionary to update
        """
        for zone_name, zone_config in self.template.zones.items():
            # Check if this zone applies to this page
            
            # Case 1: Specific page (e.g. "page": 1)
            if zone_config.page is not None:
                if zone_config.page != page_num + 1:  # page_num is 0-indexed
                    continue
            
            # Case 2: All pages ("pages": "all")
            elif zone_config.pages == "all":
                # Check exclude_page
                if zone_config.exclude_page == page_num + 1:
                    continue  # Skip this page
            
            # Case 3: No page specification → skip
            else:
                continue
            
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
    
    def _redact_signature_blocks(self, page: fitz.Page):
        """Redact complete block AFTER 'Mit freundlichen Grüßen'.
        
        Args:
            page: PDF page object
        """
        if not hasattr(self.template, 'signature_block') or not self.template.signature_block:
            return
        
        sig_config = self.template.signature_block
        if not sig_config.enabled:
            return
        
        trigger = sig_config.trigger
        height = sig_config.height_below
        
        # Find all instances of the trigger
        instances = page.search_for(trigger)
        
        for inst in instances:
            # Redact rectangle BELOW the trigger text
            # From left to right, height pixels downward
            signature_rect = fitz.Rect(
                0,                      # x_start: Left edge
                inst.y1,                # y_start: Below trigger text (y1 is bottom of trigger)
                page.rect.width,        # x_end: Right edge
                inst.y1 + height        # y_end: height pixels below
            )
            
            page.add_redact_annot(signature_rect, fill=(0, 0, 0))
            logging.getLogger(__name__).info(f"Redacted signature block at y={inst.y1}, height={height}")
    
    def _redact_personal_blocks(self, page: fitz.Page):
        """Redact complete block AFTER 'Personal:' keyword.
        
        Args:
            page: PDF page object
        """
        if not hasattr(self.template, 'personal_block') or not self.template.personal_block:
            return
        
        pers_config = self.template.personal_block
        if not pers_config.enabled:
            return
        
        trigger = pers_config.trigger
        height = pers_config.height_below
        
        # Find all instances of the trigger
        instances = page.search_for(trigger)
        
        for inst in instances:
            # Redact rectangle starting from the "P" of "Personal:"
            personal_rect = fitz.Rect(
                inst.x0,                # x_start: start of "Personal:"
                inst.y0,                # y_start: top of trigger text
                page.rect.width,        # x_end: Right edge
                inst.y0 + height        # y_end: height pixels below start
            )
            
            page.add_redact_annot(personal_rect, fill=(0, 0, 0))
            logging.getLogger(__name__).info(f"Redacted personal block at y={inst.y0}, height={height}")
    
    def _redact_header_next_pages(self, page: fitz.Page, page_num: int):
        """Redact header zone on pages 2+.

        Args:
            page: PDF page object
            page_num: Current page number (1-indexed)
        """
        if page_num == 1:
            return  # Skip page 1

        if not hasattr(self.template, 'header_next') or not self.template.header_next:
            return  # Not configured

        header_height = self.template.header_next

        # Header is at the TOP of the page (y=0 at top in PyMuPDF)
        header_rect = fitz.Rect(
            0,               # x_start: Left edge
            0,               # y_start: Top of page
            page.rect.width, # x_end: Right edge
            header_height    # y_end: header_height pixels from top
        )

        page.add_redact_annot(header_rect, fill=(0, 0, 0))
        logging.getLogger(__name__).info(
            f"Redacted header on page {page_num}, height={header_height}"
        )

    def _redact_header_until_keyword(self, page: fitz.Page):
        """Redact everything ABOVE the first found trigger keyword.

        Useful for variable-height headers (e.g. 'Sehr geehrte Kollegin',
        'Herzkatheterbriefe').

        Args:
            page: PDF page object
        """
        config = getattr(self.template, 'header_until_keyword', None)
        if not config or not config.get('enabled'):
            return

        triggers = config.get('triggers', [])
        for trigger in triggers:
            instances = page.search_for(trigger)
            if instances:
                trigger_y = instances[0].y0
                # Redact everything ABOVE the trigger line
                rect = fitz.Rect(
                    0,
                    0,
                    page.rect.width,
                    trigger_y
                )
                page.add_redact_annot(rect, fill=(0, 0, 0))
                logging.getLogger(__name__).info(
                    f"Redacted header until keyword '{trigger}' at y={trigger_y}"
                )
                break  # Only use first matching trigger

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
                # Minimal padding to handle font rendering edge cases
                # Reduced from previous values (2-10px) to prevent over-redaction
                extended_rect = fitz.Rect(
                    area.x0 - 1,   # 1px left (minimal padding)
                    area.y0 - 1,   # 1px top (minimal padding)
                    area.x1 + 2,   # 2px right (slightly more for italic fonts)
                    area.y1 + 1    # 1px bottom (minimal padding)
                )
                # Standard black redaction for all entities
                page.add_redact_annot(extended_rect, fill=(0, 0, 0))

    def _check_cutoff_trigger(self, page: fitz.Page, page_num: int) -> Optional[int]:
        """Check if the cut-off trigger keyword is on this page and redact below it.

        Args:
            page: PDF page object
            page_num: Current page number (0-indexed)

        Returns:
            page_num if trigger found and redaction applied, None otherwise
        """
        if not self.template.cut_after_keyword:
            return None

        config = self.template.cut_after_keyword
        if not config.enabled:
            return None

        instances = page.search_for(config.trigger)
        if not instances:
            return None

        # Use the first (topmost) occurrence as the cut-off point so that the
        # maximum amount of non-PII content above it is preserved.
        trigger_y = instances[0].y0

        # Redact everything from the top of the trigger text to the bottom of the page
        redact_rect = fitz.Rect(
            0,
            trigger_y,
            page.rect.width,
            page.rect.height
        )
        page.add_redact_annot(redact_rect, fill=(0, 0, 0))
        logging.getLogger(__name__).info(
            f"Cut-off triggered on page {page_num + 1} at y={trigger_y} "
            f"by keyword '{config.trigger}'"
        )

        return page_num
