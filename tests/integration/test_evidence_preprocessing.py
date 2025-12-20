"""Integration tests for evidence preprocessing pipeline.

These tests verify that the evidence preprocessing correctly formats
evidence for the LLM, particularly around tier-determining features like:
- FDA approval detection
- Later-line vs first-line classification
- Resistance marker identification
- Evidence summary header generation
- Tier hint computation (NEW)
- Variant-specific approval matching (NEW)
- Investigational-only detection (NEW)
"""

import pytest
from tumorboard.models.evidence import (
    Evidence,
    FDAApproval,
    CGIBiomarkerEvidence,
    VICCEvidence,
    CIViCEvidence,
    CIViCAssertionEvidence,
)


class TestFDAApprovalParsing:
    """Test FDA approval indication parsing."""

    def test_later_line_approval_detected(self):
        """Verify later-line approvals are correctly identified."""
        approval = FDAApproval(
            drug_name="encorafenib",
            brand_name="BRAFTOVI",
            indication="indicated for the treatment of adult patients with metastatic colorectal cancer (CRC) "
                      "with a BRAF V600E mutation, as detected by an FDA-approved test, after prior therapy.",
        )

        result = approval.parse_indication_for_tumor("Colorectal Cancer")

        assert result['tumor_match'] is True
        assert result['line_of_therapy'] == 'later-line'
        assert result['approval_type'] == 'full'

    def test_first_line_approval_detected(self):
        """Verify first-line approvals are correctly identified."""
        approval = FDAApproval(
            drug_name="osimertinib",
            brand_name="TAGRISSO",
            indication="non-small cell lung cancer (NSCLC) - indicated for first-line treatment "
                      "of adult patients with metastatic NSCLC whose tumors have EGFR mutations.",
        )

        result = approval.parse_indication_for_tumor("Non-Small Cell Lung Cancer")

        assert result['tumor_match'] is True
        assert result['line_of_therapy'] == 'first-line'

    def test_tumor_type_flexible_matching(self):
        """Verify tumor type matching works with abbreviations and full names."""
        approval = FDAApproval(
            drug_name="sotorasib",
            brand_name="LUMAKRAS",
            indication="indicated for the treatment of adult patients with KRAS G12C-mutated locally advanced "
                      "or metastatic non-small cell lung cancer (NSCLC), as determined by an FDA-approved test.",
        )

        # Should match various forms
        assert approval.parse_indication_for_tumor("NSCLC")['tumor_match'] is True
        assert approval.parse_indication_for_tumor("Non-Small Cell Lung Cancer")['tumor_match'] is True
        assert approval.parse_indication_for_tumor("lung")['tumor_match'] is True


class TestVariantMatchesApprovalClass:
    """Test the new variant-specific approval matching logic."""

    def test_braf_v600e_matches_v600_approval(self):
        """BRAF V600E should match V600-specific approvals."""
        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
            fda_approvals=[
                FDAApproval(
                    drug_name="vemurafenib",
                    brand_name="ZELBORAF",
                    indication="indicated for patients with BRAF V600E mutation detected melanoma",
                )
            ],
        )

        result = evidence._variant_matches_approval_class(
            gene="BRAF",
            variant="V600E",
            indication_text="indicated for patients with braf v600e mutation detected melanoma",
            approval=evidence.fda_approvals[0]
        )

        assert result is True

    def test_braf_g469a_does_not_match_v600_approval(self):
        """BRAF G469A should NOT match V600-specific approvals."""
        evidence = Evidence(
            variant_id="BRAF:G469A",
            gene="BRAF",
            variant="G469A",
            fda_approvals=[
                FDAApproval(
                    drug_name="vemurafenib",
                    brand_name="ZELBORAF",
                    indication="indicated for patients with BRAF V600E mutation detected melanoma",
                )
            ],
        )

        result = evidence._variant_matches_approval_class(
            gene="BRAF",
            variant="G469A",
            indication_text="indicated for patients with braf v600e mutation detected melanoma",
            approval=evidence.fda_approvals[0]
        )

        assert result is False

    def test_kras_g12c_matches_g12c_approval(self):
        """KRAS G12C should match G12C-specific approvals."""
        evidence = Evidence(
            variant_id="KRAS:G12C",
            gene="KRAS",
            variant="G12C",
            fda_approvals=[
                FDAApproval(
                    drug_name="sotorasib",
                    brand_name="LUMAKRAS",
                    indication="indicated for KRAS G12C-mutated NSCLC",
                )
            ],
        )

        result = evidence._variant_matches_approval_class(
            gene="KRAS",
            variant="G12C",
            indication_text="indicated for kras g12c-mutated nsclc",
            approval=evidence.fda_approvals[0]
        )

        assert result is True

    def test_kras_g12d_does_not_match_g12c_approval(self):
        """KRAS G12D should NOT match G12C-specific approvals."""
        evidence = Evidence(
            variant_id="KRAS:G12D",
            gene="KRAS",
            variant="G12D",
            fda_approvals=[
                FDAApproval(
                    drug_name="sotorasib",
                    brand_name="LUMAKRAS",
                    indication="indicated for KRAS G12C-mutated NSCLC",
                )
            ],
        )

        result = evidence._variant_matches_approval_class(
            gene="KRAS",
            variant="G12D",
            indication_text="indicated for kras g12c-mutated nsclc",
            approval=evidence.fda_approvals[0]
        )

        assert result is False

    def test_wild_type_exclusion_detected(self):
        """Variants should not match wild-type exclusion indications."""
        evidence = Evidence(
            variant_id="KRAS:G12D",
            gene="KRAS",
            variant="G12D",
            fda_approvals=[
                FDAApproval(
                    drug_name="cetuximab",
                    brand_name="ERBITUX",
                    indication="indicated for KRAS wild-type colorectal cancer",
                )
            ],
        )

        result = evidence._variant_matches_approval_class(
            gene="KRAS",
            variant="G12D",
            indication_text="indicated for kras wild-type colorectal cancer",
            approval=evidence.fda_approvals[0]
        )

        assert result is False


