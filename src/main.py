"""CLI entry point for the German clinical document anonymization system."""

import click
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import AnonymizationTemplate
from src.zone_anonymizer import ZoneBasedAnonymizer
from src.date_shifter import DateShifter
from src.image_anonymizer import MedicalImageAnonymizer
from src.image_extractor import ImageExtractor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.command()
@click.argument('input_pdf', type=click.Path(exists=True))
@click.option('--output', '-o', default='anonymized.pdf', help='Output PDF path')
@click.option(
    '--template', '-t',
    default='templates/german_clinical_default.json',
    help='Path to anonymization rules template'
)
@click.option(
    '--extract-images',
    is_flag=True,
    help='Extract images to separate folder'
)
@click.option(
    '--shift-days',
    default=None,
    type=int,
    help='Days to shift dates (default: random -30 to +30)'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Enable verbose logging'
)
def anonymize(input_pdf, output, template, extract_images, shift_days, verbose):
    """Anonymize German medical doctor letters (Arztbriefe).
    
    This tool uses a zone-based approach with structured PII extraction
    to anonymize clinical documents while preserving medical terminology.
    
    Example:
        redact-clinical input.pdf --output anonymized.pdf
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info(f"Starting anonymization of: {input_pdf}")
    
    try:
        # Load anonymization template
        logger.info(f"Loading template: {template}")
        with open(template, 'r', encoding='utf-8') as f:
            template_data = json.load(f)
        
        # Validate and parse template
        config = AnonymizationTemplate(**template_data)
        logger.info(f"Loaded template: {config.template_name} v{config.version}")
        
        # Initialize date shifter
        shift_range = (-30, 30)
        if 'birthdate' in config.date_handling:
            shift_range = config.date_handling['birthdate'].shift_days_range or shift_range
        
        date_shifter = DateShifter(shift_days=shift_days, shift_range=shift_range)
        logger.info(f"Date shifter initialized with offset: {date_shifter.get_shift_days()} days")
        
        # Initialize anonymizer
        anonymizer = ZoneBasedAnonymizer(config, date_shifter)
        
        # Determine image extraction path
        extract_images_path = None
        if extract_images:
            extract_images_path = str(Path(output).parent / "extracted_images")
            logger.info(f"Images will be extracted to: {extract_images_path}")
        
        # Perform anonymization
        logger.info("Starting PDF anonymization...")
        stats = anonymizer.anonymize_pdf(input_pdf, output, extract_images_path)
        
        # Anonymize extracted images if requested
        if extract_images and extract_images_path:
            logger.info("Anonymizing extracted images...")
            image_anonymizer = MedicalImageAnonymizer(config.image_pii_patterns)
            
            # Process extracted images
            extractor = ImageExtractor()
            images = extractor.extract_images(input_pdf)
            
            anonymized_images_path = Path(extract_images_path) / "anonymized"
            anonymized_images_path.mkdir(parents=True, exist_ok=True)
            
            for page_num, img_index, img in images:
                anonymized_img, redactions = image_anonymizer.anonymize_image(img)
                output_path = anonymized_images_path / f"page{page_num}_img{img_index}_anonymized.png"
                anonymized_img.save(output_path)
                
                if redactions:
                    logger.debug(f"Redacted {len(redactions)} regions in image {img_index} on page {page_num}")
        
        # Report results
        logger.info("=" * 60)
        logger.info("Anonymization completed successfully!")
        logger.info("=" * 60)
        logger.info(f"Output PDF: {output}")
        logger.info(f"Total pages processed: {stats['total_pages']}")
        logger.info(f"Zones redacted: {stats['zones_redacted']}")
        logger.info(f"PII entities found: {stats['pii_entities_found']}")
        logger.info(f"Dates shifted: {stats['dates_shifted']}")
        if extract_images:
            logger.info(f"Images extracted: {stats['images_extracted']}")
        logger.info("=" * 60)
        
        click.echo(f"✓ Successfully anonymized {input_pdf}")
        click.echo(f"✓ Output saved to {output}")
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
    
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in template file: {e}")
        click.echo(f"Error: Invalid template JSON: {e}", err=True)
        raise click.Abort()
    
    except Exception as e:
        logger.error(f"Anonymization failed: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


if __name__ == '__main__':
    anonymize()
