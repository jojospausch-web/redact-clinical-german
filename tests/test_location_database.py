"""Tests for location database functionality."""

import pytest
from src.location_database import LocationDatabase


class TestLocationDatabase:
    """Test cases for LocationDatabase class."""
    
    def test_load_cities(self):
        """Test that cities are loaded from the database file."""
        db = LocationDatabase()
        
        # Check that some major cities are in the database
        assert db.is_city("Berlin")
        assert db.is_city("Hamburg")
        assert db.is_city("München")
        assert db.is_city("Göttingen")
        assert db.is_city("Darmstadt")
    
    def test_city_not_in_database(self):
        """Test that random strings are not recognized as cities."""
        db = LocationDatabase()
        
        assert not db.is_city("NotACity")
        assert not db.is_city("RandomString123")
    
    def test_case_sensitive(self):
        """Test that city matching is case-sensitive."""
        db = LocationDatabase()
        
        # These should match exactly as stored
        assert db.is_city("Berlin")
        
        # Lowercase versions should not match
        assert not db.is_city("berlin")
        assert not db.is_city("BERLIN")
    
    def test_cities_with_spaces(self):
        """Test that cities with spaces in names are handled correctly."""
        db = LocationDatabase()
        
        assert db.is_city("Frankfurt am Main")
        assert db.is_city("Bad Homburg")
    
    def test_special_characters(self):
        """Test cities with German special characters."""
        db = LocationDatabase()
        
        # Cities with umlauts should be in database
        assert db.is_city("München")
        assert db.is_city("Düsseldorf")
        assert db.is_city("Köln")
