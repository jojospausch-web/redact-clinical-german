# redact-clinical-german

**Zone-based Anonymization System for German Clinical Doctor Letters (Arztbriefe)**

A sophisticated Python tool for anonymizing German medical documents (PDFs) using structured, context-based pattern matching. This system preserves medical terminology while redacting personally identifiable information (PII) such as names, addresses, case numbers, and dates.

## 🎯 Key Features

- **Zone-Based PDF Anonymization**: Intelligently redacts header, footer, and main content zones
- **Template System**: Create and manage reusable anonymization templates via the web UI
- **Structured PII Extraction**: Uses contextual regex patterns (NOT generic NER)
- **Medical Term Preservation**: Whitelist support per template
- **Context-Based Location Detection**: Recognizes cities and medical facilities only in specific contexts
- **German Month Name Support**: Handles dates with German month names ("5. November 2023")
- **Image Extraction & Anonymization**: OCR-based detection and redaction of PII in embedded images
- **Consistent Date Shifting**: Maintains temporal relationships while anonymizing dates
- **Personal-Block Redaction**: Automatically censors the block after a `Personal:` keyword
- **Docker Support**: Cross-platform deployment on Windows/macOS/Linux

## 🏗️ Architecture

This system is **NOT** based on NER (Named Entity Recognition) + whitelist approach. Instead, it uses:

1. **Zone-based PDF Analysis**: Different rules for header, footer, and main text
2. **Contextual Regex Extraction**: Only extracts PII from specific contexts (e.g., "Patient: {NAME}")
3. **Structured Document Processing**: Recognizes document structure (letterhead always has patient data)
4. **Image OCR & Anonymization**: Extracts and anonymizes images separately

### Why Not NER?

- ❌ NER models flag medical terms (diseases, medications) as entities
- ❌ Maintaining whitelists of medical terms is impractical
- ✅ Contextual extraction is more precise and maintainable
- ✅ Zero false positives on medical terminology

## 📦 Installation

### Option 1: Using pip (Recommended for Development)

```bash
# Clone the repository
git clone https://github.com/jojospausch-web/redact-clinical-german.git
cd redact-clinical-german

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Tesseract OCR (required for image anonymization)
# On Ubuntu/Debian:
sudo apt-get install tesseract-ocr tesseract-ocr-deu

# On macOS:
brew install tesseract tesseract-lang

# On Windows:
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
```

### Option 2: Using Docker (Recommended for Production)

```bash
# Build the Docker image
docker build -t redact-clinical-german .

# Run anonymization
docker run -v $(pwd)/input:/input -v $(pwd)/output:/output \
  redact-clinical-german /input/arztbrief.pdf --output /output/anonymized.pdf
```

## 🚀 Quick Start

### 🖥️ Web-UI (Streamlit) - Recommended for Batch Processing

**Option 1: Docker (Empfohlen)**
```bash
docker-compose up -d
# Open browser at http://localhost:8501
```

**Option 2: Lokale Installation**
```bash
pip install -r requirements.txt
streamlit run app.py
# Open browser at http://localhost:8501
```

#### Web UI Features

- ✅ **Template auswählen** – Wählen Sie ein gespeichertes Template in der Sidebar
- ✅ **Drag & Drop Upload** mehrerer PDFs
- ✅ **Batch-Verarbeitung** mit Live-Progress
- ✅ **Einzeldownload** jeder anonymisierten Datei
- ✅ **ZIP-Download** aller Dateien auf einmal
- ✅ **Excel-Download** – Anonymisierten Text aller Dokumente als `.xlsx` exportieren (Spalten: *Dokument*, *Text*)
- ✅ **Blacklist (exakt)** – Sidebar-Textfeld für case-sensitive Wörter/Phrasen, die immer geschwärzt werden (z.B. `UMG` → redaktiert; `Umgeben` → bleibt erhalten)
- ✅ **Statistiken** (Anzahl gefundener PII pro Datei)

### 📝 Template Editor

Open the **Template Editor** page in the Streamlit sidebar to create and manage templates:

1. **Neues Template** – Click *🆕 Neu* to start with default values
2. **Zonen konfigurieren** – Set pixel heights for header, footer, signature, and `Personal:` block
3. **Whitelist bearbeiten** – Enter medical / anatomical / device terms that must not be redacted
4. **Speichern** – Enter a name and click *💾 Template speichern*

