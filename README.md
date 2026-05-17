# redact-clinical-german

**Zonen-basierte Anonymisierung deutscher Arztbriefe (PDF)**

Lokal laufendes Python-Tool, das Arztbriefe als PDF anonymisiert. Es kombiniert:

- **Zonenbasierte Schwärzung** (Header / Footer / Signaturblock / „Personal:" / „Header bis Keyword")
- **Strukturierte PII-Erkennung** über kontextbasierte Regex-Patterns (Patientenblock, Fall-Nr., Adresse, Arztname, Telefon, E-Mail, Fax, HK-Nummer, …)
- **Exakte Wort-Bbox-Redaktion**: PII wird genau dort geschwärzt, wo der Treffer ist — nicht jedes weitere Vorkommen desselben Strings
- **Case-sensitive Blacklist** (exakte Wörter/Phrasen, die immer geschwärzt werden)
- **Whitelist** (medizinische Begriffe, die nie geschwärzt werden dürfen)
- **OCR-basierte Bild-Anonymisierung** (Tesseract)
- **Excel-Export** des anonymisierten Volltexts (Spalte „Dokument", Spalte „Text")

Es nutzt **kein NER** — Patterns sind explizit; medizinische Fachbegriffe lösen keine Schwärzung aus.

---

## 🏥 Klinik-Setup (Offline, Windows)

Der Rollout auf einem Klinik-Rechner ohne Internet läuft mit zwei Installern (Tesseract + Miniconda) und einem Offline-Wheel-Cache.

1. **Tesseract** installieren — `RedClinG_Requirements\tesseract-ocr-w64-setup-5.5.0.20241111.exe`
2. **Miniconda** installieren — `RedClinG_Requirements\Miniconda3-latest-Windows-x86_64.exe`
3. **Anaconda Prompt** starten
4. **Dependencies offline** installieren:
   ```bat
   pip install --no-index --find-links S:\KARD\F_KI-PROPHET\Software\RedClinG_Requirements\requiredPackages\ -r S:\KARD\F_KI-PROPHET\Software\RedClinG_Requirements\requirements.txt
   ```
5. **App starten**:
   ```bat
   streamlit run S:\KARD\F_KI-PROPHET\Software\redact-clinical-german-main\app.py
   ```
   Streamlit öffnet die Oberfläche auf `http://localhost:8501`.

### Updates ausrollen

Der Klinik-Rechner wird per Datei-Copy aktualisiert. **Wichtig:** Tests und ihre Source-Dateien gehören zusammen — wenn du nur einzelne Tests austauschst, schlagen sie ggf. fehl, weil sich z. B. eine `*.json` oder ein `src/*.py` mit verändert hat. Am sichersten: kompletten Projektordner ersetzen.

Was darf **nicht** angefasst werden:

- `requirements.txt` — wegen des Offline-Wheel-Caches sind nur die unten gelisteten Pakete erlaubt
- Setup-Workflow oben (tesseract + Miniconda + offline pip + `streamlit run app.py`)

Alles andere (UI, Templates, Patterns, Logik, Tests, Doku) ist freier Anpassungs-Spielraum.

---

## 📦 Erlaubte Python-Pakete

```text
PyMuPDF        >= 1.23.8
pytesseract    >= 0.3.10
Pillow         >= 10.1.0
pydantic       >= 2.5.0
click          >= 8.1.0
python-dateutil>= 2.8.2
openpyxl       >= 3.1.0
pytest         >= 7.4.0
streamlit      >= 1.30.0
```

Keine weiteren Dependencies. Bitte vor Änderungen daran zuerst neue Wheels in den Offline-Cache legen lassen.

---

## 🖥️ Web-UI (Streamlit)

Standard-Workflow auf dem Klinik-Rechner. Nach `streamlit run app.py`:

### Linker Sidebar-Bereich
- **📁 Template auswählen** – Dropdown mit allen gespeicherten Templates aus `templates/`
- **Bilder extrahieren** – Schaltet die OCR-Bild-Anonymisierung an/aus
- **Debug-Logging aktivieren** – schreibt detaillierte Match-Informationen in die Konsole (`[MATCH FOUND]`, `[SKIP - BOUNDARY]`, `[ENTITY EXTRACTED]`, `Redacted header until keyword …`, …)
- **🟣 Header bis Keyword** – Aktivieren + Trigger-Liste (eine Phrase pro Zeile). Schwärzt alles oberhalb des **obersten** Vorkommens eines beliebigen Triggers auf der Seite. Wird in der Vorschau magenta markiert.
- **🚫 Blacklist (exakt)** – case-sensitive Wörter/Phrasen, die immer redaktiert werden (`UMG` schwärzt `UMG`, lässt `Umgeben` stehen)
- **🗑️ Ergebnisse löschen** – wirft die anonymisierten PDFs der aktuellen Session aus dem Speicher und räumt das per-Session-Template auf

