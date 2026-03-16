#!/usr/bin/env python3
"""
Streamlit Web UI for German Clinical Document Anonymization.

This provides a user-friendly web interface for batch upload and download
of anonymized medical documents (PDFs).
"""

import streamlit as st
from pathlib import Path
from typing import List
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
from src.excel_exporter import export_to_excel, extract_text_from_pdf
from config.template_manager import (
    list_templates,
    load_template,
    ensure_default_template,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================
# HELPER FUNCTIONS
# ============================================

def create_preview_with_zones(pdf_file, header_page1: int, footer_page1: int, footer_other: int) -> Image.Image:
    """Erstellt Vorschau mit eingezeichneten Zonen.
    
    Args:
        pdf_file: Uploaded PDF file object
        header_page1: Height of header zone in PDF points from top (Page 1)
        footer_page1: Height of footer zone in PDF points from bottom (Page 1)
        footer_other: Height of footer zone in PDF points from bottom (Pages 2+)
        
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
        # Try common font paths across different operating systems
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
            "/System/Library/Fonts/Helvetica.ttc",  # macOS
            "C:\\Windows\\Fonts\\arial.ttf",  # Windows
        ]
        font = None
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, 16)
                break
            except (OSError, IOError):
                continue
        if font is None:
            font = ImageFont.load_default()
    except (OSError, IOError):
        from PIL import ImageFont
        font = ImageFont.load_default()
    
    draw.text((10, 10), f"Header: {header_page1}pt", fill=(0, 100, 255, 255), font=font)
    draw.text((10, page_height - 30), f"Footer Seite 1: {footer_page1}pt", fill=(255, 140, 0, 255), font=font)
    draw.text((10, page_height - 60), f"Footer Seite 2+: {footer_other}pt", fill=(0, 200, 0, 255), font=font)
    
    # Combine original image with overlay
    result = Image.alpha_composite(img.convert('RGBA'), overlay)
    doc.close()
    
    return result.convert('RGB')


def create_custom_template(
    header_page1: int,
    footer_page1: int,
    footer_other: int,
    signature_block_height: int,
    personal_block_height: int = 100,
    header_next: int = 0,
    active_patterns: dict = None,
    whitelist_medical: List[str] = None,
    whitelist_anatomical: List[str] = None,
    whitelist_devices: List[str] = None,
    header_until_keyword: dict = None,
    blacklist_exact: List[str] = None
) -> dict:
    """Erstellt Template-Dict aus User-Einstellungen mit separaten Zonen für Seite 1 vs. Folgeseiten.
    
    Args:
        header_page1: Header height in PDF points from top (Page 1 only)
        footer_page1: Footer height in PDF points from bottom (Page 1 only)
        footer_other: Footer height in PDF points from bottom (Pages 2+)
        signature_block_height: Height below signature trigger to redact in PDF points
        personal_block_height: Height of block redacted after "Personal:" keyword
        whitelist_medical: List of medical terms to exclude from redaction
        whitelist_anatomical: List of anatomical terms to exclude from redaction
        whitelist_devices: List of device/product names to exclude from redaction
        blacklist_exact: Case-sensitive exact-match terms/phrases that are always redacted
        
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
        "y_start": 0,  # Convert from top to bottom
        "y_end": header_page1,
        "redaction": "full",
        "preserve_logos": False  # NO logo preservation!
    }
    
    # ======= ZONE 2: FOOTER SEITE 1 =======
    template['zones']['footer_page_1'] = {
        "page": 1,
        "pages": None,
        "y_start": A4_HEIGHT - footer_page1,
        "y_end": A4_HEIGHT,
        "redaction": "full",
        "keywords": []  # No keyword search, ALWAYS redact everything
    }
    
    # ======= ZONE 3: FOOTER FOLGESEITEN =======
    template['zones']['footer_other_pages'] = {
        "page": None,
        "pages": "all",
        "exclude_page": 1,  # All EXCEPT page 1
        "y_start": A4_HEIGHT - footer_other,
        "y_end": A4_HEIGHT,
        "redaction": "full"
    }
    
    # ======= SIGNATUR-BLOCK CONFIG =======
    template['signature_block'] = {
        "enabled": True,
        "trigger": "Mit freundlichen Grüßen",
        "height_below": signature_block_height,
        "redaction": "full"
    }
    
    # ======= PERSONAL-BLOCK CONFIG =======
    template['personal_block'] = {
        "enabled": True,
        "trigger": "Personal:",
        "height_below": personal_block_height,
        "redaction": "full"
    }
    
    # ======= WHITELIST CONFIG =======
    if whitelist_medical or whitelist_anatomical or whitelist_devices:
        template['whitelist'] = {
            "medical_terms": whitelist_medical or [],
            "anatomical_terms": whitelist_anatomical or [],
            "device_names": whitelist_devices or []
        }

    # ======= HEADER FOLGESEITEN CONFIG =======
    if header_next and header_next > 0:
        template['header_next'] = header_next

    # ======= ACTIVE PATTERNS CONFIG =======
    if active_patterns is not None:
        template['active_patterns'] = active_patterns

    # ======= HEADER-UNTIL-KEYWORD CONFIG =======
    if header_until_keyword is not None:
        template['header_until_keyword'] = header_until_keyword

    # ======= BLACKLIST EXACT CONFIG =======
    if blacklist_exact is not None:
        template['blacklist_exact'] = [e for e in blacklist_exact if e.strip()]

    return template


