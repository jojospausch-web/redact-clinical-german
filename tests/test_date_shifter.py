"""Tests for date shifting functionality."""

import pytest
from datetime import datetime, timedelta
from src.date_shifter import DateShifter


class TestDateShifter:
    """Test cases for DateShifter class."""
    
    def test_shift_with_fixed_offset(self):
        """Test date shifting with a fixed offset."""
        shifter = DateShifter(shift_days=10)
        
        # Test standard date format
        result = shifter.shift_date("01.12.2023")
        expected = datetime.strptime("01.12.2023", "%d.%m.%Y") + timedelta(days=10)
        assert result == expected.strftime("%d.%m.%Y")
    
    def test_shift_consistency(self):
        """Test that the same date always shifts to the same result."""
        shifter = DateShifter(shift_days=15)
        
        date_str = "15.03.2023"
        result1 = shifter.shift_date(date_str)
        result2 = shifter.shift_date(date_str)
        
        assert result1 == result2
    
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
    
    def test_negative_shift(self):
        """Test shifting dates backwards."""
        shifter = DateShifter(shift_days=-20)
        
        result = shifter.shift_date("01.02.2023")
        expected = datetime.strptime("01.02.2023", "%d.%m.%Y") + timedelta(days=-20)
        assert result == expected.strftime("%d.%m.%Y")
    
    def test_random_shift_within_range(self):
        """Test that random shift is within the specified range."""
        shift_range = (-30, 30)
        shifter = DateShifter(shift_range=shift_range)
        
        offset = shifter.get_shift_days()
        assert shift_range[0] <= offset <= shift_range[1]
    
    def test_invalid_date_returns_original(self):
        """Test that invalid dates are returned unchanged."""
        shifter = DateShifter(shift_days=10)
        
        invalid_date = "invalid_date"
        result = shifter.shift_date(invalid_date)
        assert result == invalid_date
    
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
