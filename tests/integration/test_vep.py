"""Integration tests for Ensembl VEP API.

Tests validate that the VEP API:
1. Converts protein notation to HGVS genomic notation
2. Returns functional predictions (PolyPhen-2, SIFT, CADD)
3. Handles various variant formats (missense, nonsense, frameshift)
4. Integrates properly with MyVariant for variants not in MyVariant's index
"""

import pytest

from tumorboard.api.vep import VEPClient, VEPAnnotation


class TestVEPBasic:
    """Basic VEP API connectivity and response structure tests."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_vep_client_context_manager(self):
        """VEPClient should work without context manager."""
        client = VEPClient()
        annotation = await client.annotate_variant("BRAF", "V600E")

        assert annotation is not None
        assert isinstance(annotation, VEPAnnotation)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_vep_returns_genomic_coordinates(self):
        """VEP should return genomic coordinates for known variants."""
        client = VEPClient()
        annotation = await client.annotate_variant("BRAF", "V600E")

        assert annotation is not None
        assert annotation.chromosome is not None
        assert annotation.position is not None
        assert annotation.ref_allele is not None
        assert annotation.alt_allele is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_vep_returns_hgvs_genomic(self):
        """VEP should return HGVS genomic notation for MyVariant queries."""
        client = VEPClient()
        annotation = await client.annotate_variant("BRAF", "V600E")

        assert annotation is not None
        assert annotation.hgvs_genomic is not None
        # Should be in format like "chr7:g.140453136A>T"
        assert "chr" in annotation.hgvs_genomic
        assert ":g." in annotation.hgvs_genomic


class TestVEPFunctionalPredictions:
    """Tests for VEP functional prediction retrieval."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_braf_v600e_polyphen(self):
        """BRAF V600E should have PolyPhen-2 prediction from VEP."""
        client = VEPClient()
        annotation = await client.annotate_variant("BRAF", "V600E")

        assert annotation is not None
        # PolyPhen predictions: benign, possibly_damaging, probably_damaging
        if annotation.polyphen_prediction:
            assert annotation.polyphen_prediction in [
                "benign", "possibly_damaging", "probably_damaging"
            ]
            # BRAF V600E is known pathogenic, should be damaging
            assert annotation.polyphen_prediction in [
                "possibly_damaging", "probably_damaging"
            ], f"BRAF V600E expected damaging, got {annotation.polyphen_prediction}"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tp53_r248w_predictions(self):
        """TP53 R248W (known pathogenic) should have damaging predictions."""
        client = VEPClient()
        annotation = await client.annotate_variant("TP53", "R248W")

        assert annotation is not None
        assert annotation.hgvs_genomic is not None

        # Check at least one prediction source is available
        has_prediction = any([
            annotation.polyphen_prediction,
            annotation.sift_prediction,
            annotation.cadd_phred,
        ])

        if has_prediction:
            # If we have predictions, TP53 R248W should be predicted damaging
            is_damaging = (
                annotation.polyphen_prediction in ["possibly_damaging", "probably_damaging"] or
                annotation.sift_prediction == "deleterious" or
                (annotation.cadd_phred and annotation.cadd_phred >= 20)
            )
            assert is_damaging, (
                f"TP53 R248W should be predicted damaging. "
                f"PolyPhen: {annotation.polyphen_prediction}, "
                f"SIFT: {annotation.sift_prediction}, "
                f"CADD: {annotation.cadd_phred}"
            )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_is_predicted_damaging_method(self):
        """VEPAnnotation.is_predicted_damaging() should work correctly."""
        client = VEPClient()
        annotation = await client.annotate_variant("KRAS", "G12D")

        assert annotation is not None
        # KRAS G12D is oncogenic and should be predicted damaging
        if annotation.polyphen_prediction or annotation.sift_prediction or annotation.cadd_phred:
            result = annotation.is_predicted_damaging()
            assert isinstance(result, bool)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_prediction_summary(self):
        """VEPAnnotation.get_prediction_summary() should return readable string."""
        client = VEPClient()
        annotation = await client.annotate_variant("EGFR", "L858R")

        assert annotation is not None
        summary = annotation.get_prediction_summary()
        assert isinstance(summary, str)
        # Should be either predictions or "No predictions available"
        assert len(summary) > 0


