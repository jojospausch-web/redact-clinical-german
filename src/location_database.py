"""Location database for German cities."""

import os
from typing import Set
from pathlib import Path


class LocationDatabase:
    """Database of German cities for location recognition."""
    
    def __init__(self, db_path: str = None):
        """Initialize location database.
        
        Args:
            db_path: Path to cities database file. If None, uses default location.
        """
        if db_path is None:
            # Default to data/cities_de.txt relative to project root
            module_dir = Path(__file__).parent.parent
            db_path = module_dir / "data" / "cities_de.txt"
        
        self.cities = self._load_cities(db_path)
    
    def _load_cities(self, path: str) -> Set[str]:
        """Load German cities from database file.
        
        Args:
            path: Path to the cities database file
            
        Returns:
            Set of city names
        """
        cities = set()
        
        if not os.path.exists(path):
            # Return empty set if file doesn't exist (for testing)
            return cities
        
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                city = line.strip()
                if city:
                    cities.add(city)
        
        return cities
    
    def is_city(self, name: str) -> bool:
        """Check if name is a known German city.
        
        Args:
            name: City name to check
            
        Returns:
            True if the name is in the database
        """
        return name in self.cities
