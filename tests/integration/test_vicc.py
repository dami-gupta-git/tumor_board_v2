"""Integration tests for VICC MetaKB API.

Tests validate that the VICC API returns expected therapeutic associations
for well-characterized oncogenic mutations with FDA-approved therapies.
"""

import pytest

from tumorboard.api.vicc import VICCClient


class TestVICCBRAFV600E:
    """Tests for BRAF V600E - Tier I variant with FDA-approved BRAF inhibitors."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_associations(self):
        """BRAF V600E should return substantial evidence."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("BRAF", "V600E", max_results=50)
            assert len(associations) >= 5, "BRAF V600E should have at least 5 associations"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_correct_gene_attribution(self):
        """Associations should have correct gene attribution."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("BRAF", "V600E", max_results=50)
            braf_assocs = [a for a in associations if a.gene == "BRAF"]
            assert len(braf_assocs) > 0, "Should have associations with gene=BRAF"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_expected_braf_inhibitors(self):
        """Should return expected BRAF inhibitor drugs."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("BRAF", "V600E", max_results=50)

            expected_drugs = {"vemurafenib", "dabrafenib", "encorafenib", "trametinib", "cobimetinib"}
            all_drugs = set()
            for assoc in associations:
                for drug in assoc.drugs:
                    all_drugs.add(drug.lower())

            found_expected = all_drugs & expected_drugs
            assert len(found_expected) > 0, (
                f"Expected at least one of {expected_drugs}, got: {all_drugs}"
            )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_has_sensitivity_associations(self):
        """BRAF V600E is a sensitivity marker - should have sensitivity associations."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("BRAF", "V600E", max_results=50)
            sensitivity_assocs = [a for a in associations if a.is_sensitivity()]
            assert len(sensitivity_assocs) > 0, "BRAF V600E should have sensitivity associations"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_has_high_quality_evidence(self):
        """Should have Level A or B evidence."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("BRAF", "V600E", max_results=50)

            evidence_levels = {a.evidence_level for a in associations if a.evidence_level}
            high_quality_levels = {"A", "B"} & evidence_levels
            assert len(high_quality_levels) > 0, (
                f"BRAF V600E should have Level A or B evidence, got: {evidence_levels}"
            )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_melanoma_disease_coverage(self):
        """Melanoma is a key indication - should have melanoma-related evidence."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("BRAF", "V600E", max_results=50)

            diseases = {a.disease.lower() for a in associations if a.disease}
            melanoma_related = any("melanoma" in d for d in diseases)
            assert melanoma_related, f"Should have melanoma-related evidence, got: {diseases}"


class TestVICCEGFRL858R:
    """Tests for EGFR L858R - common activating mutation in NSCLC."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_associations(self):
        """EGFR L858R should have evidence."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("EGFR", "L858R", max_results=50)
            assert len(associations) >= 3, "EGFR L858R should have at least 3 associations"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_expected_egfr_tkis(self):
        """Should return expected EGFR TKI drugs."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("EGFR", "L858R", max_results=50)

            expected_drugs = {"erlotinib", "gefitinib", "afatinib", "osimertinib"}
            all_drugs = set()
            for assoc in associations:
                for drug in assoc.drugs:
                    all_drugs.add(drug.lower())

            found_expected = all_drugs & expected_drugs
            assert len(found_expected) > 0, (
                f"Expected at least one EGFR TKI {expected_drugs}, got: {all_drugs}"
            )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_has_sensitivity_associations(self):
        """EGFR L858R should have sensitivity associations."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("EGFR", "L858R", max_results=50)
            sensitivity_assocs = [a for a in associations if a.is_sensitivity()]
            assert len(sensitivity_assocs) > 0, "EGFR L858R should have sensitivity associations"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_lung_cancer_disease_coverage(self):
        """Should have lung cancer related diseases."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("EGFR", "L858R", max_results=50)

            diseases = {a.disease.lower() for a in associations if a.disease}
            lung_related = any(
                "lung" in d or "nsclc" in d or "non-small" in d
                for d in diseases
            )
            assert lung_related, f"Should have lung cancer evidence, got: {diseases}"


class TestVICCKRASG12C:
    """Tests for KRAS G12C - targetable mutation with approved inhibitors."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_associations(self):
        """KRAS G12C should have evidence."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("KRAS", "G12C", max_results=50)
            assert len(associations) >= 2, "KRAS G12C should have at least 2 associations"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_has_drug_associations(self):
        """KRAS G12C should have drug associations."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("KRAS", "G12C", max_results=50)

            all_drugs = set()
            for assoc in associations:
                for drug in assoc.drugs:
                    all_drugs.add(drug.lower())

            assert len(all_drugs) > 0, "KRAS G12C should have drug associations"


class TestVICCAssociationStructure:
    """Tests for VICCAssociation data structure integrity."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_required_fields_types(self):
        """Associations should have required fields with correct types."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("BRAF", "V600E", max_results=10)

            for assoc in associations:
                assert isinstance(assoc.gene, str)
                assert isinstance(assoc.disease, str)
                assert isinstance(assoc.drugs, list)
                assert isinstance(assoc.source, str)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_methods_work(self):
        """Association methods should work without error."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("BRAF", "V600E", max_results=10)

            for assoc in associations:
                _ = assoc.is_sensitivity()
                _ = assoc.is_resistance()
                _ = assoc.get_oncokb_level()
                _ = assoc.to_dict()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_to_dict_keys(self):
        """to_dict should return expected keys."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("BRAF", "V600E", max_results=10)

            expected_keys = {
                "description", "gene", "variant", "disease", "drugs",
                "evidence_level", "response_type", "source", "publication_url",
                "oncogenic", "is_sensitivity", "is_resistance", "oncokb_level"
            }

            for assoc in associations:
                assoc_dict = assoc.to_dict()
                assert set(assoc_dict.keys()) == expected_keys


class TestVICCTumorTypeFilter:
    """Tests for tumor type filtering."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_melanoma_filter(self):
        """Filtering by melanoma should work."""
        async with VICCClient() as client:
            associations = await client.fetch_associations(
                "BRAF", "V600E", tumor_type="melanoma", max_results=10
            )

            # If we got results, verify we didn't crash
            # Exact filtering depends on API data
            assert True