### Hauptbereich
1. PDFs per Drag & Drop hochladen
2. **Vorschau** der ersten Seite mit den eingezeichneten Zonen:
   - 🔵 Header Seite 1
   - 🟠 Footer Seite 1
   - 🟢 Footer Folgeseiten
   - 🟣 Header bis Keyword (falls aktiv und ein Trigger gefunden wurde — andernfalls erscheint ein gelber Warnhinweis mit den gesuchten Triggern, damit man sofort sieht, welche Schreibweise nicht gefunden wurde)
3. **🚀 Anonymisierung starten**: verarbeitet alle Uploads, lädt die anonymisierten PDFs in den Session-Speicher und löscht den Disk-Workspace sofort.
4. Downloads:
   - 📄 Einzel-PDF
   - 📦 ZIP-Bundle (PDFs + extrahierte Bilder)
   - 📊 Excel-Export (Spalten *Dokument*, *Text*) für nachgelagerte Auswertung
     *(deaktiviert, wenn Date-Shift aktiv — sonst Inkonsistenz zwischen PDF und Excel)*

---

## 📅 Date-Shift

Sidebar-Toggle **„📅 Date-Shift aktivieren"** (Default: aus). Wenn aktiv,
verschiebt das Tool nach der PII-Redaktion die im Brief gefundenen Datums-
angaben direkt im PDF nach festen Regeln.

### Regel-Auswahl (basierend auf dem Aufnahmedatum)

Das Aufnahmedatum wird aus einem Muster wie `vom 05.08. bis zum 21.08.2023`
extrahiert. Wenn das erste Datum kein Jahr trägt, wird das Jahr aus dem
zweiten Datum übernommen.

| Aufnahme-Tag | Aufnahme-Monat | Standalone `YYYY` im Text | Modus              | Verhalten |
|--------------|----------------|----------------------------|--------------------|-----------|
| 27 – 31      | beliebig       | egal                       | `monthend`         | **kein** Shift, alle Daten 🔴 |
| 01 – 26      | Sep – Dez (9–12)| ja                        | `shift_year_leak`  | Daten geshiftet 🟡, alleinstehende Jahreszahlen 🔴 |
| 01 – 26      | Sep – Dez       | nein                      | `shift_safe`       | Alles geshiftet 🟡 |
| 01 – 26      | Jan – Aug (1–8) | egal                      | `shift_safe`       | Alles geshiftet 🟡 |
| (kein `vom…bis…` gefunden)                                  | `no_stay`          | **kein** Shift, alle Daten 🔴 |

### Shift-Größen

| Format-Beispiel | Shift |
|---|---|
| `DD.MM.YYYY` (z.B. `05.08.2023`) | +120 Tage |
| `DD.MM` ohne Jahr im `vom…bis…`-Kontext (z.B. `05.08`) | +120 Tage, Output ohne Jahr (Format bleibt erhalten) |
| `D. Monatsname YYYY` (z.B. `5. November 2023`) | +120 Tage |
| `D. Mon. YYYY` (z.B. `5. Nov. 2023`) | +120 Tage |
| `MM.YYYY` (z.B. `11.2023`) | **+4 Monate** (Sep–Dez rollen ins Folgejahr) |
| `MM/YYYY` (z.B. `11/2023`) | +4 Monate |
| `MM/YY` (z.B. `11/23`, nur Jahre 20–39 = 2020–2039) | +4 Monate |
| Geburtsdaten (`geb. …`, `*…`, `geboren am …`) | **kein** Shift, 🔴 markiert |
| Alleinstehende `YYYY` im `shift_year_leak`-Fall (z.B. `seit 2019`) | **kein** Shift, 🔴 markiert |

### Markierung im PDF

