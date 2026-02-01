"""CLI entry point for the German clinical document anonymization system."""

import click
import json
import logging
import sys
from pathlib import Path
from pydantic import ValidationError

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


def load_and_validate_template(template_path: str) -> AnonymizationTemplate:
    """
    Load and validate anonymization template with helpful error messages.
    
    Args:
        template_path: Path to the template JSON file
        
    Returns:
        AnonymizationTemplate: Validated template object
        
    Raises:
        FileNotFoundError: If template file doesn't exist
        ValueError: If template validation fails
        json.JSONDecodeError: If JSON is malformed
    """
    if not Path(template_path).exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template_data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in template: {template_path}")
        raise ValueError(
            f"Template '{template_path}' enthält ungültiges JSON.\n"
            f"Fehler in Zeile {e.lineno}, Spalte {e.colno}: {e.msg}"
        )
    
    try:
        validated = AnonymizationTemplate(**template_data)
        logger.debug(f"Template validated: {validated.template_name} v{validated.version}")
        return validated
    except ValidationError as e:
        logger.error(f"Template validation failed: {template_path}")
        logger.error(f"Validation errors:\n{e}")
        
        # Create helpful error message
        error_details = []
        for error in e.errors():
            field = '.'.join(str(x) for x in error['loc'])
            error_details.append(f"  - {field}: {error['msg']}")
        
        raise ValueError(
            f"Template '{template_path}' hat Validierungsfehler.\n"
            f"Bitte prüfe die Struktur:\n" + '\n'.join(error_details)
        )


def anonymize_pdf(
    input_path: str,
    template_path: str = "templates/german_clinical_default.json",
    output_path: str = None,
    shift_days: int = None,
    extract_images: bool = True
) -> dict:
    """
    Python API for anonymizing PDFs (used by Streamlit and other integrations).
    
    Args:
        input_path: Path to input PDF file
        template_path: Path to anonymization template JSON
        output_path: Path for output PDF (auto-generated if None)
        shift_days: Days to shift dates (None for random)
        extract_images: Whether to extract and anonymize images
    
    Returns:
        dict with:
            - output_pdf: Path to anonymized PDF
            - images: List of extracted image paths
            - stats: Statistics (PII found, pages processed, etc.)
    
    Raises:
        FileNotFoundError: If input file or template doesn't exist
        Exception: For other processing errors
    """
    # Auto-generate output path if not provided
    if output_path is None:
        input_path_obj = Path(input_path)
        output_path = str(input_path_obj.parent / f"anonymized_{input_path_obj.name}")
    
    logger.info(f"Starting anonymization of: {input_path}")
    
    # Load and validate anonymization template
    logger.info(f"Loading template: {template_path}")
    config = load_and_validate_template(template_path)
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
    extracted_images = []
    
    if extract_images:
        extract_images_path = str(Path(output_path).parent / "extracted_images")
        logger.info(f"Images will be extracted to: {extract_images_path}")
    
    # Perform anonymization
    logger.info("Starting PDF anonymization...")
    stats = anonymizer.anonymize_pdf(input_path, output_path, extract_images_path)
    
    # Anonymize extracted images if requested
    if extract_images and extract_images_path:
        logger.info("Anonymizing extracted images...")
        image_anonymizer = MedicalImageAnonymizer(config.image_pii_patterns)
        
        # Process extracted images
        extractor = ImageExtractor()
        images = extractor.extract_images(input_path)
        
        anonymized_images_path = Path(extract_images_path) / "anonymized"
        anonymized_images_path.mkdir(parents=True, exist_ok=True)
        
        for page_num, img_index, img in images:
            anonymized_img, redactions = image_anonymizer.anonymize_image(img)
            anonymized_img_path = anonymized_images_path / f"page{page_num}_img{img_index}_anonymized.png"
            anonymized_img.save(anonymized_img_path)
            extracted_images.append(str(anonymized_img_path))
            
            if redactions:
                logger.debug(f"Redacted {len(redactions)} regions in image {img_index} on page {page_num}")
    
    # Report results
    logger.info("=" * 60)
    logger.info("Anonymization completed successfully!")
    logger.info("=" * 60)
    logger.info(f"Output PDF: {output_path}")
    logger.info(f"Total pages processed: {stats['total_pages']}")
    logger.info(f"Zones redacted: {stats['zones_redacted']}")
    logger.info(f"PII entities found: {stats['pii_entities_found']}")
    logger.info(f"Dates shifted: {stats['dates_shifted']}")
    if extract_images:
        logger.info(f"Images extracted: {stats['images_extracted']}")
    logger.info("=" * 60)
    
    return {
        'output_pdf': output_path,
        'images': extracted_images,
        'stats': stats
    }


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
    
    try:
        result = anonymize_pdf(
            input_path=input_pdf,
            template_path=template,
            output_path=output,
            shift_days=shift_days,
            extract_images=extract_images
        )
        
        click.echo(f"✓ Successfully anonymized {input_pdf}")
        click.echo(f"✓ Output saved to {result['output_pdf']}")
        
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
