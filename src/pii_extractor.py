"""Structured PII extraction using contextual regex patterns."""

import re
import unicodedata
import logging
from typing import List, Dict, Optional
from src.config import PIIEntity, PatternGroup

logger = logging.getLogger(__name__)

# Patterns that require strict word boundary enforcement.
# These patterns must NOT match substrings inside longer words.
#
# Why these patterns need boundaries:
#   - phone_landline / phone_mobile / phone_context / fax: Number sequences
#     can appear in many innocent positions (e.g. "0561" in a case number
#     or blood-pressure notation). Without a boundary gate the pattern would
#     fire on partial matches and produce false-positive redactions.
#   - salutation_with_name: The prefix "Herr"/"Frau" is short; without a
#     boundary check the name capture group could match inside longer words.
#   - email: The \b anchor in the email regex already helps, but the
#     boundary check adds a consistent second guard.
#
# Other patterns (e.g. doctor_name, case_id, patient_block) rely on
# structural prefix tokens (titles, keywords) in their regex and therefore
# do not need an additional boundary gate.
PATTERNS_REQUIRING_WORD_BOUNDARY = {
    "phone_landline",
    "phone_mobile",
    "phone_context",
    "fax",
    "salutation_with_name",
    "email",
}

# Patterns for which a post-match filter is applied: if every whitespace-
# separated token in the extracted entity text is shorter than 3 characters
# the match is discarded as a likely false positive (e.g. "Dr. El" with only
# the short prefix captured, or stray abbreviations).
PATTERNS_REQUIRING_TOKEN_LENGTH_FILTER = {
    "doctor_name",
    "salutation_with_name",
}


