#!/usr/bin/env python3
"""
Demonstration script for the German Clinical Document Anonymization System.

This script shows how to use the anonymization system programmatically.
"""

import json
from pathlib import Path
from src.config import AnonymizationTemplate
from src.zone_anonymizer import ZoneBasedAnonymizer
from src.date_shifter import DateShifter


def demonstrate_anonymization():
    """Demonstrate the anonymization workflow."""
    
    print("=" * 70)
    print("German Clinical Document Anonymization - Demonstration")
    print("=" * 70)
    print()
    
    # Load template
    template_path = "templates/german_clinical_default.json"
    print(f"1. Loading anonymization template: {template_path}")
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template_data = json.load(f)
    
    config = AnonymizationTemplate(**template_data)
    print(f"   ✓ Template loaded: {config.template_name} v{config.version}")
    print()
    
    # Show configured zones
    print("2. Configured anonymization zones:")
    for zone_name, zone_config in config.zones.items():
        print(f"   - {zone_name}: {zone_config.redaction} redaction")
        if zone_config.keywords:
            print(f"     Keywords: {', '.join(zone_config.keywords[:3])}...")
    print()
    
    # Show PII patterns
    print("3. Configured PII patterns:")
    for pattern_name, pattern_config in config.structured_patterns.items():
        print(f"   - {pattern_name}: {pattern_config.type or 'multiple groups'}")
        if pattern_config.context_trigger:
            print(f"     Context: '{pattern_config.context_trigger}'")
    print()
    
    # Initialize components
    print("4. Initializing anonymization components:")
    date_shifter = DateShifter(shift_days=10)
    print(f"   ✓ Date shifter ready (offset: {date_shifter.get_shift_days()} days)")
    
    anonymizer = ZoneBasedAnonymizer(config, date_shifter)
    print(f"   ✓ Zone anonymizer ready")
    print()
    
    # Check for sample PDF
    sample_pdf = "tests/fixtures/sample_arztbrief.pdf"
    if Path(sample_pdf).exists():
        print(f"5. Sample PDF found: {sample_pdf}")
        print("   To anonymize this file, run:")
        print(f"   python src/main.py {sample_pdf} --output anonymized.pdf --shift-days 10")
        print()
        
        # Anonymize the sample
        print("6. Anonymizing sample PDF...")
        output_path = "/tmp/demo_anonymized.pdf"
        stats = anonymizer.anonymize_pdf(sample_pdf, output_path)
        
        print("   ✓ Anonymization completed!")
        print(f"   - Pages processed: {stats['total_pages']}")
        print(f"   - Zones redacted: {stats['zones_redacted']}")
        print(f"   - PII entities found: {stats['pii_entities_found']}")
        print(f"   - Dates shifted: {stats['dates_shifted']}")
        print(f"   - Output saved to: {output_path}")
        print()
    else:
        print(f"5. Sample PDF not found at: {sample_pdf}")
        print("   Create one with: python -c 'from tests.test_zone_anonymizer import *; ...'")
        print()
    
    # Show what is NOT anonymized
    print("7. Medical terminology preservation:")
    print("   The following types of content are NEVER anonymized:")
    print("   ✓ Disease names (Hypertonie, Diabetes, MRSA, etc.)")
    print("   ✓ Medication names (Ramipril, Metformin, etc.)")
    print("   ✓ Medical abbreviations (NYHA, EKG, etc.)")
    print("   ✓ Lab values and measurements")
    print("   ✓ Treatment descriptions")
    print()
    
    print("=" * 70)
    print("Demonstration complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Try with your own PDFs: python src/main.py <your-file.pdf>")
    print("  2. Customize templates: edit templates/german_clinical_default.json")
    print("  3. Run tests: pytest tests/ -v")
    print("  4. Build Docker image: ./build-docker.sh")
    print()


if __name__ == '__main__':
    demonstrate_anonymization()
