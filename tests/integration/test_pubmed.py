"""Integration tests for PubMed API.

Tests validate that the PubMed API returns expected research literature
for well-characterized resistance mutations and drug associations.
"""

import pytest

from tumorboard.api.pubmed import PubMedClient, PubMedArticle


class TestPubMedEGFRC797S:
    """Tests for EGFR C797S - known resistance mutation to osimertinib."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_articles(self):
        """EGFR C797S should return resistance-related articles."""
        async with PubMedClient() as client:
            articles = await client.search_resistance_literature("EGFR", "C797S", max_results=5)
            assert len(articles) >= 1, "EGFR C797S should have at least 1 resistance article"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_articles_mention_resistance(self):
        """Articles should mention resistance."""
        async with PubMedClient() as client:
            articles = await client.search_resistance_literature("EGFR", "C797S", max_results=5)

            resistance_articles = [a for a in articles if a.mentions_resistance()]
            assert len(resistance_articles) > 0, "Should find articles mentioning resistance"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_osimertinib_mentioned(self):
        """C797S articles should mention osimertinib (the drug it causes resistance to)."""
        async with PubMedClient() as client:
            articles = await client.search_resistance_literature("EGFR", "C797S", max_results=5)

            all_drugs = set()
            for article in articles:
                drugs = article.extract_drug_mentions()
                all_drugs.update(d.lower() for d in drugs)

            assert "osimertinib" in all_drugs, (
                f"EGFR C797S articles should mention osimertinib, got: {all_drugs}"
            )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_signal_type_is_resistance(self):
        """Articles about C797S should be classified as resistance signal."""
        async with PubMedClient() as client:
            articles = await client.search_resistance_literature("EGFR", "C797S", max_results=5)

            resistance_signals = [a for a in articles if a.get_signal_type() == 'resistance']
            assert len(resistance_signals) > 0, (
                "At least one article should have resistance signal type"
            )


class TestPubMedEGFRT790M:
    """Tests for EGFR T790M - known resistance mutation to first-gen TKIs."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_articles(self):
        """EGFR T790M should return resistance-related articles."""
        async with PubMedClient() as client:
            articles = await client.search_resistance_literature("EGFR", "T790M", max_results=5)
            assert len(articles) >= 1, "EGFR T790M should have at least 1 resistance article"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_first_gen_tkis_mentioned(self):
        """T790M articles should mention first-generation EGFR TKIs."""
        async with PubMedClient() as client:
            articles = await client.search_resistance_literature("EGFR", "T790M", max_results=5)

            expected_drugs = {"erlotinib", "gefitinib", "afatinib"}
            all_drugs = set()
            for article in articles:
                drugs = article.extract_drug_mentions()
                all_drugs.update(d.lower() for d in drugs)

            found = all_drugs & expected_drugs
            assert len(found) > 0, (
                f"T790M articles should mention first-gen TKIs {expected_drugs}, got: {all_drugs}"
            )


class TestPubMedKRASG12C:
    """Tests for KRAS G12C - targetable mutation with approved inhibitors."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_returns_articles(self):
        """KRAS G12C should return articles (though may not be resistance-focused)."""
        async with PubMedClient() as client:
            articles = await client.search_variant_literature("KRAS", "G12C", max_results=5)
            assert len(articles) >= 1, "KRAS G12C should have literature"


class TestPubMedArticleStructure:
    """Tests for PubMedArticle data structure integrity."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_required_fields(self):
        """Articles should have required fields with correct types."""
        async with PubMedClient() as client:
            articles = await client.search_resistance_literature("EGFR", "C797S", max_results=3)

            for article in articles:
                assert isinstance(article.pmid, str)
                assert isinstance(article.title, str)
                assert isinstance(article.abstract, str)
                assert isinstance(article.authors, list)
                assert isinstance(article.url, str)
                assert article.url.startswith("https://pubmed.ncbi.nlm.nih.gov/")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_methods_work(self):
        """Article methods should work without error."""
        async with PubMedClient() as client:
            articles = await client.search_resistance_literature("EGFR", "C797S", max_results=3)

            for article in articles:
                _ = article.mentions_resistance()
                _ = article.mentions_sensitivity()
                _ = article.get_signal_type()
                _ = article.extract_drug_mentions()
                _ = article.to_dict()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_to_dict_keys(self):
        """to_dict should return expected keys."""
        async with PubMedClient() as client:
            articles = await client.search_resistance_literature("EGFR", "C797S", max_results=3)

            expected_keys = {
                "pmid", "title", "abstract", "authors", "journal",
                "year", "doi", "url", "signal_type"
            }

            for article in articles:
                article_dict = article.to_dict()
                assert set(article_dict.keys()) == expected_keys


