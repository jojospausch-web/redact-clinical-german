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
import shutil
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


def _safe_rmtree(path) -> None:
    """Best-effort recursive delete. Swallows errors but logs them."""
    if not path:
        return
    p = Path(path)
    if not p.exists():
        return
    try:
        shutil.rmtree(p, ignore_errors=False)
    except OSError as exc:
        logger.warning("Konnte Temp-Verzeichnis '%s' nicht entfernen: %s", p, exc)


def _safe_unlink(path) -> None:
    if not path:
        return
    p = Path(path)
    if not p.exists():
        return
    try:
        p.unlink()
    except OSError as exc:
        logger.warning("Konnte Temp-Datei '%s' nicht entfernen: %s", p, exc)

def _find_trigger_y_in_page(page, trigger: str):
    """Return topmost y0 of `trigger` on `page` (PDF points), or None.

    Mirrors `ZoneBasedAnonymizer._find_trigger_y` so the preview shows the
    exact same line the redaction would use. Robust against non-breaking
    spaces and word-tokenisation quirks.
    """
    if not trigger:
        return None
    instances = page.search_for(trigger)
    if instances:
        return min(inst.y0 for inst in instances)

    trigger_tokens = trigger.split()
    if not trigger_tokens:
        return None
    words = page.get_text("words")
    n = len(trigger_tokens)
    if n > len(words):
        return None
    for i in range(len(words) - n + 1):
        if all(words[i + j][4] == trigger_tokens[j] for j in range(n)):
            return min(words[i + j][1] for j in range(n))
    lower_tokens = [t.lower() for t in trigger_tokens]
    for i in range(len(words) - n + 1):
        if all(words[i + j][4].lower() == lower_tokens[j] for j in range(n)):
            return min(words[i + j][1] for j in range(n))
    return None


def create_preview_with_zones(
    pdf_file,
    header_page1: int,
    footer_page1: int,
    footer_other: int,
    header_until_keyword: dict = None,
) -> "tuple[Image.Image, dict]":
    """Erstellt Vorschau mit eingezeichneten Zonen.

    Args:
        pdf_file: Uploaded PDF file object
        header_page1: Height of header zone in PDF points from top (Page 1)
        footer_page1: Height of footer zone in PDF points from bottom (Page 1)
        footer_other: Height of footer zone in PDF points from bottom (Pages 2+)
        header_until_keyword: Optional `{"enabled": bool, "triggers": [str, ...]}`
            config. When enabled, the topmost matching trigger on the first
            page is highlighted in magenta.

    Returns:
        (preview_image, info_dict) where info_dict carries diagnostic data
        for the UI (e.g. which trigger was matched, or that no trigger was
        found).
    """
    info = {"trigger_hit": None, "trigger_y_pt": None, "triggers_searched": []}

    pdf_bytes = pdf_file.read()
    try:
        pdf_file.seek(0)
    except (AttributeError, io.UnsupportedOperation):
        pass

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]

    zoom = 2
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_data))

    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    page_height_px = pix.height
    page_width_px = pix.width
    # Scale factor from PDF points to preview pixels
    page_height_pt = page.rect.height or 842
    pt_to_px = page_height_px / page_height_pt

    # Header zone (blue) — y=0..header_page1 in PDF points
    header_y_end = int(header_page1 * pt_to_px)
    draw.rectangle(
        [(0, 0), (page_width_px, header_y_end)],
        fill=(0, 100, 255, 80),
        outline=(0, 100, 255, 200),
        width=3,
    )

    # Footer page 1 (orange) — bottom-aligned strip of `footer_page1` pt
    footer1_y_start = page_height_px - int(footer_page1 * pt_to_px)
    draw.rectangle(
        [(0, footer1_y_start), (page_width_px, page_height_px)],
        fill=(255, 140, 0, 80),
        outline=(255, 140, 0, 200),
        width=3,
    )

    # Footer pages 2+ (green) — bottom-aligned strip of `footer_other` pt
    footer_other_y_start = page_height_px - int(footer_other * pt_to_px)
    draw.rectangle(
        [(0, footer_other_y_start), (page_width_px, page_height_px)],
        fill=(0, 200, 0, 40),
        outline=(0, 160, 0, 200),
        width=2,
    )

    # Header-until-keyword zone (magenta) — only if enabled and a trigger hits
    if header_until_keyword and header_until_keyword.get("enabled"):
        triggers = [t for t in header_until_keyword.get("triggers", []) if t]
        info["triggers_searched"] = triggers
        candidates = []
        for trigger in triggers:
            y_pt = _find_trigger_y_in_page(page, trigger)
            if y_pt is not None:
                candidates.append((y_pt, trigger))
        if candidates:
            trigger_y_pt, hit = min(candidates, key=lambda c: c[0])
            info["trigger_hit"] = hit
            info["trigger_y_pt"] = trigger_y_pt
            trigger_y_px = int(trigger_y_pt * pt_to_px)
            # Hatched magenta zone from page top down to the trigger line
            draw.rectangle(
                [(0, 0), (page_width_px, trigger_y_px)],
                fill=(200, 0, 200, 60),
                outline=(180, 0, 180, 220),
                width=3,
            )
            # Draw the trigger baseline as a thick line for orientation
            draw.line(
                [(0, trigger_y_px), (page_width_px, trigger_y_px)],
                fill=(180, 0, 180, 255),
                width=3,
            )

    # Font selection (one source of truth)
    from PIL import ImageFont
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
        "/System/Library/Fonts/Helvetica.ttc",              # macOS
        "C:\\Windows\\Fonts\\arial.ttf",                    # Windows
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

    draw.text((10, 10), f"Header: {header_page1}pt", fill=(0, 100, 255, 255), font=font)
    draw.text((10, page_height_px - 30), f"Footer Seite 1: {footer_page1}pt", fill=(255, 140, 0, 255), font=font)
    draw.text((10, page_height_px - 60), f"Footer Seite 2+: {footer_other}pt", fill=(0, 200, 0, 255), font=font)
    if info["trigger_hit"]:
        draw.text(
            (10, max(40, int(info["trigger_y_pt"] * pt_to_px) - 22)),
            f"Header bis Keyword: '{info['trigger_hit']}'",
            fill=(180, 0, 180, 255),
            font=font,
        )

    result = Image.alpha_composite(img.convert('RGBA'), overlay)
    doc.close()
    return result.convert('RGB'), info


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
    "🟣 **Magenta** = Header bis Keyword (variable Höhe) | "
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
        for r in st.session_state.get('results', []):
            _safe_rmtree(r.get('temp_dir'))  # legacy entries (if any)
        _safe_unlink(st.session_state.pop('tpl_temp_path', None))
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