class TestInvestigationalOnly:
    """Test detection of investigational-only gene-tumor combinations."""

    def test_kras_pancreatic_is_investigational(self):
        """KRAS mutations in pancreatic cancer should be flagged as investigational."""
        evidence = Evidence(
            variant_id="KRAS:G12D",
            gene="KRAS",
            variant="G12D",
        )

        assert evidence.is_investigational_only("Pancreatic Cancer") is True
        assert evidence.is_investigational_only("pancreatic") is True

    def test_nras_melanoma_is_investigational(self):
        """NRAS mutations in melanoma should be flagged as investigational."""
        evidence = Evidence(
            variant_id="NRAS:Q61K",
            gene="NRAS",
            variant="Q61K",
        )

        assert evidence.is_investigational_only("Melanoma") is True

    def test_braf_melanoma_is_not_investigational(self):
        """BRAF V600E in melanoma should NOT be flagged as investigational."""
        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
        )

        assert evidence.is_investigational_only("Melanoma") is False

    def test_tp53_any_tumor_is_investigational(self):
        """TP53 mutations should be investigational in any tumor type."""
        evidence = Evidence(
            variant_id="TP53:R273H",
            gene="TP53",
            variant="R273H",
        )

        assert evidence.is_investigational_only("Breast Cancer") is True
        assert evidence.is_investigational_only("Lung Cancer") is True
        assert evidence.is_investigational_only("Colorectal Cancer") is True


class TestHasFDAForVariantInTumor:
    """Test the has_fda_for_variant_in_tumor method."""

    def test_braf_v600e_melanoma_has_fda(self):
        """BRAF V600E in melanoma with explicit FDA approval."""
        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
            fda_approvals=[
                FDAApproval(
                    drug_name="vemurafenib",
                    brand_name="ZELBORAF",
                    indication="indicated for melanoma with BRAF V600E mutation",
                )
            ],
        )

        assert evidence.has_fda_for_variant_in_tumor("Melanoma") is True

    def test_kras_g12d_pancreatic_no_fda(self):
        """KRAS G12D in pancreatic is investigational, no FDA."""
        evidence = Evidence(
            variant_id="KRAS:G12D",
            gene="KRAS",
            variant="G12D",
            fda_approvals=[
                FDAApproval(
                    drug_name="sotorasib",
                    indication="indicated for KRAS G12C NSCLC",  # Different variant
                )
            ],
        )

        # Should return False because pancreatic is investigational-only
        assert evidence.has_fda_for_variant_in_tumor("Pancreatic Cancer") is False

    def test_egfr_l858r_nsclc_has_fda(self):
        """EGFR L858R in NSCLC with explicit FDA approval."""
        evidence = Evidence(
            variant_id="EGFR:L858R",
            gene="EGFR",
            variant="L858R",
            fda_approvals=[
                FDAApproval(
                    drug_name="erlotinib",
                    indication="indicated for NSCLC with EGFR mutation L858R or exon 19 deletions",
                )
            ],
        )

        assert evidence.has_fda_for_variant_in_tumor("Non-Small Cell Lung Cancer") is True