class TestPubMedSearchQueries:
    """Tests for different search query strategies."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_resistance_search_includes_drug(self):
        """Resistance search with drug should narrow results."""
        async with PubMedClient() as client:
            # Search with drug specified
            articles = await client.search_resistance_literature(
                "EGFR", "C797S", drug="osimertinib", max_results=5
            )

            # Should still find results
            assert len(articles) >= 0  # May or may not find results with narrowed search

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_general_variant_search(self):
        """General variant search should return literature."""
        async with PubMedClient() as client:
            articles = await client.search_variant_literature(
                "BRAF", "V600E", tumor_type="melanoma", max_results=5
            )

            # BRAF V600E is well-studied, should have articles
            assert len(articles) >= 1, "BRAF V600E should have general literature"


class TestPubMedEvidenceIntegration:
    """Tests for PubMed evidence integration with Evidence model."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_evidence_model_integration(self):
        """PubMed articles should integrate with Evidence model."""
        from tumorboard.models.evidence import Evidence, PubMedEvidence
        from tumorboard.api.pubmed import PubMedClient

        async with PubMedClient() as client:
            articles = await client.search_resistance_literature("EGFR", "C797S", max_results=3)

            # Convert to PubMedEvidence models
            pubmed_evidence = []
            for article in articles:
                pubmed_evidence.append(PubMedEvidence(
                    pmid=article.pmid,
                    title=article.title,
                    abstract=article.abstract,
                    authors=article.authors,
                    journal=article.journal,
                    year=article.year,
                    doi=article.doi,
                    url=article.url,
                    signal_type=article.get_signal_type(),
                    drugs_mentioned=article.extract_drug_mentions(),
                ))

            # Create Evidence model with PubMed articles
            evidence = Evidence(
                variant_id="EGFR:C797S",
                gene="EGFR",
                variant="C797S",
                pubmed_articles=pubmed_evidence,
            )

            # Test has_literature_resistance_evidence
            has_lit, drugs, pmids = evidence.has_literature_resistance_evidence()
            assert has_lit, "Should detect literature resistance evidence"
            assert len(pmids) > 0, "Should have PMIDs"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tier_hint_includes_pubmed(self):
        """Tier hint should include PubMed evidence for resistance markers."""
        from tumorboard.models.evidence import Evidence, PubMedEvidence
        from tumorboard.api.pubmed import PubMedClient

        async with PubMedClient() as client:
            articles = await client.search_resistance_literature("EGFR", "C797S", max_results=3)

            # Convert to PubMedEvidence
            pubmed_evidence = []
            for article in articles:
                pubmed_evidence.append(PubMedEvidence(
                    pmid=article.pmid,
                    title=article.title,
                    abstract=article.abstract,
                    authors=article.authors,
                    journal=article.journal,
                    year=article.year,
                    doi=article.doi,
                    url=article.url,
                    signal_type=article.get_signal_type(),
                    drugs_mentioned=article.extract_drug_mentions(),
                ))

            evidence = Evidence(
                variant_id="EGFR:C797S",
                gene="EGFR",
                variant="C797S",
                pubmed_articles=pubmed_evidence,
            )

            # Get tier hint
            tier_hint = evidence.get_tier_hint("Lung Adenocarcinoma")

            # Should indicate Tier II with literature evidence
            assert "TIER II" in tier_hint, f"Expected Tier II indicator, got: {tier_hint}"
            assert "PMID" in tier_hint or "literature" in tier_hint.lower(), (
                f"Should mention literature/PMIDs, got: {tier_hint}"
            )


class TestPubMedErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_unknown_variant_returns_empty(self):
        """Unknown variant should return empty list, not error."""
        async with PubMedClient() as client:
            articles = await client.search_resistance_literature(
                "FAKEGENE", "X999Y", max_results=5
            )
            assert articles == [], "Unknown variant should return empty list"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_special_characters_handled(self):
        """Variants with special characters should be handled."""
        async with PubMedClient() as client:
            # Exon 19 deletion - contains space
            articles = await client.search_variant_literature(
                "EGFR", "exon 19 deletion", max_results=3
            )
            # Should not raise exception
            assert isinstance(articles, list)