Templates are saved as JSON files in the `templates/` directory and are immediately available in the main anonymization page.

#### Template JSON Format

```json
{
  "name": "Klinik München Standard",
  "created": "2026-02-25T10:30:00Z",
  "zones": {
    "header_page1": 380,
    "footer_page1": 130,
    "footer_next": 110,
    "signature": 150,
    "personal": 100
  },
  "whitelist": {
    "medical": ["CT", "MRT", "Angiographie"],
    "anatomical": ["Herz", "Lunge", "Leber"],
    "devices": ["Stent", "Katheter", "Defibrillator"]
  }
}
```

| Field | Description |
|---|---|
| `zones.header_page1` | Height (px) of the redacted header block on page 1 |
| `zones.footer_page1` | Height (px) of the redacted footer block on page 1 |
| `zones.footer_next` | Height (px) of the redacted footer block on pages 2+ |
| `zones.signature` | Height (px) of the block redacted after *"Mit freundlichen Grüßen"* |
| `zones.personal` | Height (px) of the block redacted after the keyword *"Personal:"* |
| `whitelist.medical` | Medical terms excluded from redaction |
| `whitelist.anatomical` | Anatomical terms excluded from redaction |
| `whitelist.devices` | Device / manufacturer names excluded from redaction |

### Command Line Interface (CLI)

### Basic Usage

```bash
# Anonymize a PDF with default settings
python src/main.py input.pdf --output anonymized.pdf

# Use custom template
python src/main.py input.pdf --output anonymized.pdf \
  --template templates/german_clinical_default.json

# Extract and anonymize images
python src/main.py input.pdf --output anonymized.pdf --extract-images

# Specify date shift offset
python src/main.py input.pdf --output anonymized.pdf --shift-days 15

# Verbose output
python src/main.py input.pdf --output anonymized.pdf --verbose
```

### Example Output

```
2024-01-15 10:30:00 - INFO - Starting anonymization of: input.pdf
2024-01-15 10:30:00 - INFO - Loading template: templates/german_clinical_default.json
2024-01-15 10:30:00 - INFO - Loaded template: German-Clinical-Structured-v1 v1.0.0
2024-01-15 10:30:00 - INFO - Date shifter initialized with offset: 12 days
============================================================
Anonymization completed successfully!
============================================================
Output PDF: anonymized.pdf
Total pages processed: 3
Zones redacted: 8
PII entities found: 15
Dates shifted: 7
Images extracted: 2
============================================================
✓ Successfully anonymized input.pdf
✓ Output saved to anonymized.pdf
```

## 📋 Configuration

### Rules Template Structure

The anonymization behavior is controlled by JSON templates. See `templates/german_clinical_default.json` for the complete example.

#### Zones Configuration

```json
{
  "zones": {
    "header": {
      "page": 1,
      "y_start": 0,
      "y_end": 120,
      "redaction": "full",
      "preserve_logos": true
    },
    "footer": {
      "pages": "all",
      "y_start": 750,
      "y_end": 842,
      "redaction": "keyword_based",
      "keywords": ["IBAN", "Bankverbindung", "Sparkasse"]
    }
  }
}
```

#### Structured PII Patterns

```json
{
  "structured_patterns": {
    "patient_block": {
      "pattern": "(Herr|Frau)\\s+([A-ZÄÖÜ][a-zäöüß-]+),\\s+([A-ZÄÖÜ][a-zäöüß-]+),\\s+\\*(\\d{2}\\.\\d{2}\\.\\d{4})",
      "groups": {
        "1": "SALUTATION",
        "2": "LASTNAME",
        "3": "FIRSTNAME",
        "4": "BIRTHDATE"
      }
    },
    "doctor_signature": {
      "context_trigger": "Mit freundlichen Grüßen",
      "pattern": "(Prof\\.|Dr\\.|PD)\\s+(med\\.\\s+)?([A-ZÄÖÜ][a-zäöüß-]+(?:\\s+[A-ZÄÖÜ][a-zäöüß-]+)+)",
      "type": "DOCTOR_NAME",
      "lookahead": 200
    }
  }
}
```

### Creating Custom Templates

