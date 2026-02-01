"""Tests for medical facility anonymization."""

import pytest
from src.facility_anonymizer import MedicalFacilityAnonymizer


class TestMedicalFacilityAnonymizer:
    """Test cases for MedicalFacilityAnonymizer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.anonymizer = MedicalFacilityAnonymizer()
    
    def test_find_abbreviation(self):
        """Test: Known abbreviation is found."""
        text = "Patient wurde im UKE behandelt."
        facilities = self.anonymizer.find_facilities(text)
        
        uke_matches = [f for f in facilities if f['text'] == 'UKE']
        assert len(uke_matches) == 1
        assert uke_matches[0]['type'] == 'MEDICAL_FACILITY'
        assert uke_matches[0]['full_name'] == 'Universitätsklinikum Eppendorf'
    
    def test_find_multiple_abbreviations(self):
        """Test: Multiple abbreviations are found."""
        text = "Überweisung von MHH an UKE"
        facilities = self.anonymizer.find_facilities(text)
        
        # Should find both MHH and UKE
        abbrs = {f['text'] for f in facilities}
        assert 'MHH' in abbrs
        assert 'UKE' in abbrs
    
    def test_find_full_facility_name(self):
        """Test: Full facility name is found."""
        text = "Behandlung in der Charité Berlin"
        facilities = self.anonymizer.find_facilities(text)
        
        # Should find Charité
        charité_matches = [f for f in facilities if 'Charité' in f['text']]
        assert len(charité_matches) >= 1
        assert charité_matches[0]['type'] == 'MEDICAL_FACILITY'
    
    def test_find_facility_alias(self):
        """Test: Facility alias is found."""
        text = "Überweisung an Universitätsklinikum Eppendorf"
        facilities = self.anonymizer.find_facilities(text)
        
        # Should find the full name as an alias
        matches = [f for f in facilities if 'Eppendorf' in f['text']]
        assert len(matches) >= 1
        assert matches[0]['type'] == 'MEDICAL_FACILITY'
    
    def test_case_insensitive_matching(self):
        """Test: Matching is case-insensitive."""
        text = "behandlung im uke"
        facilities = self.anonymizer.find_facilities(text)
        
        # Should still find UKE
        uke_matches = [f for f in facilities if f['text'].upper() == 'UKE']
        assert len(uke_matches) == 1
    
    def test_no_false_positives(self):
        """Test: Random text doesn't match facilities."""
        text = "Dies ist ein normaler medizinischer Text ohne Klinik-Namen."
        facilities = self.anonymizer.find_facilities(text)
        
        # Should not find any facilities
        assert len(facilities) == 0
    
    def test_facility_with_city_info(self):
        """Test: Facility match includes city information."""
        text = "Überweisung an Universitätsmedizin Göttingen"
        facilities = self.anonymizer.find_facilities(text)
        
        matches = [f for f in facilities if 'Göttingen' in f['text']]
        if len(matches) > 0:
            # If found, should have city info
            assert 'city' in matches[0]
            assert matches[0]['city'] == 'Göttingen'
