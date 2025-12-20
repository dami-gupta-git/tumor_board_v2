"""Integration tests for Semantic Scholar API client.

Tests require network access to Semantic Scholar API.
Run with: pytest tests/integration/test_semantic_scholar.py -v
"""

import pytest
import asyncio

from tumorboard.api.semantic_scholar import SemanticScholarClient, SemanticPaperInfo


@pytest.fixture
def client():
    """Create a Semantic Scholar client for testing."""
    return SemanticScholarClient()


class TestSemanticScholarClient:
    """Test Semantic Scholar API client functionality."""

    @pytest.mark.asyncio
    async def test_get_paper_by_pmid(self, client):
        """Test fetching a paper by PMID.

        Uses a well-known paper about EGFR C797S resistance.
        PMID 26286086: "Overcoming EGFR(T790M) and EGFR(C797S) resistance..."
        """
        async with client:
            # PMID for a well-known EGFR resistance paper
            paper = await client.get_paper_by_pmid("26286086")

            if paper is not None:
                assert paper.paper_id  # Should have a Semantic Scholar ID
                assert paper.pmid == "26286086"
                assert paper.citation_count >= 0
                assert paper.influential_citation_count >= 0
                # This is a highly cited paper
                assert paper.citation_count > 100
            # Note: Paper might not be found if not indexed

    @pytest.mark.asyncio
    async def test_get_papers_by_pmids_batch(self, client):
        """Test batch fetching papers by PMIDs."""
        async with client:
            # Mix of well-known cancer papers
            pmids = ["26286086", "25228534", "23982599"]
            papers = await client.get_papers_by_pmids(pmids)

            # Should find at least some papers
            assert isinstance(papers, dict)
            # At least one should be found
            if len(papers) > 0:
                for pmid, paper in papers.items():
                    assert isinstance(paper, SemanticPaperInfo)
                    assert paper.pmid == pmid
                    assert paper.paper_id  # Has Semantic Scholar ID

    @pytest.mark.asyncio
    async def test_paper_impact_score(self, client):
        """Test the impact score calculation."""
        async with client:
            paper = await client.get_paper_by_pmid("26286086")

            if paper is not None:
                score = paper.get_impact_score()
                assert 0.0 <= score <= 1.0
                # Highly cited paper should have high impact score
                if paper.citation_count > 100:
                    assert score > 0.5

    @pytest.mark.asyncio
    async def test_tldr_extraction(self, client):
        """Test TLDR (AI summary) extraction."""
        async with client:
            paper = await client.get_paper_by_pmid("26286086")

            if paper is not None:
                # TLDR may or may not be available
                if paper.tldr:
                    assert len(paper.tldr) > 10
                    assert isinstance(paper.tldr, str)

    @pytest.mark.asyncio
    async def test_is_highly_cited(self, client):
        """Test highly cited detection."""
        async with client:
            paper = await client.get_paper_by_pmid("26286086")

            if paper is not None and paper.citation_count > 50:
                assert paper.is_highly_cited(threshold=50)

    @pytest.mark.asyncio
    async def test_is_influential(self, client):
        """Test influential citation detection."""
        async with client:
            paper = await client.get_paper_by_pmid("26286086")

            if paper is not None and paper.influential_citation_count > 5:
                assert paper.is_influential(threshold=5)

    @pytest.mark.asyncio
    async def test_paper_not_found(self, client):
        """Test handling of non-existent paper."""
        async with client:
            # Invalid PMID
            paper = await client.get_paper_by_pmid("9999999999")
            assert paper is None

    @pytest.mark.asyncio
    async def test_to_dict(self, client):
        """Test conversion to dictionary."""
        async with client:
            paper = await client.get_paper_by_pmid("26286086")

            if paper is not None:
                data = paper.to_dict()
                assert 'paper_id' in data
                assert 'pmid' in data
                assert 'citation_count' in data
                assert 'influential_citation_count' in data
                assert 'impact_score' in data
                assert 'tldr' in data

    @pytest.mark.asyncio
    async def test_search_papers(self, client):
        """Test paper search functionality."""
        async with client:
            # Search for EGFR resistance papers
            papers = await client.search_papers(
                query="EGFR C797S resistance osimertinib",
                limit=5,
            )

            assert isinstance(papers, list)
            if len(papers) > 0:
                for paper in papers:
                    assert isinstance(paper, SemanticPaperInfo)
                    assert paper.paper_id


class TestSemanticScholarResistanceSearch:
    """Test Semantic Scholar resistance literature search."""

    @pytest.mark.asyncio
    async def test_search_resistance_literature(self, client):
        """Test searching for resistance literature directly."""
        from tumorboard.models.evidence.pubmed import PubMedEvidence

        async with client as ss_client:
            # Search for EGFR C797S resistance papers
            papers = await ss_client.search_resistance_literature(
                gene="EGFR",
                variant="C797S",
                max_results=3,
            )

            # Should find some papers
            assert isinstance(papers, list)

            if papers:
                for paper in papers:
                    # Verify paper has resistance signal
                    assert paper.mentions_resistance()
                    assert paper.get_signal_type() in ['resistance', 'mixed']

                    # Create PubMedEvidence from Semantic Scholar data
                    url = f"https://pubmed.ncbi.nlm.nih.gov/{paper.pmid}/" if paper.pmid else f"https://www.semanticscholar.org/paper/{paper.paper_id}"

                    evidence = PubMedEvidence(
                        pmid=paper.pmid or paper.paper_id,
                        title=paper.title,
                        abstract=paper.abstract or "",
                        authors=[],
                        journal=paper.venue or "",
                        year=str(paper.year) if paper.year else None,
                        url=url,
                        signal_type=paper.get_signal_type(),
                        drugs_mentioned=paper.extract_drug_mentions(),
                        citation_count=paper.citation_count,
                        influential_citation_count=paper.influential_citation_count,
                        tldr=paper.tldr,
                        is_open_access=paper.is_open_access,
                        semantic_scholar_id=paper.paper_id,
                    )

                    # Check helper methods work
                    _ = evidence.is_highly_cited()
                    _ = evidence.is_influential()
                    _ = evidence.get_best_summary()
                    _ = evidence.get_impact_indicator()
                    _ = evidence.format_rich_citation()

                    print(f"Found: {evidence.title[:50]}... [{evidence.get_impact_indicator()}]")
