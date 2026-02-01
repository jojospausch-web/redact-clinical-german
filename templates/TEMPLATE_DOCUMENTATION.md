# German Clinical Template - Dokumentation

Dieses Dokument erklärt die Struktur des `german_clinical_default.json` Templates.

## Template-Struktur

### Grundlegende Informationen

```json
{
  "template_name": "German-Clinical-Structured-v2",
  "version": "2.0.0",
  "info": "Beschreibung des Templates"
}
```

### Zonen (zones)

Definiert Bereiche im PDF, die unterschiedlich behandelt werden:

```json
"zones": {
  "header": {
    "page": 1,              // Nur auf Seite 1
    "y_start": 0,           // Y-Koordinate Start (von oben)
    "y_end": 120,           // Y-Koordinate Ende
    "redaction": "full",    // Vollständig schwärzen
    "preserve_logos": true  // Logos erhalten (optional)
  },
  "footer": {
    "pages": "all",              // Auf allen Seiten
    "y_start": 750,
    "y_end": 842,
    "redaction": "keyword_based", // Nur Keywords schwärzen
    "keywords": ["IBAN", "Sparkasse", "BIC"]
  }
}
```

**Redaction-Modi:**
- `"full"`: Gesamte Zone schwärzen
- `"keyword_based"`: Nur Keywords in der Zone schwärzen
- `"none"`: Keine Schwärzung

### Strukturierte Muster (structured_patterns)

Regex-Patterns für PII-Erkennung:

```json
"structured_patterns": {
  "patient_block": {
    "pattern": "(Herr|Frau)\\s+([A-Z][a-z]+),\\s+([A-Z][a-z]+),\\s+\\*(\\d{2}\\.\\d{2}\\.\\d{4})",
    "groups": {
      "1": "SALUTATION",  // Gruppe 1 → Anrede
      "2": "LASTNAME",    // Gruppe 2 → Nachname
      "3": "FIRSTNAME",   // Gruppe 3 → Vorname
      "4": "BIRTHDATE"    // Gruppe 4 → Geburtsdatum
    }
  },
  "case_id": {
    "pattern": "Pat\\.?-?Nr\\.?:?\\s*([0-9]{6,10})",
    "type": "CASE_ID"
  },
  "doctor_signature": {
    "context_trigger": "Mit freundlichen Grüßen",  // Suche nur nach diesem Trigger
    "pattern": "(Prof\\.|Dr\\.|PD)\\s+(med\\.\\s+)?([A-Z][a-z-]+(?:\\s+[A-Z][a-z-]+)+)",
    "type": "DOCTOR_NAME",
    "lookahead": 200  // Max. 200 Zeichen nach Trigger suchen
  }
}
```

**Pattern-Felder:**
- `pattern`: Regex-Ausdruck (Backslashes müssen escaped werden: `\\d` statt `\d`)
- `groups`: Optional - Mapping von Regex-Gruppen zu Entity-Typen
- `type`: Optional - Entity-Typ für gesamten Match
- `context_trigger`: Optional - Suche nur nach bestimmtem Kontext-Keyword
- `lookahead`: Optional - Max. Zeichen nach Trigger-Keyword

### Datumsverarbeitung (date_handling)

**Wichtig:** Jedes Pattern braucht `pattern` und `action`.

```json
"date_handling": {
  "birthdate": {
    "pattern": "\\*(\\d{2}\\.\\d{2}\\.\\d{4})",  // Geburtsdatum mit *
    "action": "shift",                            // Datum verschieben
    "shift_days_range": [-30, 30]                 // Zufällig -30 bis +30 Tage
  },
  "german_full_date": {
    "pattern": "\\b(\\d{1,2})\\. (Januar|Februar|...) (\\d{4})\\b",
    "action": "shift"
  },
  "numeric_date": {
    "pattern": "\\b(\\d{2})\\.(\\d{2})\\.(\\d{4})\\b",
    "action": "shift"
  },
  "treatment_dates": {
    "pattern": "\\b(\\d{2}\\.\\d{2}\\.\\d{4})\\b",
    "action": "shift_relative"  // Relativ zum Geburtsdatum verschieben
  }
}
```

