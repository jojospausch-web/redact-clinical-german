"""Medical facility anonymization for known German hospitals and clinics."""

import re
import json
import os
from typing import List, Dict
from pathlib import Path


class MedicalFacilityAnonymizer:
    """Anonymizer for known medical facilities and their abbreviations."""
    
    def __init__(self, facilities_db_path: str = None):
        """Initialize medical facility anonymizer.
        
        Args:
            facilities_db_path: Path to facilities JSON file. If None, uses default.
        """
        if facilities_db_path is None:
            # Default to data/medical_facilities_de.json relative to project root
            module_dir = Path(__file__).parent.parent
            facilities_db_path = module_dir / "data" / "medical_facilities_de.json"
        
        self.facilities = self._load_facilities(facilities_db_path)
    
    def _load_facilities(self, path: str) -> Dict:
        """Load medical facilities from JSON database.
        
        Args:
            path: Path to facilities JSON file
            
        Returns:
            Dictionary of facilities data
        """
        if not os.path.exists(path):
            # Return empty dict if file doesn't exist (for testing)
            return {"universities": {}, "abbreviations": {}}
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def find_facilities(self, text: str) -> List[Dict]:
        """Find known medical facilities and abbreviations.
        
        Args:
            text: Text to search
            
        Returns:
            List of facility matches with position info
        """
        found = []
        seen_positions = set()  # Track (start, end) to avoid duplicates
        
        # 1. Known abbreviations (e.g., "UKE", "MHH")
        for abbr, full_name in self.facilities.get('abbreviations', {}).items():
            pattern = rf'\b{re.escape(abbr)}\b'
            for match in re.finditer(pattern, text):
                pos = (match.start(), match.end())
                if pos not in seen_positions:
                    seen_positions.add(pos)
                    found.append({
                        'text': match.group(0),
                        'start': match.start(),
                        'end': match.end(),
                        'type': 'MEDICAL_FACILITY',
                        'full_name': full_name
                    })
        
        # 2. Full names + aliases
        for facility_name, facility_data in self.facilities.get('universities', {}).items():
            # Collect all names for this facility
            all_names = [facility_name] + facility_data.get('aliases', [])
            
            for name in all_names:
                if not name:  # Skip empty strings
                    continue
                    
                pattern = rf'\b{re.escape(name)}\b'
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    pos = (match.start(), match.end())
                    if pos not in seen_positions:
                        seen_positions.add(pos)
                        found.append({
                            'text': match.group(0),
                            'start': match.start(),
                            'end': match.end(),
                            'type': 'MEDICAL_FACILITY',
                            'city': facility_data.get('city', '')
                        })
        
        return found
