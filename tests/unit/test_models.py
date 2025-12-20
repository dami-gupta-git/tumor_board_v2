"""Tests for data models."""

import pytest
from pydantic import ValidationError

from tumorboard.models.assessment import ActionabilityAssessment, ActionabilityTier, RecommendedTherapy
from tumorboard.models.evidence import CIViCEvidence, Evidence, VICCEvidence
from tumorboard.models.validation import GoldStandardEntry, ValidationMetrics, ValidationResult
from tumorboard.models.variant import VariantInput


class TestVariantInput:
    """Tests for VariantInput model."""

    def test_variant_input_creation(self):
        """Test creating a variant input."""
        variant = VariantInput(
            gene="BRAF",
            variant="V600E",
            tumor_type="Melanoma",
        )
        assert variant.gene == "BRAF"
        assert variant.variant == "V600E"
        assert variant.tumor_type == "Melanoma"

    def test_to_hgvs(self):
        """Test HGVS conversion."""
        variant = VariantInput(gene="BRAF", variant="V600E", tumor_type="Melanoma")
        assert variant.to_hgvs() == "BRAF:V600E"

    def test_variant_input_without_tumor(self):
        """Test creating a variant input without tumor type."""
        variant = VariantInput(
            gene="KRAS",
            variant="G12C",
            tumor_type=None,
        )
        assert variant.gene == "KRAS"
        assert variant.variant == "G12C"
        assert variant.tumor_type is None

    def test_variant_input_validates_snp_indel_only(self):
        """Test that only SNPs and small indels are allowed."""
        # These should succeed
        VariantInput(gene="BRAF", variant="V600E")  # Missense
        VariantInput(gene="TP53", variant="R248*")  # Nonsense
        VariantInput(gene="BRCA1", variant="185delAG")  # Deletion
        VariantInput(gene="EGFR", variant="L747fs")  # Frameshift

        # These should fail
        with pytest.raises(ValidationError, match="fusion.*not supported"):
            VariantInput(gene="ALK", variant="fusion")

        with pytest.raises(ValidationError, match="amplification.*not supported"):
            VariantInput(gene="ERBB2", variant="amplification")

        with pytest.raises(ValidationError, match="splice.*not supported"):
            VariantInput(gene="MET", variant="exon 14 skipping")

    def test_variant_input_deletion_allowed(self):
        """Test that small deletions are allowed."""
        variant = VariantInput(gene="BRCA1", variant="185delAG")
        assert variant.gene == "BRCA1"
        assert variant.variant == "185delAG"

    def test_variant_input_insertion_allowed(self):
        """Test that small insertions are allowed."""
        # Using a variant with 'ins' keyword
        variant = VariantInput(gene="EGFR", variant="L747_P753delinsS")
        assert variant.gene == "EGFR"


class TestEvidence:
    """Tests for Evidence models."""

    def test_civic_evidence_creation(self):
        """Test creating CIViC evidence."""
        civic = CIViCEvidence(
            evidence_type="Predictive",
            evidence_level="A",
            clinical_significance="Sensitivity/Response",
            disease="Melanoma",
            drugs=["Vemurafenib"],
            description="Test evidence",
        )
        assert civic.evidence_type == "Predictive"
        assert "Vemurafenib" in civic.drugs

    def test_evidence_has_evidence(self):
        """Test has_evidence method."""
        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
        )
        assert not evidence.has_evidence()

        evidence.civic = [CIViCEvidence(evidence_type="Predictive")]
        assert evidence.has_evidence()

    def test_evidence_with_identifiers(self):
        """Test creating evidence with database identifiers."""
        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
            cosmic_id="COSM476",
            ncbi_gene_id="673",
            dbsnp_id="rs113488022",
            clinvar_id="13961",
            hgvs_genomic="NC_000007.13:g.140453136A>T",
            hgvs_protein="NP_004324.2:p.Val600Glu",
            hgvs_transcript="NM_004333.4:c.1799T>A",
        )
        assert evidence.cosmic_id == "COSM476"
        assert evidence.ncbi_gene_id == "673"
        assert evidence.dbsnp_id == "rs113488022"
        assert evidence.clinvar_id == "13961"
        assert evidence.hgvs_genomic == "NC_000007.13:g.140453136A>T"
        assert evidence.hgvs_protein == "NP_004324.2:p.Val600Glu"
        assert evidence.hgvs_transcript == "NM_004333.4:c.1799T>A"


