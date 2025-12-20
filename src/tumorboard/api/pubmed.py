"""PubMed API client for fetching research literature.

ARCHITECTURE:
    Gene + Variant + "resistance" → NCBI E-utilities → PubMed abstracts

Fetches relevant research papers to support tier classification,
especially for resistance mutations that may not be in curated databases.

Key Design:
- Async HTTP with connection pooling (httpx.AsyncClient)
- Uses NCBI E-utilities (ESearch + EFetch)
- Searches for resistance/sensitivity patterns
- Returns structured article information with abstracts
- Rate limiting to respect NCBI's 3 requests/second limit
"""

from typing import Any
from dataclasses import dataclass
import asyncio
import xml.etree.ElementTree as ET

import httpx


class PubMedError(Exception):
    """Exception raised for PubMed API errors."""
    pass


class PubMedRateLimitError(PubMedError):
    """Exception raised when PubMed rate limit (429) is hit."""
    pass


@dataclass
class PubMedArticle:
    """A research article from PubMed."""

    pmid: str
    title: str
    abstract: str
    authors: list[str]
    journal: str
    year: str | None
    doi: str | None
    keywords: list[str]
    url: str

    def mentions_resistance(self) -> bool:
        """Check if article mentions resistance."""
        text = f"{self.title} {self.abstract}".lower()
        resistance_terms = [
            'resistance', 'resistant', 'refractory',
            'acquired resistance', 'secondary resistance',
            'treatment failure', 'progression on',
        ]
        return any(term in text for term in resistance_terms)

    def mentions_sensitivity(self) -> bool:
        """Check if article mentions sensitivity/response."""
        text = f"{self.title} {self.abstract}".lower()
        sensitivity_terms = [
            'sensitivity', 'sensitive', 'response',
            'efficacy', 'effective', 'benefit',
        ]
        return any(term in text for term in sensitivity_terms)

    def get_signal_type(self) -> str:
        """Determine the primary signal from this article.

        Articles about resistance mutations (like C797S causing resistance to osimertinib)
        are classified as 'resistance' even if they discuss overcoming resistance,
        since the primary clinical relevance is that the mutation causes resistance.
        """
        text = f"{self.title} {self.abstract}".lower()
        has_resistance = self.mentions_resistance()
        has_sensitivity = self.mentions_sensitivity()

        # Check for resistance-dominant patterns
        resistance_dominant_patterns = [
            'resistance mutation', 'resistance-conferring',
            'acquired resistance', 'causes resistance',
            'resistant mutation', 'mediates resistance',
            'confers resistance', 'osimertinib-resistant',
            'osimertinib resistance', 'third-generation',
            'overcome resistance', 'overcoming resistance',  # Still about resistance
        ]

        is_resistance_focused = any(p in text for p in resistance_dominant_patterns)

        if has_resistance and is_resistance_focused:
            return 'resistance'
        elif has_resistance and not has_sensitivity:
            return 'resistance'
        elif has_sensitivity and not has_resistance:
            return 'sensitivity'
        elif has_resistance and has_sensitivity:
            # Even if mixed, if resistance is in the title, prioritize it
            if 'resist' in self.title.lower():
                return 'resistance'
            return 'mixed'
        return 'unknown'

    def extract_drug_mentions(self, known_drugs: list[str] | None = None) -> list[str]:
        """Extract drug names mentioned in the article."""
        text = f"{self.title} {self.abstract}".lower()

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
            'pmid': self.pmid,
            'title': self.title,
            'abstract': self.abstract[:500] if self.abstract else None,
            'authors': self.authors[:3],
            'journal': self.journal,
            'year': self.year,
            'doi': self.doi,
            'url': self.url,
            'signal_type': self.get_signal_type(),
        }