class TestResistanceMarkerWithoutTargetedTherapy:
    """Test detection of resistance-only markers."""

    def test_kras_crc_is_resistance_only(self):
        """KRAS G12D in CRC is resistance-only marker (no targeted therapy FOR KRAS)."""
        evidence = Evidence(
            variant_id="KRAS:G12D",
            gene="KRAS",
            variant="G12D",
            cgi_biomarkers=[
                CGIBiomarkerEvidence(
                    gene="KRAS",
                    alteration="G12D",
                    drug="cetuximab",
                    association="Resistant",
                    evidence_level="FDA guidelines",
                    tumor_type="Colorectal Cancer",
                    fda_approved=True,
                ),
            ],
            vicc=[
                VICCEvidence(
                    gene="KRAS",
                    variant="G12D",
                    drugs=["cetuximab"],
                    is_resistance=True,
                    disease="Colorectal Cancer",
                ),
            ],
        )

        is_resistance, drugs = evidence.is_resistance_marker_without_targeted_therapy("Colorectal Cancer")

        assert is_resistance is True
        assert "cetuximab" in drugs

    def test_egfr_t790m_is_not_resistance_only(self):
        """EGFR T790M has FDA-approved osimertinib, so NOT resistance-only."""
        evidence = Evidence(
            variant_id="EGFR:T790M",
            gene="EGFR",
            variant="T790M",
            fda_approvals=[
                FDAApproval(
                    drug_name="osimertinib",
                    brand_name="TAGRISSO",
                    indication="indicated for NSCLC with EGFR T790M mutation",
                )
            ],
            vicc=[
                VICCEvidence(
                    gene="EGFR",
                    variant="T790M",
                    drugs=["erlotinib"],
                    is_resistance=True,
                    disease="NSCLC",
                ),
            ],
        )

        is_resistance, drugs = evidence.is_resistance_marker_without_targeted_therapy("Non-Small Cell Lung Cancer")

        # Has FDA-approved therapy FOR T790M, so not "resistance-only"
        assert is_resistance is False


class TestGetTierHint:
    """Test the tier hint computation - core of preprocessing logic."""

    def test_tier_i_for_fda_approved(self):
        """FDA-approved therapy FOR variant in tumor = Tier I hint."""
        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
            fda_approvals=[
                FDAApproval(
                    drug_name="vemurafenib",
                    brand_name="ZELBORAF",
                    indication="indicated for melanoma with BRAF V600E mutation",
                )
            ],
        )

        hint = evidence.get_tier_hint("Melanoma")

        assert "TIER I" in hint
        assert "fda" in hint.lower()

    def test_tier_ii_for_resistance_only(self):
        """Resistance marker without targeted therapy = Tier II hint."""
        evidence = Evidence(
            variant_id="KRAS:G12D",
            gene="KRAS",
            variant="G12D",
            cgi_biomarkers=[
                CGIBiomarkerEvidence(
                    gene="KRAS",
                    drug="cetuximab",
                    association="Resistant",
                    tumor_type="Colorectal Cancer",
                    fda_approved=True,
                ),
            ],
            vicc=[
                VICCEvidence(
                    gene="KRAS",
                    variant="G12D",
                    drugs=["cetuximab"],
                    is_resistance=True,
                    disease="Colorectal Cancer",
                ),
            ],
        )

        hint = evidence.get_tier_hint("Colorectal Cancer")

        assert "TIER II" in hint
        assert "RESISTANCE" in hint.upper() or "EXCLUDES" in hint.upper()

    def test_tier_iii_for_investigational_only(self):
        """Known investigational-only combinations = Tier III hint."""
        evidence = Evidence(
            variant_id="KRAS:G12D",
            gene="KRAS",
            variant="G12D",
        )

        hint = evidence.get_tier_hint("Pancreatic Cancer")

        assert "TIER III" in hint
        assert "investigational" in hint.lower()

    def test_tier_iii_for_prognostic_only(self):
        """Prognostic-only variants = Tier III hint."""
        evidence = Evidence(
            variant_id="TP53:R273H",
            gene="TP53",
            variant="R273H",
            civic_assertions=[
                CIViCAssertionEvidence(
                    assertion_type="PROGNOSTIC",
                    significance="POOR_OUTCOME",
                    disease="Breast Cancer",
                ),
            ],
        )

        # TP53 is in investigational-only list, so returns that hint first
        hint = evidence.get_tier_hint("Breast Cancer")
        assert "TIER III" in hint


