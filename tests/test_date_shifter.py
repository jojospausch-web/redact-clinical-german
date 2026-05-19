"""Unit tests for src/date_shifter.py.

Wir testen rein die textbasierte Logik (Erkennung, Regelauswahl, Shift-
Arithmetik, Formatierung) — die PDF-Annotations-Seite läuft im
zone_anonymizer und braucht ein echtes PDF zum Testen (nicht hier).
"""

from datetime import date

import pytest

from src.date_shifter import (
    DateAction,
    DateHit,
    SHIFT_DAYS,
    SHIFT_MONTHS,
    decide_document_mode,
    decide_mode,
    detect_dates,
    find_admission_date,
    plan_actions,
    shift_full_date,
    shift_month_year,
    _format_full_date,
    _format_month_year,
)


# ── detect_dates ──────────────────────────────────────────────────────────────


class TestDetectDates:
    def test_full_date(self):
        hits = detect_dates("Aufnahme am 05.08.2023.")
        assert len(hits) == 1
        h = hits[0]
        assert h.kind == "full"
        assert h.parsed == date(2023, 8, 5)
        assert h.raw_text == "05.08.2023"

    def test_german_named_month(self):
        hits = detect_dates("am 5. November 2023 erstmals")
        assert len(hits) == 1
        assert hits[0].kind == "german"
        assert hits[0].parsed == date(2023, 11, 5)

    def test_german_abbreviated_month(self):
        hits = detect_dates("Entlassung 5. Nov. 2023")
        assert len(hits) == 1
        assert hits[0].kind == "german"
        assert hits[0].parsed == date(2023, 11, 5)

    def test_mm_yyyy_with_dot(self):
        hits = detect_dates("Diagnose erstmals 11.2020")
        assert len(hits) == 1
        h = hits[0]
        assert h.kind == "month_year"
        assert (h.month, h.year, h.fmt) == (11, 2020, "MM.YYYY")

    def test_mm_yyyy_does_not_overlap_full_date(self):
        # In "05.08.2023" the "08.2023" must NOT also match as MM.YYYY
        hits = detect_dates("Aufnahme am 05.08.2023")
        kinds = [h.kind for h in hits]
        assert kinds.count("full") == 1
        assert "month_year" not in kinds

    def test_mm_slash_yyyy(self):
        hits = detect_dates("Reha im Zeitraum 11/2020")
        assert len(hits) == 1
        h = hits[0]
        assert h.kind == "month_year"
        assert (h.month, h.year, h.fmt) == (11, 2020, "MM/YYYY")

    def test_mm_slash_yy(self):
        hits = detect_dates("Letzter Termin 11/23")
        assert any(h.kind == "month_year" and h.month == 11 and h.year == 2023 and h.fmt == "MM/YY"
                   for h in hits)

    def test_blood_pressure_is_not_a_date(self):
        # "120/80" — first number is 120, > 12, gets rejected
        # "10/80" — month 10 ok, but context contains "mmHg" → rejected
        hits = detect_dates("RR bei Aufnahme 120/80 mmHg")
        month_year_hits = [h for h in hits if h.kind == "month_year"]
        # 120/80 fails plausibility; if any 10/80 type match: rejected via blood-pressure
        for h in month_year_hits:
            assert "/80" not in h.raw_text  # nothing slipped through

    def test_standalone_yyyy(self):
        hits = detect_dates("Zustand nach OP 2017, seit 2019 stabil")
        years = [h.year for h in hits if h.kind == "standalone_yyyy"]
        assert 2017 in years
        assert 2019 in years

    def test_standalone_yyyy_does_not_double_count_full_date_year(self):
        # The "2023" in "05.08.2023" should NOT also be a standalone hit
        hits = detect_dates("Aufnahme am 05.08.2023.")
        standalone = [h for h in hits if h.kind == "standalone_yyyy"]
        assert standalone == []

    def test_birthdate_marker(self):
        hits = detect_dates("geb. 05.07.1958")
        assert len(hits) == 1
        assert hits[0].is_birthdate is True

    def test_birthdate_asterisk(self):
        hits = detect_dates("Patient, *05.07.1958")
        assert hits[0].is_birthdate is True

    def test_invalid_date_skipped(self):
        # "32.13.2023" is not a valid date — the DD.MM.YYYY pattern matches
        # but the date() constructor rejects month=13/day=32. The trailing
        # "2023" still surfaces as standalone YYYY, which is correct.
        hits = detect_dates("Random 32.13.2023 text")
        # No 'full' hit, just the standalone year
        kinds = [h.kind for h in hits]
        assert "full" not in kinds
        assert "standalone_yyyy" in kinds


