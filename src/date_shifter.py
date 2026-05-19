"""Date-Shifting für deutsche Arztbriefe.

Erkennt Datumsangaben im Text, schiebt sie nach festen Regeln um +120 Tage
(Volldaten) bzw. +4 Monate (Monat/Jahr-Formen) und liefert pro Treffer eine
Anweisung: shiften+gelb markieren oder unverändert lassen+rot markieren.

Regel-Auswahl basiert auf dem Aufnahmedatum aus einem "vom DD.MM[.YYYY] bis
(zum)? DD.MM.YYYY"-Span:

| Aufnahme-Tag | Aufnahme-Monat | Standalone YYYY im Text | Modus              |
|--------------|----------------|--------------------------|--------------------|
| 27 – 31      | beliebig       | egal                     | monthend           |
| 01 – 26      | Sep – Dez (9-12)| ja                      | shift_year_leak    |
| 01 – 26      | Sep – Dez       | nein                    | shift_safe         |
| 01 – 26      | Jan – Aug (1-8) | egal                    | shift_safe         |
| (kein "vom…bis…"-Span gefunden)                               | no_stay            |

In `monthend`/`no_stay`: kein Shift, ALLE erkannten Daten werden rot markiert.
In `shift_safe`: alle Daten werden geshiftet und gelb markiert.
In `shift_year_leak`: Volldaten/Monat-Jahr werden geshiftet (gelb),
alleinstehende Jahreszahlen werden NICHT geshiftet, aber rot markiert.

Geburtsdaten (Marker "geb.", "*", "geboren am", "Geburtstag" davor) werden
in jedem Modus rot markiert und NIE geshiftet.

Das Modul ist rein logisch — die PDF-Annotationen setzt der Anonymizer in
zone_anonymizer.py auf Basis der hier zurückgegebenen `DateAction`-Liste.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional, Tuple

from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)

# ── Konstanten ────────────────────────────────────────────────────────────────

SHIFT_DAYS = 120
SHIFT_MONTHS = 4

GERMAN_MONTHS_FULL = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]
GERMAN_MONTHS_ABBR = [
    "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
    "Jul", "Aug", "Sep", "Okt", "Nov", "Dez",
]
_GERMAN_MONTH_TO_NUM = {name.lower(): i + 1 for i, name in enumerate(GERMAN_MONTHS_FULL)}
_GERMAN_MONTH_TO_NUM.update({name.lower(): i + 1 for i, name in enumerate(GERMAN_MONTHS_ABBR)})

# ── Regex-Patterns ────────────────────────────────────────────────────────────

# DD.MM.YYYY — vollständiges Datum (höchste Priorität)
RE_DDMMYYYY = re.compile(r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b')

# D. Monatsname YYYY  (auch abgekürzt: "5. Nov. 2023")
_MONTH_NAMES_RE = "|".join(re.escape(m) for m in GERMAN_MONTHS_FULL + GERMAN_MONTHS_ABBR)
RE_GERMAN_DATE = re.compile(
    r'\b(\d{1,2})\.\s+(' + _MONTH_NAMES_RE + r')(\.?)\s+(\d{4})\b',
    re.IGNORECASE,
)

# Aufenthalts-Range / Behandlungs-Zeitraum mit numerischen Daten.
# Akzeptiert mehrere Trenner-Varianten:
#   - "vom 05.08 bis zum 21.08.2023"   (klassisch mit "vom" + "bis")
#   - "vom 20.11. bis 26.11.2024"      (trailing dot nach erstem Datum)
#   - "20.11. - 26.11.2024"            (Bindestrich statt "bis", ohne "vom")
#   - "20.11.2024 – 26.11.2024"        (Halbgeviertstrich)
#   - "zwischen 05.08.2023 und 21.08.2023"
# "vom" / "zwischen" ist OPTIONAL — Antibiotika-Ranges schreiben oft
# nur "20.11. - 26.11.2024" ohne Einleitung.
RE_STAY_RANGE = re.compile(
    r'(?:\b(?:vom|zwischen)\s+)?'
    r'(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\.?\s*'    # optional trailing dot + flex whitespace
    r'(?:bis(?:\s+zum)?|und|-|–|—)\s*'             # bis / und / Bindestrich / Halbgeviertstrich
    r'(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\b',
    re.IGNORECASE,
)

# Aufenthalts-Range mit deutschen Monatsnamen:
# "vom 5. November (2023)? bis (zum)? 21. November 2023"
RE_STAY_RANGE_GERMAN = re.compile(
    r'\b(?:vom|zwischen)\s+'
    r'(\d{1,2})\.\s+(' + _MONTH_NAMES_RE + r')\.?(?:\s+(\d{4}))?\s+'
    r'(?:bis(?:\s+zum)?|und)\s+'
    r'(\d{1,2})\.\s+(' + _MONTH_NAMES_RE + r')\.?\s+(\d{4})\b',
    re.IGNORECASE,
)

# Monatsname + Jahr OHNE Tag ("Januar 2024", "Nov. 2023")
RE_MONTH_NAME_YEAR = re.compile(
    r'\b(' + _MONTH_NAMES_RE + r')\.?\s+(\d{4})\b',
    re.IGNORECASE,
)

# Standalone Monatsname mit Kontext-Indikator (kein Jahr danach).
# Schützt vor False-Positives wie "Juli Schmidt" (Name).
_STANDALONE_MONTH_CONTEXT = (
    r'(?:seit|ab|im|in|von|bis|vom|nach|vor|zum|am|'
    r'Mitte|Anfang|Ende|Beginn)'
)
RE_STANDALONE_MONTH = re.compile(
    r'\b' + _STANDALONE_MONTH_CONTEXT + r'\s+(' + _MONTH_NAMES_RE + r')\b',
    re.IGNORECASE,
)

# MM.YYYY  (Monat + Jahr, numerisch)
RE_MM_YYYY_DOT = re.compile(r'\b(\d{1,2})\.(\d{4})\b')

# MM/YYYY oder MM/YY
RE_MM_SLASH = re.compile(r'\b(\d{1,2})/(\d{2,4})\b')

# Alleinstehende Jahreszahl 1950 – 2039
RE_STANDALONE_YYYY = re.compile(r'\b(19[5-9]\d|20[0-3]\d)\b')

# Geburtsdatums-Marker direkt VOR einem Datum
RE_BIRTHDATE_MARKER = re.compile(
    r'(?:geb\.?|\*|geboren\s+am|Geburtstag\s*:?)\s*$',
    re.IGNORECASE,
)

# Indikatoren für Blutdruck-Werte — verhindert, dass "120/80" als MM/YY
# interpretiert wird
BLOOD_PRESSURE_INDICATORS = (
    'mmhg', 'mm hg', ' rr ', 'rr:', 'rr ', 'blutdruck', '/min', 'syst', 'diast',
)


# ── Datenklassen ──────────────────────────────────────────────────────────────


@dataclass
class DateHit:
    """Ein im Text erkanntes Datum (vor Regel-Auswertung)."""
    start: int                # Char-Offset im normalisierten Text
    end: int
    raw_text: str             # Originaler Substring
    kind: str                 # 'full' | 'german' | 'month_year' |
                              # 'month_only' | 'standalone_yyyy'
    parsed: Optional[date] = None   # für full/german
    month: Optional[int] = None     # für month_year, month_only
    year: Optional[int] = None      # für month_year und standalone_yyyy
    fmt: Optional[str] = None       # Output-Format-Hint
                                    # ('MM.YYYY', 'MM/YYYY', 'MM/YY',
                                    #  'MONTH_NAME_YEAR', 'MONTH_NAME_ONLY')
    is_birthdate: bool = False


@dataclass
class DateAction:
    """Was der Anonymizer pro Treffer zu tun hat."""
    start: int
    end: int
    raw_text: str
    do_shift: bool
    new_text: Optional[str] = None   # Ersatztext bei do_shift=True
    color: str = "yellow"             # "yellow" oder "red"
    tooltip: str = ""
    reason: str = ""                  # interner Grund (für Logs)


# ── Erkennung ─────────────────────────────────────────────────────────────────


def _overlaps_any(start: int, end: int, hits: List[DateHit]) -> bool:
    """Prüfe, ob [start, end) mit einem bereits gefundenen Treffer überlappt."""
    return any(h.start < end and start < h.end for h in hits)


def _is_birthdate_context(text: str, start: int, look_back: int = 25) -> bool:
    """Liegt einer der Geburtsdatums-Marker direkt vor *start*?"""
    pre = text[max(0, start - look_back):start]
    return bool(RE_BIRTHDATE_MARKER.search(pre))


def _is_blood_pressure_context(text: str, start: int, end: int, window: int = 20) -> bool:
    """Heuristik: 'NN/MM' in Blutdruck-Kontext (mmHg, RR, …).

    Wir schauen ±20 Zeichen, aber nur bis zur nächsten Zeilen- oder
    Satzgrenze — damit ein "RR ..." in der nächsten Zeile nicht das
    Datum "11/23" in der vorigen Zeile als Blutdruck mit-klassifiziert.
    """
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    # Schneide am nächsten Newline / Satzpunkt vor *start* ab
    pre = text[lo:start]
    for sep in ("\n", ". ", "; "):
        idx = pre.rfind(sep)
        if idx >= 0:
            lo = lo + idx + len(sep)
            break
    # Genauso nach *end* abschneiden
    post = text[end:hi]
    for sep in ("\n", ". ", "; "):
        idx = post.find(sep)
        if idx >= 0:
            hi = end + idx
            break
    context = text[lo:hi].lower()
    return any(ind in context for ind in BLOOD_PRESSURE_INDICATORS)


def detect_dates(text: str) -> List[DateHit]:
    """Finde alle Datums-Vorkommen im Text, sortiert nach Position.

    Niedriger-priorisierte Patterns (z. B. MM.YYYY) werden gefiltert, damit
    sie nicht innerhalb eines schon erkannten DD.MM.YYYY matchen.
    """
    hits: List[DateHit] = []

    # 1) DD.MM.YYYY
    for m in RE_DDMMYYYY.finditer(text):
        d_, mo_, y_ = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            parsed = date(y_, mo_, d_)
        except ValueError:
            continue
        hits.append(DateHit(
            start=m.start(), end=m.end(),
            raw_text=m.group(0),
            kind="full",
            parsed=parsed,
            is_birthdate=_is_birthdate_context(text, m.start()),
        ))

    # 1b) "vom DD.MM. bis DD.MM.YYYY" — das erste Datum hat oft KEIN Jahr.
    # Wir extrahieren beide DD.MM.-Teile (mit Jahr aus dem zweiten Datum)
    # und fügen sie als Volldaten hinzu, sofern sie noch nicht erkannt sind.
    for m in RE_STAY_RANGE.finditer(text):
        d1, mo1, y1 = int(m.group(1)), int(m.group(2)), m.group(3)
        d2, mo2, y2 = int(m.group(4)), int(m.group(5)), m.group(6)
        year_str = y1 or y2
        if not year_str:
            continue
        year = int(year_str)
        # Erstes Datum
        try:
            parsed1 = date(year, mo1, d1)
        except ValueError:
            parsed1 = None
        # Zweites Datum
        try:
            parsed2 = date(year, mo2, d2)
        except ValueError:
            parsed2 = None
        for d_, mo_, parsed_, gi in [(d1, mo1, parsed1, 1), (d2, mo2, parsed2, 4)]:
            if parsed_ is None:
                continue
            raw_start = m.start(gi)
            # End-Offset: bei "DD.MM" ohne Jahr bis nach dem 2. Punkt,
            # bei "DD.MM.YYYY" bis nach dem Jahr
            year_group = gi + 2
            has_year = m.group(year_group) is not None
            raw_end = m.end(year_group) if has_year else m.end(gi + 1)
            # Plus den nachfolgenden Punkt einschließen, falls vorhanden
            # (DD.MM. mit nachgestelltem Punkt vor "bis")
            if not has_year and raw_end < len(text) and text[raw_end] == ".":
                raw_end += 1
            if _overlaps_any(raw_start, raw_end, hits):
                continue
            hits.append(DateHit(
                start=raw_start, end=raw_end,
                raw_text=text[raw_start:raw_end],
                kind="full",
                parsed=parsed_,
                is_birthdate=False,
            ))

    # 1c) "vom 5. November (2023)? bis 21. November 2023" — analog für
    # deutsche Monatsnamen.
    for m in RE_STAY_RANGE_GERMAN.finditer(text):
        d1 = int(m.group(1))
        mo1_name = m.group(2)
        y1 = m.group(3)
        d2 = int(m.group(4))
        mo2_name = m.group(5)
        y2 = m.group(6)
        mo1 = _GERMAN_MONTH_TO_NUM.get(mo1_name.lower())
        mo2 = _GERMAN_MONTH_TO_NUM.get(mo2_name.lower())
        if mo1 is None or mo2 is None:
            continue
        year_str = y1 or y2
        if not year_str:
            continue
        year = int(year_str)
        try:
            parsed1 = date(year, mo1, d1)
        except ValueError:
            parsed1 = None
        try:
            parsed2 = date(year, mo2, d2)
        except ValueError:
            parsed2 = None
        for parsed_, gi in [(parsed1, 1), (parsed2, 4)]:
            if parsed_ is None:
                continue
            raw_start = m.start(gi)
            # End-Offset: bei "D. Monat" ohne Jahr bis nach dem Monatsnamen,
            # bei "D. Monat YYYY" bis nach dem Jahr
            year_group = gi + 2
            has_year = m.group(year_group) is not None
            raw_end = m.end(year_group) if has_year else m.end(gi + 1)
            if _overlaps_any(raw_start, raw_end, hits):
                continue
            hits.append(DateHit(
                start=raw_start, end=raw_end,
                raw_text=text[raw_start:raw_end],
                kind="german",
                parsed=parsed_,
                is_birthdate=False,
            ))

    # 2) Deutsche Monatsnamen (mit Tag UND Jahr: "5. November 2023")
    for m in RE_GERMAN_DATE.finditer(text):
        d_ = int(m.group(1))
        mo_name = m.group(2)
        y_ = int(m.group(4))
        mo_ = _GERMAN_MONTH_TO_NUM.get(mo_name.lower())
        if mo_ is None:
            continue
        try:
            parsed = date(y_, mo_, d_)
        except ValueError:
            continue
        if _overlaps_any(m.start(), m.end(), hits):
            continue
        hits.append(DateHit(
            start=m.start(), end=m.end(),
            raw_text=m.group(0),
            kind="german",
            parsed=parsed,
            is_birthdate=_is_birthdate_context(text, m.start()),
        ))

    # 3) MM.YYYY
    for m in RE_MM_YYYY_DOT.finditer(text):
        mo_, y_ = int(m.group(1)), int(m.group(2))
        if not (1 <= mo_ <= 12 and 1950 <= y_ <= 2039):
            continue
        if _overlaps_any(m.start(), m.end(), hits):
            continue
        hits.append(DateHit(
            start=m.start(), end=m.end(),
            raw_text=m.group(0),
            kind="month_year",
            month=mo_, year=y_,
            fmt="MM.YYYY",
            is_birthdate=_is_birthdate_context(text, m.start()),
        ))

    # 4) MM/YYYY oder MM/YY
    for m in RE_MM_SLASH.finditer(text):
        mo_str, y_str = m.group(1), m.group(2)
        mo_ = int(mo_str)
        if not (1 <= mo_ <= 12):
            continue
        if _is_blood_pressure_context(text, m.start(), m.end()):
            continue
        y_raw = int(y_str)
        if len(y_str) == 2:
            # Konservativ: 2-stellige Jahre nur 00–39 (= 2000–2039).
            # Werte 40–99 sind ambig (40 = 1940 oder 2040? "80" = 1980 oder
            # Blutdruckwert?) → verwerfen, dann muss der Brief 4-stellig
            # schreiben.
            if not (0 <= y_raw <= 39):
                continue
            y_full = 2000 + y_raw
            fmt = "MM/YY"
        elif len(y_str) == 4:
            y_full = y_raw
            if not (1950 <= y_full <= 2039):
                continue
            fmt = "MM/YYYY"
        else:
            continue
        if _overlaps_any(m.start(), m.end(), hits):
            continue
        hits.append(DateHit(
            start=m.start(), end=m.end(),
            raw_text=m.group(0),
            kind="month_year",
            month=mo_, year=y_full,
            fmt=fmt,
            is_birthdate=_is_birthdate_context(text, m.start()),
        ))

    # 5) Monatsname + Jahr ohne Tag ("Januar 2024", "Nov. 2023")
    for m in RE_MONTH_NAME_YEAR.finditer(text):
        mo_name = m.group(1)
        y_ = int(m.group(2))
        mo_ = _GERMAN_MONTH_TO_NUM.get(mo_name.lower())
        if mo_ is None or not (1950 <= y_ <= 2039):
            continue
        if _overlaps_any(m.start(), m.end(), hits):
            continue
        hits.append(DateHit(
            start=m.start(), end=m.end(),
            raw_text=m.group(0),
            kind="month_year",
            month=mo_, year=y_,
            fmt="MONTH_NAME_YEAR",
            is_birthdate=_is_birthdate_context(text, m.start()),
        ))

    # 6) Standalone Monatsname mit Kontext ("seit Juli", "im November")
    for m in RE_STANDALONE_MONTH.finditer(text):
        mo_name = m.group(1)
        mo_ = _GERMAN_MONTH_TO_NUM.get(mo_name.lower())
        if mo_ is None:
            continue
        # Nur den Monatsnamen-Bereich ersetzen, nicht das Indikator-Wort
        mo_start, mo_end = m.start(1), m.end(1)
        if _overlaps_any(mo_start, mo_end, hits):
            continue
        hits.append(DateHit(
            start=mo_start, end=mo_end,
            raw_text=mo_name,
            kind="month_only",
            month=mo_,
            year=None,  # ohne Jahr — wird via admission inferiert
            fmt="MONTH_NAME_ONLY",
        ))

    # 7) Alleinstehende Jahreszahl
    for m in RE_STANDALONE_YYYY.finditer(text):
        y_ = int(m.group(0))
        if _overlaps_any(m.start(), m.end(), hits):
            continue
        hits.append(DateHit(
            start=m.start(), end=m.end(),
            raw_text=m.group(0),
            kind="standalone_yyyy",
            year=y_,
        ))

    hits.sort(key=lambda h: h.start)
    return hits


def find_admission_date(text: str) -> Optional[date]:
    """Aufnahmedatum aus 'vom DD.MM[.YYYY] bis DD.MM[.YYYY]' extrahieren.

    Wenn das erste Datum kein Jahr hat, wird das Jahr vom zweiten Datum
    übernommen (typisches Briefmuster „vom 05.08. bis 21.08.2023").
    Zusätzlich unterstützt: deutsche Monatsnamen
    („vom 5. November bis 21. November 2023").
    """
    # Variante 1: numerisches DD.MM[.YYYY]
    for m in RE_STAY_RANGE.finditer(text):
        d1 = int(m.group(1)); mo1 = int(m.group(2))
        y1 = m.group(3)
        y2 = m.group(6)
        year_str = y1 or y2
        if not year_str:
            continue
        try:
            return date(int(year_str), mo1, d1)
        except ValueError:
            continue
    # Variante 2: deutsche Monatsnamen
    for m in RE_STAY_RANGE_GERMAN.finditer(text):
        d1 = int(m.group(1))
        mo1_name = m.group(2)
        mo1 = _GERMAN_MONTH_TO_NUM.get(mo1_name.lower())
        if mo1 is None:
            continue
        y1 = m.group(3)
        y2 = m.group(6)
        year_str = y1 or y2
        if not year_str:
            continue
        try:
            return date(int(year_str), mo1, d1)
        except ValueError:
            continue
    return None


# ── Regel-Auswahl ─────────────────────────────────────────────────────────────


def decide_mode(admission: Optional[date], hits: List[DateHit]) -> str:
    """Liefert: 'no_stay' | 'monthend' | 'shift_year_leak' | 'shift_safe'."""
    if admission is None:
        return "no_stay"
    if admission.day >= 27:
        return "monthend"
    has_year_leak = any(h.kind == "standalone_yyyy" for h in hits)
    if admission.month >= 9 and has_year_leak:
        return "shift_year_leak"
    return "shift_safe"


def decide_document_mode(full_text: str) -> Tuple[str, Optional[date]]:
    """Bestimme den Modus über den GESAMTEN Brief (alle Seiten zusammen).

    Der „vom…bis…"-Span steht typischerweise nur auf Seite 1, das Year-Leak
    kann aber auf jeder Seite stehen. Mode-Entscheidung pro Seite würde
    Seite 2/3 in `no_stay` zwingen, obwohl der ganze Brief eigentlich
    `shift_safe` ist. Deshalb diese dokumentweite Variante.

    Returns:
        (mode, admission_date) — `admission_date` kann zum Debuggen / für
        Audit-Logs nützlich sein.
    """
    admission = find_admission_date(full_text)
    hits = detect_dates(full_text)
    return decide_mode(admission, hits), admission


# ── Shift- und Formatier-Helfer ───────────────────────────────────────────────


def shift_full_date(d: date) -> date:
    """+120 Tage."""
    return d + timedelta(days=SHIFT_DAYS)


def shift_month_year(month: int, year: int) -> Tuple[int, int]:
    """+4 Monate. Sep–Dez rollen automatisch ins nächste Jahr."""
    shifted = date(year, month, 1) + relativedelta(months=SHIFT_MONTHS)
    return shifted.month, shifted.year


_RE_GERMAN_DATE_NO_YEAR = re.compile(
    r'^(\d{1,2})\.\s+(' + _MONTH_NAMES_RE + r')(\.?)$',
    re.IGNORECASE,
)


def _format_full_date(new_d: date, raw_original: str) -> str:
    """Shifted date im selben Stil wie das Original ausgeben."""
    # German-named-month with year? ("5. November 2023")
    m = RE_GERMAN_DATE.match(raw_original)
    if m:
        orig_month_str = m.group(2)
        had_dot = m.group(3) == "."
        is_abbr = orig_month_str.lower() in (mn.lower() for mn in GERMAN_MONTHS_ABBR)
        if is_abbr:
            new_month_name = GERMAN_MONTHS_ABBR[new_d.month - 1]
            dot = "." if had_dot else ""
            return f"{new_d.day}. {new_month_name}{dot} {new_d.year}"
        new_month_name = GERMAN_MONTHS_FULL[new_d.month - 1]
        return f"{new_d.day}. {new_month_name} {new_d.year}"
    # German-named-month WITHOUT year? ("5. November" als erste Hälfte eines
    # Stay-Range)
    m = _RE_GERMAN_DATE_NO_YEAR.match(raw_original)
    if m:
        orig_month_str = m.group(2)
        had_dot = m.group(3) == "."
        is_abbr = orig_month_str.lower() in (mn.lower() for mn in GERMAN_MONTHS_ABBR)
        if is_abbr:
            new_month_name = GERMAN_MONTHS_ABBR[new_d.month - 1]
            dot = "." if had_dot else ""
            return f"{new_d.day}. {new_month_name}{dot}"
        new_month_name = GERMAN_MONTHS_FULL[new_d.month - 1]
        return f"{new_d.day}. {new_month_name}"
    # DD.MM.YYYY oder DD.MM[.] (ohne Jahr) — Original-Format beibehalten
    stripped = raw_original.rstrip(".")  # trailing dot stripped temporarily
    parts = stripped.split(".")
    if len(parts) >= 2:
        d_pad = len(parts[0]) == 2
        m_pad = len(parts[1]) == 2
        d_str = f"{new_d.day:02d}" if d_pad else str(new_d.day)
        m_str = f"{new_d.month:02d}" if m_pad else str(new_d.month)
        if len(parts) == 3:
            # Original hatte ein Jahr → mit Jahr ausgeben
            return f"{d_str}.{m_str}.{new_d.year}"
        # Original war nur DD.MM ohne Jahr → ohne Jahr zurück, evtl. mit
        # trailing dot, wie das Original
        trailing_dot = "." if raw_original.endswith(".") else ""
        return f"{d_str}.{m_str}{trailing_dot}"
    return new_d.strftime("%d.%m.%Y")


def _format_month_year(new_month: int, new_year: int, fmt: str, raw_original: str = "") -> str:
    """Shifted Monat/Jahr in das ursprüngliche Format zurück."""
    if fmt == "MM.YYYY":
        return f"{new_month:02d}.{new_year:04d}"
    if fmt == "MM/YYYY":
        return f"{new_month:02d}/{new_year:04d}"
    if fmt == "MM/YY":
        return f"{new_month:02d}/{new_year % 100:02d}"
    if fmt == "MONTH_NAME_YEAR":
        # Beibehalten ob Original abgekürzt war und ob ein Punkt folgte
        # ("Nov. 2023" vs "November 2023" vs "Nov 2023")
        is_abbr = False
        had_dot = False
        if raw_original:
            # Extrahiere den Monatsnamen-Teil
            mo_match = re.match(r'^(\S+?)(\.?)\s+\d{4}$', raw_original)
            if mo_match:
                orig_name = mo_match.group(1)
                had_dot = mo_match.group(2) == "."
                is_abbr = orig_name.lower() in (mn.lower() for mn in GERMAN_MONTHS_ABBR)
        new_name = (GERMAN_MONTHS_ABBR[new_month - 1] if is_abbr
                    else GERMAN_MONTHS_FULL[new_month - 1])
        dot = "." if (is_abbr and had_dot) else ""
        return f"{new_name}{dot} {new_year}"
    return f"{new_month:02d}.{new_year:04d}"


def _format_month_only(new_month: int, raw_original: str) -> str:
    """Ersetze einen einzelnen Monatsnamen durch den neuen.

    Beibehält Abkürzung (falls Original abgekürzt war) und Großschreibung.
    Year wird NICHT ausgegeben — wir wollen das Original-Format "Juli"
    nicht zu "November 2024" aufblähen.
    """
    is_abbr = raw_original.lower() in (mn.lower() for mn in GERMAN_MONTHS_ABBR)
    new_name = (GERMAN_MONTHS_ABBR[new_month - 1] if is_abbr
                else GERMAN_MONTHS_FULL[new_month - 1])
    # Großschreibung übernehmen (im Deutschen sind Monatsnamen
    # standardmäßig groß; Edge-Case "juli" lowercase nur falls original so)
    if raw_original and raw_original[0].islower():
        new_name = new_name[0].lower() + new_name[1:]
    return new_name


# ── Hauptfunktion ─────────────────────────────────────────────────────────────


def plan_actions(
    text: str,
    force_mode: Optional[str] = None,
    force_admission: Optional[date] = None,
) -> Tuple[str, List[DateAction]]:
    """Erkennen + Regel anwenden + Aktion pro Datum berechnen.

    Args:
        text: Der bereits zu Wörtern normalisierte Seitentext.
        force_mode: Wenn gesetzt, wird dieser Modus statt der eigenen
            Regelauswertung übernommen. Wichtig für mehrseitige Briefe:
            der Modus wird dokumentweit bestimmt (siehe
            `decide_document_mode`), damit Seite 2/3 nicht in `no_stay`
            fällt, nur weil dort kein „vom…bis…"-Span steht.
        force_admission: Aufnahme-Datum aus dem Gesamtdokument. Wird für
            standalone Monatsnamen ohne Jahr ("seit Juli") benötigt, weil
            wir dort das Jahr aus dem Aufnahme-Kontext borgen müssen.

    Returns:
        (mode, actions) — mode für Logging/Audit, actions zum Anwenden.
    """
    hits = detect_dates(text)
    if force_mode is not None:
        mode = force_mode
        admission = force_admission
    else:
        admission = find_admission_date(text)
        mode = decide_mode(admission, hits)

    actions: List[DateAction] = []

    for h in hits:
        # Geburtsdaten: nie shiften, immer rot
        if h.is_birthdate:
            actions.append(DateAction(
                start=h.start, end=h.end, raw_text=h.raw_text,
                do_shift=False, color="red",
                tooltip="Geburtsdatum — nicht verschoben",
                reason="birthdate",
            ))
            continue

        # no_stay / monthend → alles rot, kein Shift
        if mode in ("no_stay", "monthend"):
            actions.append(DateAction(
                start=h.start, end=h.end, raw_text=h.raw_text,
                do_shift=False, color="red",
                tooltip=("Kein Aufenthalts-Range erkannt"
                         if mode == "no_stay"
                         else "Aufnahme ≥ 27. — nicht verschoben"),
                reason=mode,
            ))
            continue

        # shift_year_leak: alleinstehendes YYYY rot lassen
        if mode == "shift_year_leak" and h.kind == "standalone_yyyy":
            actions.append(DateAction(
                start=h.start, end=h.end, raw_text=h.raw_text,
                do_shift=False, color="red",
                tooltip="Alleinstehende Jahreszahl — bitte prüfen",
                reason="year_leak",
            ))
            continue

        # alleinstehendes YYYY in shift_safe: nichts tun, sollte aber
        # nicht vorkommen (decide_mode liefert dann shift_year_leak)
        if h.kind == "standalone_yyyy":
            continue

        # KONSERVATIVER MODUS:
        # Nur DD.MM[.YYYY] (numerisches Voll-/Stay-Range-Datum) wird tatsächlich
        # GESHIFTET — alles andere (deutsche Monatsnamen "5. November 2023",
        # MM.YYYY, MM/YYYY, MM/YY, "Januar 2024", "seit Juli", ...) wird nur
        # ROT markiert. Begründung: bei ausgeschriebenen Formaten / Kurz-
        # formaten ist die Reading-Order-Korrektur unzuverlässig und das
        # Risiko von False-Positives (z. B. "8/31" CT-Bildnummer) zu groß.
        # Der User markiert den Rest manuell.
        if h.kind == "full":
            new_d = shift_full_date(h.parsed)
            new_text = _format_full_date(new_d, h.raw_text)
            actions.append(DateAction(
                start=h.start, end=h.end, raw_text=h.raw_text,
                do_shift=True, new_text=new_text, color="yellow",
                tooltip=f"+{SHIFT_DAYS} Tage",
                reason="shifted_full",
            ))
        elif h.kind == "german":
            # "5. November 2023" — NICHT shiften, nur markieren
            actions.append(DateAction(
                start=h.start, end=h.end, raw_text=h.raw_text,
                do_shift=False, color="red",
                tooltip="Ausgeschriebenes Datum — bitte manuell prüfen",
                reason="german_date_not_shifted",
            ))
        elif h.kind == "month_year":
            # MM.YYYY, MM/YYYY, MM/YY, "Januar 2024" — NICHT shiften
            actions.append(DateAction(
                start=h.start, end=h.end, raw_text=h.raw_text,
                do_shift=False, color="red",
                tooltip="Monat/Jahr-Format — bitte manuell prüfen",
                reason="month_year_not_shifted",
            ))
        elif h.kind == "month_only":
            # Standalone Monatsname — NICHT shiften
            actions.append(DateAction(
                start=h.start, end=h.end, raw_text=h.raw_text,
                do_shift=False, color="red",
                tooltip="Monatsname ohne Jahr — bitte manuell prüfen",
                reason="month_only_not_shifted",
            ))
        else:
            # Fallback für unbekannte kinds — fail-safe als rot markieren
            actions.append(DateAction(
                start=h.start, end=h.end, raw_text=h.raw_text,
                do_shift=False, color="red",
                tooltip="Datums-ähnlich — bitte manuell prüfen",
                reason="unknown_kind",
            ))
    logger.info(
        "Date-Shift Modus=%s | Aufnahme=%s | erkannte Daten=%d | Aktionen=%d",
        mode, admission, len(hits), len(actions),
    )
    return mode, actions
