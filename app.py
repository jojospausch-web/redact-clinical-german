#!/usr/bin/env python3
"""
Streamlit Web UI for German Clinical Document Anonymization.

This provides a user-friendly web interface for batch upload and download
of anonymized medical documents (PDFs).
"""

import streamlit as st
from pathlib import Path
import zipfile
import io
import logging
import sys
import tempfile
import os
import re
import json
import fitz  # PyMuPDF
from PIL import Image, ImageDraw

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.main import anonymize_pdf

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Redact Clinical German",
    page_icon="🏥",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'results' not in st.session_state:
    st.session_state['results'] = []

# Title and description
st.title("🏥 Redact Clinical German")
st.markdown("**Anonymisierung deutscher medizinischer Arztbriefe**")

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Einstellungen")
    
    template_file = st.selectbox(
        "Template auswählen",
        ["templates/german_clinical_default.json"],
        help="Anonymisierungs-Regeln"
    )
    
    shift_days = st.slider(
        "Datums-Shift (Tage)",
        min_value=-90,
        max_value=90,
        value=0,
        help="Positive Werte = Zukunft, Negative = Vergangenheit, 0 = zufällig"
    )
    
    extract_images = st.checkbox(
        "Bilder extrahieren",
        value=True,
        help="Bilder separat speichern und anonymisieren"
    )
    
    st.divider()
    
    # Clear results button
    if st.button("🗑️ Ergebnisse löschen"):
        st.session_state['results'] = []
        st.rerun()

# File upload
uploaded_files = st.file_uploader(
    "📂 Arztbriefe hochladen (PDF)",
    type=['pdf'],
    accept_multiple_files=True,
    help="Sie können mehrere PDF-Dateien gleichzeitig hochladen"
)

if uploaded_files:
    st.success(f"✅ {len(uploaded_files)} Datei(en) hochgeladen")
    
    # ======= ZONEN-KONFIGURATION =======
    st.header("⚙️ Zonen-Einstellungen")
    st.markdown("**Passen Sie die Schwärzungs-Bereiche individuell an**")
    
    # ======= SEITE 1 (TITELSEITE) =======
    st.subheader("📄 Seite 1 (Titelseite)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Header-Bereich**")
        header_page1 = st.slider(
            "Header-Höhe (Pixel von oben)",
            min_value=0,
            max_value=400,
            value=280,
            step=10,
            key="header_p1",
            help="Kompletter schwarzer Block oben (inkl. Logos, Adressen, Datum)"
        )
        st.info("🔲 Komplett geschwärzt (keine Logo-Erhaltung)")
    
    with col2:
        st.markdown("**Footer-Bereich**")
        footer_page1 = st.slider(
            "Footer-Höhe (Pixel von unten)",
            min_value=0,
            max_value=150,
            value=35,
            step=5,
            key="footer_p1",
            help="Nur die unterste Zeile mit IBAN/Bankdaten"
        )
        st.info("🔲 Komplett geschwärzt")
    
    st.divider()
    
    # ======= FOLGESEITEN (2+) =======
    st.subheader("📄 Folgeseiten (Seite 2, 3, ...)")
    
    footer_other = st.slider(
        "Footer-Höhe (Pixel von unten)",
        min_value=0,
        max_value=150,
        value=80,
        step=5,
        key="footer_other",
        help="Höher als Seite 1, um Name + Geburtsdatum in Fußzeile zu erfassen"
    )
    st.info("🔲 Erfasst: 'Alexander Brügge, *01.01.1960, Seite 2'")
    
    st.divider()
    
    # ======= SIGNATUR-BLOCK =======
    st.subheader("✍️ Signatur-Block")
    
    signature_block_height = st.slider(
        "Höhe nach 'Mit freundlichen Grüßen' (Pixel)",
        min_value=0,
        max_value=100,
        value=40,
        step=5,
        key="signature_block",
        help="Schwärzt kompletten Block unter der Grußformel (alle Arzt-Namen)"
    )
    st.info("✅ Erfasst alle Namen, auch mehrere Ärzte")
    
    # ======= LIVE-VORSCHAU =======
    st.header("📄 Vorschau mit Schwärzungs-Bereichen")
    
    try:
        preview_image = create_preview_with_zones(
            pdf_file=uploaded_files[0],
            header_page1=header_page1,
            footer_page1=footer_page1,
            footer_other=footer_other
        )
        
        st.image(preview_image, caption=f"Vorschau: {uploaded_files[0].name}", use_column_width=True)
        
        st.info(f"🔵 **Blauer Bereich** = Header Seite 1 ({header_page1}px von oben) | "
                f"🟠 **Oranger Bereich** = Footer Seite 1 ({footer_page1}px von unten) | "
                f"🟢 **Grüner Text** = Footer Folgeseiten ({footer_other}px)")
    except Exception as e:
        st.warning(f"⚠️ Vorschau konnte nicht erstellt werden: {str(e)}")
    
    # ======= ANONYMISIERUNG =======
    st.header("🚀 Anonymisierung")
    
    # Batch processing button and logic (consolidated in same block)
    if st.button("🚀 Anonymisierung starten", type="primary", use_container_width=True):
        # Clear previous results
        st.session_state['results'] = []
        
        # Create custom template from user settings
        custom_template = create_custom_template(
            header_page1=header_page1,
            footer_page1=footer_page1,
            footer_other=footer_other,
            signature_block_height=signature_block_height,
            shift_days=shift_days
        )
        
        # Save custom template to temp file
        temp_template_path = Path(tempfile.gettempdir()) / "custom_template.json"
        with open(temp_template_path, 'w', encoding='utf-8') as f:
            json.dump(custom_template, f, indent=2, ensure_ascii=False)
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        total = len(uploaded_files)
        
        for idx, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"Verarbeite {uploaded_file.name} ({idx+1}/{total})...")
            
            # Sanitize filename to prevent path traversal attacks
            safe_filename = re.sub(r'[^\w\s.-]', '_', uploaded_file.name)
            safe_filename = os.path.basename(safe_filename)  # Remove any path components
            
            # Create unique temporary directory for this file
            temp_dir = tempfile.mkdtemp(prefix='redact_')
            temp_input = Path(temp_dir) / safe_filename
            temp_input.write_bytes(uploaded_file.read())
            
            # Create temp output directory
            temp_output_dir = Path(temp_dir) / "output"
            temp_output_dir.mkdir(parents=True, exist_ok=True)
            temp_output = temp_output_dir / f"anonymized_{safe_filename}"
            
            # Call anonymization
            try:
                # shift_days: 0 means random shift (None triggers random behavior in backend)
                result = anonymize_pdf(
                    input_path=str(temp_input),
                    template_path=str(temp_template_path),
                    output_path=str(temp_output),
                    shift_days=shift_days if shift_days != 0 else None,
                    extract_images=extract_images
                )
                
                results.append({
                    'original_name': uploaded_file.name,
                    'anonymized_pdf': result['output_pdf'],
                    'images': result.get('images', []),
                    'stats': result.get('stats', {})
                })
                
                logger.info(f"Successfully processed {uploaded_file.name}")
                
            except Exception as e:
                logger.error(f"Error processing {uploaded_file.name}: {e}")
                st.error(f"❌ Fehler bei {uploaded_file.name}: {str(e)}")
            
            # Update progress
            progress_bar.progress((idx + 1) / total)
        
        status_text.text("✅ Fertig!")
        
        # Store results in session state
        st.session_state['results'] = results

