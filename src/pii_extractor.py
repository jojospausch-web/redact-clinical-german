"""Structured PII extraction using contextual regex patterns."""

import re
import logging
from typing import List, Dict
from src.config import PIIEntity, PatternGroup

logger = logging.getLogger(__name__)


class StructuredPIIExtractor:
    """Extracts PII using structured, context-based regex patterns.
    
    This class does NOT use NER (Named Entity Recognition).
    It only extracts PII from predefined contexts using regex patterns.
    Medical terms are never checked against any whitelist.
    """
    
    def __init__(self, patterns: Dict[str, PatternGroup]):
        """Initialize with structured patterns from configuration.
        
        Args:
            patterns: Dictionary of pattern configurations
        """
        self.patterns = patterns
    
    def _is_whole_word(self, text: str, match_start: int, match_end: int) -> bool:
        """
        Prüft ob ein Match ein ganzes Wort ist (keine Substring-Match).
        
        Args:
            text: Gesamter Text
            match_start: Start-Position des Match
            match_end: End-Position des Match
            
        Returns:
            True wenn ganzes Wort, False wenn Substring
            
        Examples:
            "in Hamburg" → Match "Hamburg" → True (Leerzeichen davor/danach)
            "Roshamburger" → Match "Hamburg" → False ('b' folgt direkt)
        """
        # Prüfe Zeichen VOR dem Match
        if match_start > 0:
            char_before = text[match_start - 1]
            # Wenn alphanumerisch, ist es kein ganzes Wort
            if char_before.isalnum():
                return False
        
        # Prüfe Zeichen NACH dem Match
        if match_end < len(text):
            char_after = text[match_end]
            # Wenn alphanumerisch, ist es kein ganzes Wort
            if char_after.isalnum():
                return False
        
        return True
    
    def extract_pii(self, text: str) -> List[PIIEntity]:
        """Extract PII entities from text using structured patterns.
        
        Args:
            text: Text to analyze
        
        Returns:
            List of detected PII entities
        """
        entities = []
        
        for pattern_name, pattern_config in self.patterns.items():
            if pattern_config.context_trigger:
                # Context-based extraction
                entities.extend(
                    self._extract_with_context(text, pattern_config)
                )
            elif pattern_config.groups:
                # Multi-group extraction
                entities.extend(
                    self._extract_with_groups(text, pattern_config)
                )
            else:
                # Simple pattern extraction
                entities.extend(
                    self._extract_simple(text, pattern_config)
                )
        
        return entities
    
    def _extract_simple(self, text: str, config: PatternGroup) -> List[PIIEntity]:
        """Extract PII using a simple regex pattern.
        
        Args:
            text: Text to search
            config: Pattern configuration
        
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
            
            # Apply word boundary check
            if not self._is_whole_word(text, start_pos, end_pos):
                logger.debug(f"Skipped substring match '{entity_text}' in pattern")
                continue
            
            entities.append(PIIEntity(
                text=entity_text,
                entity_type=config.type or "UNKNOWN",
                start_pos=start_pos,
                end_pos=end_pos
            ))
        
        return entities
    
    def _extract_with_groups(self, text: str, config: PatternGroup) -> List[PIIEntity]:
        """Extract PII with multiple named groups.
        
        Args:
            text: Text to search
            config: Pattern configuration with group mappings
        
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
                        # Apply word boundary check for each group
                        start_pos = match.start(group_idx)
                        end_pos = match.end(group_idx)
                        
                        if not self._is_whole_word(text, start_pos, end_pos):
                            logger.debug(f"Skipped substring match '{entity_text}' in group {group_num}")
                            continue
                        
                        entities.append(PIIEntity(
                            text=entity_text,
                            entity_type=entity_type,
                            start_pos=start_pos,
                            end_pos=end_pos,
                            context=match.group(0)  # Full match as context
                        ))
        
        return entities
    
    def _extract_with_context(self, text: str, config: PatternGroup) -> List[PIIEntity]:
        """Extract PII only within a specific context.
        
        Args:
            text: Text to search
            config: Pattern configuration with context trigger
        
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
            
            # Apply word boundary check
            if not self._is_whole_word(text, actual_start, actual_end):
                logger.debug(f"Skipped substring match '{match.group(0)}' in context")
                continue
            
            entities.append(PIIEntity(
                text=match.group(0),
                entity_type=config.type or "CONTEXT_BASED",
                start_pos=actual_start,
                end_pos=actual_end,
                context=config.context_trigger
            ))
        
        return entities
