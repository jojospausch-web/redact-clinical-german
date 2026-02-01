"""Configuration models for the anonymization system using Pydantic."""

from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field, ConfigDict


class ZoneConfig(BaseModel):
    """Configuration for a PDF zone (header, footer, etc.)."""
    model_config = ConfigDict(extra='allow')
    
    page: Optional[int] = None  # None means all pages
    pages: Optional[str] = None  # "all" or specific page numbers
    y_start: float
    y_end: float
    redaction: str = Field(..., pattern="^(full|keyword_based|none)$")
    preserve_logos: bool = False
    keywords: Optional[List[str]] = None


class PatternGroup(BaseModel):
    """Configuration for a pattern group mapping."""
    model_config = ConfigDict(extra='allow')
    
    pattern: str
    groups: Optional[Dict[str, str]] = None
    type: Optional[str] = None
    context_trigger: Optional[str] = None
    lookahead: Optional[int] = None


class DateHandlingConfig(BaseModel):
    """Configuration for date handling."""
    model_config = ConfigDict(extra='allow')
    
    pattern: str
    action: str = Field(..., pattern="^(shift|shift_relative|remove)$")
    shift_days_range: Optional[Tuple[int, int]] = None


class AnonymizationTemplate(BaseModel):
    """Main configuration template for anonymization rules."""
    model_config = ConfigDict(extra='allow')
    
    template_name: str
    version: str
    zones: Dict[str, ZoneConfig]
    structured_patterns: Dict[str, PatternGroup]
    date_handling: Dict[str, Any]  # Can contain DateHandlingConfig or other dicts
    image_pii_patterns: Dict[str, str]


class PIIEntity(BaseModel):
    """Represents a detected PII entity."""
    text: str
    entity_type: str
    start_pos: int
    end_pos: int
    replacement: Optional[str] = None
    context: Optional[str] = None
