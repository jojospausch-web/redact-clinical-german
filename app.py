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

# Batch processing
if uploaded_files:
    if st.button("🚀 Anonymisierung starten", type="primary"):
        # Clear previous results
        st.session_state['results'] = []
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        total = len(uploaded_files)
        
        for idx, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"Verarbeite {uploaded_file.name} ({idx+1}/{total})...")
            
            # Save uploaded file temporarily
            temp_input = Path(f"/tmp/{uploaded_file.name}")
            temp_input.write_bytes(uploaded_file.read())
            
            # Create temp output directory
            temp_output_dir = Path(f"/tmp/output_{idx}")
            temp_output_dir.mkdir(parents=True, exist_ok=True)
            temp_output = temp_output_dir / f"anonymized_{uploaded_file.name}"
            
            # Call anonymization
            try:
                result = anonymize_pdf(
                    input_path=str(temp_input),
                    template_path=template_file,
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