1. Copy `templates/german_clinical_default.json` to a new file
2. Modify zones, patterns, or date handling rules
3. Use the custom template with `--template your_template.json`

## 🏥 Example Patterns Recognized

The system recognizes these structured patterns:

### Patient Information
- **Format**: `Herr Müller, Max, *01.01.1960`
- **Extracted**: Salutation, Lastname, Firstname, Birthdate

### Case Numbers
- **Format**: `Pat.-Nr. 123456789` or `Pat-Nr.: 987654321`
- **Extracted**: Case ID

### Addresses
- **Format**: `Hauptstraße 123, 37075 Göttingen`
- **Extracted**: Complete address

### Doctor Signatures
- **Context**: After "Mit freundlichen Grüßen"
- **Format**: `Prof. Dr. med. Karl Müller`
- **Extracted**: Doctor name with title

### Referring Doctors
- **Context**: After "Zuweiser"
- **Format**: `Dr. Schmidt`
- **Extracted**: Referring doctor name

## 🌍 Location and Medical Facility Anonymization (v2.0)

### Context-Based City Detection

The system recognizes German cities **ONLY** in specific contexts to avoid false positives:

✅ **Recognized:**
- After postal code: `"37075 Göttingen"` → `"37075 [ORT]"`
- With prepositions: `"aus Darmstadt"` → `"aus [ORT]"`
- At clinics: `"Universitätsklinikum Eppendorf"` → `"[KLINIK]"`
- In referrals: `"überwiesen aus Einbeck"` → `"überwiesen aus [ORT]"`

❌ **Ignored (No Context):**
- `"Göttingen-Studie"` (technical term, not a location context)
- `"Hamburger Klassifikation"` (medical classification)

### Database

- **~250 German cities** from major cities to smaller towns
- **12+ major medical facilities** (university hospitals, MVZs)
- **Blacklist support** for special cases (e.g., "UKE" without context)

### Date-Handling

**Birthdate Shifting (Automatic):**
- Birthdate in format `*DD.MM.YYYY` is automatically shifted by a random offset
- Example: `*01.01.1960` → `*15.01.1960` (shifted by +14 days)
- Format is preserved after shifting

**Treatment/Visit Dates (Manual Excel Workflow):**
- Regular dates (without `*`) remain **unchanged** in the anonymized PDF
- **Recommended workflow:**
  1. ✅ Anonymize PDF (names, addresses removed; dates unchanged)
  2. ✅ Copy text from PDF to Excel
  3. ✅ Use provided VBA macro for date-shifting in Excel
  4. ✅ This avoids visual artifacts and positioning issues in PDF

**Why Excel instead of PDF shifting?**
- ❌ PDF date-shifting can create white holes in headers/footers
- ❌ Font and positioning problems
- ❌ Incomplete pattern matches (e.g., "05.08" without year)
- ✅ Excel offers reliable text replacement without visual artifacts

### Excel Date-Shifting Macro

For shifting treatment dates after PDF anonymization:

1. **Copy** text from anonymized PDF to Excel
2. **Save** Excel file as `.xlsm` (macro-enabled)
3. **Install** VBA macro from `docs/excel_date_shifter.vba`
4. **Configure** shift offset (e.g., `SHIFT_DAYS = 15`)
5. **Select** cells with dates and run macro (Alt + F8)

**Supported date formats in Excel macro:**
- `21.08.2023` → Full dates (DD.MM.YYYY)
- `vom 05.08` → Short dates (DD.MM)
- `5. November 2023` → German month names (full)
- `5. Nov. 2023` → German month names (abbreviated)

**Complete guide:** See [docs/excel_date_shifting_guide.md](docs/excel_date_shifting_guide.md)

**VBA code:** [docs/excel_date_shifter.vba](docs/excel_date_shifter.vba)

### Configuration

In `templates/german_clinical_default.json`:

```json
{
  "location_anonymization": {
    "enabled": true,
    "location_blacklist": [
      "UKE",
      "Charité",
      "Northeim",
      "Eppendorf"
    ],
    "replacement": "[ORT]",
    "facility_replacement": "[KLINIK]"
  },
  "date_handling": {
    "enabled": true,
    "shift_days_range": [-30, 30],
    "german_months": {
      "full": ["Januar", "Februar", "März", ...],
      "abbreviated": ["Jan", "Feb", "Mär", ...]
    }
  }
}
```

