"""Template manager for user-facing anonymization templates."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

DEFAULT_TEMPLATE: dict = {
    "name": "Standard",
    "created": "2026-02-25T05:07:00Z",
    "zones": {
        "header_page1": 380,
        "header_next": 100,
        "footer_page1": 130,
        "footer_next": 110,
        "signature": 150,
        "personal": 100
    },
    "active_patterns": {
        "patient_block": True,
        "case_id": True,
        "address": True,
        "doctor_name": True,
        "doctor_with_location": True,
        "doctor_signature": True,
        "referring_doctor": True,
        "postal_code_with_city": True,
        "postal_code_standalone": True,
        "city_facility_simple": True,
        "university_hospital": True,
        "medical_facility_with_city": True
    },
    "whitelist": {
        "medical": [],
        "anatomical": [],
        "devices": []
    }
}

# Name of the default template file (created automatically on first use)
DEFAULT_TEMPLATE_FILE = "default.json"

# The base anonymization template file (not a user template)
_BASE_TEMPLATE_FILE = "german_clinical_default.json"


def _template_path(name: str) -> Path:
    """Return the path for a template by name."""
    safe = name.replace("/", "_").replace("\\", "_")
    return TEMPLATES_DIR / f"{safe}.json"


def get_default_template() -> dict:
    """Return a copy of the built-in default template."""
    return dict(DEFAULT_TEMPLATE)


def ensure_default_template() -> None:
    """Create templates/default.json if it does not exist yet."""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    default_path = TEMPLATES_DIR / DEFAULT_TEMPLATE_FILE
    if not default_path.exists():
        save_template("default", get_default_template())
        logger.info("Created default template: templates/default.json")


def list_templates() -> List[str]:
    """Return the names of all user templates (alphabetically sorted).

    The base anonymization template ``german_clinical_default.json`` is
    intentionally excluded because it is not a user-editable template.
    """
    ensure_default_template()
    names = []
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        if path.name == _BASE_TEMPLATE_FILE:
            continue
        names.append(path.stem)
    return names


def load_template(name: str) -> Optional[dict]:
    """Load a user template by name.

    Args:
        name: Template name (without .json extension)

    Returns:
        Template dict, or None if not found / invalid JSON.
    """
    path = _template_path(name)
    if not path.exists():
        logger.warning(f"Template not found: {path}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Fill missing keys with defaults so callers can rely on all keys
        data = _fill_defaults(data)
        return data
    except json.JSONDecodeError as exc:
        logger.error(f"Invalid JSON in template '{name}': {exc}")
        return None


def save_template(name: str, config: dict) -> bool:
    """Save a user template.

    Args:
        name: Template name (without .json extension)
        config: Template dict

    Returns:
        True on success, False on error.
    """
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    path = _template_path(name)
    config = dict(config)
    config.setdefault("name", name)
    config.setdefault("created", datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved template '{name}' to {path}")
        return True
    except OSError as exc:
        logger.error(f"Failed to save template '{name}': {exc}")
        return False


def delete_template(name: str) -> bool:
    """Delete a user template.

    Args:
        name: Template name (without .json extension)

    Returns:
        True if the file was deleted, False otherwise.
    """
    path = _template_path(name)
    if not path.exists():
        logger.warning(f"Template '{name}' does not exist, nothing to delete")
        return False
    try:
        path.unlink()
        logger.info(f"Deleted template '{name}'")
        return True
    except OSError as exc:
        logger.error(f"Failed to delete template '{name}': {exc}")
        return False


def _fill_defaults(data: dict) -> dict:
    """Fill missing keys in a user template with default values."""
    result = get_default_template()
    result.update(data)
    # Merge nested dicts
    for section in ("zones", "whitelist", "active_patterns"):
        if section in data and isinstance(data[section], dict):
            result[section] = dict(result.get(section, {}))
            result[section].update(data[section])
    return result
