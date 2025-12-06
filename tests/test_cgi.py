"""Tests for CGI (Cancer Genome Interpreter) biomarkers client."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from tumorboard.api.cgi import CGIClient, CGIBiomarker, CGIError


class TestCGIBiomarker:
    """Tests for CGIBiomarker class."""

    def test_biomarker_creation(self):
        """Test creating a CGI biomarker."""
        biomarker = CGIBiomarker(
            gene="EGFR",
            alteration="EGFR:G719S",
            drug="Afatinib",
            drug_status="Approved",
            association="Responsive",
            evidence_level="FDA guidelines",
            source="FDA",
            tumor_type="NSCLC",
            tumor_type_full="Non-small cell lung",
        )

        assert biomarker.gene == "EGFR"
        assert biomarker.drug == "Afatinib"
        assert biomarker.drug_status == "Approved"
        assert biomarker.association == "Responsive"

    def test_is_fda_approved_true(self):
        """Test is_fda_approved returns True for FDA-approved drugs."""
        biomarker = CGIBiomarker(
            gene="EGFR",
            alteration="EGFR:G719S",
            drug="Afatinib",
            drug_status="Approved",
            association="Responsive",
            evidence_level="FDA guidelines",
            source="FDA",
            tumor_type="NSCLC",
            tumor_type_full="Non-small cell lung",
        )

        assert biomarker.is_fda_approved() is True

    def test_is_fda_approved_nccn(self):
        """Test is_fda_approved returns True for NCCN guideline drugs."""
        biomarker = CGIBiomarker(
            gene="EGFR",
            alteration="EGFR:G719S",
            drug="Erlotinib",
            drug_status="Approved",
            association="Responsive",
            evidence_level="NCCN guidelines",
            source="NCCN",
            tumor_type="NSCLC",
            tumor_type_full="Non-small cell lung",
        )

        assert biomarker.is_fda_approved() is True

    def test_is_fda_approved_false_clinical_trial(self):
        """Test is_fda_approved returns False for clinical trial drugs."""
        biomarker = CGIBiomarker(
            gene="EGFR",
            alteration="EGFR:G719S",
            drug="TestDrug",
            drug_status="Clinical trial",
            association="Responsive",
            evidence_level="Late trials",
            source="PMID:12345",
            tumor_type="NSCLC",
            tumor_type_full="Non-small cell lung",
        )

        assert biomarker.is_fda_approved() is False

    def test_is_fda_approved_false_not_approved(self):
        """Test is_fda_approved returns False for non-approved drugs."""
        biomarker = CGIBiomarker(
            gene="EGFR",
            alteration="EGFR:G719S",
            drug="TestDrug",
            drug_status="",  # Not approved
            association="Responsive",
            evidence_level="FDA guidelines",
            source="FDA",
            tumor_type="NSCLC",
            tumor_type_full="Non-small cell lung",
        )

        assert biomarker.is_fda_approved() is False

    def test_to_dict(self):
        """Test converting biomarker to dictionary."""
        biomarker = CGIBiomarker(
            gene="BRAF",
            alteration="BRAF:V600E",
            drug="Dabrafenib",
            drug_status="Approved",
            association="Responsive",
            evidence_level="FDA guidelines",
            source="FDA",
            tumor_type="MEL",
            tumor_type_full="Melanoma",
        )

        result = biomarker.to_dict()

        assert result["gene"] == "BRAF"
        assert result["drug"] == "Dabrafenib"
        assert result["fda_approved"] is True


class TestCGIClient:
    """Tests for CGIClient class."""

    def test_variant_matches_exact(self):
        """Test exact variant matching."""
        client = CGIClient()

        # Exact match
        assert client._variant_matches("EGFR:G719S", "EGFR", "G719S") is True
        assert client._variant_matches("BRAF:V600E", "BRAF", "V600E") is True

        # No match
        assert client._variant_matches("EGFR:L858R", "EGFR", "G719S") is False
        assert client._variant_matches("BRAF:V600K", "BRAF", "V600E") is False

    def test_variant_matches_wildcard(self):
        """Test wildcard variant matching (G719. matches G719S, G719A, etc.)."""
        client = CGIClient()

        # Wildcard match: G719. should match G719S, G719A, G719C, G719D
        assert client._variant_matches("EGFR:G719.", "EGFR", "G719S") is True
        assert client._variant_matches("EGFR:G719.", "EGFR", "G719A") is True
        assert client._variant_matches("EGFR:G719.", "EGFR", "G719C") is True

        # Wildcard should not match multi-character variants
        assert client._variant_matches("EGFR:G719.", "EGFR", "G719SX") is False

        # Q61. should match Q61K, Q61R, Q61L, Q61H
        assert client._variant_matches("NRAS:Q61.", "NRAS", "Q61K") is True
        assert client._variant_matches("NRAS:Q61.", "NRAS", "Q61R") is True

    def test_variant_matches_list(self):
        """Test matching against comma-separated list of variants."""
        client = CGIClient()

        # List of variants
        alteration = "EGFR:L858R,G719A,G719S,G719C,G719D,L861Q,S768I"

        assert client._variant_matches(alteration, "EGFR", "G719S") is True
        assert client._variant_matches(alteration, "EGFR", "L858R") is True
        assert client._variant_matches(alteration, "EGFR", "L861Q") is True

        # Not in list
        assert client._variant_matches(alteration, "EGFR", "T790M") is False

    def test_variant_matches_case_insensitive(self):
        """Test case-insensitive variant matching."""
        client = CGIClient()

        assert client._variant_matches("EGFR:G719S", "egfr", "g719s") is True
        assert client._variant_matches("EGFR:V600E", "BRAF", "v600e") is True

    def test_variant_matches_with_p_prefix(self):
        """Test matching variants with p. prefix."""
        client = CGIClient()

        # With p. prefix in query
        assert client._variant_matches("EGFR:G719S", "EGFR", "p.G719S") is True
        assert client._variant_matches("BRAF:V600E", "BRAF", "p.V600E") is True

    def test_tumor_type_matches_nsclc(self):
        """Test tumor type matching for NSCLC."""
        client = CGIClient()

        # Various NSCLC representations
        assert client._tumor_type_matches("NSCLC", "Non-Small Cell Lung Cancer") is True
        assert client._tumor_type_matches("NSCLC", "NSCLC") is True
        assert client._tumor_type_matches("L", "Lung Cancer") is True

        # Non-matching
        assert client._tumor_type_matches("NSCLC", "Melanoma") is False

    def test_tumor_type_matches_melanoma(self):
        """Test tumor type matching for melanoma."""
        client = CGIClient()

        assert client._tumor_type_matches("MEL", "Melanoma") is True
        assert client._tumor_type_matches("MEL", "Cutaneous Melanoma") is True

    def test_tumor_type_matches_colorectal(self):
        """Test tumor type matching for colorectal cancer."""
        client = CGIClient()

        assert client._tumor_type_matches("CRC", "Colorectal Cancer") is True
        assert client._tumor_type_matches("CRC", "Colon Cancer") is True

    def test_tumor_type_matches_none(self):
        """Test that None tumor type matches all."""
        client = CGIClient()

        # None tumor type should match anything
        assert client._tumor_type_matches("NSCLC", None) is True
        assert client._tumor_type_matches("MEL", None) is True
        assert client._tumor_type_matches("CRC", None) is True

    def test_cache_is_valid_no_file(self):
        """Test cache validation when file doesn't exist."""
        client = CGIClient()

        with patch.object(Path, "exists", return_value=False):
            assert client._cache_is_valid() is False

    @patch("tumorboard.api.cgi.CGIClient._load_biomarkers")
    def test_fetch_biomarkers_egfr_g719s(self, mock_load):
        """Test fetching biomarkers for EGFR G719S."""
        client = CGIClient()

        # Mock the TSV data
        mock_load.return_value = [
            {
                "Gene": "EGFR",
                "Alteration": "EGFR:L858R,G719A,G719S,G719C",
                "Drug": "Afatinib",
                "Drug status": "Approved",
                "Association": "Responsive",
                "Evidence level": "FDA guidelines",
                "Source": "FDA",
                "Primary Tumor type": "NSCLC",
                "Primary Tumor type full name": "Non-Small Cell Lung Cancer",
            },
            {
                "Gene": "EGFR",
                "Alteration": "EGFR:L858R,G719A,G719S,G719C",
                "Drug": "Gefitinib",
                "Drug status": "Approved",
                "Association": "Responsive",
                "Evidence level": "FDA guidelines",
                "Source": "FDA",
                "Primary Tumor type": "NSCLC",
                "Primary Tumor type full name": "Non-Small Cell Lung Cancer",
            },
            {
                "Gene": "BRAF",
                "Alteration": "BRAF:V600E",
                "Drug": "Dabrafenib",
                "Drug status": "Approved",
                "Association": "Responsive",
                "Evidence level": "FDA guidelines",
                "Source": "FDA",
                "Primary Tumor type": "MEL",
                "Primary Tumor type full name": "Melanoma",
            },
        ]

        biomarkers = client.fetch_biomarkers("EGFR", "G719S", "Non-Small Cell Lung Cancer")

        assert len(biomarkers) == 2
        assert all(b.gene == "EGFR" for b in biomarkers)
        assert all(b.is_fda_approved() for b in biomarkers)
        drugs = [b.drug for b in biomarkers]
        assert "Afatinib" in drugs
        assert "Gefitinib" in drugs

    @patch("tumorboard.api.cgi.CGIClient._load_biomarkers")
    def test_fetch_biomarkers_no_match(self, mock_load):
        """Test fetching biomarkers with no matching results."""
        client = CGIClient()

        mock_load.return_value = [
            {
                "Gene": "BRAF",
                "Alteration": "BRAF:V600E",
                "Drug": "Dabrafenib",
                "Drug status": "Approved",
                "Association": "Responsive",
                "Evidence level": "FDA guidelines",
                "Source": "FDA",
                "Primary Tumor type": "MEL",
                "Primary Tumor type full name": "Melanoma",
            },
        ]

        biomarkers = client.fetch_biomarkers("UNKNOWN", "X123Y")

        assert len(biomarkers) == 0

    @patch("tumorboard.api.cgi.CGIClient._load_biomarkers")
    def test_fetch_fda_approved_only(self, mock_load):
        """Test fetch_fda_approved filters for FDA-approved only."""
        client = CGIClient()

        mock_load.return_value = [
            {
                "Gene": "EGFR",
                "Alteration": "EGFR:G719S",
                "Drug": "Afatinib",
                "Drug status": "Approved",
                "Association": "Responsive",
                "Evidence level": "FDA guidelines",
                "Source": "FDA",
                "Primary Tumor type": "NSCLC",
                "Primary Tumor type full name": "Non-Small Cell Lung Cancer",
            },
            {
                "Gene": "EGFR",
                "Alteration": "EGFR:G719S",
                "Drug": "TestDrug",
                "Drug status": "",  # Not approved
                "Association": "Responsive",
                "Evidence level": "Late trials",
                "Source": "PMID:12345",
                "Primary Tumor type": "NSCLC",
                "Primary Tumor type full name": "Non-Small Cell Lung Cancer",
            },
            {
                "Gene": "EGFR",
                "Alteration": "EGFR:G719S",
                "Drug": "ResistDrug",
                "Drug status": "Approved",
                "Association": "Resistant",  # Not responsive
                "Evidence level": "FDA guidelines",
                "Source": "FDA",
                "Primary Tumor type": "NSCLC",
                "Primary Tumor type full name": "Non-Small Cell Lung Cancer",
            },
        ]

        biomarkers = client.fetch_fda_approved("EGFR", "G719S")

        assert len(biomarkers) == 1
        assert biomarkers[0].drug == "Afatinib"
        assert biomarkers[0].is_fda_approved() is True
        assert biomarkers[0].association == "Responsive"

    @patch("tumorboard.api.cgi.CGIClient._load_biomarkers")
    def test_fetch_biomarkers_wildcard_pattern(self, mock_load):
        """Test fetching biomarkers using wildcard pattern matching."""
        client = CGIClient()

        mock_load.return_value = [
            {
                "Gene": "NRAS",
                "Alteration": "NRAS:Q61.",  # Wildcard matches Q61K, Q61R, etc.
                "Drug": "Binimetinib",
                "Drug status": "Approved",
                "Association": "Responsive",
                "Evidence level": "Late trials",  # Not FDA approved
                "Source": "PMID:12345",
                "Primary Tumor type": "MEL",
                "Primary Tumor type full name": "Melanoma",
            },
        ]

        # Q61K should match Q61. pattern
        biomarkers = client.fetch_biomarkers("NRAS", "Q61K", "Melanoma")

        assert len(biomarkers) == 1
        assert biomarkers[0].drug == "Binimetinib"


class TestCGIClientIntegration:
    """Integration tests for CGI client (requires network)."""

    @pytest.mark.integration
    def test_fetch_real_biomarkers(self):
        """Test fetching real biomarkers from CGI database."""
        client = CGIClient()

        # This will download the actual CGI file
        biomarkers = client.fetch_biomarkers("EGFR", "G719S", "Non-Small Cell Lung Cancer")

        # Should find some biomarkers
        assert len(biomarkers) > 0

        # Should include FDA-approved drugs
        fda_approved = [b for b in biomarkers if b.is_fda_approved()]
        assert len(fda_approved) > 0

        # Should include Afatinib
        drugs = [b.drug for b in biomarkers]
        assert any("Afatinib" in d for d in drugs)