class TestEvidenceSummaryHeader:
    """Test evidence summary header generation with tier hints."""

    def test_header_includes_tier_guidance(self):
        """Header should include tier classification guidance."""
        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
            fda_approvals=[
                FDAApproval(
                    drug_name="vemurafenib",
                    indication="indicated for melanoma with BRAF V600E mutation",
                )
            ],
        )

        header = evidence.format_evidence_summary_header(tumor_type="Melanoma")

        assert "TIER CLASSIFICATION GUIDANCE" in header
        assert "TIER I" in header

    def test_later_line_header_does_not_say_tier_ii(self):
        """CRITICAL: Later-line FDA approval should NOT say 'Tier II' in the header."""
        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
            fda_approvals=[
                FDAApproval(
                    drug_name="encorafenib",
                    brand_name="BRAFTOVI",
                    indication="indicated for metastatic colorectal cancer with BRAF V600E after prior therapy.",
                )
            ],
        )

        header = evidence.format_evidence_summary_header(tumor_type="Colorectal Cancer")

        # Should NOT contain misleading "Tier II" guidance for later-line approvals
        assert "TIER II, not Tier I" not in header
        assert "typically indicates TIER II" not in header

    def test_resistance_marker_correctly_labeled(self):
        """Verify resistance markers are identified in the header."""
        evidence = Evidence(
            variant_id="KRAS:G12D",
            gene="KRAS",
            variant="G12D",
            cgi_biomarkers=[
                CGIBiomarkerEvidence(
                    gene="KRAS",
                    alteration="G12D",
                    drug="cetuximab",
                    association="Resistant",
                    evidence_level="FDA guidelines",
                    tumor_type="Colorectal Cancer",
                    fda_approved=True,
                ),
            ],
            vicc=[
                VICCEvidence(drugs=["cetuximab"], is_resistance=True),
            ],
        )

        header = evidence.format_evidence_summary_header(tumor_type="Colorectal Cancer")

        assert "TIER II" in header
        assert "RESISTANCE" in header.upper() or "EXCLUDES" in header.upper()


class TestEvidenceCompactSummary:
    """Test compact evidence summary generation."""

    def test_variant_explicit_in_label_highlighted(self):
        """Verify variants explicitly in FDA labels are highlighted."""
        evidence = Evidence(
            variant_id="EGFR:G719S",
            gene="EGFR",
            variant="G719S",
            fda_approvals=[
                FDAApproval(
                    drug_name="afatinib",
                    brand_name="GILOTRIF",
                    indication="indicated for NSCLC with EGFR mutations",
                    variant_in_clinical_studies=True,
                )
            ],
        )

        summary = evidence.summary_compact(tumor_type="Non-Small Cell Lung Cancer")

        assert "VARIANT EXPLICITLY IN FDA LABEL" in summary

    def test_cgi_resistance_markers_separated(self):
        """Verify CGI resistance markers are clearly separated from sensitivity markers."""
        evidence = Evidence(
            variant_id="KRAS:G12D",
            gene="KRAS",
            variant="G12D",
            cgi_biomarkers=[
                CGIBiomarkerEvidence(
                    gene="KRAS",
                    drug="cetuximab",
                    association="Resistant",
                    evidence_level="FDA guidelines",
                    fda_approved=True,
                ),
                CGIBiomarkerEvidence(
                    gene="KRAS",
                    drug="panitumumab",
                    association="Resistant",
                    evidence_level="FDA guidelines",
                    fda_approved=True,
                ),
            ],
        )

        summary = evidence.summary_compact(tumor_type="Colorectal Cancer")

        assert "RESISTANCE MARKER" in summary.upper() or "EXCLUDE" in summary.upper()

    def test_civic_predictive_vs_prognostic_separation(self):
        """Verify CIViC PREDICTIVE assertions are separated from PROGNOSTIC."""
        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
            civic_assertions=[
                CIViCAssertionEvidence(
                    assertion_id=1,
                    amp_tier="Tier I",
                    assertion_type="PREDICTIVE",
                    significance="SENSITIVITYRESPONSE",
                    therapies=["vemurafenib"],
                    disease="Melanoma",
                ),
                CIViCAssertionEvidence(
                    assertion_id=2,
                    amp_tier="Tier I",
                    assertion_type="PROGNOSTIC",
                    significance="POOR_OUTCOME",
                    disease="Colorectal Cancer",
                ),
            ],
        )

        summary = evidence.summary_compact(tumor_type="Melanoma")

        # Should have separate sections
        assert "PREDICTIVE" in summary
        assert "PROGNOSTIC" in summary


