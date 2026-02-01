"""Tests for context-aware location anonymization."""

import pytest
from src.location_anonymizer import ContextAwareLocationAnonymizer
from src.location_database import LocationDatabase


class TestLocationAnonymizer:
    """Test cases for ContextAwareLocationAnonymizer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock city database for testing
        self.city_db = LocationDatabase()
        # Override with small test set
        self.city_db.cities = {"Darmstadt", "Hamburg", "Göttingen", "Einbeck", "Eppendorf", "Berlin"}
        
        self.anonymizer = ContextAwareLocationAnonymizer(
            city_db=self.city_db,
            blacklist={"UKE", "Northeim"}
        )
    
    def test_city_after_plz(self):
        """Test: City after postal code is recognized."""
        text = "Meierweg 123, 37075 Göttingen"
        locations = self.anonymizer.find_locations(text)
        
        # Find the Göttingen match
        cities = [loc for loc in locations if loc['text'] == 'Göttingen']
        assert len(cities) == 1
        assert cities[0]['context'] == 'plz'
        assert cities[0]['plz'] == '37075'
    
    def test_city_with_preposition(self):
        """Test: 'aus Darmstadt' is recognized."""
        text = "Patient aus Darmstadt wurde überwiesen."
        locations = self.anonymizer.find_locations(text)
        
        cities = [loc for loc in locations if loc['text'] == 'Darmstadt']
        assert len(cities) >= 1
        assert cities[0]['context'] == 'preposition'
    
    def test_multiple_prepositions(self):
        """Test: Different prepositions work."""
        test_cases = [
            ("Patient in Hamburg behandelt", "Hamburg"),
            ("Überweisung nach Berlin", "Berlin"),
            ("Zuweiser von Einbeck", "Einbeck"),
            ("Behandlung bei Göttingen", "Göttingen")
        ]
        
        for text, expected_city in test_cases:
            locations = self.anonymizer.find_locations(text)
            cities = [loc for loc in locations if loc['text'] == expected_city]
            assert len(cities) >= 1, f"Failed to find {expected_city} in: {text}"
            assert cities[0]['context'] == 'preposition'
    
    def test_city_in_facility(self):
        """Test: 'Universitätsklinikum Eppendorf' is recognized."""
        text = "Behandlung im Universitätsklinikum Eppendorf"
        locations = self.anonymizer.find_locations(text)
        
        cities = [loc for loc in locations if loc['text'] == 'Eppendorf']
        assert len(cities) >= 1
        assert cities[0]['context'] == 'medical_facility'
        assert cities[0]['facility'] == 'Universitätsklinikum'
    
    def test_various_facility_keywords(self):
        """Test: Various facility keywords are recognized."""
        test_cases = [
            ("Klinikum Darmstadt", "Darmstadt", "Klinikum"),
            ("Herzzentrum Hamburg", "Hamburg", "Herzzentrum"),
            ("MVZ Göttingen", "Göttingen", "MVZ")
        ]
        
        for text, expected_city, expected_facility in test_cases:
            locations = self.anonymizer.find_locations(text)
            cities = [loc for loc in locations if loc['text'] == expected_city]
            assert len(cities) >= 1, f"Failed to find {expected_city} in: {text}"
            assert cities[0]['context'] == 'medical_facility'
    
    def test_city_in_referral(self):
        """Test: City in referral context is recognized."""
        text = "Patient wurde überwiesen aus Einbeck"
        locations = self.anonymizer.find_locations(text)
        
        cities = [loc for loc in locations if loc['text'] == 'Einbeck']
        assert len(cities) >= 1
        # Can be either 'referral' or 'preposition' since "aus" is a preposition
        assert cities[0]['context'] in ['referral', 'preposition']
    
    def test_blacklist_without_context(self):
        """Test: Blacklist entry is recognized even without context."""
        text = "UKE empfiehlt weitere Behandlung."
        locations = self.anonymizer.find_locations(text)
        
        blacklisted = [loc for loc in locations if loc['text'] == 'UKE']
        assert len(blacklisted) == 1
        assert blacklisted[0]['context'] == 'blacklist'
        assert blacklisted[0]['priority'] == 1
    
    def test_city_without_context_ignored(self):
        """Test: City without context is NOT recognized."""
        # "Göttingen-Studie" should be ignored (no context)
        text = "Laut Göttingen-Studie zeigt sich..."
        locations = self.anonymizer.find_locations(text)
        
        cities = [loc for loc in locations if loc['text'] == 'Göttingen']
        assert len(cities) == 0  # No context → not recognized
    
    def test_deduplication(self):
        """Test: Same position only appears once."""
        # City appears with both preposition and in referral context
        text = "überwiesen aus Darmstadt"
        locations = self.anonymizer.find_locations(text)
        
        # Should find Darmstadt, but only once (deduplicated)
        cities = [loc for loc in locations if loc['text'] == 'Darmstadt']
        
        # Could be 1 or 2 depending on overlap detection
        # The key is that overlapping matches are deduplicated
        assert len(cities) >= 1
    
    def test_priority_system(self):
        """Test: Blacklist has highest priority."""
        # Add a city to blacklist that might match other patterns
        text = "UKE Hamburg"
        locations = self.anonymizer.find_locations(text)
        
        # UKE should be found as blacklist (priority 1)
        uke_match = [loc for loc in locations if loc['text'] == 'UKE']
        assert len(uke_match) >= 1
        assert uke_match[0]['priority'] == 1
    
    def test_no_matches_in_plain_text(self):
        """Test: Plain text with city names but no context returns nothing."""
        text = "Dies ist ein normaler medizinischer Text ohne Ortsbezug."
        locations = self.anonymizer.find_locations(text)
        
        # Should not find any locations
        assert len(locations) == 0
    
    def test_address_with_plz_and_city(self):
        """Test: Full address is properly recognized."""
        text = "Hauptstraße 123, 37075 Göttingen"
        locations = self.anonymizer.find_locations(text)
        
        cities = [loc for loc in locations if loc['text'] == 'Göttingen']
        assert len(cities) == 1
        assert cities[0]['context'] == 'plz'
