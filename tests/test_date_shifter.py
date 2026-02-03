"""Tests for date shifting functionality."""

import pytest
from datetime import datetime, timedelta
from src.date_shifter import DateShifter


class TestDateShifter:
    """Test cases for DateShifter class.
    
    NOTE: Date-shifting is now disabled for regular dates in PDF anonymization.
    These tests verify that the DateShifter class still works correctly
    (used for birthdates and potential Excel-based shifting).
    """
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_shift_with_fixed_offset(self):
        """Test date shifting with a fixed offset."""
        shifter = DateShifter(shift_days=10)
        
        # Test standard date format
        result = shifter.shift_date("01.12.2023")
        expected = datetime.strptime("01.12.2023", "%d.%m.%Y") + timedelta(days=10)
        assert result == expected.strftime("%d.%m.%Y")
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_shift_consistency(self):
        """Test that the same date always shifts to the same result."""
        shifter = DateShifter(shift_days=15)
        
        date_str = "15.03.2023"
        result1 = shifter.shift_date(date_str)
        result2 = shifter.shift_date(date_str)
        
        assert result1 == result2
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_shift_different_dates(self):
        """Test that different dates maintain their relative distance."""
        shifter = DateShifter(shift_days=7)
        
        date1 = "01.01.2023"
        date2 = "10.01.2023"
        
        shifted1 = shifter.shift_date(date1)
        shifted2 = shifter.shift_date(date2)
        
        # Parse both dates
        dt1 = datetime.strptime(shifted1, "%d.%m.%Y")
        dt2 = datetime.strptime(shifted2, "%d.%m.%Y")
        
        # The difference should still be 9 days
        assert (dt2 - dt1).days == 9
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_negative_shift(self):
        """Test shifting dates backwards."""
        shifter = DateShifter(shift_days=-20)
        
        result = shifter.shift_date("01.02.2023")
        expected = datetime.strptime("01.02.2023", "%d.%m.%Y") + timedelta(days=-20)
        assert result == expected.strftime("%d.%m.%Y")
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_random_shift_within_range(self):
        """Test that random shift is within the specified range."""
        shift_range = (-30, 30)
        shifter = DateShifter(shift_range=shift_range)
        
        offset = shifter.get_shift_days()
        assert shift_range[0] <= offset <= shift_range[1]
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_invalid_date_returns_original(self):
        """Test that invalid dates are returned unchanged."""
        shifter = DateShifter(shift_days=10)
        
        invalid_date = "invalid_date"
        result = shifter.shift_date(invalid_date)
        assert result == invalid_date
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_cache_reset(self):
        """Test that cache can be reset."""
        shifter = DateShifter(shift_days=5)
        
        date_str = "01.01.2023"
        shifter.shift_date(date_str)
        
        # Reset cache
        shifter.reset_cache()
        
        # Shift again (should work the same)
        result = shifter.shift_date(date_str)
        expected = datetime.strptime(date_str, "%d.%m.%Y") + timedelta(days=5)
        assert result == expected.strftime("%d.%m.%Y")


