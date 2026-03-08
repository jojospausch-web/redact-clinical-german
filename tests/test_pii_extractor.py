"""Tests for structured PII extraction."""

import pytest
from src.pii_extractor import StructuredPIIExtractor
from src.config import PatternGroup


class TestStructuredPIIExtractor:
    """Test cases for StructuredPIIExtractor class."""
    
    def test_extract_case_id(self):
        """Test extraction of case/patient ID."""
        patterns = {
            "case_id": PatternGroup(
                pattern=r"Pat\.?-?Nr\.?:?\s*([0-9]{6,10})",
                type="CASE_ID"
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = "Patient information: Pat.-Nr. 123456789"
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 1
        assert entities[0].entity_type == "CASE_ID"
        assert entities[0].text == "123456789"
    
    def test_extract_patient_block_with_groups(self):
        """Test extraction of patient block with multiple groups."""
        patterns = {
            "patient_block": PatternGroup(
                pattern=r"(Herr|Frau)\s+([A-ZÄÖÜ][a-zäöüß-]+),\s+([A-ZÄÖÜ][a-zäöüß-]+),\s+\*(\d{2}\.\d{2}\.\d{4})",
                groups={
                    "1": "SALUTATION",
                    "2": "LASTNAME",
                    "3": "FIRSTNAME",
                    "4": "BIRTHDATE"
                }
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = "Herr Müller, Max, *01.01.1960"
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 4
        
        # Check each entity type
        types = {e.entity_type for e in entities}
        assert types == {"SALUTATION", "LASTNAME", "FIRSTNAME", "BIRTHDATE"}
        
        # Check specific values
        lastname = next(e for e in entities if e.entity_type == "LASTNAME")
        assert lastname.text == "Müller"
        
        firstname = next(e for e in entities if e.entity_type == "FIRSTNAME")
        assert firstname.text == "Max"
        
        birthdate = next(e for e in entities if e.entity_type == "BIRTHDATE")
        assert birthdate.text == "01.01.1960"
    
    def test_extract_address(self):
        """Test extraction of address."""
        patterns = {
            "address": PatternGroup(
                pattern=r"([A-ZÄÖÜ][a-zäöüß]+(?:straße|str\.|weg|platz|allee))\s+(\d+[a-z]?),?\s+(\d{5})\s+([A-ZÄÖÜ][a-zäöüß]+)",
                type="ADDRESS"
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = "Wohnhaft in Hauptstraße 123, 37075 Göttingen"
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 1
        assert entities[0].entity_type == "ADDRESS"
        assert "Hauptstraße" in entities[0].text
    
    def test_extract_doctor_signature_with_context(self):
        """Test extraction of doctor name with context trigger."""
        patterns = {
            "doctor_signature": PatternGroup(
                context_trigger="Mit freundlichen Grüßen",
                pattern=r"(Prof\.|Dr\.|PD)\s+(med\.\s+)?([A-ZÄÖÜ][a-zäöüß-]+(?:\s+[A-ZÄÖÜ][a-zäöüß-]+)+)",
                type="DOCTOR_NAME",
                lookahead=200
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = """
        Vielen Dank für Ihre Überweisung.
        
        Mit freundlichen Grüßen
        
        Prof. Dr. med. Karl Müller
        """
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 1
        assert entities[0].entity_type == "DOCTOR_NAME"
        assert "Karl Müller" in entities[0].text
        assert entities[0].context == "Mit freundlichen Grüßen"
    
    def test_no_extraction_without_context(self):
        """Test that extraction doesn't happen without proper context."""
        patterns = {
            "doctor_signature": PatternGroup(
                context_trigger="Mit freundlichen Grüßen",
                pattern=r"Prof\.\s+Dr\.\s+med\.\s+([A-ZÄÖÜ][a-zäöüß-]+)",
                type="DOCTOR_NAME",
                lookahead=100
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        # Text without the context trigger
        text = "Prof. Dr. med. Müller ist der Chefarzt."
        entities = extractor.extract_pii(text)
        
        # Should not extract because context trigger is missing
        assert len(entities) == 0
    
    def test_multiple_patterns(self):
        """Test extraction with multiple different patterns."""
        patterns = {
            "case_id": PatternGroup(
                pattern=r"Pat\.-Nr\.\s*([0-9]{6,10})",
                type="CASE_ID"
            ),
            "birthdate": PatternGroup(
                pattern=r"\*(\d{2}\.\d{2}\.\d{4})",
                type="BIRTHDATE"
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = "Patient Pat.-Nr. 987654321, geboren *15.05.1975"
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 2
        
        case_id = next(e for e in entities if e.entity_type == "CASE_ID")
        assert case_id.text == "987654321"
        
        birthdate = next(e for e in entities if e.entity_type == "BIRTHDATE")
        assert birthdate.text == "15.05.1975"
    
    def test_german_umlauts(self):
        """Test that German umlauts are properly handled."""
        patterns = {
            "patient_block": PatternGroup(
                pattern=r"(Herr|Frau)\s+([A-ZÄÖÜ][a-zäöüß-]+)",
                groups={
                    "1": "SALUTATION",
                    "2": "NAME"
                }
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = "Frau Müßiggang"
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 2
        name = next(e for e in entities if e.entity_type == "NAME")
        assert name.text == "Müßiggang"
    
    def test_extract_postal_code_with_city(self):
        """Test extraction of postal code with city name."""
        patterns = {
            "postal_code_with_city": PatternGroup(
                pattern=r"(\d{5})\s+([A-ZÄÖÜ][a-zäöüß]+)",
                groups={
                    "1": "POSTAL_CODE",
                    "2": "CITY"
                }
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = "Wohnhaft in 37075 Göttingen"
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 2
        
        postal_code = next(e for e in entities if e.entity_type == "POSTAL_CODE")
        assert postal_code.text == "37075"
        
        city = next(e for e in entities if e.entity_type == "CITY")
        assert city.text == "Göttingen"
    
    def test_extract_postal_code_standalone(self):
        """Test extraction of standalone postal code."""
        patterns = {
            "postal_code_standalone": PatternGroup(
                pattern=r"(?:PLZ:?\s*)?(\d{5})(?!\d)",
                type="POSTAL_CODE"
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = "PLZ: 20246"
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 1
        assert entities[0].entity_type == "POSTAL_CODE"
        assert entities[0].text == "20246"
    
    def test_extract_multiple_postal_codes(self):
        """Test extraction of multiple postal codes in text."""
        patterns = {
            "postal_code_with_city": PatternGroup(
                pattern=r"(\d{5})\s+([A-ZÄÖÜ][a-zäöüß]+)",
                groups={
                    "1": "POSTAL_CODE",
                    "2": "CITY"
                }
            )
        }
        extractor = StructuredPIIExtractor(patterns)
        
        text = "Patient von 37075 Göttingen nach 20246 Hamburg verlegt"
        entities = extractor.extract_pii(text)
        
        # Should find 2 postal codes and 2 cities
        assert len(entities) == 4
        
        postal_codes = [e for e in entities if e.entity_type == "POSTAL_CODE"]
        assert len(postal_codes) == 2
        assert postal_codes[0].text == "37075"
        assert postal_codes[1].text == "20246"
        
        cities = [e for e in entities if e.entity_type == "CITY"]
        assert len(cities) == 2
        assert cities[0].text == "Göttingen"
        assert cities[1].text == "Hamburg"


class TestFallnummerPattern:
    """Test cases for the extended case_id pattern including Fallnummer variants."""

    def setup_method(self):
        """Set up extractor with the extended case_id pattern."""
        self.patterns = {
            "case_id": PatternGroup(
                pattern=r"(?:Pat\.?-?(?:Nr\.?|Nummer)|Fall-?(?:Nr\.?|Nummer)):?\s*([0-9]{6,10})",
                type="CASE_ID"
            )
        }
        self.extractor = StructuredPIIExtractor(self.patterns)

    def test_fallnummer(self):
        """Test that 'Fallnummer: 310736' is recognized."""
        entities = self.extractor.extract_pii("Fallnummer: 310736")
        assert len(entities) == 1
        assert entities[0].entity_type == "CASE_ID"
        assert entities[0].text == "310736"

    def test_fall_nr_with_dot(self):
        """Test that 'Fall-Nr.: 310736' is recognized."""
        entities = self.extractor.extract_pii("Fall-Nr.: 310736")
        assert len(entities) == 1
        assert entities[0].text == "310736"

    def test_fall_nummer(self):
        """Test that 'Fall-Nummer: 310736' is recognized."""
        entities = self.extractor.extract_pii("Fall-Nummer: 310736")
        assert len(entities) == 1
        assert entities[0].text == "310736"

    def test_fallnr_no_separator(self):
        """Test that 'FallNr 310736' is recognized."""
        entities = self.extractor.extract_pii("FallNr 310736")
        assert len(entities) == 1
        assert entities[0].text == "310736"

    def test_pat_nr_still_works(self):
        """Test that the original 'Pat.-Nr.: 123456' still works."""
        entities = self.extractor.extract_pii("Pat.-Nr.: 123456")
        assert len(entities) == 1
        assert entities[0].text == "123456"

    def test_pat_nummer(self):
        """Test that 'Pat-Nummer: 123456' is recognized."""
        entities = self.extractor.extract_pii("Pat-Nummer: 123456")
        assert len(entities) == 1
        assert entities[0].text == "123456"

    def test_fallnummer_with_many_spaces(self):
        """Test 'Fallnummer:        310736' (many spaces, as in real PDFs)."""
        entities = self.extractor.extract_pii("Fallnummer:        310736")
        assert len(entities) == 1
        assert entities[0].text == "310736"


class TestMedicalFacilityPattern:
    """Test cases for the new medical_facility pattern."""

    def setup_method(self):
        """Set up extractor with the medical_facility pattern."""
        self.patterns = {
            "medical_facility": PatternGroup(
                pattern=r"(?:Ambulante[sn]?\s+)?(Herzzentrum|Tumorzentrum|Lungenzentrum|Ambulanzzentrum|Rehabilitationszentrum|Reha-?Zentrum|Rehaklinik|Klinik(?: und Rehabilitationszentrum)?)\s+((?:Bad\s+)?[A-ZÄÖÜ][a-zäöüß]+(?:\s+(?:am|an|der|im|in|ob)\s+[A-ZÄÖÜ][a-zäöüß]+)?)",
                groups={
                    "1": "FACILITY_TYPE",
                    "2": "CITY"
                }
            )
        }
        self.extractor = StructuredPIIExtractor(self.patterns)

    def test_ambulanten_herzzentrum_kassel(self):
        """Test that 'Ambulanten Herzzentrum Kassel' is recognized."""
        entities = self.extractor.extract_pii("im Ambulanten Herzzentrum Kassel (PD Dr. Jensen)")
        facility = next((e for e in entities if e.entity_type == "FACILITY_TYPE"), None)
        city = next((e for e in entities if e.entity_type == "CITY"), None)
        assert facility is not None
        assert facility.text == "Herzzentrum"
        assert city is not None
        assert city.text == "Kassel"

    def test_ambulantes_herzzentrum(self):
        """Test that 'Ambulantes Herzzentrum Kassel' is recognized."""
        entities = self.extractor.extract_pii("das Ambulantes Herzzentrum Kassel")
        assert any(e.entity_type == "FACILITY_TYPE" and e.text == "Herzzentrum" for e in entities)

    def test_klinik_und_rehabilitationszentrum(self):
        """Test that 'Klinik und Rehabilitationszentrum Lippoldsberg' is recognized."""
        entities = self.extractor.extract_pii("die Klinik und Rehabilitationszentrum Lippoldsberg")
        facility = next((e for e in entities if e.entity_type == "FACILITY_TYPE"), None)
        city = next((e for e in entities if e.entity_type == "CITY"), None)
        assert facility is not None
        assert "Klinik" in facility.text
        assert city is not None
        assert city.text == "Lippoldsberg"

    def test_rehabilitationszentrum(self):
        """Test that 'Rehabilitationszentrum Lippoldsberg' is recognized."""
        entities = self.extractor.extract_pii("Rehabilitationszentrum Lippoldsberg")
        assert any(e.entity_type == "CITY" and e.text == "Lippoldsberg" for e in entities)

    def test_rehaklinik(self):
        """Test that 'Rehaklinik Kassel' is recognized."""
        entities = self.extractor.extract_pii("Rehaklinik Kassel")
        assert any(e.entity_type == "FACILITY_TYPE" and e.text == "Rehaklinik" for e in entities)

    def test_city_with_am_suffix(self):
        """Test that cities with 'am' connector are recognized (e.g. 'Frankfurt am Main')."""
        entities = self.extractor.extract_pii("Herzzentrum Frankfurt am Main")
        city = next((e for e in entities if e.entity_type == "CITY"), None)
        assert city is not None
        assert city.text == "Frankfurt am Main"

    def test_city_with_bad_prefix(self):
        """Test that cities with 'Bad' prefix are recognized (e.g. 'Bad Homburg')."""
        entities = self.extractor.extract_pii("Rehaklinik Bad Homburg")
        city = next((e for e in entities if e.entity_type == "CITY"), None)
        assert city is not None
        assert city.text == "Bad Homburg"


class TestWhitespaceNormalization:
    """Test cases for whitespace normalization in extract_pii."""

    def setup_method(self):
        """Set up extractor with a simple pattern."""
        self.patterns = {
            "case_id": PatternGroup(
                pattern=r"(?:Pat\.?-?(?:Nr\.?|Nummer)|Fall-?(?:Nr\.?|Nummer)):?\s*([0-9]{6,10})",
                type="CASE_ID"
            )
        }
        self.extractor = StructuredPIIExtractor(self.patterns)

    def test_non_breaking_space_normalized(self):
        """Test that non-breaking space (\\xa0) is normalized to regular space."""
        # Non-breaking space between label and number
        text = "Fallnummer:\xa0310736"
        entities = self.extractor.extract_pii(text)
        assert len(entities) == 1
        assert entities[0].text == "310736"

    def test_narrow_no_break_space_normalized(self):
        """Test that narrow no-break space (\\u202f) is normalized."""
        text = "Fallnummer:\u202f310736"
        entities = self.extractor.extract_pii(text)
        assert len(entities) == 1
        assert entities[0].text == "310736"

    def test_whitelist_with_non_breaking_space(self):
        """Test that whitelist works consistently with non-breaking spaces."""
        from src.config import WhitelistConfig

        patterns = {
            "device": PatternGroup(
                pattern=r"\b(Medtronic Evolut)\b",
                type="DEVICE"
            )
        }
        whitelist = WhitelistConfig(
            medical_terms=[],
            anatomical_terms=[],
            device_names=["Medtronic Evolut"]
        )
        extractor = StructuredPIIExtractor(patterns, whitelist)

        # Non-breaking space variant should be normalized and thus whitelisted
        text = "Medtronic\xa0Evolut"
        entities = extractor.extract_pii(text)
        assert len(entities) == 0  # Should be whitelisted, not extracted


class TestWhitelistFunctionality:
    
    def test_whitelist_excludes_medical_terms(self):
        """Test that whitelisted medical terms are not extracted as PII."""
        from src.config import WhitelistConfig
        
        patterns = {
            "medical_facility": PatternGroup(
                pattern=r"\b(Medtronic|Edwards)\b",
                type="DEVICE"
            )
        }
        
        whitelist = WhitelistConfig(
            medical_terms=["Medtronic"],
            anatomical_terms=[],
            device_names=[]
        )
        
        extractor = StructuredPIIExtractor(patterns, whitelist)
        
        text = "Implantation einer Medtronic Klappe und Edwards Sapien"
        entities = extractor.extract_pii(text)
        
        # Medtronic should be whitelisted, Edwards should be extracted
        assert len(entities) == 1
        assert entities[0].text == "Edwards"
    
    def test_whitelist_case_insensitive(self):
        """Test that whitelist matching is case-insensitive."""
        from src.config import WhitelistConfig
        
        patterns = {
            "device": PatternGroup(
                pattern=r"\b(medtronic|MEDTRONIC|Medtronic)\b",
                type="DEVICE"
            )
        }
        
        whitelist = WhitelistConfig(
            medical_terms=["medtronic"],  # lowercase in whitelist
            anatomical_terms=[],
            device_names=[]
        )
        
        extractor = StructuredPIIExtractor(patterns, whitelist)
        
        # All variations should be whitelisted
        text = "medtronic MEDTRONIC Medtronic"
        entities = extractor.extract_pii(text)
        
        assert len(entities) == 0
    
    def test_whitelist_anatomical_terms(self):
        """Test that whitelisted anatomical terms are not extracted."""
        from src.config import WhitelistConfig
        
        patterns = {
            "anatomical": PatternGroup(
                pattern=r"\b(Aortenklappe|Herzklappe)\b",
                type="ANATOMY"
            )
        }
        
        whitelist = WhitelistConfig(
            medical_terms=[],
            anatomical_terms=["Aortenklappe"],
            device_names=[]
        )
        
        extractor = StructuredPIIExtractor(patterns, whitelist)
        
        text = "Erkrankung der Aortenklappe und Herzklappe"
        entities = extractor.extract_pii(text)
        
        # Aortenklappe whitelisted, Herzklappe extracted
        assert len(entities) == 1
        assert entities[0].text == "Herzklappe"
    
    def test_whitelist_device_names(self):
        """Test that whitelisted device names are not extracted."""
        from src.config import WhitelistConfig
        
        patterns = {
            "device": PatternGroup(
                pattern=r"\b(Edwards Sapien|Medtronic Evolut)\b",
                type="DEVICE"
            )
        }
        
        whitelist = WhitelistConfig(
            medical_terms=[],
            anatomical_terms=[],
            device_names=["Edwards Sapien"]
        )
        
        extractor = StructuredPIIExtractor(patterns, whitelist)
        
        text = "Verwendung von Edwards Sapien und Medtronic Evolut"
        entities = extractor.extract_pii(text)
        
        # Edwards Sapien whitelisted, Medtronic Evolut extracted
        assert len(entities) == 1
        assert entities[0].text == "Medtronic Evolut"
    
    def test_no_whitelist_all_extracted(self):
        """Test that without whitelist, all matching patterns are extracted."""
        patterns = {
            "device": PatternGroup(
                pattern=r"\b(Medtronic|Edwards)\b",
                type="DEVICE"
            )
        }
        
        # No whitelist provided
        extractor = StructuredPIIExtractor(patterns, whitelist=None)
        
        text = "Medtronic und Edwards"
        entities = extractor.extract_pii(text)
        
        # Both should be extracted
        assert len(entities) == 2


class TestSalutationWithNamePattern:
    """Test cases for the salutation_with_name pattern."""

    def setup_method(self):
        """Set up extractor with the salutation_with_name pattern."""
        self.patterns = {
            "salutation_with_name": PatternGroup(
                pattern=r"(?:Herr|Frau)\s+(?!(?:Kollege|Kollegin)\b)([A-ZÄÖÜ][a-zäöüß-]{2,})",
                type="PERSON_NAME"
            )
        }
        self.extractor = StructuredPIIExtractor(self.patterns)

    def test_herr_with_lastname(self):
        """Test that 'Herr Jensen' is recognized and 'Jensen' extracted."""
        entities = self.extractor.extract_pii("Herr Jensen schlägt als ersten Termin den 28.05.2025 vor.")
        assert len(entities) == 1
        assert entities[0].entity_type == "PERSON_NAME"
        assert entities[0].text == "Jensen"

    def test_frau_with_lastname(self):
        """Test that 'Frau Meier' is recognized and 'Meier' extracted."""
        entities = self.extractor.extract_pii("Der Patient Frau Meier wurde entlassen.")
        assert len(entities) == 1
        assert entities[0].entity_type == "PERSON_NAME"
        assert entities[0].text == "Meier"

    def test_herr_kollege_not_matched(self):
        """Test that 'Herr Kollege' is NOT redacted (generic salutation)."""
        entities = self.extractor.extract_pii("Sehr geehrter Herr Kollege,")
        assert len(entities) == 0

    def test_frau_kollegin_not_matched(self):
        """Test that 'Frau Kollegin' is NOT redacted (generic salutation)."""
        entities = self.extractor.extract_pii("Sehr geehrte Frau Kollegin,")
        assert len(entities) == 0

    def test_umlaut_lastname(self):
        """Test that names with German umlauts are recognized."""
        entities = self.extractor.extract_pii("Herr Müller wurde aufgenommen.")
        assert len(entities) == 1
        assert entities[0].text == "Müller"

    def test_multiple_salutations(self):
        """Test that multiple salutation patterns in one text are all found."""
        text = "Herr Jensen und Frau Schmidt wurden überwiesen."
        entities = self.extractor.extract_pii(text)
        names = {e.text for e in entities}
        assert "Jensen" in names
        assert "Schmidt" in names

    def test_hyphenated_lastname(self):
        """Test that hyphenated names are recognized."""
        entities = self.extractor.extract_pii("Frau Müller-Weber wurde entlassen.")
        assert len(entities) == 1
        assert entities[0].text == "Müller-Weber"


class TestDoctorNameParenthesesPattern:
    """Test cases for the doctor_name_parentheses pattern."""

    def setup_method(self):
        """Set up extractor with the doctor_name_parentheses pattern."""
        self.patterns = {
            "doctor_name_parentheses": PatternGroup(
                pattern=r"\(((Prof\.|Dr\.|PD)(?:[^\)]+))\)",
                type="DOCTOR_NAME"
            )
        }
        self.extractor = StructuredPIIExtractor(self.patterns)

    def test_pd_dr_in_parentheses(self):
        """Test that '(PD Dr. Christoph Jensen)' is recognized."""
        entities = self.extractor.extract_pii(
            "im Ambulanten Herzzentrum Kassel (PD Dr. Christoph Jensen)."
        )
        assert len(entities) == 1
        assert entities[0].entity_type == "DOCTOR_NAME"
        assert "Christoph Jensen" in entities[0].text

    def test_prof_med_in_parentheses(self):
        """Test that '(Prof. med. Müller)' is recognized."""
        entities = self.extractor.extract_pii("Behandelnder Arzt (Prof. med. Müller)")
        assert len(entities) == 1
        assert "Müller" in entities[0].text

    def test_dr_in_parentheses(self):
        """Test that '(Dr. Schmidt)' is recognized."""
        entities = self.extractor.extract_pii("Die Überweisung erfolgte durch (Dr. Schmidt).")
        assert len(entities) == 1
        assert entities[0].text.strip() == "Dr. Schmidt"

    def test_doctor_without_parentheses_not_matched(self):
        """Test that doctor names without parentheses are NOT matched by this pattern."""
        entities = self.extractor.extract_pii("Dr. Jensen übernimmt die Behandlung.")
        assert len(entities) == 0