# ============================================
# STREAMLIT APP CONFIGURATION
# ============================================

# Ensure the default template exists before rendering the UI
ensure_default_template()

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

# ── Zone legend ───────────────────────────────────────────────────────────────

st.info(
    "🔵 **Blau** = Header Seite 1 | "
    "🟠 **Orange** = Footer Seite 1 | "
    "🟢 **Grün** = Footer Folgeseiten | "
    "⬛ **Schwarz** = Signatur-Block & Personal:-Block"
)

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Einstellungen")

    # ── Template selection ────────────────────────────────────────────────────
    available_templates = list_templates()
    selected_template = st.selectbox(
        "📁 Template auswählen",
        options=available_templates if available_templates else ["default"],
        help="Wählen Sie ein gespeichertes Template. Templates können im Template-Editor erstellt werden."
    )

    extract_images = st.checkbox(
        "Bilder extrahieren",
        value=True,
        help="Bilder separat speichern und anonymisieren"
    )

    st.divider()

    # ── Debug mode ────────────────────────────────────────────────────────────
    st.header("⚙️ Debug-Einstellungen")

    debug_mode = st.checkbox(
        "Debug-Logging aktivieren",
        value=False,
        help="Zeigt detaillierte Muster-Match-Informationen in der Konsole an"
    )

    if debug_mode:
        logging.getLogger().setLevel(logging.DEBUG)
        st.success("✅ Debug-Logging aktiviert (Konsole prüfen)")
    else:
        logging.getLogger().setLevel(logging.INFO)

    st.divider()

    st.markdown("💡 **Tipp:** Templates bearbeiten Sie unter\n**📝 Template Editor**")

    st.divider()

    # Clear results button
    if st.button("🗑️ Ergebnisse löschen"):
        st.session_state['results'] = []
        st.rerun()

# ── Load the selected user template ───────────────────────────────────────────

user_tpl = load_template(selected_template)
if user_tpl is None:
    st.warning(f"⚠️ Template '{selected_template}' konnte nicht geladen werden. Standardwerte werden verwendet.")
    user_tpl = {
        "zones": {"header_page1": 380, "footer_page1": 130, "footer_next": 200, "signature": 150, "personal": 100},
        "whitelist": {"medical": [], "anatomical": [], "devices": []}
    }

# ── Blacklist sidebar section (needs user_tpl, so placed after template load) ─

with st.sidebar:
    st.divider()

    # ── Blacklist (exact, case-sensitive) ─────────────────────────────────────
    st.header("🚫 Blacklist (exakt)")

    _bl_default = "\n".join(user_tpl.get("blacklist_exact", []))
    blacklist_input = st.text_area(
        "Begriffe/Phrasen (eine pro Zeile)",
        value=_bl_default,
        height=120,
        help=(
            "Groß-/Kleinschreibung wird beachtet. Ganze Wörter/Phrasen werden geschwärzt.\n"
            "Beispiel: 'UMG' schwärzt 'UMG', aber nicht 'Umgeben'."
        )
    )
    blacklist_entries = [line.strip() for line in blacklist_input.splitlines() if line.strip()]

# ── File upload ────────────────────────────────────────────────────────────────

uploaded_files = st.file_uploader(
    "📂 Arztbriefe hochladen (PDF)",
    type=['pdf'],
    accept_multiple_files=True,
    help="Sie können mehrere PDF-Dateien gleichzeitig hochladen"
)

