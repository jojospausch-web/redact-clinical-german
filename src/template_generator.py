"""Custom template generator for dynamic anonymization configuration."""

import json
from pathlib import Path
from typing import List, Optional


def create_custom_template(
    header_height: int,
    header_page: str,
    footer_height: int,
    footer_keywords: List[str],
    base_template_path: str = "templates/german_clinical_default.json"
) -> dict:
    """
    Create a custom template dictionary based on user settings.
    
    Args:
        header_height: Height in pixels from top (in A4 point scale)
        header_page: "1" for first page only, "all" for all pages
        footer_height: Height in pixels from bottom (in A4 point scale)
        footer_keywords: List of keywords for keyword-based footer redaction
        base_template_path: Path to base template file
    
    Returns:
        Template dictionary ready for anonymization
    """
    # Load base template
    with open(base_template_path, 'r', encoding='utf-8') as f:
        template = json.load(f)
    
    # Standard A4 dimensions in PDF points
    A4_HEIGHT = 842
    
    # Update header zone
    # Header height is given "from top", but PDF coordinates are from bottom
    # So we need to convert: y_start = A4_HEIGHT - header_height
    template['zones']['header'] = {
        "y_start": A4_HEIGHT - header_height,
        "y_end": A4_HEIGHT,
        "redaction": "full",
        "preserve_logos": True
    }
    
    # Set header page configuration
    if header_page == "1":
        template['zones']['header']['page'] = 1
        template['zones']['header']['pages'] = None
    else:  # "all"
        template['zones']['header']['page'] = None
        template['zones']['header']['pages'] = "all"
    
    # Update footer zone
    # Footer height is given "from bottom", which matches PDF coordinates
    template['zones']['footer'] = {
        "pages": "all",
        "y_start": 0,
        "y_end": footer_height,
        "redaction": "keyword_based" if footer_keywords else "full",
    }
    
    # Add keywords if provided
    if footer_keywords:
        template['zones']['footer']['keywords'] = footer_keywords
    
    return template
