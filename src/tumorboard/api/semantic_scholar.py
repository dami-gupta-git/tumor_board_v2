"""Semantic Scholar API client for enriching literature with semantic information.

ARCHITECTURE:
    PMID → Semantic Scholar API → Citation counts, influential citations, TLDR, embeddings

Enriches PubMed articles with:
- Citation counts and influential citation counts
- TLDR (AI-generated paper summaries)
- Fields of study classification
- Open access status and PDF links

Key Design:
- Async HTTP with connection pooling (httpx.AsyncClient)
- Rate limiting (1 RPS without API key, higher with key)
- Batch lookups to minimize API calls
- Graceful degradation if enrichment fails

API Documentation: https://www.semanticscholar.org/product/api
"""

from typing import Any
from dataclasses import dataclass, field
import asyncio

import httpx


class SemanticScholarError(Exception):
    """Exception raised for Semantic Scholar API errors."""
    pass


class SemanticScholarRateLimitError(SemanticScholarError):
    """Exception raised when Semantic Scholar rate limit (429) is hit."""
    pass


@dataclass
class SemanticPaperInfo:
    """Semantic Scholar paper information."""

    paper_id: str
    pmid: str | None
    title: str
    abstract: str | None
    citation_count: int
    influential_citation_count: int
    reference_count: int
    year: int | None
    venue: str | None
    is_open_access: bool
    open_access_pdf_url: str | None
    tldr: str | None
    fields_of_study: list[str] = field(default_factory=list)
    publication_types: list[str] = field(default_factory=list)

    def get_impact_score(self) -> float:
        """Calculate a simple impact score based on citations.

        Returns a score from 0-1 based on citation metrics.
        """
        if self.citation_count == 0:
            return 0.0

        # Influential citations are weighted more heavily
        base_score = min(self.citation_count / 100, 1.0)
        influential_boost = min(self.influential_citation_count / 20, 0.5)

        return min(base_score + influential_boost, 1.0)

    def is_highly_cited(self, threshold: int = 50) -> bool:
        """Check if paper is highly cited."""
        return self.citation_count >= threshold

    def is_influential(self, threshold: int = 5) -> bool:
        """Check if paper has influential citations."""
        return self.influential_citation_count >= threshold

    def mentions_resistance(self) -> bool:
        """Check if paper mentions resistance."""
        text = f"{self.title} {self.abstract or ''} {self.tldr or ''}".lower()
        resistance_terms = [
            'resistance', 'resistant', 'refractory',
            'acquired resistance', 'secondary resistance',
            'treatment failure', 'progression on',
        ]
        return any(term in text for term in resistance_terms)

    def mentions_sensitivity(self) -> bool:
        """Check if paper mentions sensitivity/response."""
        text = f"{self.title} {self.abstract or ''} {self.tldr or ''}".lower()
        sensitivity_terms = [
            'sensitivity', 'sensitive', 'response',
            'efficacy', 'effective', 'benefit',
        ]
        return any(term in text for term in sensitivity_terms)

    def get_signal_type(self) -> str:
        """Determine the primary signal from this paper.

        Papers about resistance mutations are classified as 'resistance'
        even if they discuss overcoming resistance.
        """
        text = f"{self.title} {self.abstract or ''} {self.tldr or ''}".lower()
        has_resistance = self.mentions_resistance()
        has_sensitivity = self.mentions_sensitivity()

        # Check for resistance-dominant patterns
        resistance_dominant_patterns = [
            'resistance mutation', 'resistance-conferring',
            'acquired resistance', 'causes resistance',
            'resistant mutation', 'mediates resistance',
            'confers resistance', 'osimertinib-resistant',
            'osimertinib resistance', 'third-generation',
            'overcome resistance', 'overcoming resistance',
        ]

        is_resistance_focused = any(p in text for p in resistance_dominant_patterns)

        if has_resistance and is_resistance_focused:
            return 'resistance'
        elif has_resistance and not has_sensitivity:
            return 'resistance'
        elif has_sensitivity and not has_resistance:
            return 'sensitivity'
        elif has_resistance and has_sensitivity:
            if 'resist' in self.title.lower():
                return 'resistance'
            return 'mixed'
        return 'unknown'

    def extract_drug_mentions(self, known_drugs: list[str] | None = None) -> list[str]:
        """Extract drug names mentioned in the paper."""
        text = f"{self.title} {self.abstract or ''} {self.tldr or ''}".lower()

        # Common targeted therapy drugs
        common_drugs = [
            'osimertinib', 'tagrisso', 'erlotinib', 'tarceva',
            'gefitinib', 'iressa', 'afatinib', 'gilotrif',
            'dacomitinib', 'vizimpro', 'lazertinib',
            'sotorasib', 'lumakras', 'adagrasib', 'krazati',
            'vemurafenib', 'zelboraf', 'dabrafenib', 'tafinlar',
            'trametinib', 'mekinist', 'encorafenib', 'braftovi',
            'imatinib', 'gleevec', 'sunitinib', 'sutent',
            'cetuximab', 'erbitux', 'panitumumab', 'vectibix',
            'crizotinib', 'xalkori', 'alectinib', 'alecensa',
            'brigatinib', 'alunbrig', 'lorlatinib', 'lorbrena',
        ]

        drugs_to_check = known_drugs or common_drugs
        found = []
        for drug in drugs_to_check:
            if drug.lower() in text:
                found.append(drug)
        return list(set(found))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'paper_id': self.paper_id,
            'pmid': self.pmid,
            'title': self.title,
            'citation_count': self.citation_count,
            'influential_citation_count': self.influential_citation_count,
            'reference_count': self.reference_count,
            'year': self.year,
            'venue': self.venue,
            'is_open_access': self.is_open_access,
            'tldr': self.tldr,
            'fields_of_study': self.fields_of_study,
            'impact_score': self.get_impact_score(),
            'signal_type': self.get_signal_type(),
        }


