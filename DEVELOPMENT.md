# Development Notes

## Design Decisions

### Why Zone-Based Instead of NER?

1. **Medical Term Problem**: NER models (spaCy, Stanza) are trained on general text and frequently misidentify medical terms as person names or organizations:
   - "Müller-Syndrom" → flagged as person name
   - "NYHA-Klassifikation" → flagged as organization
   - Drug names, procedures, conditions → all potential false positives

2. **Whitelist Maintenance**: Maintaining a comprehensive whitelist of medical terms is:
   - Time-consuming (thousands of terms)
   - Never complete (new terms, abbreviations)
   - Language-specific
   - Domain-specific (cardiology vs. oncology)

3. **Precision Over Recall**: In medical document anonymization:
   - False positives (redacting medical terms) are worse than false negatives
   - Contextual extraction provides better precision
   - Structure of clinical documents is predictable

### Why PyMuPDF Over Alternatives?

- **pdf2image**: Converts to images, loses text structure
- **pdfplumber**: Good for tables, less precise for coordinate-based redaction
- **PyPDF2**: Limited redaction capabilities
- **PyMuPDF (fitz)**: Native redaction support, precise coordinate control, excellent performance

### Date Shifting Strategy

We use consistent shifting with a fixed offset because:
- Preserves temporal relationships (time between events)
- Deterministic (same input → same output with same seed)
- Maintains data utility for research
- Complies with HIPAA Safe Harbor method

## Performance Optimization

### Current Bottlenecks

1. **Tesseract OCR**: ~500ms per image
   - Could parallelize image processing
   - Consider GPU acceleration for large batches

2. **PDF Parsing**: ~200ms per page
   - Already optimized by PyMuPDF
   - Could implement page-level parallelization

3. **Regex Matching**: Negligible (~1ms per page)

### Future Improvements

- [ ] Parallel image processing
- [ ] Batch processing mode
- [ ] Caching of compiled regex patterns
- [ ] Optional GPU-accelerated OCR

## Testing Strategy

### Unit Tests
- Individual component testing
- Edge cases (umlauts, special characters)
- Boundary conditions (empty documents, malformed input)

### Integration Tests
- Full workflow testing
- Real document processing (with fixtures)
- Cross-platform compatibility

### Manual Testing Checklist
- [ ] Header zone correctly redacted
- [ ] Footer keywords found and redacted
- [ ] Patient information extracted
- [ ] Doctor signature after greeting detected
- [ ] Dates consistently shifted
- [ ] Medical terms NOT redacted
- [ ] Images extracted and anonymized
- [ ] Output PDF is valid and readable

## Known Limitations

1. **Handwriting**: OCR cannot reliably read handwritten notes
2. **Scanned PDFs**: Text extraction depends on OCR quality
3. **Complex Layouts**: Multi-column layouts may confuse zone detection
4. **Languages**: Optimized for German; other languages need pattern adjustments
5. **Image Quality**: Low-resolution images may have poor OCR results

## Security Considerations

### Threat Model

**In Scope:**
- Accidental PII leakage in anonymized documents
- Consistent anonymization across multiple documents
- Data exfiltration during processing

**Out of Scope:**
- Adversarial attacks on OCR
- Statistical re-identification
- Side-channel attacks

### Mitigations

1. **Local Processing**: No network calls, no cloud dependencies
2. **Memory Cleanup**: Objects are properly disposed after processing
3. **Docker Isolation**: Complete process isolation in containers
4. **No Logging**: PII is never logged or cached
5. **Deterministic Output**: Prevents correlation attacks

## Deployment Scenarios

### Scenario 1: Research Institution (Linux Servers)
- **Solution**: Docker containers
- **Scale**: Batch processing
- **Integration**: REST API (future work)

### Scenario 2: Clinical Workstation (Windows, No Admin)
- **Solution**: PyInstaller executable
- **Scale**: Single documents
- **Integration**: Drag-and-drop UI (future work)

### Scenario 3: Hospital IT (macOS Development)
- **Solution**: Python virtual environment
- **Scale**: Development and testing
- **Integration**: CLI workflows

## Future Roadmap

### Version 1.1
- [ ] FastAPI REST interface
- [ ] Batch processing mode
- [ ] Configuration validation UI
- [ ] Progress bar for long documents

### Version 1.2
- [ ] Machine learning for layout detection
- [ ] Improved OCR with preprocessing
- [ ] Multi-language support
- [ ] GUI application (Tkinter/Qt)

### Version 2.0
- [ ] Cloud deployment option
- [ ] Audit logging
- [ ] Template marketplace
- [ ] Plugin system for custom extractors