class TestDrugAggregation:
    """Test drug-level evidence aggregation."""

    def test_drug_aggregation_net_signal(self):
        """Verify drug aggregation correctly computes net sensitivity/resistance signal."""
        evidence = Evidence(
            variant_id="EGFR:L858R",
            gene="EGFR",
            variant="L858R",
            vicc=[
                VICCEvidence(
                    gene="EGFR",
                    variant="L858R",
                    drugs=["erlotinib"],
                    evidence_level="A",
                    is_sensitivity=True,
                ),
                VICCEvidence(
                    gene="EGFR",
                    variant="L858R",
                    drugs=["erlotinib"],
                    evidence_level="B",
                    is_sensitivity=True,
                ),
                VICCEvidence(
                    gene="EGFR",
                    variant="L858R",
                    drugs=["erlotinib"],
                    evidence_level="C",
                    is_resistance=True,
                ),
            ],
        )

        aggregated = evidence.aggregate_evidence_by_drug()

        erlotinib_entry = next(d for d in aggregated if d['drug'].lower() == 'erlotinib')
        assert erlotinib_entry['sensitivity_count'] == 2
        assert erlotinib_entry['resistance_count'] == 1
        assert erlotinib_entry['best_level'] == 'A'

    def test_drug_aggregation_summary_format(self):
        """Verify drug aggregation summary format is correct."""
        evidence = Evidence(
            variant_id="EGFR:L858R",
            gene="EGFR",
            variant="L858R",
            vicc=[
                VICCEvidence(
                    gene="EGFR",
                    variant="L858R",
                    drugs=["gefitinib"],
                    evidence_level="A",
                    is_sensitivity=True,
                ),
            ],
        )

        summary = evidence.format_drug_aggregation_summary()

        assert "DRUG-LEVEL SUMMARY" in summary
        assert "gefitinib" in summary.lower()


class TestEvidenceStats:
    """Test evidence statistics computation."""

    def test_conflict_detection(self):
        """Verify conflicts (same drug with sensitivity AND resistance) are detected."""
        evidence = Evidence(
            variant_id="EGFR:T790M",
            gene="EGFR",
            variant="T790M",
            vicc=[
                VICCEvidence(
                    gene="EGFR",
                    variant="T790M",
                    drugs=["erlotinib"],
                    disease="lung adenocarcinoma",
                    evidence_level="A",
                    is_sensitivity=True,
                ),
                VICCEvidence(
                    gene="EGFR",
                    variant="T790M",
                    drugs=["erlotinib"],
                    disease="NSCLC",
                    evidence_level="C",
                    is_resistance=True,
                ),
            ],
        )

        stats = evidence.compute_evidence_stats()

        assert len(stats['conflicts']) > 0
        assert any(c['drug'].lower() == 'erlotinib' for c in stats['conflicts'])

    def test_dominant_signal_calculation(self):
        """Verify dominant signal is correctly calculated."""
        # 100% sensitivity
        evidence_sens = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
            vicc=[
                VICCEvidence(drugs=["vemurafenib"], is_sensitivity=True),
                VICCEvidence(drugs=["dabrafenib"], is_sensitivity=True),
            ],
        )
        assert evidence_sens.compute_evidence_stats()['dominant_signal'] == 'sensitivity_only'

        # 100% resistance
        evidence_res = Evidence(
            variant_id="KRAS:G12D",
            gene="KRAS",
            variant="G12D",
            vicc=[
                VICCEvidence(drugs=["cetuximab"], is_resistance=True),
                VICCEvidence(drugs=["panitumumab"], is_resistance=True),
            ],
        )
        assert evidence_res.compute_evidence_stats()['dominant_signal'] == 'resistance_only'