**Action-Typen:**
- `"shift"`: Datum um feste Anzahl Tage verschieben
- `"shift_relative"`: Relativ zu anderem Datum verschieben
- `"remove"`: Datum entfernen

### Ortsanonymisierung (location_anonymization)

```json
"location_anonymization": {
  "enabled": true,
  "city_database": "data/cities_de.txt",
  "facilities_database": "data/medical_facilities_de.json",
  "context_triggers": {
    "prepositions": ["in", "aus", "nach", "von", "bei"],
    "facility_keywords": ["Universitätsklinikum", "Klinikum", "Krankenhaus"],
    "referral_keywords": ["überwiesen", "Zuweiser", "eingewiesen"]
  },
  "location_blacklist": ["UKE", "Charité", "Northeim"],
  "replacement": "[ORT]",
  "facility_replacement": "[KLINIK]"
}
```

**Hinweis:** Falls die Datenbanken fehlen, verwendet das System eine eingebaute Minimal-Liste häufiger deutscher Städte.

### PII-Mechanismen (pii_mechanisms)

Definiert, wie mit verschiedenen PII-Typen umgegangen wird:

```json
"pii_mechanisms": {
  "PATIENT_NAME": "redact",    // Schwärzen
  "DOCTOR_NAME": "redact",
  "ADDRESS": "redact",
  "DATE": "shift_date",        // Datum verschieben
  "BIRTHDATE": "shift_date",
  "CASE_ID": "redact",
  "PHONE": "redact",
  "EMAIL": "redact",
  "IBAN": "redact"
}
```

### Bild-PII-Patterns (image_pii_patterns)

Patterns für OCR-Texterkennung in Bildern:

```json
"image_pii_patterns": {
  "case_number": "\\d{6,10}",
  "name": "^[A-ZÄÖÜ][a-zäöüß]+\\s+[A-ZÄÖÜ][a-zäöüß]+$",
  "birthdate": "\\d{2}\\.\\d{2}\\.\\d{4}"
}
```

## Häufige Fehler

### 1. Fehlende `pattern` oder `action` in `date_handling`

❌ **Falsch:**
```json
"date_handling": {
  "enabled": true,
  "shift_days_range": [-30, 30]
}
```

✅ **Richtig:**
```json
"date_handling": {
  "birthdate": {
    "pattern": "\\*(\\d{2}\\.\\d{2}\\.\\d{4})",
    "action": "shift",
    "shift_days_range": [-30, 30]
  }
}
```

### 2. Nicht-escapte Backslashes in Regex

❌ **Falsch:**
```json
"pattern": "\d{2}\.\d{2}\.\d{4}"
```

✅ **Richtig:**
```json
"pattern": "\\d{2}\\.\\d{2}\\.\\d{4}"
```

### 3. Fehlende Pflichtfelder

Pflichtfelder im Template:
- `template_name`
- `version`
- `zones`
- `structured_patterns`
- `date_handling`
- `image_pii_patterns`

## Validierung

Das Template wird beim Laden mit Pydantic validiert. Bei Fehlern erscheint eine hilfreiche Fehlermeldung:

```
Template 'templates/german_clinical_default.json' hat Validierungsfehler.
Bitte prüfe die Struktur:
  - date_handling.birthdate.action: Field required
  - date_handling.birthdate.pattern: Field required
```

## Erweiterung

Das Template kann beliebig erweitert werden:

```json
{
  "template_name": "...",
  "version": "...",
  // ... Pflichtfelder ...
  
  // Eigene Felder sind erlaubt:
  "custom_field": "custom_value",
  "processing_options": {
    "enable_xyz": true
  }
}
```

Die Pydantic-Models erlauben zusätzliche Felder (`ConfigDict(extra='allow')`).
