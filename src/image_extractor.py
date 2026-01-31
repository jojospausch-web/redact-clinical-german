"""Image extraction from PDF documents."""

import fitz  # PyMuPDF
from PIL import Image
import io
from typing import List, Tuple
from pathlib import Path


class ImageExtractor:
    """Extracts images from PDF documents for separate anonymization."""
    
    def extract_images(self, pdf_path: str, output_dir: str = None) -> List[Tuple[int, int, Image.Image]]:
        """Extract all images from a PDF.
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Optional directory to save extracted images
        
        Returns:
            List of tuples (page_number, image_index, PIL.Image)
        """
        images = []
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)
            
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                # Convert to PIL Image
                pil_image = Image.open(io.BytesIO(image_bytes))
                images.append((page_num, img_index, pil_image))
                
                # Optionally save to disk
                if output_dir:
                    Path(output_dir).mkdir(parents=True, exist_ok=True)
                    image_path = Path(output_dir) / f"page{page_num}_img{img_index}.png"
                    pil_image.save(image_path)
        
        doc.close()
        return images
    
    def get_image_positions(self, pdf_path: str) -> List[dict]:
        """Get position information for all images in the PDF.
        
        Args:
            pdf_path: Path to the PDF file
        
        Returns:
            List of dictionaries with image position information
        """
        positions = []
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)
            
            for img_index, img in enumerate(image_list):
                xref = img[0]
                
                # Get all instances of this image on the page
                for img_rect in page.get_image_rects(xref):
                    positions.append({
                        'page': page_num,
                        'image_index': img_index,
                        'xref': xref,
                        'rect': img_rect,
                        'x0': img_rect.x0,
                        'y0': img_rect.y0,
                        'x1': img_rect.x1,
                        'y1': img_rect.y1,
                    })
        
        doc.close()
        return positions
    
    def is_logo(self, rect: fitz.Rect, page_height: float, header_height: float = 120) -> bool:
        """Determine if an image is likely a logo based on position.
        
        Args:
            rect: Image rectangle
            page_height: Total page height
            header_height: Height of header zone
        
        Returns:
            True if image is in header zone (likely a logo)
        """
        # Check if image is in the header zone
        return rect.y0 < header_height