# ── find_admission_date ───────────────────────────────────────────────────────


class TestFindAdmissionDate:
    def test_classic_vom_bis_pattern(self):
        text = ("wir berichten Ihnen nachfolgend über o.g. Pat., der sich "
                "vom 05.08 bis zum 21.08.2023 in unserer stationären Behandlung befand.")
        assert find_admission_date(text) == date(2023, 8, 5)

    def test_year_taken_from_end_date(self):
        text = "Aufenthalt vom 05.08 bis 21.08.2023"
        assert find_admission_date(text) == date(2023, 8, 5)

    def test_year_on_both_sides(self):
        text = "vom 05.08.2023 bis 21.08.2023"
        assert find_admission_date(text) == date(2023, 8, 5)

    def test_no_pattern_returns_none(self):
        text = "Aufnahme am 05.08.2023, Entlassung am 21.08.2023"
        # No "vom...bis..." phrasing
        assert find_admission_date(text) is None

    def test_zwischen_und_pattern(self):
        text = "Behandlung zwischen 05.08.2023 und 21.08.2023"
        assert find_admission_date(text) == date(2023, 8, 5)


# ── decide_mode ───────────────────────────────────────────────────────────────


class TestDecideMode:
    def test_no_admission_is_no_stay(self):
        assert decide_mode(None, []) == "no_stay"

    def test_monthend_day_27(self):
        # Tag 27 fällt nach Klärung in den "nicht-shift"-Bereich
        assert decide_mode(date(2023, 5, 27), []) == "monthend"

    def test_monthend_day_31(self):
        assert decide_mode(date(2023, 5, 31), []) == "monthend"

    def test_safe_january(self):
        assert decide_mode(date(2023, 1, 15), []) == "shift_safe"

    def test_safe_august(self):
        assert decide_mode(date(2023, 8, 5), []) == "shift_safe"

    def test_year_leak_september_with_standalone_yyyy(self):
        hits = [DateHit(start=0, end=4, raw_text="2019", kind="standalone_yyyy", year=2019)]
        assert decide_mode(date(2023, 9, 15), hits) == "shift_year_leak"

    def test_safe_september_without_standalone_yyyy(self):
        assert decide_mode(date(2023, 9, 15), []) == "shift_safe"

    def test_year_leak_december(self):
        hits = [DateHit(start=0, end=4, raw_text="2017", kind="standalone_yyyy", year=2017)]
        assert decide_mode(date(2023, 12, 10), hits) == "shift_year_leak"


# ── shift_full_date ───────────────────────────────────────────────────────────


class TestShiftFullDate:
    def test_simple_shift(self):
        assert shift_full_date(date(2023, 1, 1)) == date(2023, 5, 1)

    def test_shift_across_year(self):
        # 15.10.2023 + 120 Tage = 12.02.2024
        assert shift_full_date(date(2023, 10, 15)) == date(2024, 2, 12)

    def test_shift_across_leap_year(self):
        # 01.01.2024 + 120 Tage = 01.05.2024
        assert shift_full_date(date(2024, 1, 1)) == date(2024, 4, 30)


# ── shift_month_year ──────────────────────────────────────────────────────────


class TestShiftMonthYear:
    def test_same_year(self):
        # Mai 2023 + 4 Monate = September 2023
        assert shift_month_year(5, 2023) == (9, 2023)

    def test_august_to_december(self):
        assert shift_month_year(8, 2023) == (12, 2023)

    def test_september_rolls_to_next_year(self):
        # September 2023 + 4 Monate = Januar 2024
        assert shift_month_year(9, 2023) == (1, 2024)

    def test_december_rolls_to_next_year(self):
        # Dezember 2023 + 4 Monate = April 2024
        assert shift_month_year(12, 2023) == (4, 2024)


# ── Formatter ─────────────────────────────────────────────────────────────────


class TestFormatters:
    def test_ddmmyyyy_zero_padded(self):
        # Original was zero-padded → output stays zero-padded
        assert _format_full_date(date(2023, 12, 5), "05.08.2023") == "05.12.2023"

    def test_ddmmyyyy_not_padded(self):
        assert _format_full_date(date(2023, 12, 5), "5.8.2023") == "5.12.2023"

    def test_german_full_month(self):
        out = _format_full_date(date(2024, 3, 5), "5. November 2023")
        assert out == "5. März 2024"

    def test_german_abbr_month_preserves_dot(self):
        out = _format_full_date(date(2024, 3, 5), "5. Nov. 2023")
        assert out == "5. Mär. 2024"

    def test_mm_yyyy_dot(self):
        assert _format_month_year(3, 2024, "MM.YYYY") == "03.2024"

    def test_mm_yyyy_slash(self):
        assert _format_month_year(3, 2024, "MM/YYYY") == "03/2024"

    def test_mm_yy(self):
        assert _format_month_year(3, 2024, "MM/YY") == "03/24"


