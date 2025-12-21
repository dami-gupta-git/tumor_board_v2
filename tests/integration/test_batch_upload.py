"""Integration tests for batch variant upload/assessment functionality.

Tests validate the batch_assess_variants function used by the Streamlit app
for processing multiple variants from CSV uploads.
"""

import sys
from pathlib import Path

import pytest

# Add streamlit directory to path for backend imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "streamlit"))

from backend import batch_assess_variants


class TestBatchAssessVariants:
    """Tests for batch variant assessment functionality."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_single_variant_batch(self):
        """Single variant batch should return correct structure."""
        variants = [
            {"gene": "BRAF", "variant": "V600E", "tumor_type": "Melanoma"}
        ]

        results = await batch_assess_variants(
            variants, model="gpt-4o-mini", temperature=0.1
        )

        assert len(results) == 1
        result = results[0]

        # Check structure
        assert "variant" in result
        assert "assessment" in result
        assert "identifiers" in result
        assert "recommended_therapies" in result

        # Check variant info
        assert result["variant"]["gene"] == "BRAF"
        assert result["variant"]["variant"] == "V600E"
        assert result["variant"]["tumor_type"] == "Melanoma"

        # Check assessment
        assert "tier" in result["assessment"]
        assert "confidence" in result["assessment"]
        assert "rationale" in result["assessment"]

        # BRAF V600E in melanoma should be Tier I
        assert result["assessment"]["tier"] == "Tier I"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_multiple_variants_batch(self):
        """Multiple variants should all be processed."""
        variants = [
            {"gene": "BRAF", "variant": "V600E", "tumor_type": "Melanoma"},
            {"gene": "EGFR", "variant": "L858R", "tumor_type": "NSCLC"},
            {"gene": "KRAS", "variant": "G12C", "tumor_type": "Lung"},
        ]

        results = await batch_assess_variants(
            variants, model="gpt-4o-mini", temperature=0.1
        )

        assert len(results) == 3

        # All results should have proper structure
        for result in results:
            assert "variant" in result
            assert "assessment" in result or "error" in result

        # Check each variant was processed
        genes = [r["variant"]["gene"] for r in results]
        assert "BRAF" in genes
        assert "EGFR" in genes
        assert "KRAS" in genes

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_without_tumor_type(self):
        """Variants without tumor_type should still be processed."""
        variants = [
            {"gene": "BRAF", "variant": "V600E", "tumor_type": None},
            {"gene": "TP53", "variant": "R248W"},  # No tumor_type key at all
        ]

        results = await batch_assess_variants(
            variants, model="gpt-4o-mini", temperature=0.1
        )

        assert len(results) == 2

        for result in results:
            assert "variant" in result
            # Should still produce assessment even without tumor type
            assert "assessment" in result or "error" in result

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_progress_callback(self):
        """Progress callback should be called for each variant."""
        variants = [
            {"gene": "BRAF", "variant": "V600E", "tumor_type": "Melanoma"},
            {"gene": "EGFR", "variant": "L858R", "tumor_type": "NSCLC"},
        ]

        progress_calls = []

        def track_progress(current: int, total: int):
            progress_calls.append((current, total))

        results = await batch_assess_variants(
            variants,
            model="gpt-4o-mini",
            temperature=0.1,
            progress_callback=track_progress,
        )

        assert len(results) == 2
        assert len(progress_calls) == 2
        assert progress_calls[0] == (1, 2)
        assert progress_calls[1] == (2, 2)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_tier_assignments(self):
        """Batch should correctly assign tiers based on evidence."""
        variants = [
            # Tier I - FDA approved
            {"gene": "BRAF", "variant": "V600E", "tumor_type": "Melanoma"},
            # Tier III - VUS/uncertain
            {"gene": "TP53", "variant": "R248W", "tumor_type": "Breast"},
        ]

        results = await batch_assess_variants(
            variants, model="gpt-4o-mini", temperature=0.1
        )

        assert len(results) == 2

        # Find results by gene
        braf_result = next(r for r in results if r["variant"]["gene"] == "BRAF")
        tp53_result = next(r for r in results if r["variant"]["gene"] == "TP53")

        # BRAF V600E should be Tier I
        assert braf_result["assessment"]["tier"] == "Tier I"

        # TP53 R248W should be Tier III or IV (no approved therapies)
        assert tp53_result["assessment"]["tier"] in ["Tier III", "Tier IV"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_therapies_returned(self):
        """Batch results should include recommended therapies field."""
        variants = [
            {"gene": "BRAF", "variant": "V600E", "tumor_type": "Melanoma"},
        ]

        results = await batch_assess_variants(
            variants, model="gpt-4o-mini", temperature=0.1
        )

        result = results[0]
        assert "recommended_therapies" in result

        # Check therapy structure if any are returned
        therapies = result["recommended_therapies"]
        assert isinstance(therapies, list)

        # If therapies present, validate structure
        for therapy in therapies:
            assert "drug_name" in therapy
            assert "evidence_level" in therapy
            assert "approval_status" in therapy

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_identifiers_returned(self):
        """Batch results should include variant identifiers."""
        variants = [
            {"gene": "BRAF", "variant": "V600E", "tumor_type": "Melanoma"},
        ]

        results = await batch_assess_variants(
            variants, model="gpt-4o-mini", temperature=0.1
        )

        result = results[0]
        assert "identifiers" in result

        identifiers = result["identifiers"]
        assert "cosmic_id" in identifiers
        assert "ncbi_gene_id" in identifiers
        assert "dbsnp_id" in identifiers
        assert "clinvar_id" in identifiers

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_empty_batch(self):
        """Empty batch should return empty list."""
        variants = []

        results = await batch_assess_variants(
            variants, model="gpt-4o-mini", temperature=0.1
        )

        assert results == []


class TestBatchErrorHandling:
    """Tests for batch error handling."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_invalid_variant_handled_gracefully(self):
        """Invalid variants should not crash the batch."""
        variants = [
            {"gene": "BRAF", "variant": "V600E", "tumor_type": "Melanoma"},
            {"gene": "INVALID_GENE", "variant": "X999Y", "tumor_type": "Unknown"},
            {"gene": "EGFR", "variant": "L858R", "tumor_type": "NSCLC"},
        ]

        results = await batch_assess_variants(
            variants, model="gpt-4o-mini", temperature=0.1
        )

        # All three should be processed (even if one has error)
        assert len(results) == 3

        # Valid variants should succeed
        braf_result = next(r for r in results if r["variant"]["gene"] == "BRAF")
        assert "assessment" in braf_result

        egfr_result = next(r for r in results if r["variant"]["gene"] == "EGFR")
        assert "assessment" in egfr_result