class TestActionabilityAssessment:
    """Tests for ActionabilityAssessment model."""

    def test_assessment_creation(self):
        """Test creating an assessment."""
        assessment = ActionabilityAssessment(
            gene="BRAF",
            variant="V600E",
            tumor_type="Melanoma",
            tier=ActionabilityTier.TIER_I,
            confidence_score=0.95,
            summary="Test summary",
            rationale="Test rationale",
            cosmic_id="COSM476",
            ncbi_gene_id="673",
        )
        assert assessment.tier == ActionabilityTier.TIER_I
        assert assessment.confidence_score == 0.95
        assert assessment.cosmic_id == "COSM476"
        assert assessment.ncbi_gene_id == "673"

    def test_to_report(self):
        """Test simple report generation."""
        assessment = ActionabilityAssessment(
            gene="BRAF",
            variant="V600E",
            tumor_type="Melanoma",
            tier=ActionabilityTier.TIER_I,
            confidence_score=0.95,
            summary="Test summary",
            rationale="Test rationale",
            recommended_therapies=[
                RecommendedTherapy(
                    drug_name="Vemurafenib",
                    evidence_level="FDA-approved",
                )
            ],
            cosmic_id="COSM476",
            dbsnp_id="rs113488022",
            hgvs_protein="NP_004324.2:p.Val600Glu",
        )
        report = assessment.to_report()
        assert "BRAF" in report
        assert "V600E" in report
        assert "Melanoma" in report
        assert "Tier I" in report
        assert "Vemurafenib" in report
        assert "COSM476" in report
        assert "rs113488022" in report
        assert "NP_004324.2:p.Val600Glu" in report

    def test_assessment_without_tumor(self):
        """Test creating an assessment without tumor type."""
        assessment = ActionabilityAssessment(
            gene="KRAS",
            variant="G12C",
            tumor_type=None,
            tier=ActionabilityTier.TIER_III,
            confidence_score=0.5,
            summary="General assessment without tumor context",
            rationale="Test rationale",
        )
        assert assessment.gene == "KRAS"
        assert assessment.tumor_type is None
        assert assessment.tier == ActionabilityTier.TIER_III

    def test_to_report_without_tumor(self):
        """Test report generation without tumor type."""
        assessment = ActionabilityAssessment(
            gene="KRAS",
            variant="G12C",
            tumor_type=None,
            tier=ActionabilityTier.TIER_III,
            confidence_score=0.5,
            summary="General assessment",
            rationale="Test rationale",
        )
        report = assessment.to_report()
        assert "KRAS" in report
        assert "G12C" in report
        assert "Not specified" in report
        assert "Tier III" in report


class TestValidationModels:
    """Tests for validation models."""

    def test_gold_standard_entry(self):
        """Test gold standard entry creation."""
        entry = GoldStandardEntry(
            gene="BRAF",
            variant="V600E",
            tumor_type="Melanoma",
            expected_tier=ActionabilityTier.TIER_I,
        )
        assert entry.expected_tier == ActionabilityTier.TIER_I

    def test_validation_result_tier_distance(self):
        """Test tier distance calculation."""
        assessment = ActionabilityAssessment(
            gene="BRAF",
            variant="V600E",
            tumor_type="Melanoma",
            tier=ActionabilityTier.TIER_II,
            confidence_score=0.8,
            summary="Test",
            rationale="Test",
        )

        result = ValidationResult(
            gene="BRAF",
            variant="V600E",
            tumor_type="Melanoma",
            expected_tier=ActionabilityTier.TIER_I,
            predicted_tier=ActionabilityTier.TIER_II,
            is_correct=False,
            confidence_score=0.8,
            assessment=assessment,
        )

        assert result.tier_distance == 1

    def test_tier_metrics_calculation(self):
        """Test tier metrics calculation."""
        from tumorboard.models.validation import TierMetrics

        metrics = TierMetrics(
            tier=ActionabilityTier.TIER_I,
            true_positives=8,
            false_positives=2,
            false_negatives=1,
        )
        metrics.calculate()

        assert metrics.precision == 0.8  # 8/(8+2)
        assert metrics.recall == 8 / 9  # 8/(8+1)
        assert metrics.f1_score > 0

    def test_validation_metrics(self, sample_gold_standard_entry):
        """Test validation metrics calculation."""
        # Create mock results
        assessment = ActionabilityAssessment(
            gene="BRAF",
            variant="V600E",
            tumor_type="Melanoma",
            tier=ActionabilityTier.TIER_I,
            confidence_score=0.95,
            summary="Test",
            rationale="Test",
        )

        result = ValidationResult(
            gene="BRAF",
            variant="V600E",
            tumor_type="Melanoma",
            expected_tier=ActionabilityTier.TIER_I,
            predicted_tier=ActionabilityTier.TIER_I,
            is_correct=True,
            confidence_score=0.95,
            assessment=assessment,
        )

        metrics = ValidationMetrics()
        metrics.calculate([result])

        assert metrics.total_cases == 1
        assert metrics.correct_predictions == 1
        assert metrics.accuracy == 1.0


