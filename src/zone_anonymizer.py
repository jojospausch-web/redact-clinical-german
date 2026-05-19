"""Zone-based PDF anonymization using PyMuPDF."""

import re
import fitz  # PyMuPDF
from typing import Dict, List, Optional
from pathlib import Path
import logging

from src.config import ZoneConfig, AnonymizationTemplate, PIIEntity
from src.pii_extractor import StructuredPIIExtractor
from src.image_extractor import ImageExtractor
from src.date_shifter import DateAction, decide_document_mode, plan_actions


class ZoneBasedAnonymizer:
    """Anonymizes PDFs using zone-based approach with structured PII extraction."""

    def __init__(
        self,
        template: AnonymizationTemplate,
        date_shift_enabled: bool = False,
    ):
        """Initialize the anonymizer.

        Args:
            template: Anonymization template with rules
            date_shift_enabled: When True, run the rule-based date shifter
                after PII redaction. Shifted dates get a yellow highlight,
                non-shifted dates a red highlight (see src/date_shifter.py).
        """
        self.template = template
        self.date_shift_enabled = date_shift_enabled
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

        # Date-Shift: Modus EINMAL über das gesamte Dokument bestimmen.
        # Sonst würde Seite 2+ ohne „vom…bis…"-Span automatisch in
        # `no_stay` fallen (rot statt geshiftet).
        doc_date_mode: Optional[str] = None
        doc_date_admission = None
        if self.date_shift_enabled:
            full_text = "\n".join(p.get_text() for p in doc)
            doc_date_mode, doc_date_admission = decide_document_mode(full_text)
            logging.getLogger(__name__).info(
                "Date-Shift Dokument-Modus: %s (Aufnahme=%s)",
                doc_date_mode, doc_date_admission,
            )
            stats['date_shifter_mode'] = doc_date_mode

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
            
            # 3. Build a position-aware text from PyMuPDF word tokens.
            #    Each word carries its pixel bbox; we reconstruct the page
            #    text (joining same-line words with " ", new lines with "\n")
            #    and remember the char offset of each word. This lets us map
            #    PII char offsets back to exact pixel rectangles without
            #    re-searching the page text (which over-redacts when a name
            #    appears more than once on the page).
            words = page.get_text("words")
            joined_text, word_ranges = self._build_text_with_offsets(words)

            active_patterns = getattr(self.template, 'active_patterns', None)
            pii_entities = self.pii_extractor.extract_pii(joined_text, active_patterns)
            stats['pii_entities_found'] += len(pii_entities)

            # 4. Redact PII entities at the exact word rectangles
            self._redact_pii_entities(page, pii_entities, words, word_ranges, joined_text)

            # 5. Redact exact blacklist entries (case-sensitive, whole-word)
            self._redact_blacklist_exact(page, joined_text)

            # Apply redactions per page (zone / PII / blacklist)
            page.apply_redactions()

            # 6. Optional date-shifting pass — runs AFTER the redaction pass so
            #    that already-redacted text (e.g. birthdate inside the patient
            #    block) is not touched again. The shifter applies its own
            #    `add_redact_annot(..., text=new_date)` for shifted dates and
            #    adds yellow/red highlight annotations as marks. We then call
            #    `apply_redactions()` a second time to materialise the new
            #    date text into the PDF stream.
            if self.date_shift_enabled:
                ds_stats = self._apply_date_shift(
                    page,
                    doc_mode=doc_date_mode,
                    doc_admission=doc_date_admission,
                )
                stats['date_shifter'] = stats.get('date_shifter', [])
                stats['date_shifter'].append({
                    'page': page_num + 1,
                    **ds_stats,
                })
        
        # Extract images if requested. We keep the in-memory PIL images so the
        # caller (main.py) can run image anonymisation on the same objects
        # instead of reading every image out of the PDF a second time.
        extracted_images: list = []
        if extract_images_path:
            extracted_images = self.image_extractor.extract_images(pdf_path, extract_images_path)
            stats['images_extracted'] = len(extracted_images)
            stats['extracted_image_objects'] = extracted_images

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

    def _find_trigger_y(self, page: fitz.Page, trigger: str) -> Optional[float]:
        """Return the topmost y0 where *trigger* appears on the page, or None.

        Robust against PDF whitespace quirks: PyMuPDF's `search_for` matches the
        raw content stream and fails when the PDF uses non-breaking spaces
        (\\xa0), narrow no-break spaces (\\u202f), thin spaces (\\u2009) or
        double spaces between words (very common in clinical headers). When
        the native search misses, we fall back to a token-based scan via
        `get_text("words")`, which tokenises on any Unicode whitespace.

        Args:
            page: PDF page
            trigger: Trigger phrase to locate

        Returns:
            Smallest y0 of any matching instance, or None if not found.
        """
        if not trigger:
            return None

        instances = page.search_for(trigger)
        if instances:
            return min(inst.y0 for inst in instances)

        # Fallback: token-based scan (handles NBSP / multi-space between words)
        # words tuple layout: (x0, y0, x1, y1, text, block_no, line_no, word_no)
        trigger_tokens = trigger.split()
        if not trigger_tokens:
            return None
        words = page.get_text("words")
        n = len(trigger_tokens)
        if n > len(words):
            return None

        # First: case-sensitive consecutive match
        for i in range(len(words) - n + 1):
            if all(words[i + j][4] == trigger_tokens[j] for j in range(n)):
                return min(words[i + j][1] for j in range(n))

        # Last resort: case-insensitive (some PDFs lower-case the header)
        lower_tokens = [t.lower() for t in trigger_tokens]
        for i in range(len(words) - n + 1):
            if all(words[i + j][4].lower() == lower_tokens[j] for j in range(n)):
                return min(words[i + j][1] for j in range(n))

        return None

    def _redact_header_until_keyword(self, page: fitz.Page):
        """Redact everything ABOVE the topmost trigger keyword on the page.

        Useful for variable-height headers (e.g. 'Sehr geehrte Kollegin',
        'Untersucher:', 'Herzkatheterbriefe'). All trigger phrases are
        searched and the topmost (smallest y0) wins — so the order of the
        trigger list in the template doesn't matter.

        Args:
            page: PDF page object
        """
        config = getattr(self.template, 'header_until_keyword', None)
        if not config or not config.get('enabled'):
            return

        triggers = config.get('triggers', [])
        log = logging.getLogger(__name__)

        # Collect the topmost hit per trigger, then pick overall topmost.
        candidates = []
        for trigger in triggers:
            y = self._find_trigger_y(page, trigger)
            if y is not None:
                candidates.append((y, trigger))

        if not candidates:
            log.debug(
                f"header_until_keyword: no trigger from {triggers!r} found on page"
            )
            return

        trigger_y, trigger = min(candidates, key=lambda c: c[0])
        if trigger_y <= 0:
            log.debug(
                f"header_until_keyword: trigger '{trigger}' is at top of page "
                f"(y={trigger_y}); nothing to redact above it"
            )
            return

        rect = fitz.Rect(0, 0, page.rect.width, trigger_y)
        page.add_redact_annot(rect, fill=(0, 0, 0))
        log.info(
            f"Redacted header until keyword '{trigger}' at y={trigger_y:.1f}"
        )

    @staticmethod
    def _build_text_with_offsets(words):
        """Reconstruct page text from PyMuPDF word tokens and remember offsets.

        ``words`` is the list returned by ``page.get_text("words")``; each
        entry has layout ``(x0, y0, x1, y1, text, block_no, line_no, word_no)``.
        We join words on the same (block, line) with a single space and use
        ``\\n`` between lines so the resulting text behaves like the regular
        ``page.get_text()`` output (regex patterns using ``^`` keep working
        under ``re.MULTILINE``).

        Returns:
            (joined_text, word_ranges) — ``word_ranges`` is a list of
            ``(char_start, char_end, word_index)`` aligned with the input
            list, where ``char_start`` / ``char_end`` are offsets in
            ``joined_text``.
        """
        parts = []
        word_ranges = []
        pos = 0
        prev_block = None
        prev_line = None
        for i, w in enumerate(words):
            text = w[4]
            block_no = w[5]
            line_no = w[6]
            if prev_block is not None:
                if block_no != prev_block or line_no != prev_line:
                    parts.append("\n")
                    pos += 1
                else:
                    parts.append(" ")
                    pos += 1
            parts.append(text)
            word_ranges.append((pos, pos + len(text), i))
            pos += len(text)
            prev_block = block_no
            prev_line = line_no
        return "".join(parts), word_ranges

    def _redact_pii_entities(
        self,
        page: fitz.Page,
        entities: List[PIIEntity],
        words: list,
        word_ranges: list,
        joined_text: str,
    ):
        """Redact PII entities at their exact word rectangles.

        For each entity we find the words whose character ranges overlap
        ``[entity.start_pos, entity.end_pos)`` and add a redact annotation
        around the union of their bounding boxes. Falls back to
        ``page.search_for`` only when the entity text cannot be mapped to
        a word range (rare; happens e.g. when the extractor normalises
        whitespace differently than the word tokenisation).

        Args:
            page: PDF page object
            entities: PIIEntity objects whose offsets refer to ``joined_text``
            words: page.get_text("words") output
            word_ranges: parallel list of (char_start, char_end, word_idx)
            joined_text: the reconstructed text the extractor ran on
        """
        log = logging.getLogger(__name__)
        for entity in entities:
            overlapping = [
                wr for wr in word_ranges
                if wr[1] > entity.start_pos and wr[0] < entity.end_pos
            ]
            if overlapping:
                x0 = min(words[wr[2]][0] for wr in overlapping) - 1
                y0 = min(words[wr[2]][1] for wr in overlapping) - 1
                x1 = max(words[wr[2]][2] for wr in overlapping) + 2
                y1 = max(words[wr[2]][3] for wr in overlapping) + 1
                page.add_redact_annot(fitz.Rect(x0, y0, x1, y1), fill=(0, 0, 0))
                continue

            # Fallback for the rare case the offset mapping doesn't line up
            # (e.g. extractor saw a normalised character the words list
            # doesn't expose). Use search_for, but only redact the first hit
            # to avoid the historical over-redaction problem.
            log.debug(
                f"PII entity '{entity.text}' could not be mapped to word "
                f"tokens (pos {entity.start_pos}-{entity.end_pos}); falling "
                f"back to page.search_for"
            )
            areas = page.search_for(entity.text)
            if not areas:
                continue
            area = areas[0]
            page.add_redact_annot(
                fitz.Rect(area.x0 - 1, area.y0 - 1, area.x1 + 2, area.y1 + 1),
                fill=(0, 0, 0),
            )

    def _apply_date_shift(
        self,
        page: fitz.Page,
        doc_mode: Optional[str] = None,
        doc_admission=None,
    ) -> dict:
        """Run the rule-based date-shifter on the (already-PII-redacted) page.

        Args:
            page: PDF page object
            doc_mode: Pre-computed document-wide mode (see
                `date_shifter.decide_document_mode`). When given, the
                per-page mode decision is bypassed — important because the
                „vom…bis…"-span usually only lives on page 1, but every
                page needs the same shift rule for the document to remain
                temporally consistent.
            doc_admission: The admission date from the document-wide pass.
                Needed for standalone month names without a year ("seit
                Juli") — we borrow the admission's year there.

        Flow:
        1. Re-extract words from the page (PII text has already been removed
           by `apply_redactions()`, so we won't see redacted birthdates here).
        2. Ask `date_shifter.plan_actions` for one DateAction per detected
           date, forcing the document mode.
        3. For each action:
           - `do_shift=True`: add a redact-annot with the new text; PyMuPDF
             will replace the original date on the next `apply_redactions()`.
           - `do_shift=False`: leave the text alone — only mark.
           - In both cases add a yellow or red highlight annotation on top
             of the original bbox.
        4. Call `apply_redactions()` once more to materialise the new dates.
           Highlights survive this call because PyMuPDF's redact pass only
           touches text/images, not markup annotations.

        Returns:
            A small statistics dict for the page (mode, counts).
        """
        log = logging.getLogger(__name__)
        words = page.get_text("words")
        if not words:
            return {"mode": "no_text", "shifted": 0, "marked_red": 0, "marked_yellow": 0}

        joined_text, word_ranges = self._build_text_with_offsets(words)
        mode, actions = plan_actions(
            joined_text,
            force_mode=doc_mode,
            force_admission=doc_admission,
        )

        shifted = 0
        marked_red = 0
        marked_yellow = 0

        # We collect highlight specs and add the annotations only AFTER the
        # second `apply_redactions()` call, because PyMuPDF removes overlapping
        # markup annotations when a redaction is applied.
        highlight_specs = []  # list of (rect, color, tooltip)

        for action in actions:
            bbox = self._bbox_for_offsets(action.start, action.end, words, word_ranges)
            if bbox is None:
                # Fallback: try to find the literal date text on the page
                fallback = page.search_for(action.raw_text)
                if not fallback:
                    log.debug("Date-Shift: bbox for '%s' not found, skipping", action.raw_text)
                    continue
                bbox = fallback[0]

            # Slightly pad so the replacement covers the original text exactly
            padded = fitz.Rect(bbox.x0 - 1, bbox.y0 - 1, bbox.x1 + 2, bbox.y1 + 1)

            if action.do_shift and action.new_text:
                # Derive the font size from the original character bbox so the
                # replacement glyph sits on the same baseline as its neighbours.
                # If we left the default 10pt in place, a brief printed at e.g.
                # 11pt would land the new text on a slightly different y, and
                # PDF readers would split the line in two during text
                # extraction (= Excel rows shift on Ctrl+A copy).
                # PDF rule of thumb: line_height ≈ 1.2 × fontsize, so
                #   fontsize ≈ bbox_height / 1.2
                char_height = max(1.0, bbox.y1 - bbox.y0)
                est_fontsize = char_height / 1.2
                # Clamp so a single oddly tall glyph doesn't blow up the size
                fontsize = max(7.0, min(14.0, est_fontsize))
                page.add_redact_annot(
                    padded,
                    text=action.new_text,
                    fontname="helv",
                    fontsize=fontsize,
                    align=fitz.TEXT_ALIGN_LEFT,
                    fill=(1, 1, 1),
                )
                shifted += 1

            highlight_specs.append((bbox, action.color, action.tooltip))

        # Materialise the new dates
        page.apply_redactions()

        # Now place the highlights — they survive future operations
        for rect, color, tooltip in highlight_specs:
            try:
                annot = page.add_highlight_annot(rect)
                if color == "red":
                    annot.set_colors(stroke=(1.0, 0.0, 0.0))
                    marked_red += 1
                else:
                    # Default highlight is yellow
                    marked_yellow += 1
                if tooltip:
                    annot.set_info(content=tooltip)
                annot.update()
            except Exception as exc:
                log.warning("Date-Shift: could not place highlight: %s", exc)

        log.info(
            "Date-Shift page: mode=%s shifted=%d red=%d yellow=%d",
            mode, shifted, marked_red, marked_yellow,
        )
        return {
            "mode": mode,
            "shifted": shifted,
            "marked_red": marked_red,
            "marked_yellow": marked_yellow,
        }

    @staticmethod
    def _bbox_for_offsets(
        start: int,
        end: int,
        words: list,
        word_ranges: list,
    ) -> Optional["fitz.Rect"]:
        """Compute the union bbox of all words overlapping `[start, end)`."""
        overlapping = [wr for wr in word_ranges if wr[1] > start and wr[0] < end]
        if not overlapping:
            return None
        x0 = min(words[wr[2]][0] for wr in overlapping)
        y0 = min(words[wr[2]][1] for wr in overlapping)
        x1 = max(words[wr[2]][2] for wr in overlapping)
        y1 = max(words[wr[2]][3] for wr in overlapping)
        return fitz.Rect(x0, y0, x1, y1)

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

        # Redact from 200px above the trigger line (inclusive) to the bottom of
        # the page so that any lead-in content on the same line band is covered.
        redact_start_y = max(0, trigger_y - 200)
        redact_rect = fitz.Rect(
            0,
            redact_start_y,
            page.rect.width,
            page.rect.height
        )
        page.add_redact_annot(redact_rect, fill=(0, 0, 0))
        logging.getLogger(__name__).info(
            f"Cut-off triggered on page {page_num + 1} at y={trigger_y} "
            f"(redacting from y={redact_start_y}) by keyword '{config.trigger}'"
        )

        return page_num

    def _redact_blacklist_exact(self, page: fitz.Page, text: str):
        """Redact exact case-sensitive blacklist entries with whole-word boundaries.

        Only entries that have a whole-word case-sensitive regex match in *text* are
        processed; this prevents false positives (e.g. 'UMG' will not redact
        'Umgeben') and avoids the overhead of scanning word-tokens for every page.

        For multi-word entries the method checks that consecutive PDF word-tokens
        match every part of the entry (case-sensitive).  Because the page-text
        regex filter already rejects double-space variants the consecutive-token
        scan is only reached for genuine exact matches.

        Args:
            page: PDF page object
            text: Full extracted text of this page (used for fast regex pre-filter)
        """
        blacklist = getattr(self.template, 'blacklist_exact', None) or []
        if not blacklist:
            return

        for entry in blacklist:
            entry = entry.strip()
            if not entry:
                continue

            # Pre-filter: require a whole-word case-sensitive match in the text.
            # This also rejects double-space variants for multi-word phrases.
            pre_pattern = re.compile(r'\b' + re.escape(entry) + r'\b')
            if not pre_pattern.search(text):
                continue

            entry_parts = entry.split()
            # PDF word list: (x0, y0, x1, y1, word_text, block_no, line_no, word_no)
            words = page.get_text("words")

            if len(entry_parts) == 1:
                # Single-word entry: exact case-sensitive match against word tokens
                for w in words:
                    if w[4] == entry:
                        rect = fitz.Rect(w[0] - 1, w[1] - 1, w[2] + 2, w[3] + 1)
                        page.add_redact_annot(rect, fill=(0, 0, 0))
            else:
                # Multi-word entry: find consecutive word-token sequences
                n = len(entry_parts)
                for i in range(len(words) - n + 1):
                    if all(words[i + j][4] == entry_parts[j] for j in range(n)):
                        x0 = min(words[i + j][0] for j in range(n)) - 1
                        y0 = min(words[i + j][1] for j in range(n)) - 1
                        x1 = max(words[i + j][2] for j in range(n)) + 2
                        y1 = max(words[i + j][3] for j in range(n)) + 1
                        page.add_redact_annot(fitz.Rect(x0, y0, x1, y1), fill=(0, 0, 0))
