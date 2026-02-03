"""Date shifting module for consistent date anonymization."""

import re
import random
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dateutil import parser


class DateShifter:
    """Handles consistent date shifting for anonymization.
    
    All dates in a document are shifted by the same offset to maintain
    temporal relationships and time intervals.
    
    Supports German month names:
    - "5. November 2023"
    - "5. Nov. 2023"
    - "05.11.2023"
    - "November 2023" (without day)
    """
    
    # German month name mappings
    MONTHS = {
        'januar': 1, 'jan': 1, 'jan.': 1,
        'februar': 2, 'feb': 2, 'feb.': 2,
        'märz': 3, 'mär': 3, 'mär.': 3,
        'april': 4, 'apr': 4, 'apr.': 4,
        'mai': 5,
        'juni': 6, 'jun': 6, 'jun.': 6,
        'juli': 7, 'jul': 7, 'jul.': 7,
        'august': 8, 'aug': 8, 'aug.': 8,
        'september': 9, 'sep': 9, 'sept': 9, 'sept.': 9,
        'oktober': 10, 'okt': 10, 'okt.': 10,
        'november': 11, 'nov': 11, 'nov.': 11,
        'dezember': 12, 'dez': 12, 'dez.': 12
    }
    
    MONTH_NAMES = {
        1: 'Januar', 2: 'Februar', 3: 'März', 4: 'April',
        5: 'Mai', 6: 'Juni', 7: 'Juli', 8: 'August',
        9: 'September', 10: 'Oktober', 11: 'November', 12: 'Dezember'
    }
    
    MONTH_ABBR = {
        1: 'Jan', 2: 'Feb', 3: 'Mär', 4: 'Apr',
        5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Aug',
        9: 'Sep', 10: 'Okt', 11: 'Nov', 12: 'Dez'
    }
    
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
    
    def parse_german_date(self, date_str: str, context_year: Optional[int] = None) -> Optional[datetime]:
        """Parse various German date formats.
        
        Args:
            date_str: Date string to parse
            context_year: Year to use for short dates (DD.MM) if not provided, uses current year
        
        Returns:
            datetime object or None if parsing fails
        """
        # Format 1: "5. November 2023" or "5. Nov. 2023" (with or without period)
        pattern1 = r'(\d{1,2})\.\s+([A-Za-zä]+\.?)\s+(\d{4})'
        match = re.search(pattern1, date_str, re.IGNORECASE)
        if match:
            day = int(match.group(1))
            month_name = match.group(2).lower().rstrip('.')
            year = int(match.group(3))
            
            month = self.MONTHS.get(month_name)
            if month:
                try:
                    return datetime(year, month, day)
                except ValueError:
                    return None
        
        # Format 2: "05.11.2023"
        pattern2 = r'^(\d{2})\.(\d{2})\.(\d{4})$'
        match = re.search(pattern2, date_str)
        if match:
            try:
                day = int(match.group(1))
                month = int(match.group(2))
                year = int(match.group(3))
                return datetime(year, month, day)
            except ValueError:
                return None
        
        # Format 3: "05.11" (short date without year)
        pattern3 = r'^(\d{1,2})\.(\d{1,2})$'
        match = re.search(pattern3, date_str)
        if match:
            try:
                day = int(match.group(1))
                month = int(match.group(2))
                # Use context year or current year
                year = context_year if context_year else datetime.now().year
                return datetime(year, month, day)
            except ValueError:
                return None
        
        # Format 4: "November 2023" (without day, use day 1)
        pattern4 = r'\b([A-Za-zä]+\.?)\s+(\d{4})\b'
        match = re.search(pattern4, date_str, re.IGNORECASE)
        if match:
            month_name = match.group(1).lower().rstrip('.')
            year = int(match.group(2))
            
            month = self.MONTHS.get(month_name)
            if month:
                return datetime(year, month, 1)
        
        return None
    
    def shift_date(self, date_str: str, date_format: str = "%d.%m.%Y", context_year: Optional[int] = None) -> str:
        """Shift a date string by the configured offset.
        
        Supports multiple formats:
        - "5. November 2023" → "30. November 2023"
        - "5. Nov. 2023" → "30. Nov. 2023"
        - "05.11.2023" → "30.11.2023"
        - "05.08" → "15.08" (short date without year)
        
        Args:
            date_str: Date string to shift (e.g., "01.12.2023")
            date_format: Expected date format (default: DD.MM.YYYY)
            context_year: Year to use for short dates (DD.MM) if not in date_str
        
        Returns:
            Shifted date string in the same format
        """
        # Check if we've already shifted this exact date
        if date_str in self._shifted_dates:
            return self._shifted_dates[date_str]
        
        # Try parsing as German date first
        date_obj = self.parse_german_date(date_str, context_year)
        
        if date_obj:
            # Shift the date
            shifted = date_obj + timedelta(days=self.shift_days)
            
            # Detect original format and format accordingly
            # Format 1: "05.08" (short date without year)
            if re.search(r'^\d{1,2}\.\d{1,2}$', date_str):
                result = f"{shifted.day:02d}.{shifted.month:02d}"
            
            # Format 2: "5. Nov. 2023" (abbreviated month) - check this first
            elif re.search(r'\d{1,2}\.\s+[A-Za-zä]{3}\.?\s+\d{4}', date_str):
                result = f"{shifted.day}. {self.MONTH_ABBR[shifted.month]}. {shifted.year}"
            
            # Format 3: "5. November 2023" (full month name)
            elif re.search(r'\d{1,2}\.\s+[A-Za-zä]{4,}\s+\d{4}', date_str):
                result = f"{shifted.day}. {self.MONTH_NAMES[shifted.month]} {shifted.year}"
            
            # Format 4: "05.11.2023" (numeric)
            elif re.search(r'^\d{2}\.\d{2}\.\d{4}$', date_str):
                result = shifted.strftime("%d.%m.%Y")
            
            # Format 5: "November 2023" (month only)
            elif re.search(r'[A-Za-zä]+\.?\s+\d{4}', date_str):
                result = f"{self.MONTH_NAMES[shifted.month]} {shifted.year}"
            
            else:
                result = shifted.strftime("%d.%m.%Y")  # Fallback
            
            # Cache the result
            self._shifted_dates[date_str] = result
            return result
        
        # Fall back to standard parsing
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
    
    def find_all_dates(self, text: str) -> List[Dict]:
        """Find all dates in text (for anonymization).
        
        Args:
            text: Text to search
            
        Returns:
            List of date matches with position info
        """
        found = []
        
        # Pattern 1: "5. November 2023"
        pattern1 = r'\b(\d{1,2}\.\s+[A-Za-zä]+\s+\d{4})\b'
        for match in re.finditer(pattern1, text):
            found.append({
                'text': match.group(1),
                'start': match.start(),
                'end': match.end(),
                'type': 'DATE_GERMAN_FULL'
            })
        
        # Pattern 2: "05.11.2023"
        pattern2 = r'\b(\d{2}\.\d{2}\.\d{4})\b'
        for match in re.finditer(pattern2, text):
            # Check if not already found as Pattern 1
            overlaps = any(
                match.start() >= f['start'] and match.end() <= f['end']
                for f in found
            )
            if not overlaps:
                found.append({
                    'text': match.group(1),
                    'start': match.start(),
                    'end': match.end(),
                    'type': 'DATE_NUMERIC'
                })
        
        # Pattern 3: "*05.11.2023" (birthdate with asterisk)
        pattern3 = r'\*(\d{2}\.\d{2}\.\d{4})'
        for match in re.finditer(pattern3, text):
            found.append({
                'text': match.group(1),
                'start': match.start(1),
                'end': match.end(1),
                'type': 'BIRTHDATE'
            })
        
        return found
    
    def get_shift_days(self) -> int:
        """Get the current shift offset in days."""
        return self.shift_days
    
    def reset_cache(self):
        """Clear the cache of shifted dates."""
        self._shifted_dates.clear()