# ── plan_actions — Integration ────────────────────────────────────────────────


class TestPlanActionsIntegration:
    def test_safe_january_stay(self):
        text = ("Sehr geehrte Kollegin, wir berichten über den Pat., "
                "der sich vom 05.01 bis 21.01.2023 in unserer Behandlung befand.")
        mode, actions = plan_actions(text)
        assert mode == "shift_safe"
        # 21.01.2023 should be shifted
        full_actions = [a for a in actions if a.do_shift]
        assert len(full_actions) >= 1
        # All shift actions are yellow
        assert all(a.color == "yellow" for a in full_actions)

    def test_monthend_stay_no_shift(self):
        text = "vom 27.05.2023 bis 30.05.2023"
        mode, actions = plan_actions(text)
        assert mode == "monthend"
        # Nothing shifted, all red
        for a in actions:
            assert a.do_shift is False
            assert a.color == "red"

    def test_year_leak_marks_standalone_yyyy_red(self):
        text = ("vom 05.10 bis 21.10.2023, Zustand nach OP 2017.")
        mode, actions = plan_actions(text)
        assert mode == "shift_year_leak"
        # Standalone "2017" is red, the date is yellow
        red_actions = [a for a in actions if a.color == "red"]
        yellow_actions = [a for a in actions if a.color == "yellow"]
        assert any("2017" in a.raw_text for a in red_actions)
        assert any("10.2023" in a.raw_text or "21.10.2023" in a.raw_text
                   for a in yellow_actions)

    def test_birthdate_is_always_red(self):
        text = "Pat. geb. 05.07.1958, vom 05.01 bis 21.01.2023 stationär."
        mode, actions = plan_actions(text)
        assert mode == "shift_safe"
        birthdate_action = next(a for a in actions if a.raw_text == "05.07.1958")
        assert birthdate_action.do_shift is False
        assert birthdate_action.color == "red"

    def test_no_stay_marks_everything_red(self):
        text = "Aufnahme 05.08.2023, Entlassung 21.08.2023"  # no "vom...bis..."
        mode, actions = plan_actions(text)
        assert mode == "no_stay"
        assert all(a.do_shift is False and a.color == "red" for a in actions)


# ── decide_document_mode + force_mode ────────────────────────────────────────


class TestDocumentMode:
    """The 'vom…bis…' span often lives only on page 1. We must compute the
    mode over the whole document and force it on every page — otherwise
    pages 2+ fall into 'no_stay' and stay unshifted (the TAVI-Arztbrief bug).
    """

    def test_document_mode_uses_full_text(self):
        full_doc = (
            "Page1: vom 05.08 bis zum 21.08.2023 stationär.\n"
            "Page3: Herzkatheterbefund vom 16.08.2023.\n"
        )
        mode, admission = decide_document_mode(full_doc)
        assert mode == "shift_safe"
        assert admission == date(2023, 8, 5)

    def test_force_mode_overrides_per_page_decision(self):
        # Page 3 in isolation has no vom-bis → would otherwise be 'no_stay'
        page3 = "Herzkatheterbefund vom 16.08.2023:\nEchokardiographie vom 17.08.2023:"
        # Without force: no_stay, red
        mode, actions = plan_actions(page3)
        assert mode == "no_stay"
        assert all(a.color == "red" for a in actions)
        # With force_mode='shift_safe': shifted, yellow
        mode, actions = plan_actions(page3, force_mode="shift_safe")
        assert mode == "shift_safe"
        assert all(a.do_shift is True and a.color == "yellow" for a in actions)
        # And the shifts are exact +120 days
        shifted = {a.raw_text: a.new_text for a in actions}
        assert shifted["16.08.2023"] == "14.12.2023"
        assert shifted["17.08.2023"] == "15.12.2023"

    def test_force_mode_monthend_blocks_shift(self):
        # If document mode says monthend, even a page 1 with a valid date
        # gets red marks (admission was 27.-31. somewhere)
        page1 = "Termin am 12.06.2023"
        mode, actions = plan_actions(page1, force_mode="monthend")
        assert mode == "monthend"
        assert all(a.do_shift is False and a.color == "red" for a in actions)