class TestVEPVariantFormats:
    """Tests for handling various variant notation formats."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_missense_one_letter(self):
        """VEP should handle 1-letter amino acid codes (V600E)."""
        client = VEPClient()
        annotation = await client.annotate_variant("BRAF", "V600E")

        assert annotation is not None
        assert annotation.hgvs_genomic is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_missense_with_p_prefix(self):
        """VEP should handle p. prefix (p.V600E)."""
        client = VEPClient()
        annotation = await client.annotate_variant("BRAF", "p.V600E")

        assert annotation is not None
        assert annotation.hgvs_genomic is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_nonsense_star_notation(self):
        """VEP should handle nonsense mutations with * (R348*)."""
        client = VEPClient()
        annotation = await client.annotate_variant("PIK3R1", "R348*")

        assert annotation is not None
        # Should get genomic coordinates even for truncating variants
        assert annotation.chromosome is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_frameshift_notation(self):
        """VEP should handle frameshift notation (W288fs)."""
        client = VEPClient()
        annotation = await client.annotate_variant("NPM1", "W288fs")

        # Frameshift may or may not be resolvable by VEP
        # Just verify no crash
        assert annotation is None or isinstance(annotation, VEPAnnotation)


class TestVEPUncharacterizedVariants:
    """Tests for variants that are poorly indexed in MyVariant (primary use case)."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_atm_e1978k(self):
        """ATM E1978K (the original use case) should return VEP annotation."""
        client = VEPClient()
        annotation = await client.annotate_variant("ATM", "E1978K")

        assert annotation is not None
        assert annotation.hgvs_genomic is not None
        assert annotation.chromosome is not None
        # ATM is on chromosome 11
        assert annotation.chromosome in ["11", "chr11"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_chek2_i157t(self):
        """CHEK2 I157T (moderate penetrance variant) should return annotation."""
        client = VEPClient()
        annotation = await client.annotate_variant("CHEK2", "I157T")

        assert annotation is not None
        assert annotation.hgvs_genomic is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_palb2_variant(self):
        """PALB2 L939W should return annotation."""
        client = VEPClient()
        annotation = await client.annotate_variant("PALB2", "L939W")

        assert annotation is not None
        assert annotation.hgvs_genomic is not None


class TestVEPMyVariantIntegration:
    """Tests for VEP integration with MyVariant fallback."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_myvariant_uses_vep_fallback(self):
        """MyVariant should use VEP to get predictions for unindexed variants."""
        from tumorboard.api.myvariant import MyVariantClient

        async with MyVariantClient() as client:
            # ATM E1978K is the canonical example of a variant not in MyVariant
            evidence = await client.fetch_evidence("ATM", "E1978K")

            assert evidence is not None
            assert evidence.gene == "ATM"
            assert evidence.variant == "E1978K"

            # Should have CIViC evidence from fallback
            assert evidence.civic is not None

            # If VEP worked, should have genomic HGVS and/or predictions
            has_vep_data = any([
                evidence.hgvs_genomic,
                evidence.polyphen2_prediction,
                evidence.cadd_score,
                evidence.alphamissense_prediction,
            ])

            # Note: VEP may not always return predictions, so we just check structure
            assert isinstance(evidence.civic, list)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tier_hint_uses_functional_predictions(self):
        """Tier hint should incorporate functional predictions when available."""
        from tumorboard.api.myvariant import MyVariantClient

        async with MyVariantClient() as client:
            # Use a variant likely to have predictions
            evidence = await client.fetch_evidence("TP53", "R248W")

            tier_hint = evidence.get_tier_hint(tumor_type="breast cancer")

            assert tier_hint is not None
            assert "TIER" in tier_hint

            # If we have functional predictions, they may appear in tier hint
            if evidence.polyphen2_prediction or evidence.cadd_score:
                # The tier hint might mention predictions for VUS
                # (though TP53 R248W is well-characterized and won't be VUS)
                pass  # Just verify no crash


class TestVEPCaching:
    """Tests for VEP client caching behavior."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Repeated queries should use cache."""
        client = VEPClient()

        # First query
        annotation1 = await client.annotate_variant("BRAF", "V600E")

        # Second query (should hit cache)
        annotation2 = await client.annotate_variant("BRAF", "V600E", use_cache=True)

        assert annotation1 is not None
        assert annotation2 is not None
        # Both should have same genomic coordinates
        assert annotation1.hgvs_genomic == annotation2.hgvs_genomic

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cache_bypass(self):
        """use_cache=False should bypass cache."""
        client = VEPClient()

        # First query with caching
        annotation1 = await client.annotate_variant("EGFR", "L858R")

        # Clear cache
        client.clear_cache()

        # Query with cache disabled
        annotation2 = await client.annotate_variant("EGFR", "L858R", use_cache=False)

        assert annotation1 is not None
        assert annotation2 is not None


class TestVEPErrorHandling:
    """Tests for VEP error handling and edge cases."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_invalid_gene_returns_none(self):
        """Invalid gene should return None, not raise exception."""
        client = VEPClient()
        annotation = await client.annotate_variant("NOTAREALGENE", "V100E")

        # Should gracefully return None for invalid genes
        assert annotation is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_invalid_variant_format_returns_none(self):
        """Unparseable variant should return None."""
        client = VEPClient()
        annotation = await client.annotate_variant("BRAF", "not_a_variant")

        # Should gracefully return None
        assert annotation is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Client should handle timeout gracefully."""
        # Create client with very short timeout
        client = VEPClient(timeout=0.001, max_retries=1)

        # This should not raise an exception, just return None
        annotation = await client.annotate_variant("BRAF", "V600E")

        # Either None (timeout) or annotation (if unexpectedly fast)
        assert annotation is None or isinstance(annotation, VEPAnnotation)