# When the user picks a different template, push that template's state into
# the sidebar widget keys. Without this, Streamlit keeps showing the inputs
# from the previous template (key= wins over value= after the first render).
_DEFAULT_HUK_TRIGGERS = [
    "Sehr geehrte Kollegin",
    "Sehr geehrter Kollege",
    "Sehr geehrter Herr Kollege",
    "Untersucher",
    "Herzkatheterbriefe",
    "Arztbrief",
]


def _sync_sidebar_to_template(tpl: dict) -> None:
    huk = tpl.get("header_until_keyword") or {}
    st.session_state["sb_huk_enabled"] = bool(huk.get("enabled", False))
    st.session_state["sb_huk_triggers"] = "\n".join(
        huk.get("triggers") or _DEFAULT_HUK_TRIGGERS
    )
    st.session_state["sb_bl_exact"] = "\n".join(tpl.get("blacklist_exact") or [])


if st.session_state.get("_active_template_name") != selected_template:
    _sync_sidebar_to_template(user_tpl)
    st.session_state["_active_template_name"] = selected_template

# ── Sidebar: header-until-keyword + blacklist ─────────────────────────────────

with st.sidebar:
    st.divider()

    # ── Header bis Keyword (variable Header-Höhe) ─────────────────────────────
    st.header("🟣 Header bis Keyword")
    huk_enabled = st.checkbox(
        "Aktivieren",
        help=(
            "Schwärzt alles ÜBER dem ersten gefundenen Keyword (z.B. 'Untersucher', "
            "'Sehr geehrte Kollegin'). Nützlich für Header mit variabler Höhe."
        ),
        key="sb_huk_enabled",
    )
    huk_triggers_raw = st.text_area(
        "Trigger-Keywords (einer pro Zeile)",
        height=120,
        help="Es gewinnt das oberste Vorkommen auf der Seite — Reihenfolge ist egal.",
        key="sb_huk_triggers",
        disabled=not huk_enabled,
    )
    huk_triggers = [t.strip() for t in huk_triggers_raw.splitlines() if t.strip()]
    header_until_keyword_runtime = {
        "enabled": huk_enabled,
        "triggers": huk_triggers,
    }

    st.divider()

    # ── Blacklist (exact, case-sensitive) ─────────────────────────────────────
    st.header("🚫 Blacklist (exakt)")

    blacklist_input = st.text_area(
        "Begriffe/Phrasen (eine pro Zeile)",
        height=120,
        help=(
            "Groß-/Kleinschreibung wird beachtet. Ganze Wörter/Phrasen werden geschwärzt.\n"
            "Beispiel: 'UMG' schwärzt 'UMG', aber nicht 'Umgeben'."
        ),
        key="sb_bl_exact",
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
        preview_image, preview_info = create_preview_with_zones(
            pdf_file=uploaded_files[0],
            header_page1=header_page1,
            footer_page1=footer_page1,
            footer_other=footer_other,
            header_until_keyword=header_until_keyword_runtime,
        )

        st.image(preview_image, caption=f"Vorschau: {uploaded_files[0].name}", use_container_width=True)

        legend = (
            f"🔵 **Header Seite 1** ({header_page1}pt) | "
            f"🟠 **Footer Seite 1** ({footer_page1}pt) | "
            f"🟢 **Footer Folgeseiten** ({footer_other}pt)"
        )
        if header_until_keyword_runtime["enabled"]:
            if preview_info["trigger_hit"]:
                legend += (
                    f" | 🟣 **Header bis Keyword** — Trigger gefunden: "
                    f"`{preview_info['trigger_hit']}` bei y={preview_info['trigger_y_pt']:.0f}pt"
                )
            else:
                legend += " | 🟣 **Header bis Keyword** — kein Trigger auf Seite 1 gefunden"
        st.info(legend)

        if (
            header_until_keyword_runtime["enabled"]
            and not preview_info["trigger_hit"]
            and preview_info["triggers_searched"]
        ):
            st.warning(
                "⚠️ Keiner der konfigurierten Trigger ("
                + ", ".join(f"`{t}`" for t in preview_info["triggers_searched"])
                + ") wurde auf Seite 1 gefunden. Auf dieser Seite wird KEIN "
                "Header-bis-Keyword-Bereich geschwärzt. Bitte Schreibweise prüfen."
            )
    except Exception as e:
        st.warning(f"⚠️ Vorschau konnte nicht erstellt werden: {str(e)}")

    # ======= ANONYMISIERUNG =======
    st.header("🚀 Anonymisierung")

    # Batch processing button and logic (consolidated in same block)
    if st.button("🚀 Anonymisierung starten", type="primary", use_container_width=True):
        # Drop in-memory bytes from previous runs (Temp-Dirs were cleaned up
        # right after their previous run already).
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
            header_until_keyword=header_until_keyword_runtime,
            blacklist_exact=blacklist_entries
        )

        # Per-session temp template file (avoids collisions between parallel
        # Streamlit tabs / users).
        if 'tpl_temp_path' not in st.session_state:
            tpl_fd, tpl_path = tempfile.mkstemp(prefix='redact_tpl_', suffix='.json')
            os.close(tpl_fd)
            st.session_state['tpl_temp_path'] = tpl_path
        temp_template_path = Path(st.session_state['tpl_temp_path'])
        with open(temp_template_path, 'w', encoding='utf-8') as f:
            json.dump(custom_template, f, indent=2, ensure_ascii=False)

        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()

        results = []
        total = len(uploaded_files)

        for idx, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"Verarbeite {uploaded_file.name} ({idx+1}/{total})...")

            safe_filename = re.sub(r'[^\w\s.-]', '_', uploaded_file.name)
            safe_filename = os.path.basename(safe_filename)

            temp_dir = tempfile.mkdtemp(prefix='redact_')
            try:
                temp_input = Path(temp_dir) / safe_filename
                temp_input.write_bytes(uploaded_file.read())

                temp_output_dir = Path(temp_dir) / "output"
                temp_output_dir.mkdir(parents=True, exist_ok=True)
                temp_output = temp_output_dir / f"anonymized_{safe_filename}"

                try:
                    result = anonymize_pdf(
                        input_path=str(temp_input),
                        template_path=str(temp_template_path),
                        output_path=str(temp_output),
                        extract_images=extract_images
                    )
                except Exception as e:
                    logger.error(f"Error processing {uploaded_file.name}: {e}")
                    st.error(f"❌ Fehler bei {uploaded_file.name}: {str(e)}")
                    continue

                # Load the produced artefacts into memory so we can throw the
                # disk copies away straight away — no leftover Temp-Dirs.
                anonymized_bytes = Path(result['output_pdf']).read_bytes()
                image_blobs = []
                for img_path in result.get('images', []):
                    try:
                        image_blobs.append({
                            'name': Path(img_path).name,
                            'bytes': Path(img_path).read_bytes(),
                        })
                    except OSError as exc:
                        logger.warning("Konnte Bild '%s' nicht lesen: %s", img_path, exc)

                results.append({
                    'original_name': uploaded_file.name,
                    'safe_filename': safe_filename,
                    'pdf_bytes': anonymized_bytes,
                    'image_blobs': image_blobs,
                    'stats': result.get('stats', {}),
                })
                logger.info(f"Successfully processed {uploaded_file.name}")

            finally:
                # Always wipe the per-file Temp-Dir, success or failure.
                _safe_rmtree(temp_dir)

            progress_bar.progress((idx + 1) / total)

        status_text.text("✅ Fertig!")
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

            st.download_button(
                label="📄 PDF",
                data=result['pdf_bytes'],
                file_name=f"anonymized_{result['original_name']}",
                mime="application/pdf",
                key=f"pdf_{idx}",
            )

            stats = result['stats']
            st.caption(f"Seiten: {stats.get('total_pages', 0)}")
            st.caption(f"PII gefunden: {stats.get('pii_entities_found', 0)}")
            st.caption(f"Zonen redaktiert: {stats.get('zones_redacted', 0)}")

    # Bulk ZIP download
    st.subheader("📦 Alle als ZIP herunterladen")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for result in st.session_state['results']:
            zip_file.writestr(
                f"anonymized_{result['original_name']}",
                result['pdf_bytes'],
            )
            for img_idx, blob in enumerate(result.get('image_blobs', [])):
                zip_file.writestr(
                    f"images/{result['original_name']}_image_{img_idx}.png",
                    blob['bytes'],
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
            anon_text = extract_text_from_pdf(result['pdf_bytes'])
        except Exception as exc:
            logger.warning(
                "Excel export: failed to extract text from '%s': %s",
                result['original_name'],
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