class TestEvidenceStats:
    """Tests for evidence statistics and conflict detection."""

    def test_compute_stats_sensitivity_only(self):
        """Test stats when all evidence is sensitivity."""
        evidence = Evidence(
            variant_id="EGFR:L858R",
            gene="EGFR",
            variant="L858R",
            vicc=[
                VICCEvidence(drugs=["Erlotinib"], evidence_level="A", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Gefitinib"], evidence_level="B", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Osimertinib"], evidence_level="A", is_sensitivity=True, disease="NSCLC"),
            ]
        )

        stats = evidence.compute_evidence_stats()

        assert stats['sensitivity_count'] == 3
        assert stats['resistance_count'] == 0
        assert stats['dominant_signal'] == 'sensitivity_only'
        assert stats['conflicts'] == []

    def test_compute_stats_resistance_only(self):
        """Test stats when all evidence is resistance."""
        evidence = Evidence(
            variant_id="KRAS:G12V",
            gene="KRAS",
            variant="G12V",
            vicc=[
                VICCEvidence(drugs=["Cetuximab"], evidence_level="A", is_resistance=True, disease="Colorectal Cancer"),
                VICCEvidence(drugs=["Panitumumab"], evidence_level="B", is_resistance=True, disease="Colorectal Cancer"),
            ]
        )

        stats = evidence.compute_evidence_stats()

        assert stats['sensitivity_count'] == 0
        assert stats['resistance_count'] == 2
        assert stats['dominant_signal'] == 'resistance_only'

    def test_compute_stats_sensitivity_dominant(self):
        """Test stats when sensitivity strongly predominates (>80%)."""
        evidence = Evidence(
            variant_id="EGFR:S768I",
            gene="EGFR",
            variant="S768I",
            vicc=[
                VICCEvidence(drugs=["Erlotinib"], evidence_level="C", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Erlotinib"], evidence_level="C", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Erlotinib"], evidence_level="B", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Gefitinib"], evidence_level="B", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Gefitinib"], evidence_level="D", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Gefitinib"], evidence_level="C", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Afatinib"], evidence_level="A", is_sensitivity=True, disease="NSCLC"),
                # 1 resistance entry
                VICCEvidence(drugs=["Erlotinib"], evidence_level="C", is_resistance=True, disease="NSCLC"),
            ]
        )

        stats = evidence.compute_evidence_stats()

        assert stats['sensitivity_count'] == 7
        assert stats['resistance_count'] == 1
        assert stats['dominant_signal'] == 'sensitivity_dominant'
        # Should have sensitivity percentage > 80%
        total = stats['sensitivity_count'] + stats['resistance_count']
        sens_pct = stats['sensitivity_count'] / total * 100
        assert sens_pct >= 80

    def test_compute_stats_mixed_signals(self):
        """Test stats when signals are mixed (neither dominates)."""
        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
            vicc=[
                VICCEvidence(drugs=["Dabrafenib"], evidence_level="A", is_sensitivity=True, disease="Melanoma"),
                VICCEvidence(drugs=["Vemurafenib"], evidence_level="A", is_sensitivity=True, disease="Melanoma"),
                VICCEvidence(drugs=["Dabrafenib"], evidence_level="B", is_resistance=True, disease="Colorectal Cancer"),
                VICCEvidence(drugs=["Vemurafenib"], evidence_level="B", is_resistance=True, disease="Colorectal Cancer"),
            ]
        )

        stats = evidence.compute_evidence_stats()

        assert stats['sensitivity_count'] == 2
        assert stats['resistance_count'] == 2
        assert stats['dominant_signal'] == 'mixed'

    def test_detect_conflicts(self):
        """Test detection of conflicting evidence for the same drug."""
        evidence = Evidence(
            variant_id="EGFR:S768I",
            gene="EGFR",
            variant="S768I",
            vicc=[
                VICCEvidence(drugs=["Erlotinib"], evidence_level="C", is_sensitivity=True, disease="lung adenocarcinoma"),
                VICCEvidence(drugs=["Erlotinib"], evidence_level="C", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Erlotinib"], evidence_level="C", is_resistance=True, disease="lung cancer"),
            ]
        )

        stats = evidence.compute_evidence_stats()

        assert len(stats['conflicts']) == 1
        conflict = stats['conflicts'][0]
        assert conflict['drug'].lower() == 'erlotinib'
        assert conflict['sensitivity_count'] == 2
        assert conflict['resistance_count'] == 1

    def test_format_evidence_summary_header(self):
        """Test that summary header is formatted correctly."""
        evidence = Evidence(
            variant_id="EGFR:L858R",
            gene="EGFR",
            variant="L858R",
            vicc=[
                VICCEvidence(drugs=["Erlotinib"], evidence_level="A", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Gefitinib"], evidence_level="B", is_sensitivity=True, disease="NSCLC"),
            ]
        )

        header = evidence.format_evidence_summary_header()

        assert "EVIDENCE SUMMARY" in header
        assert "Sensitivity entries: 2" in header
        assert "sensitivity_only" in header.lower() or "sensitivity" in header.lower()
        assert "100%" in header  # 100% sensitivity

    def test_format_evidence_summary_header_with_conflicts(self):
        """Test that conflicts appear in the summary header."""
        evidence = Evidence(
            variant_id="EGFR:S768I",
            gene="EGFR",
            variant="S768I",
            vicc=[
                VICCEvidence(drugs=["Erlotinib"], evidence_level="C", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Erlotinib"], evidence_level="C", is_resistance=True, disease="NSCLC"),
            ]
        )

        header = evidence.format_evidence_summary_header()

        assert "CONFLICTS DETECTED" in header
        assert "Erlotinib" in header

    def test_evidence_level_breakdown(self):
        """Test that evidence levels are correctly counted."""
        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
            vicc=[
                VICCEvidence(drugs=["Dabrafenib"], evidence_level="A", is_sensitivity=True, disease="Melanoma"),
                VICCEvidence(drugs=["Vemurafenib"], evidence_level="A", is_sensitivity=True, disease="Melanoma"),
                VICCEvidence(drugs=["Encorafenib"], evidence_level="B", is_sensitivity=True, disease="Melanoma"),
                VICCEvidence(drugs=["Dabrafenib"], evidence_level="C", is_resistance=True, disease="CRC"),
            ]
        )

        stats = evidence.compute_evidence_stats()

        assert stats['sensitivity_by_level'] == {'A': 2, 'B': 1}
        assert stats['resistance_by_level'] == {'C': 1}


class TestLowQualityMinorityFilter:
    """Tests for filtering low-quality minority signals."""

    def test_filter_drops_low_quality_resistance_when_high_quality_sensitivity(self):
        """When we have Level A/B sensitivity and only C/D resistance (<=2), drop resistance."""
        evidence = Evidence(
            variant_id="EGFR:L858R",
            gene="EGFR",
            variant="L858R",
            vicc=[
                # High-quality sensitivity
                VICCEvidence(drugs=["Erlotinib"], evidence_level="A", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Gefitinib"], evidence_level="B", is_sensitivity=True, disease="NSCLC"),
                # Low-quality resistance (noise)
                VICCEvidence(drugs=["Erlotinib"], evidence_level="C", is_resistance=True, disease="lung cancer"),
            ]
        )

        filtered_sens, filtered_res = evidence.filter_low_quality_minority_signals()

        assert len(filtered_sens) == 2
        assert len(filtered_res) == 0  # Low-quality resistance dropped

    def test_filter_drops_low_quality_sensitivity_when_high_quality_resistance(self):
        """When we have Level A/B resistance and only C/D sensitivity (<=2), drop sensitivity."""
        evidence = Evidence(
            variant_id="KRAS:G12V",
            gene="KRAS",
            variant="G12V",
            vicc=[
                # High-quality resistance
                VICCEvidence(drugs=["Cetuximab"], evidence_level="A", is_resistance=True, disease="CRC"),
                VICCEvidence(drugs=["Panitumumab"], evidence_level="B", is_resistance=True, disease="CRC"),
                # Low-quality sensitivity (noise)
                VICCEvidence(drugs=["Cetuximab"], evidence_level="D", is_sensitivity=True, disease="preclinical"),
            ]
        )

        filtered_sens, filtered_res = evidence.filter_low_quality_minority_signals()

        assert len(filtered_sens) == 0  # Low-quality sensitivity dropped
        assert len(filtered_res) == 2

    def test_filter_keeps_both_when_both_have_high_quality(self):
        """When both sensitivity and resistance have high-quality evidence, keep both."""
        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
            vicc=[
                VICCEvidence(drugs=["Vemurafenib"], evidence_level="A", is_sensitivity=True, disease="Melanoma"),
                VICCEvidence(drugs=["Vemurafenib"], evidence_level="B", is_resistance=True, disease="CRC"),
            ]
        )

        filtered_sens, filtered_res = evidence.filter_low_quality_minority_signals()

        assert len(filtered_sens) == 1
        assert len(filtered_res) == 1  # Both kept - both have high-quality

    def test_filter_keeps_both_when_low_quality_but_many_entries(self):
        """Keep low-quality minority if there are more than 2 entries (might be real signal)."""
        evidence = Evidence(
            variant_id="TEST:V123A",
            gene="TEST",
            variant="V123A",
            vicc=[
                VICCEvidence(drugs=["DrugA"], evidence_level="A", is_sensitivity=True, disease="cancer"),
                # 3 low-quality resistance entries - might be real signal
                VICCEvidence(drugs=["DrugA"], evidence_level="C", is_resistance=True, disease="cancer"),
                VICCEvidence(drugs=["DrugA"], evidence_level="D", is_resistance=True, disease="cancer"),
                VICCEvidence(drugs=["DrugA"], evidence_level="C", is_resistance=True, disease="cancer"),
            ]
        )

        filtered_sens, filtered_res = evidence.filter_low_quality_minority_signals()

        assert len(filtered_sens) == 1
        assert len(filtered_res) == 3  # All kept - too many to be noise


class TestDrugAggregation:
    """Tests for drug-level evidence aggregation."""

    def test_aggregate_single_drug_sensitivity_only(self):
        """Aggregate multiple entries for a single drug with only sensitivity."""
        evidence = Evidence(
            variant_id="EGFR:L858R",
            gene="EGFR",
            variant="L858R",
            vicc=[
                VICCEvidence(drugs=["Erlotinib"], evidence_level="A", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Erlotinib"], evidence_level="B", is_sensitivity=True, disease="lung adenocarcinoma"),
                VICCEvidence(drugs=["Erlotinib"], evidence_level="C", is_sensitivity=True, disease="NSCLC"),
            ]
        )

        aggregated = evidence.aggregate_evidence_by_drug()

        assert len(aggregated) == 1
        drug = aggregated[0]
        assert drug['drug'].lower() == 'erlotinib'
        assert drug['sensitivity_count'] == 3
        assert drug['resistance_count'] == 0
        assert drug['net_signal'] == 'SENSITIVE'
        assert drug['best_level'] == 'A'

    def test_aggregate_single_drug_resistance_only(self):
        """Aggregate multiple entries for a single drug with only resistance."""
        evidence = Evidence(
            variant_id="KRAS:G12V",
            gene="KRAS",
            variant="G12V",
            vicc=[
                VICCEvidence(drugs=["Cetuximab"], evidence_level="A", is_resistance=True, disease="CRC"),
                VICCEvidence(drugs=["Cetuximab"], evidence_level="B", is_resistance=True, disease="CRC"),
            ]
        )

        aggregated = evidence.aggregate_evidence_by_drug()

        assert len(aggregated) == 1
        drug = aggregated[0]
        assert drug['drug'].lower() == 'cetuximab'
        assert drug['sensitivity_count'] == 0
        assert drug['resistance_count'] == 2
        assert drug['net_signal'] == 'RESISTANT'

    def test_aggregate_drug_mixed_with_clear_winner(self):
        """Aggregate drug with mixed signals but clear sensitivity winner (3:1)."""
        evidence = Evidence(
            variant_id="EGFR:S768I",
            gene="EGFR",
            variant="S768I",
            vicc=[
                VICCEvidence(drugs=["Erlotinib"], evidence_level="B", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Erlotinib"], evidence_level="C", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Erlotinib"], evidence_level="C", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Erlotinib"], evidence_level="C", is_resistance=True, disease="NSCLC"),
            ]
        )

        aggregated = evidence.aggregate_evidence_by_drug()

        assert len(aggregated) == 1
        drug = aggregated[0]
        assert drug['sensitivity_count'] == 3
        assert drug['resistance_count'] == 1
        assert drug['net_signal'] == 'SENSITIVE'  # 3:1 ratio -> SENSITIVE

    def test_aggregate_drug_truly_mixed(self):
        """Aggregate drug with truly mixed signals (no clear winner)."""
        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
            vicc=[
                VICCEvidence(drugs=["Vemurafenib"], evidence_level="A", is_sensitivity=True, disease="Melanoma"),
                VICCEvidence(drugs=["Vemurafenib"], evidence_level="A", is_sensitivity=True, disease="Melanoma"),
                VICCEvidence(drugs=["Vemurafenib"], evidence_level="B", is_resistance=True, disease="CRC"),
            ]
        )

        aggregated = evidence.aggregate_evidence_by_drug()

        assert len(aggregated) == 1
        drug = aggregated[0]
        assert drug['sensitivity_count'] == 2
        assert drug['resistance_count'] == 1
        assert drug['net_signal'] == 'MIXED'  # 2:1 ratio -> not 3:1, so MIXED

    def test_aggregate_multiple_drugs(self):
        """Aggregate evidence for multiple drugs."""
        evidence = Evidence(
            variant_id="EGFR:L858R",
            gene="EGFR",
            variant="L858R",
            vicc=[
                VICCEvidence(drugs=["Erlotinib"], evidence_level="A", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Gefitinib"], evidence_level="B", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Osimertinib"], evidence_level="A", is_sensitivity=True, disease="NSCLC"),
            ]
        )

        aggregated = evidence.aggregate_evidence_by_drug()

        assert len(aggregated) == 3
        # Should be sorted by best level (A > B)
        drug_names = [d['drug'].lower() for d in aggregated]
        # A-level drugs first
        assert aggregated[0]['best_level'] == 'A'
        assert aggregated[1]['best_level'] == 'A'
        assert aggregated[2]['best_level'] == 'B'

    def test_format_drug_aggregation_summary(self):
        """Test formatted drug aggregation summary for LLM."""
        evidence = Evidence(
            variant_id="EGFR:L858R",
            gene="EGFR",
            variant="L858R",
            vicc=[
                VICCEvidence(drugs=["Erlotinib"], evidence_level="A", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Erlotinib"], evidence_level="B", is_sensitivity=True, disease="NSCLC"),
                VICCEvidence(drugs=["Erlotinib"], evidence_level="C", is_resistance=True, disease="NSCLC"),
            ]
        )

        summary = evidence.format_drug_aggregation_summary()

        assert "DRUG-LEVEL SUMMARY" in summary
        assert "Erlotinib" in summary
        assert "2 sens" in summary
        assert "1 res" in summary
        assert "SENSITIVE" in summary or "MIXED" in summary  # 2:1 ratio

    def test_aggregate_empty_evidence(self):
        """Test aggregation with no drug evidence."""
        evidence = Evidence(
            variant_id="TEST:V123A",
            gene="TEST",
            variant="V123A",
            vicc=[]
        )

        aggregated = evidence.aggregate_evidence_by_drug()
        assert len(aggregated) == 0

        summary = evidence.format_drug_aggregation_summary()
        assert summary == ""  # No summary for empty evidence
