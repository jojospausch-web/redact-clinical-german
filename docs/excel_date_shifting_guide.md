# Excel Date-Shifting für anonymisierte Arztbriefe

## Warum Excel statt PDF?

Date-Shifting direkt im PDF ist fehleranfällig:
- ❌ Weiße Löcher bei Header/Footer-Überlappung
- ❌ Font-Probleme (Standard-Font vs. Original-Font)
- ❌ Positionierungsprobleme (Text überlappend oder verschoben)
- ❌ Unvollständige Pattern-Matches (z.B. "05.08" ohne Jahr)

Excel bietet eine zuverlässige Alternative:
- ✅ Text-basiertes Replacement (keine Positionierungsprobleme)
- ✅ Vollständige Kontrolle über den Prozess
- ✅ Kein Risiko von visuellen Artefakten
- ✅ Einfaches Undo bei Fehlern

## Workflow-Übersicht

```
PDF anonymisieren → Text nach Excel kopieren → VBA-Makro ausführen → Fertig
(OHNE Date-Shift)   (Daten unverändert)       (Date-Shift in Excel)
```

## Schritt-für-Schritt Anleitung

### 1. PDF anonymisieren (OHNE Date-Shifting)

Das Tool anonymisiert bereits:
- ✅ Namen (Patienten, Ärzte)
- ✅ Adressen
- ✅ Fallnummern
- ✅ Geburtsdatum (wird automatisch geshiftet: `*DD.MM.YYYY`)
- ❌ Behandlungsdaten (bleiben unverändert)

### 2. Text aus PDF nach Excel kopieren

1. Öffnen Sie das anonymisierte PDF
2. Markieren Sie den gesamten Text (Ctrl+A oder Cmd+A)
3. Kopieren Sie den Text (Ctrl+C oder Cmd+C)
4. Öffnen Sie Excel und erstellen Sie eine neue Datei
5. Fügen Sie den Text ein (Ctrl+V oder Cmd+V)
   - Tipp: Nutzen Sie "Als Text einfügen" für beste Ergebnisse

### 3. Excel-Datei als Makro-fähig speichern

1. Speichern Sie die Datei: **Datei → Speichern unter**
2. Wählen Sie das Format: **Excel-Arbeitsmappe mit Makros (*.xlsm)**
3. Speichern Sie die Datei mit einem aussagekräftigen Namen

### 4. VBA-Makro installieren

1. Drücken Sie **Alt + F11** (Windows) oder **Fn + Alt + F11** (Mac)
   - Der VBA-Editor öffnet sich
2. Klicken Sie auf **Einfügen → Modul**
3. Kopieren Sie den Code aus `excel_date_shifter.vba` (siehe unten oder separates File)
4. Fügen Sie den Code in das Modul ein
5. Schließen Sie den VBA-Editor (Alt + Q oder Cmd + Q)

### 5. Shift-Offset festlegen

Am Anfang des Makros finden Sie diese Zeile:

```vba
Const SHIFT_DAYS As Integer = 15  ' ← Hier Offset ändern
```

**Ändern Sie `15` auf Ihren gewünschten Offset:**
- Positiv: Daten werden in die Zukunft verschoben (z.B. `15` = +15 Tage)
- Negativ: Daten werden in die Vergangenheit verschoben (z.B. `-10` = -10 Tage)

### 6. Makro ausführen

1. Markieren Sie die Zellen mit den Daten, die Sie shiften möchten
   - Tipp: Markieren Sie die gesamte Spalte oder den gesamten Bereich
2. Drücken Sie **Alt + F8** (Windows) oder **Fn + Alt + F8** (Mac)
3. Wählen Sie das Makro **"DatumsShift"** aus
4. Klicken Sie auf **Ausführen**

Das Makro:
- Findet alle Daten in den markierten Zellen
- Shiftet sie um den konfigurierten Offset
- Ersetzt sie direkt in den Zellen

### 7. Ergebnis prüfen

Prüfen Sie stichprobenartig einige Daten:
- Sind alle Daten korrekt geshiftet?
- Sind die Formate erhalten geblieben?
- Gibt es fehlerhafte Ersetzungen?

**Beispiel:**

| Vorher | Nachher (Shift +15 Tage) |
|--------|--------------------------|
| `Aufenthalt vom 05.08 bis zum 21.08.2023` | `Aufenthalt vom 20.08 bis zum 05.09.2023` |
| `Herzkatheteruntersuchung vom 16.08.2023` | `Herzkatheteruntersuchung vom 31.08.2023` |
| `Patient aufgenommen am 5. November 2023` | `Patient aufgenommen am 20. November 2023` |

## Unterstützte Datumsformate

Das Makro erkennt folgende Formate:

### 1. Vollständige Daten (DD.MM.YYYY)
- `21.08.2023` → `05.09.2023`
- `05.08.2023` → `20.08.2023`

### 2. Kurzdaten (DD.MM ohne Jahr)
- `vom 05.08` → `vom 20.08`
- `bis zum 21.08` → `bis zum 05.09`

### 3. Deutsche Monatsnamen (ausgeschrieben)
- `5. November 2023` → `20. November 2023`
- `16. August 2023` → `31. August 2023`

### 4. Abgekürzte Monatsnamen
- `5. Nov. 2023` → `20. Nov. 2023`
- `16. Aug. 2023` → `31. Aug. 2023`

### 5. Datumsbereiche
- `vom 05.08 bis zum 21.08.2023` → `vom 20.08 bis zum 05.09.2023`

## Fehlerbehebung

### Problem: "Makros sind deaktiviert"

**Lösung:**
1. Schließen Sie die Datei
2. Öffnen Sie Excel → Optionen → Trust Center → Einstellungen für das Trust Center
3. Makroeinstellungen: Wählen Sie "Alle Makros mit Benachrichtigung aktivieren"
4. Öffnen Sie die Datei erneut
5. Klicken Sie auf "Inhalt aktivieren"

### Problem: "Makro nicht gefunden"

**Lösung:**
- Überprüfen Sie, ob die Datei als `.xlsm` gespeichert ist
- Öffnen Sie den VBA-Editor (Alt + F11) und prüfen Sie, ob das Modul vorhanden ist

### Problem: "Datum wird nicht geshiftet"

**Mögliche Ursachen:**
1. Format wird nicht erkannt → Prüfen Sie das Format
2. Zelle ist nicht markiert → Markieren Sie die richtige Zelle
3. Datum ist kein Text → Konvertieren Sie Zellen zu Text-Format

### Problem: "Monat wechselt falsch (z.B. August → September)"

**Das ist korrekt!**
- Beispiel: `25. August + 15 Tage = 9. September`
- Das Makro berücksichtigt automatisch Monats- und Jahreswechsel

## Sicherheitshinweise

1. **Immer eine Backup-Kopie erstellen** bevor Sie das Makro ausführen
2. **Prüfen Sie das Ergebnis** stichprobenartig
3. **Nutzen Sie Undo (Ctrl+Z)** falls etwas schief geht
4. **Speichern Sie erst nach Prüfung** der Ergebnisse

## VBA-Code-Quelle

Der komplette VBA-Code befindet sich in der Datei:
- **`docs/excel_date_shifter.vba`**

Alternativ können Sie den Code direkt aus der Dokumentation kopieren (siehe nächste Seite).

## Lizenz und Support

Dieses Makro ist Teil des `redact-clinical-german` Projekts.
- **Lizenz:** [Siehe Repository-Lizenz]
- **Issues:** https://github.com/jojospausch-web/redact-clinical-german/issues
- **Dokumentation:** https://github.com/jojospausch-web/redact-clinical-german