class StructuredPIIExtractor:
    """Extracts PII using structured, context-based regex patterns.
    
    This class does NOT use NER (Named Entity Recognition).
    It only extracts PII from predefined contexts using regex patterns.
    Medical terms are never checked against any whitelist.
    """
    
    def __init__(self, patterns: Dict[str, PatternGroup], whitelist: Optional['WhitelistConfig'] = None):
        """Initialize with structured patterns from configuration.
        
        Args:
            patterns: Dictionary of pattern configurations
            whitelist: Optional whitelist of terms to exclude from redaction
        """
        self.patterns = patterns
        self.whitelist = whitelist
        
        # Pre-process whitelist for performance (convert to lowercase set for O(1) lookups)
        self._whitelist_terms_lower = set()
        if whitelist:
            self._whitelist_terms_lower = set(
                term.lower() 
                for term in (
                    whitelist.medical_terms + 
                    whitelist.anatomical_terms + 
                    whitelist.device_names
                )
            )
    
    def _requires_word_boundary_check(self, pattern_name: str) -> bool:
        """Determine if a pattern requires word boundary validation.

        Args:
            pattern_name: Name of the pattern

        Returns:
            True if word boundary check is required
        """
        return pattern_name in PATTERNS_REQUIRING_WORD_BOUNDARY

    def _requires_token_length_filter(self, pattern_name: str) -> bool:
        """Determine if a pattern requires the token-length post-match filter.

        Args:
            pattern_name: Name of the pattern

        Returns:
            True if the token-length filter should be applied
        """
        return pattern_name in PATTERNS_REQUIRING_TOKEN_LENGTH_FILTER

    def _all_tokens_short(self, entity_text: str, min_length: int = 3) -> bool:
        """Return True when every whitespace-separated token is shorter than *min_length*.

        Used as a post-match guard: if every token in the extracted text is
        very short (e.g. only abbreviations or prefixes were captured) the
        match is likely a false positive and should be discarded.

        Args:
            entity_text: The extracted entity text to inspect.
            min_length: Minimum token length threshold (default: 3).

        Returns:
            True if ALL tokens are shorter than min_length, False otherwise.
        """
        tokens = entity_text.split()
        if not tokens:
            return True
        return all(len(t) < min_length for t in tokens)

    def _is_whole_word(self, text: str, match_start: int, match_end: int) -> bool:
        """
        Check if a match is a whole word (not a substring).

        Correctly handles German umlauts (ä, ö, ü, ß) and other Unicode
        letters as word characters.

        Args:
            text: Full text
            match_start: Start position of match
            match_end: End position of match

        Returns:
            True if whole word, False if substring

        Examples:
            "in Hamburg" → Match "Hamburg" → True (space before/after)
            "Roshamburger" → Match "Hamburg" → False ('b' follows directly)
            "Hämatologie" → Match "matologie" → False ('ä' precedes directly)
        """
        def is_word_char(char: str) -> bool:
            """Return True for any character that is part of a word.

            Covers all Unicode letters (including ä, ö, ü, ß) and decimal
            digits. Using Unicode categories ensures German umlauts are
            correctly treated as word characters.
            """
            category = unicodedata.category(char)
            return (
                category.startswith('L') or  # All Unicode letters (Ll, Lu, Lt, Lm, Lo)
                category == 'Nd'             # Decimal digits
            )

        # Check character BEFORE match
        if match_start > 0:
            if is_word_char(text[match_start - 1]):
                return False

        # Check character AFTER match
        if match_end < len(text):
            if is_word_char(text[match_end]):
                return False

        return True
    
    def _is_whitelisted(self, entity_text: str) -> bool:
        """Check if an entity text is on the whitelist.
        
        Args:
            entity_text: The text to check
            
        Returns:
            True if the text is whitelisted, False otherwise
        """
        if not self.whitelist:
            return False
        
        # Use pre-computed lowercase set for O(1) lookup
        return entity_text.lower() in self._whitelist_terms_lower
    
    def extract_pii(self, text: str, active_patterns: Optional[Dict[str, bool]] = None) -> List[PIIEntity]:
        """Extract PII entities from text using structured patterns.
        
        Args:
            text: Text to analyze
            active_patterns: Optional dict of pattern_name -> enabled (True/False).
                             If None or pattern missing, default to enabled.
        
        Returns:
            List of detected PII entities
        """
        entities = []
        
        # Normalize whitespace characters BEFORE pattern matching
        # Different PDFs may use different Unicode space characters (non-breaking spaces, etc.)
        # This ensures consistent pattern matching regardless of PDF encoding
        text = text.replace('\xa0', ' ')      # Non-breaking space (most common in PDFs)
        text = text.replace('\u202f', ' ')    # Narrow no-break space
        text = text.replace('\u2009', ' ')    # Thin space
        text = text.replace('\u2007', ' ')    # Figure space
        text = re.sub(r'\s+', ' ', text)      # Collapse multiple consecutive spaces

        for pattern_name, pattern_config in self.patterns.items():
            # Check if pattern is enabled
            if active_patterns is not None:
                is_enabled = active_patterns.get(pattern_name, True)  # Default: True
                if not is_enabled:
                    logger.debug(f"Skipping disabled pattern: {pattern_name}")
                    continue

            if pattern_config.context_trigger:
                # Context-based extraction
                entities.extend(
                    self._extract_with_context(text, pattern_config, pattern_name)
                )
            elif pattern_config.groups:
                # Multi-group extraction
                entities.extend(
                    self._extract_with_groups(text, pattern_config, pattern_name)
                )
            else:
                # Simple pattern extraction
                entities.extend(
                    self._extract_simple(text, pattern_config, pattern_name)
                )
        
        return entities
    
    def _extract_simple(self, text: str, config: PatternGroup, pattern_name: str = "") -> List[PIIEntity]:
        """Extract PII using a simple regex pattern.
        
        Args:
            text: Text to search
            config: Pattern configuration
            pattern_name: Name of the pattern (used for word boundary check)
        
        Returns:
            List of PIIEntity objects
        """
        entities = []
        # Use MULTILINE flag to support ^ (line beginning) patterns
        pattern = re.compile(config.pattern, re.MULTILINE | re.IGNORECASE)
        
        for match in pattern.finditer(text):
            # Use the first capturing group if it exists, otherwise the whole match
            if match.groups():
                entity_text = match.group(1)
                start_pos = match.start(1)
                end_pos = match.end(1)
            else:
                entity_text = match.group(0)
                start_pos = match.start(0)
                end_pos = match.end(0)
            
            # Debug logging BEFORE any filtering
            context_start = max(0, start_pos - 20)
            context_end = min(len(text), end_pos + 20)
            context_text = text[context_start:context_end]
            logger.debug(
                f"[MATCH FOUND] Pattern: {pattern_name} | "
                f"Type: {config.type} | "
                f"Text: '{entity_text}' | "
                f"Pos: {start_pos}-{end_pos} | "
                f"Context: ...{context_text}..."
            )

            # Apply word boundary check only for patterns that require it
            if self._requires_word_boundary_check(pattern_name):
                if not self._is_whole_word(text, start_pos, end_pos):
                    logger.debug(
                        f"[SKIP - BOUNDARY] Pattern: {pattern_name} | "
                        f"Text: '{entity_text}' | "
                        f"Reason: Not a whole word (substring match)"
                    )
                    continue

            # Apply token-length filter for patterns that require it
            if self._requires_token_length_filter(pattern_name):
                if self._all_tokens_short(entity_text):
                    logger.debug(
                        f"[SKIP - TOKEN LENGTH] Pattern: {pattern_name} | "
                        f"Text: '{entity_text}' | "
                        f"Reason: All tokens shorter than 3 characters"
                    )
                    continue
            
            # Check whitelist
            if self._is_whitelisted(entity_text):
                logger.debug(
                    f"[SKIP - WHITELIST] Pattern: {pattern_name} | "
                    f"Text: '{entity_text}' | "
                    f"Reason: On whitelist"
                )
                continue

            logger.info(
                f"[ENTITY EXTRACTED] Pattern: {pattern_name} | "
                f"Type: {config.type} | "
                f"Text: '{entity_text}' | "
                f"Pos: {start_pos}-{end_pos}"
            )

            entities.append(PIIEntity(
                text=entity_text,
                entity_type=config.type or "UNKNOWN",
                start_pos=start_pos,
                end_pos=end_pos
            ))
        
        return entities
    
    def _extract_with_groups(self, text: str, config: PatternGroup, pattern_name: str = "") -> List[PIIEntity]:
        """Extract PII with multiple named groups.
        
        Args:
            text: Text to search
            config: Pattern configuration with group mappings
            pattern_name: Name of the pattern (used for word boundary check)
        
        Returns:
            List of PIIEntity objects
        """
        entities = []
        # Use MULTILINE flag to support ^ (line beginning) patterns
        pattern = re.compile(config.pattern, re.MULTILINE | re.IGNORECASE)
        
        for match in pattern.finditer(text):
            # Extract each group according to the configuration
            for group_num, entity_type in config.groups.items():
                group_idx = int(group_num)
                if group_idx <= len(match.groups()):
                    entity_text = match.group(group_idx)
                    if entity_text:  # Only add non-empty groups
                        # Apply word boundary check for each group (only if required)
                        start_pos = match.start(group_idx)
                        end_pos = match.end(group_idx)

                        # Debug logging BEFORE any filtering
                        context_start = max(0, start_pos - 20)
                        context_end = min(len(text), end_pos + 20)
                        context_text = text[context_start:context_end]
                        logger.debug(
                            f"[MATCH FOUND] Pattern: {pattern_name} (group {group_num}) | "
                            f"Type: {entity_type} | "
                            f"Text: '{entity_text}' | "
                            f"Pos: {start_pos}-{end_pos} | "
                            f"Context: ...{context_text}..."
                        )

                        if self._requires_word_boundary_check(pattern_name):
                            if not self._is_whole_word(text, start_pos, end_pos):
                                logger.debug(
                                    f"[SKIP - BOUNDARY] Pattern: {pattern_name} (group {group_num}) | "
                                    f"Text: '{entity_text}' | "
                                    f"Reason: Not a whole word (substring match)"
                                )
                                continue

                        # Apply token-length filter for patterns that require it
                        if self._requires_token_length_filter(pattern_name):
                            if self._all_tokens_short(entity_text):
                                logger.debug(
                                    f"[SKIP - TOKEN LENGTH] Pattern: {pattern_name} (group {group_num}) | "
                                    f"Text: '{entity_text}' | "
                                    f"Reason: All tokens shorter than 3 characters"
                                )
                                continue
                        
                        # Check whitelist
                        if self._is_whitelisted(entity_text):
                            logger.debug(
                                f"[SKIP - WHITELIST] Pattern: {pattern_name} (group {group_num}) | "
                                f"Text: '{entity_text}' | "
                                f"Reason: On whitelist"
                            )
                            continue

                        logger.info(
                            f"[ENTITY EXTRACTED] Pattern: {pattern_name} (group {group_num}) | "
                            f"Type: {entity_type} | "
                            f"Text: '{entity_text}' | "
                            f"Pos: {start_pos}-{end_pos}"
                        )

                        entities.append(PIIEntity(
                            text=entity_text,
                            entity_type=entity_type,
                            start_pos=start_pos,
                            end_pos=end_pos,
                            context=match.group(0)  # Full match as context
                        ))
        
        return entities
    
    def _extract_with_context(self, text: str, config: PatternGroup, pattern_name: str = "") -> List[PIIEntity]:
        """Extract PII only within a specific context.
        
        Args:
            text: Text to search
            config: Pattern configuration with context trigger
            pattern_name: Name of the pattern (used for word boundary check)
        
        Returns:
            List of PIIEntity objects
        """
        entities = []
        
        # Find the context trigger
        trigger_pos = text.find(config.context_trigger)
        if trigger_pos == -1:
            return entities
        
        # Define the search window after the trigger
        lookahead = config.lookahead or 200
        search_start = trigger_pos + len(config.context_trigger)
        search_end = min(search_start + lookahead, len(text))
        search_text = text[search_start:search_end]
        
        # Search for pattern within the window
        # Use MULTILINE flag to support ^ (line beginning) patterns
        pattern = re.compile(config.pattern, re.MULTILINE | re.IGNORECASE)
        for match in pattern.finditer(search_text):
            # Adjust positions relative to the full text
            actual_start = search_start + match.start(0)
            actual_end = search_start + match.end(0)
            entity_text = match.group(0)

            # Debug logging BEFORE any filtering
            context_start = max(0, actual_start - 20)
            context_end = min(len(text), actual_end + 20)
            context_text = text[context_start:context_end]
            logger.debug(
                f"[MATCH FOUND] Pattern: {pattern_name} (context: '{config.context_trigger}') | "
                f"Type: {config.type} | "
                f"Text: '{entity_text}' | "
                f"Pos: {actual_start}-{actual_end} | "
                f"Context: ...{context_text}..."
            )

            # Apply word boundary check only for patterns that require it
            if self._requires_word_boundary_check(pattern_name):
                if not self._is_whole_word(text, actual_start, actual_end):
                    logger.debug(
                        f"[SKIP - BOUNDARY] Pattern: {pattern_name} | "
                        f"Text: '{entity_text}' | "
                        f"Reason: Not a whole word (substring match)"
                    )
                    continue
            
            # Check whitelist
            if self._is_whitelisted(entity_text):
                logger.debug(
                    f"[SKIP - WHITELIST] Pattern: {pattern_name} | "
                    f"Text: '{entity_text}' | "
                    f"Reason: On whitelist"
                )
                continue

            logger.info(
                f"[ENTITY EXTRACTED] Pattern: {pattern_name} (context: '{config.context_trigger}') | "
                f"Type: {config.type} | "
                f"Text: '{entity_text}' | "
                f"Pos: {actual_start}-{actual_end}"
            )

            entities.append(PIIEntity(
                text=entity_text,
                entity_type=config.type or "CONTEXT_BASED",
                start_pos=actual_start,
                end_pos=actual_end,
                context=config.context_trigger
            ))
        
        return entities