# Download section
if 'results' in st.session_state and st.session_state['results']:
    st.success(f"✅ {len(st.session_state['results'])} Dateien erfolgreich anonymisiert!")
    
    # Individual downloads
    st.subheader("📥 Einzelne Dateien herunterladen")
    
    cols = st.columns(3)
    for idx, result in enumerate(st.session_state['results']):
        col = cols[idx % 3]
        with col:
            st.markdown(f"**{result['original_name']}**")
            
            # PDF download
            with open(result['anonymized_pdf'], 'rb') as f:
                st.download_button(
                    label="📄 PDF",
                    data=f.read(),
                    file_name=f"anonymized_{result['original_name']}",
                    mime="application/pdf",
                    key=f"pdf_{idx}"
                )
            
            # Stats
            stats = result['stats']
            st.caption(f"Seiten: {stats.get('total_pages', 0)}")
            st.caption(f"PII gefunden: {stats.get('pii_entities_found', 0)}")
            st.caption(f"Zonen redaktiert: {stats.get('zones_redacted', 0)}")
    
    # Bulk ZIP download
    st.subheader("📦 Alle als ZIP herunterladen")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for result in st.session_state['results']:
            # Add PDF
            with open(result['anonymized_pdf'], 'rb') as f:
                zip_file.writestr(
                    f"anonymized_{result['original_name']}",
                    f.read()
                )
            
            # Add images if any
            for img_idx, img_path in enumerate(result['images']):
                with open(img_path, 'rb') as f:
                    zip_file.writestr(
                        f"images/{result['original_name']}_image_{img_idx}.png",
                        f.read()
                    )
    
    st.download_button(
        label="📦 Alle Dateien als ZIP herunterladen",
        data=zip_buffer.getvalue(),
        file_name="anonymized_batch.zip",
        mime="application/zip"
    )

# Info section when no files uploaded
if not uploaded_files:
    st.info("""
    ### 📋 Anleitung
    
    1. **Hochladen**: Wählen Sie eine oder mehrere PDF-Dateien aus
    2. **Konfigurieren**: Passen Sie die Einstellungen in der Sidebar an
    3. **Starten**: Klicken Sie auf "Anonymisierung starten"
    4. **Herunterladen**: Laden Sie einzelne Dateien oder alle als ZIP herunter
    
    ### ✨ Features
    
    - ✅ Mehrere PDFs gleichzeitig hochladen
    - ✅ Batch-Verarbeitung mit Live-Progress
    - ✅ Einzeldownload jeder anonymisierten Datei
    - ✅ ZIP-Download aller Dateien auf einmal
    - ✅ Konfigurierbare Anonymisierung
    - ✅ Statistiken pro Datei
    """)


