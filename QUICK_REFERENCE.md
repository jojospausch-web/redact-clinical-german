# Quick Reference Guide

## Command Line Usage

### Basic Commands

```bash
# Simple anonymization
python src/main.py input.pdf --output anonymized.pdf

# With specific date shift
python src/main.py input.pdf -o output.pdf --shift-days 15

# Extract images
python src/main.py input.pdf -o output.pdf --extract-images

# Verbose output
python src/main.py input.pdf -o output.pdf --verbose

# Custom template
python src/main.py input.pdf -o output.pdf -t custom_template.json
```

### Docker Commands

```bash
# Build image
docker build -t redact-clinical-german .

# Run with volume mounts
docker run -v $(pwd)/input:/input -v $(pwd)/output:/output \
  redact-clinical-german /input/document.pdf --output /output/anonymized.pdf

# Run with custom template
docker run -v $(pwd)/input:/input -v $(pwd)/output:/output \
  -v $(pwd)/templates:/templates \
  redact-clinical-german /input/document.pdf \
  --output /output/anonymized.pdf \
  --template /templates/custom.json
```

## Pattern Syntax

### Regex Special Characters

| Character | Meaning | Example |
|-----------|---------|---------|
| `\d` | Any digit | `\d{6}` = 6 digits |
| `\s` | Whitespace | `\s+` = one or more spaces |
| `[A-Z]` | Character class | `[A-ZÄÖÜ]` = uppercase letter |
| `+` | One or more | `\d+` = one or more digits |
| `*` | Zero or more | `\s*` = optional whitespace |
| `?` | Optional | `\.?` = optional period |
| `()` | Capture group | `(\d{2})` = capture 2 digits |
| `\|` | OR operator | `Herr\|Frau` = Herr or Frau |

### Common German Patterns

```regex
# Names
[A-ZÄÖÜ][a-zäöüß-]+

# Dates (DD.MM.YYYY)
\d{2}\.\d{2}\.\d{4}

# Postal codes
\d{5}

# Street names
[A-ZÄÖÜ][a-zäöüß]+(?:straße|str\.|weg|platz|allee)

# Titles
(?:Prof\.|Dr\.|PD)

# Case numbers
\d{6,10}
```

## Template Configuration

### Zone Configuration

```json
{
  "zone_name": {
    "page": 1,              // Page number (1-indexed) or null for all
    "pages": "all",         // "all" or null
    "y_start": 0,          // Top Y coordinate
    "y_end": 120,          // Bottom Y coordinate
    "redaction": "full",   // "full", "keyword_based", or "none"
    "preserve_logos": true, // Keep images in zone
    "keywords": ["IBAN"]   // For keyword_based redaction
  }
}
```

### Pattern Configuration

#### Simple Pattern
```json
{
  "pattern_name": {
    "pattern": "Pat\\.?-?Nr\\.?:?\\s*([0-9]{6,10})",
    "type": "CASE_ID"
  }
}
```

#### Multi-Group Pattern
```json
{
  "pattern_name": {
    "pattern": "(Herr|Frau)\\s+([A-Z][a-z]+),\\s+([A-Z][a-z]+)",
    "groups": {
      "1": "SALUTATION",
      "2": "LASTNAME",
      "3": "FIRSTNAME"
    }
  }
}
```

#### Context-Based Pattern
```json
{
  "pattern_name": {
    "context_trigger": "Mit freundlichen Grüßen",
    "pattern": "Dr\\.\\s+([A-Z][a-z]+)",
    "type": "DOCTOR_NAME",
    "lookahead": 200
  }
}
```

## Coordinate System

PDF coordinates start at bottom-left corner:
- `x=0, y=0`: Bottom-left
- `x=595, y=842`: Top-right (A4 page)

### Common Zones (A4 portrait)

| Zone | Y-Start | Y-End | Description |
|------|---------|-------|-------------|
| Header | 0 | 120 | Top 120 points |
| Main content | 120 | 720 | Middle area |
| Footer | 720 | 842 | Bottom 122 points |

Note: In PyMuPDF, Y coordinates increase from bottom to top.

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'src'"

**Solution:**
```bash
# Run from project root
cd /path/to/redact-clinical-german
python src/main.py ...
```

### Issue: Tesseract not found

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-deu

# macOS
brew install tesseract tesseract-lang

# Windows
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
```

### Issue: Medical terms being redacted

**Check:**
1. Are you using the correct template?
2. Is the pattern too broad?
3. Is there an unintended context trigger?

**Solution:** Review pattern configuration and test with sample documents.

### Issue: PII not being detected

**Check:**
1. Is the text in the expected format?
2. Does the pattern account for variations?
3. Is the context trigger present?

**Debug:**
```bash
# Run with verbose flag
python src/main.py input.pdf -o output.pdf --verbose
```

### Issue: Docker container permissions

**Solution:**
```bash
# Run as current user
docker run --user $(id -u):$(id -g) \
  -v $(pwd)/input:/input -v $(pwd)/output:/output \
  redact-clinical-german /input/document.pdf --output /output/anonymized.pdf
```

## Performance Tips

1. **Process images separately** if you have many images:
   ```bash
   python src/main.py input.pdf -o output.pdf --extract-images
   ```

2. **Use specific date shifts** instead of random for reproducibility:
   ```bash
   python src/main.py input.pdf -o output.pdf --shift-days 15
   ```

3. **Optimize templates** - remove unused patterns to speed up processing

4. **Batch processing** - create a shell script:
   ```bash
   for file in input/*.pdf; do
       python src/main.py "$file" -o "output/$(basename "$file")"
   done
   ```

## Testing

### Run all tests
```bash
pytest tests/ -v
```

### Run specific test file
```bash
pytest tests/test_pii_extractor.py -v
```

### Run with coverage
```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

### Test with sample data
```bash
python demo.py
```

## Getting Help

1. Check the README.md for detailed documentation
2. Review DEVELOPMENT.md for design decisions
3. Run demo.py for examples
4. Check test files for usage examples
5. Open an issue on GitHub

## Common Patterns Library

### Patient Information
```regex
# Full patient block
(Herr|Frau)\s+([A-ZÄÖÜ][a-zäöüß-]+),\s+([A-ZÄÖÜ][a-zäöüß-]+),\s+\*(\d{2}\.\d{2}\.\d{4})

# Name only
[A-ZÄÖÜ][a-zäöüß-]+\s+[A-ZÄÖÜ][a-zäöüß-]+

# Birthdate with asterisk
\*(\d{2}\.\d{2}\.\d{4})
```

### Contact Information
```regex
# Address
([A-ZÄÖÜ][a-zäöüß]+(?:straße|str\.|weg|platz|allee))\s+(\d+[a-z]?),?\s+(\d{5})\s+([A-ZÄÖÜ][a-zäöüß]+)

# Phone
(?:\+49\s?)?\d{2,5}[-\s]?\d{3,9}

# Email
[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}
```

### Medical IDs
```regex
# Patient number
Pat\.?-?Nr\.?:?\s*([0-9]{6,10})

# Insurance number
\d{10}[A-Z]\d{3}

# Case/Fall number
Fall[-\s]?(?:Nr\.?|Nummer):?\s*(\d{6,10})
```

### Doctor Information
```regex
# Full title and name
(Prof\.|Dr\.|PD)\s+(med\.\s+)?([A-ZÄÖÜ][a-zäöüß-]+(?:\s+[A-ZÄÖÜ][a-zäöüß-]+)+)

# Simple doctor name (after context)
Dr\.\s+([A-ZÄÖÜ][a-zäöüß-]+)

# Signature context
Mit\s+freundlichen\s+Grüßen
```
