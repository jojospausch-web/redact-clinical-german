"""Date shifting module for consistent date anonymization."""

import random
from datetime import datetime, timedelta
from typing import Dict, Optional
from dateutil import parser


class DateShifter:
    """Handles consistent date shifting for anonymization.
    
    All dates in a document are shifted by the same offset to maintain
    temporal relationships and time intervals.
    """
    
    def __init__(self, shift_days: Optional[int] = None, shift_range: tuple = (-30, 30)):
        """Initialize the date shifter.
        
        Args:
            shift_days: Specific number of days to shift. If None, random within shift_range.
            shift_range: Tuple of (min_days, max_days) for random shift.
        """
        if shift_days is not None:
            self.shift_days = shift_days
        else:
            # Generate a consistent random shift within the range
            self.shift_days = random.randint(shift_range[0], shift_range[1])
        
        self._shifted_dates: Dict[str, str] = {}
    
    def shift_date(self, date_str: str, date_format: str = "%d.%m.%Y") -> str:
        """Shift a date string by the configured offset.
        
        Args:
            date_str: Date string to shift (e.g., "01.12.2023")
            date_format: Expected date format (default: DD.MM.YYYY)
        
        Returns:
            Shifted date string in the same format
        """
        # Check if we've already shifted this exact date
        if date_str in self._shifted_dates:
            return self._shifted_dates[date_str]
        
        try:
            # Parse the date
            date_obj = datetime.strptime(date_str, date_format)
            
            # Apply shift
            shifted_date = date_obj + timedelta(days=self.shift_days)
            
            # Format back to string
            shifted_str = shifted_date.strftime(date_format)
            
            # Cache the result
            self._shifted_dates[date_str] = shifted_str
            
            return shifted_str
        except ValueError:
            # If parsing fails, try with dateutil parser
            try:
                date_obj = parser.parse(date_str, dayfirst=True)
                shifted_date = date_obj + timedelta(days=self.shift_days)
                shifted_str = shifted_date.strftime(date_format)
                self._shifted_dates[date_str] = shifted_str
                return shifted_str
            except Exception:
                # If all parsing fails, return original
                return date_str
    
    def get_shift_days(self) -> int:
        """Get the current shift offset in days."""
        return self.shift_days
    
    def reset_cache(self):
        """Clear the cache of shifted dates."""
        self._shifted_dates.clear()