if uploaded_files:
    st.success(f"✅ {len(uploaded_files)} Datei(en) hochgeladen")

    # ======= LIVE-VORSCHAU =======
    zones = user_tpl.get("zones", {})
    header_page1 = int(zones.get("header_page1", 380))
    footer_page1 = int(zones.get("footer_page1", 130))
    footer_other = int(zones.get("footer_next", 110))

    st.header("📄 Vorschau mit Schwärzungs-Bereichen")

    try:
        preview_image = create_preview_with_zones(
            pdf_file=uploaded_files[0],
            header_page1=header_page1,
            footer_page1=footer_page1,
            footer_other=footer_other
        )

        st.image(preview_image, caption=f"Vorschau: {uploaded_files[0].name}", use_container_width=True)

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

        # Extract settings from user template
        wl = user_tpl.get("whitelist", {})
        medical_terms = wl.get("medical", [])
        anatomical_terms = wl.get("anatomical", [])
        device_names = wl.get("devices", [])
        active_patterns = user_tpl.get("active_patterns", None)

        # Create custom template from user settings
        custom_template = create_custom_template(
            header_page1=header_page1,
            footer_page1=footer_page1,
            footer_other=footer_other,
            signature_block_height=int(zones.get("signature", 150)),
            personal_block_height=int(zones.get("personal", 100)),
            header_next=int(zones.get("header_next", 100)),
            active_patterns=active_patterns,
            whitelist_medical=medical_terms,
            whitelist_anatomical=anatomical_terms,
            whitelist_devices=device_names,
            header_until_keyword=user_tpl.get("header_until_keyword"),
            blacklist_exact=blacklist_entries
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

            # Call anonymization (date shifting is handled internally / randomly)
            try:
                result = anonymize_pdf(
                    input_path=str(temp_input),
                    template_path=str(temp_template_path),
                    output_path=str(temp_output),
                    shift_days=None,  # Always random shift
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

    # Excel download: extract anonymized text from each PDF and bundle into XLSX
    st.subheader("📊 Anonymisierte Texte als Excel herunterladen")
    excel_results = []
    for result in st.session_state['results']:
        try:
            anon_text = extract_text_from_pdf(result['anonymized_pdf'])
        except Exception as exc:
            logger.warning(
                "Excel export: failed to extract text from '%s': %s",
                result['anonymized_pdf'],
                exc,
            )
            anon_text = ""
        excel_results.append({
            "document": result['original_name'],
            "text": anon_text,
        })
    excel_buffer = io.BytesIO()
    export_to_excel(excel_results, excel_buffer)
    st.download_button(
        label="📊 Anonymisierte Texte (Excel)",
        data=excel_buffer.getvalue(),
        file_name="anonymized_texts.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # ── Debug summary (shown when debug mode is active) ───────────────────────
    if debug_mode:
        st.subheader("🔍 Debug: Anonymisierungs-Zusammenfassung")
        st.info(
            "Detaillierte Muster-Match-Informationen wurden in die Konsole geloggt.\n"
            "Suche nach `[MATCH FOUND]`, `[SKIP - BOUNDARY]`, "
            "`[SKIP - WHITELIST]`, `[ENTITY EXTRACTED]` und `[LOCATION MATCH]`."
        )
        for result in st.session_state['results']:
            stats = result['stats']
            pii_count = stats.get('pii_entities_found', 0)
            with st.expander(f"📄 {result['original_name']} — {pii_count} PII-Entität(en) gefunden"):
                st.write(f"**Seiten verarbeitet:** {stats.get('total_pages', 0)}")
                st.write(f"**PII-Entitäten gefunden:** {pii_count}")
                st.write(f"**Zonen geschwärzt:** {stats.get('zones_redacted', 0)}")

# Info section when no files uploaded
if not uploaded_files:
    st.info("""
    ### 📋 Anleitung

    1. **Template wählen**: Wählen Sie ein Template in der Sidebar aus
    2. **Hochladen**: Wählen Sie eine oder mehrere PDF-Dateien aus
    3. **Starten**: Klicken Sie auf "Anonymisierung starten"
    4. **Herunterladen**: Laden Sie einzelne Dateien oder alle als ZIP herunter

    ### ✨ Features

    - ✅ Mehrere PDFs gleichzeitig hochladen
    - ✅ Batch-Verarbeitung mit Live-Progress
    - ✅ Einzeldownload jeder anonymisierten Datei
    - ✅ ZIP-Download aller Dateien auf einmal
    - ✅ Template-basierte Konfiguration
    - ✅ Statistiken pro Datei
    """)
