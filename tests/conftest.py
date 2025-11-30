"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_variant_input():
    """Sample variant input for testing."""
    from tumorboard.models.variant import VariantInput

    return VariantInput(
        gene="BRAF",
        variant="V600E",
        tumor_type="Melanoma",
    )


@pytest.fixture
def sample_evidence():
    """Sample evidence for testing."""
    from tumorboard.models.evidence import CIViCEvidence, Evidence

    civic_ev = CIViCEvidence(
        evidence_type="Predictive",
        evidence_level="A",
        evidence_direction="Supports",
        clinical_significance="Sensitivity/Response",
        disease="Melanoma",
        drugs=["Vemurafenib", "Dabrafenib"],
        description="BRAF V600E mutation confers sensitivity to BRAF inhibitors in melanoma.",
        source="PubMed",
        rating=5,
    )

    return Evidence(
        variant_id="BRAF:V600E",
        gene="BRAF",
        variant="V600E",
        civic=[civic_ev],
        clinvar=[],
        cosmic=[],
    )


@pytest.fixture
def sample_gold_standard_entry():
    """Sample gold standard entry for testing."""
    from tumorboard.models.assessment import ActionabilityTier
    from tumorboard.models.validation import GoldStandardEntry

    return GoldStandardEntry(
        gene="BRAF",
        variant="V600E",
        tumor_type="Melanoma",
        expected_tier=ActionabilityTier.TIER_I,
        notes="FDA-approved BRAF inhibitors for melanoma",
        references=["PMID:22356324"],
    )


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return """{
        "tier": "Tier I",
        "confidence_score": 0.95,
        "summary": "BRAF V600E is a well-established actionable mutation in melanoma with FDA-approved targeted therapies.",
        "rationale": "Multiple FDA-approved BRAF inhibitors (vemurafenib, dabrafenib, encorafenib) exist for this mutation in melanoma. Strong clinical evidence from multiple phase III trials.",
        "evidence_strength": "Strong",
        "recommended_therapies": [
            {
                "drug_name": "Vemurafenib",
                "evidence_level": "FDA-approved",
                "approval_status": "Approved",
                "clinical_context": "First-line therapy"
            },
            {
                "drug_name": "Dabrafenib + Trametinib",
                "evidence_level": "FDA-approved",
                "approval_status": "Approved",
                "clinical_context": "First-line therapy"
            }
        ],
        "clinical_trials_available": true,
        "references": ["Chapman PB et al. NEJM 2011", "Hauschild A et al. Lancet 2012"]
    }"""