class SemanticScholarClient:
    """Client for Semantic Scholar Academic Graph API.

    Enriches PubMed articles with citation metrics, TLDR summaries,
    and other semantic information.

    API Documentation: https://www.semanticscholar.org/product/api
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    DEFAULT_TIMEOUT = 30.0
    # Rate limit: 1 RPS without API key
    RATE_LIMIT_DELAY = 1.1

    # Fields to request from the API
    PAPER_FIELDS = [
        "paperId",
        "externalIds",
        "title",
        "abstract",
        "year",
        "venue",
        "citationCount",
        "influentialCitationCount",
        "referenceCount",
        "isOpenAccess",
        "openAccessPdf",
        "tldr",
        "s2FieldsOfStudy",
        "publicationTypes",
    ]

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, api_key: str | None = None):
        """Initialize the Semantic Scholar client.

        Args:
            timeout: Request timeout in seconds
            api_key: Optional API key for higher rate limits
        """
        self.timeout = timeout
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None
        self._last_request_time: float = 0

    async def __aenter__(self) -> "SemanticScholarClient":
        """Async context manager entry."""
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        self._client = httpx.AsyncClient(timeout=self.timeout, headers=headers)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["x-api-key"] = self.api_key
            self._client = httpx.AsyncClient(timeout=self.timeout, headers=headers)
        return self._client

    async def _rate_limit(self) -> None:
        """Enforce rate limiting to respect API limits."""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            await asyncio.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    async def get_paper_by_pmid(self, pmid: str) -> SemanticPaperInfo | None:
        """Get paper information by PubMed ID.

        Args:
            pmid: PubMed ID (without "PMID:" prefix)

        Returns:
            SemanticPaperInfo or None if not found
        """
        client = self._get_client()

        # Semantic Scholar uses PMID:12345 format
        paper_id = f"PMID:{pmid}"
        url = f"{self.BASE_URL}/paper/{paper_id}"

        params = {
            "fields": ",".join(self.PAPER_FIELDS),
        }

        try:
            await self._rate_limit()
            response = await client.get(url, params=params)

            if response.status_code == 404:
                # Paper not found in Semantic Scholar
                return None

            response.raise_for_status()
            data = response.json()

            return self._parse_paper(data, pmid)

        except httpx.HTTPStatusError:
            return None
        except httpx.HTTPError:
            return None
        except Exception:
            return None

    async def get_papers_by_pmids(self, pmids: list[str]) -> dict[str, SemanticPaperInfo]:
        """Get paper information for multiple PMIDs.

        Uses batch endpoint for efficiency when available, falls back to
        individual requests.

        Args:
            pmids: List of PubMed IDs

        Returns:
            Dictionary mapping PMID to SemanticPaperInfo
        """
        if not pmids:
            return {}

        # Use batch endpoint for efficiency
        client = self._get_client()
        url = f"{self.BASE_URL}/paper/batch"

        # Semantic Scholar batch API accepts paper IDs
        paper_ids = [f"PMID:{pmid}" for pmid in pmids]

        params = {
            "fields": ",".join(self.PAPER_FIELDS),
        }

        try:
            await self._rate_limit()
            response = await client.post(
                url,
                params=params,
                json={"ids": paper_ids},
            )

            if response.status_code == 404:
                # Batch endpoint not found, fall back to individual requests
                return await self._get_papers_individually(pmids)

            response.raise_for_status()
            data = response.json()

            results = {}
            for i, paper_data in enumerate(data):
                if paper_data is not None:
                    pmid = pmids[i]
                    paper_info = self._parse_paper(paper_data, pmid)
                    if paper_info:
                        results[pmid] = paper_info

            return results

        except httpx.HTTPError:
            # Fall back to individual requests
            return await self._get_papers_individually(pmids)

    async def _get_papers_individually(self, pmids: list[str]) -> dict[str, SemanticPaperInfo]:
        """Fall back to individual paper lookups."""
        results = {}
        for pmid in pmids:
            paper_info = await self.get_paper_by_pmid(pmid)
            if paper_info:
                results[pmid] = paper_info
        return results

    def _parse_paper(self, data: dict[str, Any], pmid: str) -> SemanticPaperInfo | None:
        """Parse API response into SemanticPaperInfo."""
        try:
            # Extract TLDR if available
            tldr = None
            tldr_data = data.get("tldr")
            if tldr_data and isinstance(tldr_data, dict):
                tldr = tldr_data.get("text")

            # Extract open access PDF URL
            open_access_pdf_url = None
            oa_data = data.get("openAccessPdf")
            if oa_data and isinstance(oa_data, dict):
                open_access_pdf_url = oa_data.get("url")

            # Extract fields of study
            fields_of_study = []
            s2_fields = data.get("s2FieldsOfStudy", [])
            if s2_fields:
                for f in s2_fields:
                    if isinstance(f, dict) and f.get("category"):
                        fields_of_study.append(f["category"])

            return SemanticPaperInfo(
                paper_id=data.get("paperId", ""),
                pmid=pmid,
                title=data.get("title", ""),
                abstract=data.get("abstract"),
                citation_count=data.get("citationCount", 0) or 0,
                influential_citation_count=data.get("influentialCitationCount", 0) or 0,
                reference_count=data.get("referenceCount", 0) or 0,
                year=data.get("year"),
                venue=data.get("venue"),
                is_open_access=data.get("isOpenAccess", False) or False,
                open_access_pdf_url=open_access_pdf_url,
                tldr=tldr,
                fields_of_study=fields_of_study,
                publication_types=data.get("publicationTypes", []) or [],
            )

        except Exception:
            return None

    async def search_papers(
        self,
        query: str,
        year_range: tuple[int, int] | None = None,
        min_citations: int | None = None,
        limit: int = 10,
    ) -> list[SemanticPaperInfo]:
        """Search for papers using Semantic Scholar's relevance search.

        Args:
            query: Search query (e.g., "EGFR C797S resistance osimertinib")
            year_range: Optional (start_year, end_year) filter
            min_citations: Minimum citation count filter
            limit: Maximum number of results

        Returns:
            List of SemanticPaperInfo objects
        """
        client = self._get_client()
        url = f"{self.BASE_URL}/paper/search"

        params: dict[str, Any] = {
            "query": query,
            "fields": ",".join(self.PAPER_FIELDS),
            "limit": limit,
        }

        if year_range:
            params["year"] = f"{year_range[0]}-{year_range[1]}"

        if min_citations:
            params["minCitationCount"] = min_citations

        try:
            await self._rate_limit()
            response = await client.get(url, params=params)

            # Check for rate limit before raising for other errors
            if response.status_code == 429:
                raise SemanticScholarRateLimitError("Semantic Scholar rate limit exceeded")

            response.raise_for_status()
            data = response.json()

            papers = []
            for paper_data in data.get("data", []):
                # Extract PMID from externalIds if available
                pmid = None
                external_ids = paper_data.get("externalIds", {})
                if external_ids:
                    pmid = external_ids.get("PubMed")

                paper_info = self._parse_paper(paper_data, pmid or "")
                if paper_info:
                    papers.append(paper_info)

            return papers

        except SemanticScholarRateLimitError:
            # Re-raise rate limit errors for caller to handle
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise SemanticScholarRateLimitError("Semantic Scholar rate limit exceeded")
            return []
        except httpx.HTTPError:
            return []

    async def search_resistance_literature(
        self,
        gene: str,
        variant: str,
        drug: str | None = None,
        tumor_type: str | None = None,
        max_results: int = 5,
    ) -> list[SemanticPaperInfo]:
        """Search for resistance-related literature for a variant.

        This is the primary method for finding evidence that a variant
        causes resistance to a therapy.

        Args:
            gene: Gene symbol (e.g., "EGFR")
            variant: Variant notation (e.g., "C797S")
            drug: Optional specific drug to search for
            tumor_type: Optional tumor type for more specific search (e.g., "GIST")
            max_results: Maximum number of articles to return

        Returns:
            List of SemanticPaperInfo objects discussing resistance
        """
        # Build query for resistance literature
        query_parts = [gene, variant, "resistance"]

        # Use tumor type if provided, otherwise fall back to generic "cancer"
        if tumor_type:
            # Simplify tumor type for search (e.g., "Gastrointestinal Stromal Tumor" -> "GIST" or "gastrointestinal stromal")
            tumor_lower = tumor_type.lower()
            if "gastrointestinal stromal" in tumor_lower or tumor_lower == "gist":
                query_parts.append("GIST")
            else:
                tumor_simple = tumor_lower.replace('adenocarcinoma', '').replace('carcinoma', '').strip()
                if tumor_simple:
                    query_parts.append(tumor_simple)
                else:
                    query_parts.append("cancer")
        else:
            query_parts.append("cancer")

        if drug:
            query_parts.append(drug)

        query = " ".join(query_parts)

        # Fetch more results to filter for resistance
        papers = await self.search_papers(
            query=query,
            limit=max_results * 2,
        )

        if not papers:
            return []

        # Filter to papers that actually mention resistance
        resistance_papers = [p for p in papers if p.mentions_resistance()]

        return resistance_papers[:max_results]

    async def search_variant_literature(
        self,
        gene: str,
        variant: str,
        tumor_type: str | None = None,
        max_results: int = 5,
    ) -> list[SemanticPaperInfo]:
        """Search for general literature about a variant.

        Args:
            gene: Gene symbol
            variant: Variant notation
            tumor_type: Optional tumor type filter
            max_results: Maximum results

        Returns:
            List of SemanticPaperInfo objects
        """
        query_parts = [gene, variant]
        if tumor_type:
            # Simplify tumor type for search
            tumor_simple = tumor_type.lower().replace('adenocarcinoma', '').replace('carcinoma', '').strip()
            if tumor_simple:
                query_parts.append(tumor_simple)

        query = " ".join(query_parts)

        return await self.search_papers(
            query=query,
            limit=max_results,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
