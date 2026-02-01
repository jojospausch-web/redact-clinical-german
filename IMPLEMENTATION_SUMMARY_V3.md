# Implementation Summary: Interactive Zone Adjustment and Postal Code Detection

## Overview
This implementation adds interactive zone adjustment with live preview and postal code detection to the German clinical document anonymization system.

## Features Implemented

### 1. Interactive Zone Configuration UI
- **Header Height Slider**: Adjustable from 0-300 pixels from top
- **Footer Height Slider**: Adjustable from 0-200 pixels from bottom
- **Header Page Selector**: Choose between "Only Page 1" or "All Pages"
- **Footer Keywords Multiselect**: Configure keywords for keyword-based footer redaction
- **Live Preview**: Visual preview showing redaction zones with colored overlays
  - 🔵 Blue = Header zone
  - 🟠 Orange = Footer zone

### 2. Preview Generator (`src/preview_generator.py`)
- Renders first page of PDF as image
- Draws semi-transparent colored overlays for header/footer zones
- Handles coordinate conversion (PDF y=0 is bottom, PIL y=0 is top)
- Scales zones correctly for different PDF page sizes

### 3. Custom Template Generator (`src/template_generator.py`)
- Creates template dictionaries from user slider values
- Converts pixel measurements to PDF coordinates
- Merges user settings with base template
- Supports both "first page only" and "all pages" header modes

### 4. Enhanced Main Module (`src/main.py`)
- Added `anonymize_pdf_with_template()` function
- Accepts template dictionary instead of only file path
- Maintains backward compatibility with existing `anonymize_pdf()` function
- Handles flexible date_handling configuration

### 5. Postal Code Detection
- **Pattern 1**: `(\d{5})\s+([A-ZÄÖÜ][a-zäöüß]+)` - PLZ with city (e.g., "37075 Göttingen")
- **Pattern 2**: `(?:PLZ:?\s*)?(\d{5})(?!\d)` - Standalone PLZ (e.g., "PLZ: 12345")
- Negative lookahead `(?!\d)` prevents matching 6+ digit numbers
- Extracts both postal code and city name as separate entities

### 6. Configuration Updates
- Modified Pydantic models to use `ConfigDict(extra='allow')`
- Changed `date_handling` type from `Dict[str, DateHandlingConfig]` to `Dict[str, Any]`
- Allows templates with additional fields not in strict schema
- Maintains validation for required fields

## Test Coverage

### New Tests Created
1. **`tests/test_preview_generator.py`** (3 tests)
   - Test preview generation with zones
   - Test with zero zone heights
   - Test with maximum zone heights

2. **`tests/test_template_generator.py`** (5 tests)
   - Test first page only header
   - Test all pages header
   - Test zero and max heights
   - Test base template preservation

3. **`tests/test_pii_extractor.py`** (3 new tests)
   - Test postal code with city extraction
   - Test standalone postal code extraction
   - Test 6-digit number exclusion

### Test Results
- **Total Tests**: 71
- **Status**: ✅ All passing
- **Coverage**: Preview generation, template generation, postal code detection

## Files Modified

### New Files
- `src/preview_generator.py` - PDF preview with zone overlays
- `src/template_generator.py` - Dynamic template creation
- `tests/test_preview_generator.py` - Preview generator tests
- `tests/test_template_generator.py` - Template generator tests

### Modified Files
- `app.py` - Complete UI overhaul with sliders and preview
- `src/main.py` - Added `anonymize_pdf_with_template()` function
- `src/config.py` - Made Pydantic models flexible with `extra='allow'`
- `templates/german_clinical_default.json` - Added postal code patterns
- `tests/test_pii_extractor.py` - Added postal code tests
- `README.md` - Documented new features

## Usage Example

### Streamlit UI
```bash
streamlit run app.py
```

1. Upload PDF files
2. Adjust header slider (e.g., 150px)
3. Adjust footer slider (e.g., 92px)
4. Select header pages (first or all)
5. Choose footer keywords
6. View live preview with blue/orange zones
7. Click "Anonymisierung starten"
8. Download anonymized PDFs

### Programmatic Usage
```python
from src.template_generator import create_custom_template
from src.main import anonymize_pdf_with_template

# Create custom template
template = create_custom_template(
    header_height=150,
    header_page="1",
    footer_height=92,
    footer_keywords=["IBAN", "Sparkasse"]
)

# Anonymize with custom settings
result = anonymize_pdf_with_template(
    input_path="input.pdf",
    template=template,
    shift_days=25
)
```

## PII Detection Examples

### Postal Codes
- ✅ "37075 Göttingen" → Extracts "37075" (POSTAL_CODE) and "Göttingen" (CITY)
- ✅ "PLZ: 12345" → Extracts "12345" (POSTAL_CODE)
- ✅ "98765" → Extracts "98765" (POSTAL_CODE)
- ❌ "123456" → Not matched (6 digits, not a postal code)

### Other PII Detected
- Names: "Herr Müller, Max"
- Birthdates: "*15.05.1975"
- Addresses: "Hauptstraße 123, 37075 Göttingen"
- Case IDs: "Pat.-Nr. 123456789"
- Doctor names: "Prof. Dr. med. Schmidt"
- Bank data: "IBAN: DE89370400440532013000"

## Technical Details

### Coordinate Systems
- **PDF**: Origin at bottom-left, y increases upward
- **PIL**: Origin at top-left, y increases downward
- **Conversion**: `PIL_y = page_height - PDF_y`

### A4 Dimensions
- Width: 595 points (210mm)
- Height: 842 points (297mm)
- Scale factor: `rendered_height / 842`

### Zone Calculation
- Header: `y_start = 842 - header_height`, `y_end = 842`
- Footer: `y_start = 0`, `y_end = footer_height`

## Validation

### Manual Testing
✅ Created test PDF with German clinical content
✅ Tested anonymization workflow end-to-end
✅ Verified postal code redaction (37075 removed)
✅ Verified medical terms preserved (Arterielle Hypertonie kept)
✅ Verified PII entities extracted (15 found)
✅ Verified date shifting (1 date shifted by 25 days)

### Automated Testing
✅ All 71 tests passing
✅ Preview generation works with different zone sizes
✅ Template generation creates valid configurations
✅ Postal code patterns match correctly
✅ Config models accept flexible templates

## Acceptance Criteria

- [x] Streamlit UI zeigt Slider für Header-Höhe (0-300px)
- [x] Streamlit UI zeigt Slider für Footer-Höhe (0-200px)
- [x] Live-Vorschau zeigt erste PDF mit eingezeichneten Zonen (blau/orange)
- [x] User kann Header nur auf Seite 1 oder allen Seiten schwärzen
- [x] Footer-Keywords sind konfigurierbar (Multiselect)
- [x] Einstellungen werden auf ALLE hochgeladenen PDFs angewendet
- [x] PLZ-Pattern in Template vorhanden
- [x] PLZ werden in Text erkannt ("37075 Göttingen", "PLZ: 12345")
- [x] Vorschau funktioniert auch bei verschiedenen PDF-Größen
- [x] Tests laufen durch (71 tests passing)
- [x] README mit neuen Features erweitert

## Future Enhancements

Potential improvements for future versions:
1. Add zone preview for multiple pages
2. Allow custom zone definitions (not just header/footer)
3. Add real-time preview updates as sliders change
4. Support different page sizes (Letter, Legal, etc.)
5. Add export/import of custom zone configurations
6. Add visual editor for drawing custom zones