def create_preview_with_zones(pdf_file, header_page1: int, footer_page1: int, footer_other: int) -> Image.Image:
    """Erstellt Vorschau mit eingezeichneten Zonen.
    
    Args:
        pdf_file: Uploaded PDF file object
        header_page1: Height of header zone in pixels from top (Page 1)
        footer_page1: Height of footer zone in pixels from bottom (Page 1)
        footer_other: Height of footer zone in pixels from bottom (Pages 2+)
        
    Returns:
        PIL Image with zone overlays
    """
    # Read PDF bytes and handle potential seek issues
    pdf_bytes = pdf_file.read()
    
    # Reset file pointer if possible (for later use by other functions)
    try:
        pdf_file.seek(0)
    except (AttributeError, io.UnsupportedOperation):
        # If seek is not supported, that's okay - we already have the bytes
        pass
    
    # Open PDF with PyMuPDF using the bytes we read
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]  # Get first page
    
    # Render page as image with 2x zoom for better quality
    zoom = 2
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    
    # Convert to PIL Image
    img_data = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_data))
    
    # Create transparent overlay for zones
    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    
    page_height = pix.height
    page_width = pix.width
    
    # PDF coordinates are from bottom, but display is from top
    # header_page1 is from top in PDF points (A4 = 842pt)
    # Scale to actual image pixels
    A4_HEIGHT = 842
    header_y_end = int((header_page1 / A4_HEIGHT) * page_height)
    
    # Draw header zone (blue)
    draw.rectangle(
        [(0, 0), (page_width, header_y_end)],
        fill=(0, 100, 255, 80),
        outline=(0, 100, 255, 200),
        width=3
    )
    
    # Draw footer zone Page 1 (orange)
    footer1_y_start = page_height - int((footer_page1 / A4_HEIGHT) * page_height)
    draw.rectangle(
        [(0, footer1_y_start), (page_width, page_height)],
        fill=(255, 140, 0, 80),
        outline=(255, 140, 0, 200),
        width=3
    )
    
    # Add text overlay for info
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        from PIL import ImageFont
        font = ImageFont.load_default()
    
    draw.text((10, 10), f"Header: {header_page1}px", fill=(0, 100, 255, 255), font=font)
    draw.text((10, page_height - 30), f"Footer Seite 1: {footer_page1}px", fill=(255, 140, 0, 255), font=font)
    draw.text((10, page_height - 60), f"Footer Seite 2+: {footer_other}px", fill=(0, 200, 0, 255), font=font)
    
    # Combine original image with overlay
    result = Image.alpha_composite(img.convert('RGBA'), overlay)
    doc.close()
    
    return result.convert('RGB')


def create_custom_template(
    header_page1: int,
    footer_page1: int,
    footer_other: int,
    signature_block_height: int,
    shift_days: int = 0
) -> dict:
    """Erstellt Template-Dict aus User-Einstellungen mit separaten Zonen für Seite 1 vs. Folgeseiten.
    
    Args:
        header_page1: Header height in pixels from top (Page 1 only)
        footer_page1: Footer height in pixels from bottom (Page 1 only)
        footer_other: Footer height in pixels from bottom (Pages 2+)
        signature_block_height: Height below signature trigger to redact
        shift_days: Days to shift dates (0 = random)
        
    Returns:
        Dictionary with template configuration
    """
    # Load base template
    template_path = Path(__file__).parent / 'templates' / 'german_clinical_default.json'
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template = json.load(f)
    except Exception as e:
        logger.error(f"Error loading template: {e}")
        template = {
            "template_name": "Custom",
            "version": "2.0",
            "zones": {},
            "structured_patterns": {},
            "date_handling": {},
            "pii_mechanisms": {},
            "image_pii_patterns": {}
        }
    
    # A4 page height in points
    A4_HEIGHT = 842
    
    # ======= ZONE 1: HEADER SEITE 1 =======
    template['zones']['header_page_1'] = {
        "page": 1,
        "pages": None,
        "y_start": A4_HEIGHT - header_page1,  # Convert from top to bottom
        "y_end": A4_HEIGHT,
        "redaction": "full",
        "preserve_logos": False  # NO logo preservation!
    }
    
    # ======= ZONE 2: FOOTER SEITE 1 =======
    template['zones']['footer_page_1'] = {
        "page": 1,
        "pages": None,
        "y_start": 0,
        "y_end": footer_page1,
        "redaction": "full",
        "keywords": []  # No keyword search, ALWAYS redact everything
    }
    
    # ======= ZONE 3: FOOTER FOLGESEITEN =======
    template['zones']['footer_other_pages'] = {
        "page": None,
        "pages": "all",
        "exclude_page": 1,  # All EXCEPT page 1
        "y_start": 0,
        "y_end": footer_other,
        "redaction": "full"
    }
    
    # ======= SIGNATUR-BLOCK CONFIG =======
    template['signature_block'] = {
        "enabled": True,
        "trigger": "Mit freundlichen Grüßen",
        "height_below": signature_block_height,
        "redaction": "full"
    }
    
    # ======= SHIFT-DAYS CONFIG =======
    template['shift_days'] = shift_days if shift_days != 0 else None
    
    return template
