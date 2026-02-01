"""Context-aware location anonymization for German cities."""

import re
from typing import List, Dict, Set
from src.location_database import LocationDatabase


class ContextAwareLocationAnonymizer:
    """
    Recognizes cities ONLY in specific contexts:
    1. After postal code: "37075 Göttingen"
    2. With prepositions: "aus Darmstadt", "in Hamburg"
    3. At medical facilities: "Universitätsklinikum Eppendorf"
    4. In addresses: "Meierweg 123, 37075 Göttingen"
    5. In referrals: "überwiesen aus Einbeck"
    """
    
    def __init__(self, city_db: LocationDatabase, blacklist: Set[str] = None):
        """Initialize the location anonymizer.
        
        Args:
            city_db: Database of German cities
            blacklist: Set of terms that should always be redacted (even without context)
        """
        self.city_db = city_db
        self.blacklist = blacklist or set()
    
    def find_locations(self, text: str) -> List[Dict]:
        """Find all cities and medical facilities in context.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of location dictionaries with position and context info
        """
        locations = []
        
        # PRIORITY 1: BLACKLIST (highest priority)
        locations.extend(self._find_blacklisted(text))
        
        # PRIORITY 2: Cities after postal code
        locations.extend(self._find_cities_after_plz(text))
        
        # PRIORITY 3: Cities with prepositions
        locations.extend(self._find_cities_with_prepositions(text))
        
        # PRIORITY 4: Cities at medical facilities
        locations.extend(self._find_cities_in_facilities(text))
        
        # PRIORITY 5: Cities in referral context
        locations.extend(self._find_cities_in_referrals(text))
        
        # Deduplication (same position only once)
        return self._deduplicate(locations)
    
    def _find_blacklisted(self, text: str) -> List[Dict]:
        """Blacklist entries are ALWAYS recognized (even without context).
        
        Args:
            text: Text to search
            
        Returns:
            List of blacklisted location matches
        """
        found = []
        for term in self.blacklist:
            pattern = rf'\b{re.escape(term)}\b'
            for match in re.finditer(pattern, text, re.IGNORECASE):
                found.append({
                    'text': match.group(0),
                    'start': match.start(),
                    'end': match.end(),
                    'type': 'LOCATION_BLACKLIST',
                    'context': 'blacklist',
                    'priority': 1
                })
        return found
    
    def _find_cities_after_plz(self, text: str) -> List[Dict]:
        """
        CONTEXT 1: City after postal code.
        "37075 Göttingen", "20246 Hamburg"
        
        Args:
            text: Text to search
            
        Returns:
            List of city matches after postal codes
        """
        found = []
        pattern = r'\b(\d{5})\s+([A-ZÄÖÜ][a-zäöüß\s-]+?)(?=[,.\n]|$)'
        
        for match in re.finditer(pattern, text):
            plz = match.group(1)
            city_candidate = match.group(2).strip()
            
            # Check if city is in database
            if self.city_db.is_city(city_candidate):
                found.append({
                    'text': city_candidate,
                    'start': match.start(2),
                    'end': match.end(2),
                    'type': 'CITY',
                    'context': 'plz',
                    'plz': plz,
                    'priority': 2
                })
        return found
    
    def _find_cities_with_prepositions(self, text: str) -> List[Dict]:
        """
        CONTEXT 2: City with preposition.
        "aus Darmstadt", "in Hamburg", "nach Berlin", "von Einbeck"
        
        Args:
            text: Text to search
            
        Returns:
            List of city matches with prepositions
        """
        found = []
        prepositions = ['aus', 'in', 'nach', 'von', 'bei']
        
        for city in self.city_db.cities:
            # Escape special characters in city name
            city_escaped = re.escape(city)
            pattern = rf'\b({"|".join(prepositions)})\s+{city_escaped}\b'
            
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Calculate the start position of the city (after preposition and space)
                city_start = match.start() + len(match.group(1)) + 1
                found.append({
                    'text': city,
                    'start': city_start,
                    'end': match.end(),
                    'type': 'CITY',
                    'context': 'preposition',
                    'preposition': match.group(1),
                    'priority': 3
                })
        return found
    
    def _find_cities_in_facilities(self, text: str) -> List[Dict]:
        """
        CONTEXT 3: City at medical facility.
        "Universitätsklinikum Eppendorf", "Klinikum Darmstadt", "Herzzentrum Hamburg"
        
        Args:
            text: Text to search
            
        Returns:
            List of city matches in facility names
        """
        found = []
        facility_keywords = [
            'Universitätsklinikum', 'Uniklinik', 'Klinikum', 'Krankenhaus',
            'Herzzentrum', 'Tumorzentrum', 'Lungenzentrum', 'MVZ',
            'Medizinisches Versorgungszentrum', 'Charité'
        ]
        
        for city in self.city_db.cities:
            city_escaped = re.escape(city)
            
            for keyword in facility_keywords:
                # Pattern: "Keyword City" or "Keyword City-Suffix"
                pattern = rf'\b{keyword}\s+{city_escaped}(?:-\w+)?\b'
                
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    # Find position of the city name within the match
                    full_text = match.group(0)
                    city_start_in_match = full_text.find(city)
                    
                    found.append({
                        'text': city,
                        'start': match.start() + city_start_in_match,
                        'end': match.start() + city_start_in_match + len(city),
                        'type': 'CITY',
                        'context': 'medical_facility',
                        'facility': keyword,
                        'priority': 4
                    })
        
        return found
    
    def _find_cities_in_referrals(self, text: str) -> List[Dict]:
        """
        CONTEXT 4: City in referral context.
        "überwiesen aus Einbeck", "Zuweiser Dr. Schmidt, Hamburg"
        
        Args:
            text: Text to search
            
        Returns:
            List of city matches in referral contexts
        """
        found = []
        referral_keywords = ['überwiesen', 'Zuweiser', 'eingewiesen', 'verlegt']
        
        for city in self.city_db.cities:
            city_escaped = re.escape(city)
            
            for keyword in referral_keywords:
                # Pattern: Keyword ... City (within 50 characters)
                pattern = rf'\b{keyword}\b.{{0,50}}\b{city_escaped}\b'
                
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    # Find exact position of the city name
                    city_match = re.search(rf'\b{city_escaped}\b', match.group(0))
                    if city_match:
                        found.append({
                            'text': city,
                            'start': match.start() + city_match.start(),
                            'end': match.start() + city_match.end(),
                            'type': 'CITY',
                            'context': 'referral',
                            'priority': 5
                        })
        
        return found
    
    def _deduplicate(self, locations: List[Dict]) -> List[Dict]:
        """
        Remove duplicates (same position).
        For overlaps: Higher priority wins.
        
        Args:
            locations: List of location matches
            
        Returns:
            Deduplicated list of locations
        """
        # Sort by start position and priority
        sorted_locs = sorted(locations, key=lambda x: (x['start'], x['priority']))
        
        unique = []
        for loc in sorted_locs:
            # Check if overlapping with already added locations
            overlapping = False
            for existing in unique:
                if (loc['start'] >= existing['start'] and loc['start'] < existing['end']) or \
                   (loc['end'] > existing['start'] and loc['end'] <= existing['end']):
                    overlapping = True
                    break
            
            if not overlapping:
                unique.append(loc)
        
        return unique