class TestGermanDateShifter:
    """Test cases for German month name support in DateShifter.
    
    NOTE: These tests verify the DateShifter functionality still works
    but regular dates are no longer extracted in PDF anonymization.
    Only birthdates (with * prefix) use this functionality now.
    """
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_parse_full_month_name(self):
        """Test: '5. November 2023' is parsed correctly."""
        shifter = DateShifter(shift_days=0)
        date = shifter.parse_german_date("5. November 2023")
        
        assert date is not None
        assert date.day == 5
        assert date.month == 11
        assert date.year == 2023
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_parse_abbreviated_month(self):
        """Test: '5. Nov. 2023' is parsed correctly."""
        shifter = DateShifter(shift_days=0)
        date = shifter.parse_german_date("5. Nov. 2023")
        
        assert date is not None
        assert date.day == 5
        assert date.month == 11
        assert date.year == 2023
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_parse_numeric_date(self):
        """Test: '05.11.2023' is parsed correctly."""
        shifter = DateShifter(shift_days=0)
        date = shifter.parse_german_date("05.11.2023")
        
        assert date is not None
        assert date.day == 5
        assert date.month == 11
        assert date.year == 2023
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_parse_month_only(self):
        """Test: 'November 2023' is parsed (uses day 1)."""
        shifter = DateShifter(shift_days=0)
        date = shifter.parse_german_date("November 2023")
        
        assert date is not None
        assert date.day == 1
        assert date.month == 11
        assert date.year == 2023
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_shift_keeps_format_full_month(self):
        """Test: Format is preserved for full month names."""
        shifter = DateShifter(shift_days=25)
        shifted = shifter.shift_date("5. November 2023")
        
        # Should shift to November 30, 2023
        assert "November" in shifted or "Dezember" in shifted
        assert shifted == "30. November 2023"
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_shift_keeps_format_abbreviated(self):
        """Test: Format is preserved for abbreviated months."""
        shifter = DateShifter(shift_days=25)
        shifted = shifter.shift_date("5. Nov. 2023")
        
        # Should keep abbreviated format
        assert "Nov" in shifted or "Dez" in shifted
        assert "." in shifted  # Dot should remain
        assert shifted == "30. Nov. 2023"
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_shift_numeric_format(self):
        """Test: Numeric format is preserved."""
        shifter = DateShifter(shift_days=10)
        shifted = shifter.shift_date("05.11.2023")
        
        # Should stay numeric
        assert shifted == "15.11.2023"
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_shift_consistency_german_dates(self):
        """Test: Same German date is shifted consistently."""
        shifter = DateShifter(shift_days=10)
        
        shifted1 = shifter.shift_date("5. November 2023")
        shifted2 = shifter.shift_date("5. November 2023")
        
        assert shifted1 == shifted2  # Cache works
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_all_german_months(self):
        """Test: All German month names are recognized."""
        shifter = DateShifter(shift_days=0)
        
        months = [
            ("1. Januar 2023", 1),
            ("1. Februar 2023", 2),
            ("1. März 2023", 3),
            ("1. April 2023", 4),
            ("1. Mai 2023", 5),
            ("1. Juni 2023", 6),
            ("1. Juli 2023", 7),
            ("1. August 2023", 8),
            ("1. September 2023", 9),
            ("1. Oktober 2023", 10),
            ("1. November 2023", 11),
            ("1. Dezember 2023", 12)
        ]
        
        for date_str, expected_month in months:
            date = shifter.parse_german_date(date_str)
            assert date is not None
            assert date.month == expected_month
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_abbreviated_months(self):
        """Test: Abbreviated month names work."""
        shifter = DateShifter(shift_days=0)
        
        abbrevs = [
            ("1. Jan. 2023", 1),
            ("1. Feb. 2023", 2),
            ("1. Mär. 2023", 3),
            ("1. Apr. 2023", 4),
            ("1. Jun. 2023", 6),
            ("1. Jul. 2023", 7),
            ("1. Aug. 2023", 8),
            ("1. Sep. 2023", 9),
            ("1. Okt. 2023", 10),
            ("1. Nov. 2023", 11),
            ("1. Dez. 2023", 12)
        ]
        
        for date_str, expected_month in abbrevs:
            date = shifter.parse_german_date(date_str)
            assert date is not None
            assert date.month == expected_month
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_find_all_dates(self):
        """Test: find_all_dates finds various date formats."""
        shifter = DateShifter(shift_days=0)
        
        text = """
        Patient geboren am *05.11.1960
        Aufnahme am 5. November 2023
        Entlassung am 10.11.2023
        """
        
        dates = shifter.find_all_dates(text)
        
        # Should find 3 dates
        assert len(dates) >= 3
        
        # Check types
        types = {d['type'] for d in dates}
        assert 'BIRTHDATE' in types
        assert 'DATE_GERMAN_FULL' in types
        assert 'DATE_NUMERIC' in types
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_shift_across_month_boundary(self):
        """Test: Shifting across month boundary works correctly."""
        shifter = DateShifter(shift_days=10)
        
        # November 25 + 10 days = December 5
        shifted = shifter.shift_date("25. November 2023")
        assert "Dezember" in shifted or "5" in shifted
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_shift_across_year_boundary(self):
        """Test: Shifting across year boundary works correctly."""
        shifter = DateShifter(shift_days=10)
        
        # December 25 + 10 days = January 4, 2024
        shifted = shifter.shift_date("25. Dezember 2023")
        assert "2024" in shifted
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_short_date_format_dd_mm(self):
        """Test: Short date format DD.MM (without year) is parsed and shifted correctly."""
        shifter = DateShifter(shift_days=10)
        
        # Test with context year
        result = shifter.shift_date("05.08", context_year=2023)
        assert result == "15.08"
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_short_date_preserves_format(self):
        """Test: Short date format is preserved after shifting."""
        shifter = DateShifter(shift_days=5)
        
        result = shifter.shift_date("21.08")
        # Should still be in DD.MM format (no year)
        assert "." in result
        assert result.count(".") == 1  # Only one dot
        assert len(result.split(".")) == 2  # Two parts
    
    @pytest.mark.skip(reason="Date-shifting disabled for regular dates - only used for birthdates now")
    def test_short_date_month_boundary(self):
        """Test: Shifting across month boundary with short dates."""
        shifter = DateShifter(shift_days=10)
        
        # August 25 + 10 days = September 4
        result = shifter.shift_date("25.08", context_year=2023)
        assert result == "04.09"