class TestTumorTypeMatching:
    """Test tumor type flexible matching."""

    @pytest.mark.parametrize("user_input,database_disease,expected", [
        ("CRC", "Colorectal Cancer", True),
        ("colorectal", "colorectal adenocarcinoma", True),  # Partial match works
        ("NSCLC", "Non-Small Cell Lung Cancer", True),
        ("lung", "lung adenocarcinoma", True),
        ("melanoma", "Cutaneous Melanoma", True),
        ("breast", "Breast Carcinoma", True),
        ("CRC", "Melanoma", False),
        ("NSCLC", "Colorectal Cancer", False),
    ])
    def test_tumor_type_matching(self, user_input, database_disease, expected):
        """Verify flexible tumor type matching works correctly."""
        result = Evidence._tumor_matches(user_input, database_disease)
        assert result == expected, f"Expected {user_input} vs {database_disease} to be {expected}"


class TestIntegrationWithLLMPrompt:
    """Integration tests verifying evidence formatting for LLM consumption."""

    def test_evidence_summary_for_tier_i_case(self):
        """Verify evidence summary for a known Tier I case (BRAF V600E melanoma)."""
        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
            fda_approvals=[
                FDAApproval(
                    drug_name="vemurafenib",
                    brand_name="ZELBORAF",
                    indication="indicated for the treatment of patients with unresectable or metastatic melanoma "
                              "with BRAF V600E mutation as detected by an FDA-approved test.",
                    variant_in_clinical_studies=True,
                )
            ],
            cgi_biomarkers=[
                CGIBiomarkerEvidence(
                    gene="BRAF",
                    alteration="V600E",
                    drug="vemurafenib",
                    association="Responsive",
                    evidence_level="FDA guidelines",
                    tumor_type="Melanoma",
                    fda_approved=True,
                )
            ],
        )

        header = evidence.format_evidence_summary_header(tumor_type="Melanoma")
        compact = evidence.summary_compact(tumor_type="Melanoma")
        tier_hint = evidence.get_tier_hint(tumor_type="Melanoma")

        # Should clearly indicate Tier I
        assert "TIER I" in tier_hint or "TIER I" in header
        assert "FDA" in header or "FDA" in compact

    def test_evidence_summary_for_resistance_marker(self):
        """Verify evidence summary for a resistance marker (KRAS G12D CRC)."""
        evidence = Evidence(
            variant_id="KRAS:G12D",
            gene="KRAS",
            variant="G12D",
            cgi_biomarkers=[
                CGIBiomarkerEvidence(
                    gene="KRAS",
                    alteration="G12D",
                    drug="cetuximab",
                    association="Resistant",
                    evidence_level="FDA guidelines",
                    tumor_type="Colorectal Cancer",
                    fda_approved=True,
                ),
                CGIBiomarkerEvidence(
                    gene="KRAS",
                    alteration="G12D",
                    drug="panitumumab",
                    association="Resistant",
                    evidence_level="FDA guidelines",
                    tumor_type="Colorectal Cancer",
                    fda_approved=True,
                ),
            ],
            vicc=[
                VICCEvidence(
                    gene="KRAS",
                    variant="G12D",
                    drugs=["cetuximab"],
                    evidence_level="A",
                    is_resistance=True,
                    disease="Colorectal Cancer",
                ),
            ],
        )

        header = evidence.format_evidence_summary_header(tumor_type="Colorectal Cancer")
        compact = evidence.summary_compact(tumor_type="Colorectal Cancer")
        tier_hint = evidence.get_tier_hint(tumor_type="Colorectal Cancer")

        full_summary = header + compact

        # Should indicate Tier II for resistance marker
        assert "TIER II" in tier_hint
        # Should clearly indicate resistance marker
        assert "RESISTANCE" in full_summary.upper()
        # Should mention the drugs it excludes
        assert "cetuximab" in full_summary.lower() or "panitumumab" in full_summary.lower()

    def test_evidence_summary_for_investigational_only(self):
        """Verify evidence summary for investigational-only case (KRAS G12D pancreatic)."""
        evidence = Evidence(
            variant_id="KRAS:G12D",
            gene="KRAS",
            variant="G12D",
            vicc=[
                VICCEvidence(
                    gene="KRAS",
                    variant="G12D",
                    drugs=["some_experimental_drug"],
                    evidence_level="C",
                    is_sensitivity=True,
                    disease="Pancreatic Cancer",
                ),
            ],
        )

        tier_hint = evidence.get_tier_hint(tumor_type="Pancreatic Cancer")
        header = evidence.format_evidence_summary_header(tumor_type="Pancreatic Cancer")

        # Should indicate Tier III for investigational-only
        assert "TIER III" in tier_hint
        assert "investigational" in tier_hint.lower()
        assert "TIER III" in header