class PubMedClient:
    """Client for NCBI PubMed E-utilities API.

    Uses ESearch to find articles and EFetch to retrieve abstracts.
    Free to use without API key (limited to 3 requests/second).

    API Documentation: https://www.ncbi.nlm.nih.gov/books/NBK25501/
    """

    ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_MAX_RESULTS = 5
    # NCBI rate limit: 3 requests/second without API key, 10/second with key
    RATE_LIMIT_DELAY = 0.35  # ~3 requests/second

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, api_key: str | None = None):
        """Initialize the PubMed client.

        Args:
            timeout: Request timeout in seconds
            api_key: Optional NCBI API key for higher rate limits
        """
        self.timeout = timeout
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None
        self._last_request_time: float = 0

    async def __aenter__(self) -> "PubMedClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def _rate_limit(self) -> None:
        """Enforce rate limiting to respect NCBI's API limits."""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            await asyncio.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _build_resistance_query(
        self,
        gene: str,
        variant: str,
        drug: str | None = None,
        tumor_type: str | None = None,
    ) -> str:
        """Build a PubMed search query for resistance information.

        Args:
            gene: Gene symbol (e.g., "EGFR")
            variant: Variant notation (e.g., "C797S")
            drug: Optional specific drug to search for
            tumor_type: Optional tumor type for more specific search (e.g., "GIST")

        Returns:
            PubMed search query string
        """
        # Core query: gene + variant + resistance
        query_parts = [
            f'"{gene}"[Title/Abstract]',
            f'("{variant}"[Title/Abstract] OR "{gene} {variant}"[Title/Abstract])',
            '(resistance[Title/Abstract] OR resistant[Title/Abstract] OR refractory[Title/Abstract])',
        ]

        if drug:
            query_parts.append(f'"{drug}"[Title/Abstract]')

        # Add tumor type filter if provided, otherwise use generic cancer filter
        if tumor_type:
            tumor_lower = tumor_type.lower()
            if "gastrointestinal stromal" in tumor_lower or tumor_lower == "gist":
                query_parts.append('(GIST[Title/Abstract] OR "gastrointestinal stromal"[Title/Abstract])')
            else:
                tumor_simple = tumor_lower.replace('adenocarcinoma', '').replace('carcinoma', '').strip()
                if tumor_simple:
                    query_parts.append(f'"{tumor_simple}"[Title/Abstract]')
                else:
                    query_parts.append('(cancer[Title/Abstract] OR tumor[Title/Abstract] OR neoplasm[Title/Abstract] OR oncology[Title/Abstract])')
        else:
            query_parts.append('(cancer[Title/Abstract] OR tumor[Title/Abstract] OR neoplasm[Title/Abstract] OR oncology[Title/Abstract])')

        return ' AND '.join(query_parts)

    def _build_general_query(
        self,
        gene: str,
        variant: str,
        tumor_type: str | None = None,
    ) -> str:
        """Build a general PubMed search query for a variant.

        Args:
            gene: Gene symbol (e.g., "EGFR")
            variant: Variant notation (e.g., "C797S")
            tumor_type: Optional tumor type

        Returns:
            PubMed search query string
        """
        query_parts = [
            f'"{gene}"[Title/Abstract]',
            f'("{variant}"[Title/Abstract] OR "{gene} {variant}"[Title/Abstract])',
        ]

        if tumor_type:
            # Simplify tumor type for search
            tumor_simple = tumor_type.lower().replace('adenocarcinoma', '').replace('carcinoma', '').strip()
            query_parts.append(f'"{tumor_simple}"[Title/Abstract]')

        return ' AND '.join(query_parts)

    async def _search_pmids(self, query: str, max_results: int = 10) -> list[str]:
        """Search PubMed and return PMIDs.

        Args:
            query: PubMed search query
            max_results: Maximum number of results

        Returns:
            List of PMIDs
        """
        client = self._get_client()

        params: dict[str, Any] = {
            'db': 'pubmed',
            'term': query,
            'retmax': max_results,
            'retmode': 'json',
            'sort': 'relevance',
        }

        if self.api_key:
            params['api_key'] = self.api_key

        try:
            await self._rate_limit()
            response = await client.get(self.ESEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()

            result = data.get('esearchresult', {})
            pmids = result.get('idlist', [])
            return pmids

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise PubMedRateLimitError("PubMed rate limit exceeded")
            return []
        except httpx.HTTPError:
            return []
        except Exception:
            return []

    async def _fetch_articles(self, pmids: list[str]) -> list[PubMedArticle]:
        """Fetch article details for given PMIDs.

        Args:
            pmids: List of PubMed IDs

        Returns:
            List of PubMedArticle objects
        """
        if not pmids:
            return []

        client = self._get_client()

        params: dict[str, Any] = {
            'db': 'pubmed',
            'id': ','.join(pmids),
            'rettype': 'abstract',
            'retmode': 'xml',
        }

        if self.api_key:
            params['api_key'] = self.api_key

        try:
            await self._rate_limit()
            response = await client.get(self.EFETCH_URL, params=params)
            response.raise_for_status()

            # Parse XML response
            root = ET.fromstring(response.text)
            articles = []

            for article_elem in root.findall('.//PubmedArticle'):
                article = self._parse_article(article_elem)
                if article:
                    articles.append(article)

            return articles

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise PubMedRateLimitError("PubMed rate limit exceeded")
            return []
        except httpx.HTTPError:
            return []
        except ET.ParseError:
            return []
        except Exception:
            return []

    def _parse_article(self, article_elem: ET.Element) -> PubMedArticle | None:
        """Parse a PubmedArticle XML element.

        Args:
            article_elem: XML element for PubmedArticle

        Returns:
            PubMedArticle object or None if parsing fails
        """
        try:
            # Get PMID
            pmid_elem = article_elem.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else ''

            if not pmid:
                return None

            # Get article info
            medline = article_elem.find('.//MedlineCitation')
            if medline is None:
                return None

            article = medline.find('.//Article')
            if article is None:
                return None

            # Title
            title_elem = article.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else ''

            # Abstract
            abstract_parts = []
            abstract_elem = article.find('.//Abstract')
            if abstract_elem is not None:
                for text_elem in abstract_elem.findall('.//AbstractText'):
                    if text_elem.text:
                        label = text_elem.get('Label', '')
                        if label:
                            abstract_parts.append(f"{label}: {text_elem.text}")
                        else:
                            abstract_parts.append(text_elem.text)
            abstract = ' '.join(abstract_parts)

            # Authors
            authors = []
            author_list = article.find('.//AuthorList')
            if author_list is not None:
                for author_elem in author_list.findall('.//Author'):
                    last_name = author_elem.find('.//LastName')
                    initials = author_elem.find('.//Initials')
                    if last_name is not None and last_name.text:
                        author_str = last_name.text
                        if initials is not None and initials.text:
                            author_str += f" {initials.text}"
                        authors.append(author_str)

            # Journal
            journal_elem = article.find('.//Journal/Title')
            journal = journal_elem.text if journal_elem is not None else ''

            # Year
            year = None
            pub_date = article.find('.//Journal/JournalIssue/PubDate')
            if pub_date is not None:
                year_elem = pub_date.find('.//Year')
                if year_elem is not None:
                    year = year_elem.text

            # DOI
            doi = None
            for id_elem in article_elem.findall('.//ArticleIdList/ArticleId'):
                if id_elem.get('IdType') == 'doi':
                    doi = id_elem.text
                    break

            # Keywords
            keywords = []
            keyword_list = medline.find('.//KeywordList')
            if keyword_list is not None:
                for kw_elem in keyword_list.findall('.//Keyword'):
                    if kw_elem.text:
                        keywords.append(kw_elem.text)

            # MeSH terms as additional keywords
            mesh_list = medline.find('.//MeshHeadingList')
            if mesh_list is not None:
                for mesh_elem in mesh_list.findall('.//MeshHeading/DescriptorName'):
                    if mesh_elem.text:
                        keywords.append(mesh_elem.text)

            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            return PubMedArticle(
                pmid=pmid,
                title=title,
                abstract=abstract,
                authors=authors,
                journal=journal,
                year=year,
                doi=doi,
                keywords=keywords,
                url=url,
            )

        except Exception:
            return None

    async def search_resistance_literature(
        self,
        gene: str,
        variant: str,
        drug: str | None = None,
        tumor_type: str | None = None,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> list[PubMedArticle]:
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
            List of PubMedArticle objects discussing resistance
        """
        query = self._build_resistance_query(gene, variant, drug, tumor_type)
        pmids = await self._search_pmids(query, max_results * 2)  # Fetch extra for filtering

        if not pmids:
            return []

        articles = await self._fetch_articles(pmids)

        # Filter to articles that actually mention resistance
        resistance_articles = [a for a in articles if a.mentions_resistance()]

        return resistance_articles[:max_results]

    async def search_variant_literature(
        self,
        gene: str,
        variant: str,
        tumor_type: str | None = None,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> list[PubMedArticle]:
        """Search for general literature about a variant.

        Args:
            gene: Gene symbol
            variant: Variant notation
            tumor_type: Optional tumor type filter
            max_results: Maximum results

        Returns:
            List of PubMedArticle objects
        """
        query = self._build_general_query(gene, variant, tumor_type)
        pmids = await self._search_pmids(query, max_results)

        if not pmids:
            return []

        return await self._fetch_articles(pmids)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