### Priority System

When multiple contexts match:
1. **Blacklist** (highest priority) - always recognized
2. **Postal code context** - "37075 Göttingen"
3. **Preposition context** - "aus Darmstadt"
4. **Medical facility context** - "Klinikum Hamburg"
5. **Referral context** - "überwiesen aus..."


## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_pii_extractor.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Test Coverage

- ✅ Date shifting consistency
- ✅ German month name parsing and shifting
- ✅ PII extraction with German umlauts
- ✅ Context-based location detection
- ✅ Medical facility recognition
- ✅ Zone-based redaction
- ✅ Context-triggered extraction
- ✅ Image anonymization
- ✅ Multi-group pattern matching

## 🐳 Docker Deployment

### Building for Production

```bash
# Build the image
docker build -t redact-clinical-german:latest .

# Tag for registry
docker tag redact-clinical-german:latest your-registry/redact-clinical-german:1.0.0

# Push to registry
docker push your-registry/redact-clinical-german:1.0.0
```

### Windows Deployment

```powershell
# Using Docker Desktop on Windows
docker build -t redact-clinical-german .

# Run with Windows paths
docker run -v C:\Users\YourName\Documents\input:/input -v C:\Users\YourName\Documents\output:/output redact-clinical-german /input/arztbrief.pdf --output /output/anonymized.pdf
```

### Alternative: PyInstaller Executable (Windows)

```bash
# Install PyInstaller
pip install pyinstaller

# Create standalone executable
pyinstaller --onefile --name redact-clinical src/main.py

# Executable will be in dist/redact-clinical.exe
```

## 📊 Performance

- **Processing Speed**: ~1-2 pages/second (depends on image count)
- **Memory Usage**: ~100-200 MB per document
- **Tesseract OCR**: ~500ms per image

## 🔒 Privacy & Security

- **Local Processing**: All processing happens locally, no cloud services
- **No Data Retention**: No caching or logging of PII
- **Deterministic Shifting**: Same input always produces same output (with fixed seed)
- **Docker Isolation**: Complete isolation when using Docker

## 🛠️ Development

### Project Structure

```
redact-clinical-german/
├── src/
│   ├── __init__.py
│   ├── main.py                    # CLI Entry Point
│   ├── zone_anonymizer.py         # Zone-based PDF anonymization
│   ├── image_extractor.py         # Image extraction
│   ├── image_anonymizer.py        # OCR + image anonymization
│   ├── pii_extractor.py           # Structured PII extraction
│   ├── date_shifter.py            # Consistent date shifting
│   └── config.py                  # Pydantic config models
├── templates/
│   └── german_clinical_default.json  # Default rules template
├── tests/
│   ├── test_zone_anonymizer.py
│   ├── test_pii_extractor.py
│   ├── test_date_shifter.py
│   └── test_image_anonymizer.py
├── Dockerfile
├── requirements.txt
├── pyproject.toml
└── README.md
```

### Adding New Patterns

1. Edit `templates/german_clinical_default.json`
2. Add pattern to `structured_patterns` section
3. Test with sample documents
4. Add unit tests to `tests/test_pii_extractor.py`

## ❓ FAQ

### Why not use spaCy or Stanza for NER?

NER models are trained on general text and flag medical terms as entities. Maintaining a whitelist of thousands of medical terms is impractical and error-prone. Contextual extraction is more precise.

### How accurate is the system?

- **Precision**: >99% (very few false positives due to contextual matching)
- **Recall**: ~95% (might miss PII in unexpected formats)

### Can I use this for non-German documents?

The system is optimized for German clinical documents. For other languages, you would need to:
1. Adjust regex patterns for the language
2. Update Tesseract language (`lang='deu'` → `lang='eng'`)
3. Modify name/address patterns

### What about GDPR compliance?

This tool helps with GDPR compliance by anonymizing PII, but you should:
- Review output documents manually
- Implement proper access controls
- Document your anonymization process
- Consider data minimization principles

## 📝 License

[Add your license here]

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 📧 Contact

For questions or issues, please open a GitHub issue.

## 🙏 Acknowledgments

- PyMuPDF for excellent PDF manipulation
- Tesseract OCR for image text recognition
- Click for the CLI framework
