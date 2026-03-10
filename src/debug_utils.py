"""Debug utilities for pattern matching analysis."""

import logging
from typing import List
from src.config import PIIEntity

logger = logging.getLogger(__name__)


def generate_match_report(text: str, entities: List[PIIEntity]) -> str:
    """Generate a detailed report of all pattern matches.

    Args:
        text: Original text
        entities: List of extracted PII entities

    Returns:
        Formatted report string
    """
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("PATTERN MATCH REPORT")
    report_lines.append("=" * 80)
    report_lines.append(f"\nTotal entities found: {len(entities)}")
    report_lines.append("\n" + "-" * 80)

    # Group by entity type
    by_type: dict = {}
    for entity in entities:
        if entity.entity_type not in by_type:
            by_type[entity.entity_type] = []
        by_type[entity.entity_type].append(entity)

    for entity_type, entities_of_type in sorted(by_type.items()):
        report_lines.append(f"\n{entity_type}: {len(entities_of_type)} match(es)")
        report_lines.append("-" * 40)

        for entity in entities_of_type:
            # Get surrounding context
            context_start = max(0, entity.start_pos - 30)
            context_end = min(len(text), entity.end_pos + 30)
            context = text[context_start:context_end]

            # Highlight the matched part
            highlight_start = entity.start_pos - context_start
            highlight_end = entity.end_pos - context_start
            highlighted = (
                context[:highlight_start]
                + f">>>{context[highlight_start:highlight_end]}<<<"
                + context[highlight_end:]
            )

            report_lines.append(f"\n  Text: '{entity.text}'")
            report_lines.append(f"  Position: {entity.start_pos}-{entity.end_pos}")
            report_lines.append(f"  Context: ...{highlighted}...")

    report_lines.append("\n" + "=" * 80)

    return "\n".join(report_lines)


def save_debug_report(text: str, entities: List[PIIEntity], output_path: str) -> None:
    """Save debug report to file.

    Args:
        text: Original text
        entities: List of extracted PII entities
        output_path: Path to save report
    """
    report = generate_match_report(text, entities)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    logger.info(f"Debug report saved to: {output_path}")
