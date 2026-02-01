"""Preview generator for PDF anonymization zones."""

import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import io
from typing import BinaryIO


def create_preview_with_zones(
    pdf_file: BinaryIO,
    header_height: int,
    footer_height: int
) -> Image.Image:
    """
    Create a preview image of the first PDF page with drawn redaction zones.
    
    Args:
        pdf_file: Uploaded PDF file (Streamlit UploadedFile or file-like object)
        header_height: Header height in pixels (from top)
        footer_height: Footer height in pixels (from bottom)
    
    Returns:
        PIL Image with drawn zones (header=blue, footer=orange)
    """
    # Read PDF bytes and reset file pointer for later use
    pdf_bytes = pdf_file.read()
    pdf_file.seek(0)
    
    # Open PDF document
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]  # First page
    
    # Render PDF page as image (2x zoom = ~144 DPI for good preview quality)
    zoom = 2
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    
    # Convert to PIL Image
    img_data = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_data))
    
    # Create overlay for zones
    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Get page dimensions
    page_height = pix.height
    page_width = pix.width
    
    # Standard A4 height in PDF points
    A4_HEIGHT_POINTS = 842
    
    # Calculate actual PDF page height in points
    pdf_page_height = page.rect.height
    
    # Scale header height from "pixels" (assumed A4) to actual render pixels
    # User provides height in terms of A4 points, we need to scale to rendered image
    scale_factor = page_height / pdf_page_height
    header_y_end = int(header_height * scale_factor)
    footer_y_start = page_height - int(footer_height * scale_factor)
    
    # Draw header zone (blue)
    if header_height > 0:
        draw.rectangle(
            [(0, 0), (page_width, header_y_end)],
            fill=(0, 100, 255, 80),  # Blue with transparency
            outline=(0, 100, 255, 200),
            width=3
        )
    
    # Draw footer zone (orange)
    if footer_height > 0:
        draw.rectangle(
            [(0, footer_y_start), (page_width, page_height)],
            fill=(255, 140, 0, 80),  # Orange with transparency
            outline=(255, 140, 0, 200),
            width=3
        )
    
    # Combine original image with overlay
    result = Image.alpha_composite(img.convert('RGBA'), overlay)
    
    doc.close()
    
    return result.convert('RGB')