- 🟡 **Gelbe Highlight-Annotation** auf jedem geshifteten Datum
- 🔴 **Rote Highlight-Annotation** auf jedem nicht-geshifteten Datum, plus alleinstehende `YYYY` im Year-Leak-Fall, plus Geburtsdaten
- Annotations-Tooltip enthält den Grund („Geburtsdatum — nicht verschoben", „+120 Tage", „Alleinstehende Jahreszahl — bitte prüfen", …)

Beim manuellen Sichten kannst du in Acrobat / PDF-Viewer die Anmerkungen über das Hand-Werkzeug einsehen oder einzeln löschen, sobald du sie geprüft hast.

### Was passiert mit dem Excel-Export?

Wenn Date-Shift aktiv ist, wird der Excel-Export-Button **ausgeblendet** —
ansonsten würde Excel den geshifteten Text ohne die farbigen Markierungen
enthalten und ein Doppelversionierungs-Chaos bringen.

### Blutdruck-Schutz

Slash-Formate wie `120/80 mmHg`, `10/80` mit Indikatoren wie „RR", „mmHg",
„Blutdruck", „/min", „Puls" im selben Satz werden **nicht** als Datum
interpretiert. Sätze sind durch `\n`, `. ` oder `; ` getrennt.

### Verbleibende Risiken

- **Font-Mismatch**: PyMuPDF rendert den Ersatztext in Helvetica. Bei
  Briefen in z. B. Calibri/Arial fällt der Wechsel meist bei Ziffern nicht
  auf, kann aber bei deutschen Monatsnamen sichtbar sein.
- **Längenänderung**: `5.8.2023` → `5.12.2023` wird ein Zeichen länger.
  PyMuPDF zentriert den Ersatz; visuell entsteht im Schlimmstfall ein
  leicht engerer Buchstabenabstand. Die gelbe Markierung hilft beim
  Sichten.
- **Nicht erkannte Formate** (etwa „im Sommer 2023", „letzte Woche")
  werden nicht angefasst — manuelle Nachkontrolle bleibt Pflicht.

---

## 📝 Template-Editor

Streamlit-Seite **„📝 Template Editor"** (Sidebar > Pages). Erlaubt das pflegen wiederverwendbarer Konfigurationen.

| Tab | Inhalt |
|---|---|
| **⚙️ Zonen-Konfiguration** | Pixelhöhen für Header (Seite 1), Header Folgeseiten, Footer (Seite 1 / Folgeseiten), Signaturblock, `Personal:`-Block. Plus „Header bis Keyword" mit Trigger-Liste. |
| **🔍 PII-Pattern Aktivierung** | Toggle jeder Mustergruppe (Patient, Arzt, Anrede + Name, Adresse, PLZ, Klinik, Telefon, Fax, E-Mail, HK-Nummer, Schrittmacher-ID, …). |
| **📋 Whitelist-Begriffe** | Medizinische / anatomische / Geräte-Begriffe, die nie redaktiert werden dürfen. |
| **🚫 Blacklist (exakt)** | Case-sensitive Phrasen, die immer redaktiert werden — ergänzt die Sidebar-Eingabe. |
| **🔍 Vorschau** | JSON-Live-Vorschau des aktuellen Templates. |

Templates landen als JSON in `templates/`. Das Template `default.json` wird beim ersten Start automatisch angelegt.

### Template-JSON-Format

```json
{
  "name": "Klinik München Standard",
  "created": "2026-02-25T10:30:00Z",
  "zones": {
    "header_page1": 380,
    "header_next": 100,
    "footer_page1": 130,
    "footer_next": 110,
    "signature": 150,
    "personal": 100
  },
  "header_until_keyword": {
    "enabled": true,
    "triggers": [
      "Sehr geehrte Kollegin",
      "Sehr geehrter Kollege",
      "Untersucher"
    ]
  },
  "active_patterns": {
    "patient_block": true,
    "salutation_with_name": true,
    "case_id": true,
    "address": true,
    "doctor_name": true,
    "phone_landline": true,
    "phone_mobile": true,
    "email": true,
    "fax": true,
    "hk_number": true,
    "pacemaker_id": true
  },
  "whitelist": {
    "medical": ["CT", "MRT", "Angiographie"],
    "anatomical": ["Herz", "Lunge", "Leber"],
    "devices": ["Stent", "Katheter", "Defibrillator"]
  },
  "blacklist_exact": ["UMG", "Universitätsmedizin Göttingen"]
}
```

| Feld | Bedeutung |
|---|---|
| `zones.header_page1` | Höhe der Header-Schwärzung auf Seite 1 (PDF-Punkte, oben gemessen) |
| `zones.header_next` | Header-Höhe auf Seiten 2+ |
| `zones.footer_page1` | Footer-Höhe Seite 1 (von unten gemessen) |
| `zones.footer_next` | Footer-Höhe Seiten 2+ |
| `zones.signature` | Höhe des Blocks nach „Mit freundlichen Grüßen" |
| `zones.personal` | Höhe des Blocks nach Keyword „Personal:" |
| `header_until_keyword.enabled` | Schwärzt alles oberhalb des obersten Trigger-Vorkommens |
| `header_until_keyword.triggers` | Liste aller Phrasen, die als Trigger gelten — die oberste auf der Seite gewinnt |
| `active_patterns` | Welche PII-Muster aktiv sind |
| `whitelist.*` | Wörter/Phrasen, die nie geschwärzt werden |
| `blacklist_exact` | Wörter/Phrasen, die immer geschwärzt werden (case-sensitive, ganze Wörter) |

---

## 🗺️ Zone-Koordinatensystem (PyMuPDF)

PyMuPDF zählt y von oben:

- `y = 0` ist die **Oberkante** der Seite
- `y = page.rect.height` (A4 ≈ 842) ist die **Unterkante**

Templates in der UI verwenden „Höhe in Pixeln" (= PDF-Punkte). Der Header ist immer ein Streifen vom oberen Rand abwärts; Footer-Werte sind ein Streifen von der Unterkante aufwärts. Die zur Laufzeit gebaute `custom_template.json` rechnet das in die nativen `y_start`/`y_end`-Felder um.

---

## 🩺 PII-Patterns

Die ausgelieferten Patterns liegen in [`templates/german_clinical_default.json`](templates/german_clinical_default.json). Wichtigste Gruppen:

| Gruppe | Beispiel-Match |
|---|---|
| `patient_block` | `Herr Müller, Max, *01.01.1960` |
| `case_id` | `Pat.-Nr. 123456789`, `Fall-Nr.: 987654` |
| `address` | `Hauptstraße 123, 37075 Göttingen` |
| `doctor_name` | `Dr. med. Karl Müller`, `Prof. Dr. Schmidt` |
| `doctor_name_parentheses` | `(PD Dr. Christoph Jensen)` |
| `salutation_with_name` | `Herr Müller`, `Frau Schmidt-Bayer` |
| `doctor_signature` (Kontext) | Arztname nach „Mit freundlichen Grüßen" |
| `referring_doctor` (Kontext) | Arztname nach „Zuweiser:" |
| `phone_landline` / `phone_mobile` / `phone_context` | `Tel.: 0561/937690`, `+49 173 1234567`, „unter 12345" |
| `email`, `fax`, `hk_number` | wie zu erwarten |
| `pacemaker_id` | `DR 268880`, `ICD 987654`, `CRT 456789` |

Neue Patterns: in der JSON unter `structured_patterns` ergänzen → im Template-Editor unter „PII-Pattern Aktivierung" einen Toggle hinzufügen (`pages/1_📝_Template_Editor.py`, `_DEFAULT_PATTERNS`).

---

## 🖼️ Bild-Anonymisierung (OCR)

Eingebettete Bilder werden mit Tesseract (deutsch) gescannt. Patterns aus `image_pii_patterns` im Template (Fall-Nr., Name, Geburtsdatum) lösen schwarze Rechtecke auf den Bild-Pixeln aus. Vom selben PDF werden die Bilder nur einmal extrahiert (Effizienz-Fix).

---

## ✂️ Cut-After-Keyword

Im JSON unter `cut_after_keyword`:

```json
"cut_after_keyword": {
  "enabled": true,
  "trigger": "HÄMOSTASEOLOGIE Roche",
  "redact_all_following_pages": true
}
```

Schwärzt von 200pt über der Trigger-Zeile bis zum Seitenende **und** alle nachfolgenden Seiten komplett.

---

## ⌨️ CLI

Sekundärer Aufruf — wenn man mal ein einzelnes PDF ohne UI verarbeiten will:

```bash
python src/main.py input.pdf --output anonymized.pdf \
  --template templates/german_clinical_default.json --extract-images --verbose
```

Optionen:
- `--template / -t` – Pfad zur Template-JSON (Standard: `templates/german_clinical_default.json`)
- `--output / -o` – Output-Pfad
- `--extract-images` – Bilder extrahieren und mit OCR redigieren
- `--verbose / -v` – Debug-Logging

---

## 🧪 Tests

```bash
pytest tests/ -v
```

Abdeckung u. a.:
- Pattern-Matches (Patient-Block, Arztname, PLZ, Adresse, Kontakt, HK-Nummer, Schrittmacher)
- Whitespace-Normalisierung
- Whitelist + Blacklist
- Zone-Schwärzung inkl. `exclude_page`
- Cut-After-Keyword
- Template-Laden + Pydantic-Validierung
- Excel-Export

**Hinweis für Klinik-Rollouts:** Tests und ihre Source-Dateien gehören zusammen — siehe oben.

---

## 🗂️ Projektstruktur

```
redact-clinical-german/
├── app.py                              # Streamlit-Einstiegspunkt
├── pages/
│   └── 1_📝_Template_Editor.py         # Template-Editor-Seite
├── config/
│   └── template_manager.py             # Laden/Speichern der templates/*.json
├── src/
│   ├── main.py                         # CLI + Python-API
│   ├── zone_anonymizer.py              # Zonen + PII-Redaktion + Header-Trigger
│   ├── pii_extractor.py                # Regex-basierte PII-Extraktion
│   ├── image_extractor.py              # Bild-Extraktion aus PDF
│   ├── image_anonymizer.py             # OCR + Bild-Schwärzung
│   ├── excel_exporter.py               # XLSX-Export des anonymisierten Texts
│   └── config.py                       # Pydantic-Modelle
├── templates/
│   ├── german_clinical_default.json    # Basis-Template mit allen Patterns + Zonen
│   ├── default.json                    # User-Template, automatisch erzeugt
│   └── TEMPLATE_DOCUMENTATION.md       # JSON-Felder-Referenz
├── docs/
│   ├── excel_date_shifter.vba          # Optional: Excel-Makro für Datums-Shift
│   └── excel_date_shifting_guide.md
├── tests/
├── requirements.txt                    # Pakete-Whitelist (Offline-Install!)
└── README.md
```

---

## 🔐 Datenschutz

- **Komplett lokal**: kein Cloud-Aufruf, keine Telemetrie.
- **Kein Caching von PII**: Temp-Verzeichnisse werden direkt nach jedem Lauf entfernt; anonymisierte Daten leben nur im Streamlit-Session-Speicher bis du „Ergebnisse löschen" klickst oder den Browser-Tab schließt.
- **Manuelle Nachkontrolle** bleibt Pflicht — Regex erfasst nicht jedes Korner-Case (selten geschriebene Namen, gescannte Bilder ohne OCR-Treffer).

---

## ❓ FAQ

**Warum kein NER?** NER-Modelle markieren medizinische Begriffe (Krankheiten, Medikamente) regelmäßig als Entitäten. Whitelisten für Tausende Fachbegriffe ist nicht praktikabel. Kontextuelle Regex ist präziser.

**Was passiert, wenn ein Patientenname auch im Befundtext steht?** Nur der eigentliche Treffer (z. B. der Name im Patient-Block) wird geschwärzt. Andere Vorkommen bleiben unangetastet, weil PII-Positionen aus dem Page-Wort-Index abgeleitet werden statt per `page.search_for`.

**Header bis Keyword greift nicht — was tun?** Im Sidebar „Debug-Logging aktivieren" und in der Konsole nach `Redacted header until keyword 'X' at y=…` bzw. `header_until_keyword: no trigger from […] found on page` suchen. Der gelbe Warn-Hinweis in der UI listet außerdem alle gesuchten Trigger. Häufige Ursachen: Doppelpunkt/Leerzeichen anders geschrieben („Untersucher" vs. „Untersucher:"), oder das PDF benutzt Non-Breaking-Spaces zwischen Wörtern — letzteres wird seit der robusten Token-Suche aber abgefangen.

**Wie passe ich Pattern an?** [`templates/german_clinical_default.json`](templates/german_clinical_default.json) editieren, Pattern unter `structured_patterns` ergänzen, in `pages/1_📝_Template_Editor.py:_DEFAULT_PATTERNS` denselben Namen aufnehmen und einen Checkbox-Eintrag im passenden Tab anlegen.

**Date-Shifting?** Optional einschaltbar über den Sidebar-Toggle „📅 Date-Shift aktivieren". Verschiebt Datumsangaben direkt im PDF nach festen Regeln (+120 Tage / +4 Monate), markiert geshiftete Daten **gelb**, nicht-geshiftete **rot**. Details im Abschnitt „📅 Date-Shift" weiter oben. Wer den alten Excel-Workflow weiter nutzen will: [`docs/excel_date_shifter.vba`](docs/excel_date_shifter.vba) + [`docs/excel_date_shifting_guide.md`](docs/excel_date_shifting_guide.md) liegen weiterhin im Repo.

---

## 📜 Lizenz

Bitte projektintern klären.
