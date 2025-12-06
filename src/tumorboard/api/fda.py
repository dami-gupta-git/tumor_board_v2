"""FDA OpenFDA API client for fetching drug approval data.

ARCHITECTURE:
    Gene + Variant → openFDA API → Drug Approvals (oncology indications)

Fetches FDA-approved drug information for cancer biomarkers.

Key Design:
- Async HTTP with connection pooling (httpx.AsyncClient)
- Retry with exponential backoff (tenacity)
- Structured parsing to typed FDAEvidence models
- Context manager for session cleanup
"""

import asyncio
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class FDAAPIError(Exception):
    """Exception raised for FDA API errors."""

    pass


class FDAClient:
    """Client for FDA openFDA API.

    openFDA provides access to FDA drug approval data including
    oncology drug approvals with companion diagnostics and biomarkers.

    Uses the /drug/label.json endpoint which contains full prescribing
    information with indication text mentioning biomarkers.
    """

    BASE_URL = "https://api.fda.gov/drug"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = 3,
    ) -> None:
        """Initialize the FDA client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "FDAClient":
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

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _query_drugsfda(self, search_query: str, limit: int = 10) -> dict[str, Any]:
        """Execute a query against FDA Drug Label API.

        Uses /drug/label.json endpoint which contains full prescribing information
        including indications_and_usage text that mentions biomarkers.

        Args:
            search_query: Search query string (e.g., "indications_and_usage:(BRAF AND V600E)")
            limit: Maximum number of results to return

        Returns:
            API response as dictionary

        Raises:
            FDAAPIError: If the API request fails
        """
        client = self._get_client()

        # Use drug label endpoint which has full indication text
        url = f"{self.BASE_URL}/label.json"
        params = {
            "search": search_query,
            "limit": limit
        }

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                raise FDAAPIError(f"API error: {data['error']}")

            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # No results found
                return {"results": []}
            raise FDAAPIError(f"HTTP error: {e}")

    # Gene aliases for FDA label search (FDA labels often use different nomenclature)
    GENE_ALIASES = {
        "ERBB2": ["HER2"],
        "HER2": ["ERBB2"],
        "EGFR": ["HER1"],
        "ERBB1": ["EGFR", "HER1"],
    }

    async def fetch_drug_approvals(
        self, gene: str, variant: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetch FDA drug approvals related to a gene and optional variant.

        Searches FDA Drugs@FDA database for oncology drugs approved with
        companion diagnostics or biomarker-based indications.

        Args:
            gene: Gene symbol (e.g., "BRAF", "EGFR")
            variant: Optional variant notation (e.g., "V600E", "L858R")

        Returns:
            List of drug approval records with indications and biomarkers
        """
        gene_upper = gene.upper()
        approvals = []
        seen_drugs = set()  # Track drugs to avoid duplicates

        # Get all gene names to search (primary + aliases)
        genes_to_search = [gene_upper]
        if gene_upper in self.GENE_ALIASES:
            genes_to_search.extend(self.GENE_ALIASES[gene_upper])

        try:
            # Clean variant notation
            variant_clean = None
            if variant:
                variant_clean = variant.strip().upper()
                # Remove common prefixes
                for prefix in ["P.", "C.", "G."]:
                    if variant_clean.startswith(prefix):
                        variant_clean = variant_clean[2:]

            # Strategy 1: Search for gene + variant in indication text (most specific)
            # Search with all gene aliases
            if variant_clean:
                for search_gene in genes_to_search:
                    search_query = f'indications_and_usage:({search_gene} AND {variant_clean})'
                    result = await self._query_drugsfda(search_query, limit=15)
                    for r in result.get("results", []):
                        drug_id = r.get("openfda", {}).get("brand_name", [""])[0]
                        if drug_id and drug_id not in seen_drugs:
                            seen_drugs.add(drug_id)
                            approvals.append(r)

            # Strategy 2: If no results, search for just gene in indications
            if not approvals:
                for search_gene in genes_to_search:
                    gene_search = f'indications_and_usage:{search_gene}'
                    result = await self._query_drugsfda(gene_search, limit=15)
                    for r in result.get("results", []):
                        drug_id = r.get("openfda", {}).get("brand_name", [""])[0]
                        if drug_id and drug_id not in seen_drugs:
                            seen_drugs.add(drug_id)
                            approvals.append(r)

            # Strategy 3: Known gene-drug mappings as final fallback
            # This ensures major drugs like Tafinlar, Zelboraf are captured
            if not approvals:
                known_drugs = self._get_known_gene_drugs(gene_upper)
                if known_drugs:
                    for drug_name in known_drugs[:5]:  # Top 5 known drugs
                        drug_search = f'openfda.brand_name:"{drug_name}"'
                        result = await self._query_drugsfda(drug_search, limit=1)
                        if result.get("results"):
                            approvals.extend(result["results"])

            return approvals[:10]  # Return top 10 most relevant

        except Exception as e:
            # Return empty list on error, don't fail the whole pipeline
            print(f"FDA API warning: {str(e)}")
            return []

    def _get_known_gene_drugs(self, gene: str) -> list[str]:
        """Get known FDA-approved drugs for major oncology genes.

        This is a fallback mapping for well-established gene-drug pairs
        to ensure critical approvals are captured even if API search fails.

        Args:
            gene: Gene symbol (uppercase)

        Returns:
            List of known drug brand names
        """
        # Major oncology gene-drug mappings (brand names)
        known_mappings = {
            "BRAF": ["Tafinlar", "Zelboraf", "Braftovi"],
            "EGFR": ["Tagrisso", "Tarceva", "Iressa", "Gilotrif"],
            "KRAS": ["Lumakras", "Krazati"],
            "ALK": ["Xalkori", "Alecensa", "Zykadia"],
            "ROS1": ["Xalkori", "Rozlytrek"],
            "ERBB2": ["Herceptin", "Enhertu", "Kadcyla", "Tukysa", "Nerlynx"],
            "HER2": ["Herceptin", "Enhertu", "Kadcyla", "Tukysa", "Nerlynx"],
            "KIT": ["Gleevec", "Sutent"],
            "PDGFRA": ["Gleevec", "Ayvakit"],
            "IDH1": ["Tibsovo"],
            "IDH2": ["Idhifa"],
            "PIK3CA": ["Piqray"],
            "NTRK1": ["Vitrakvi", "Rozlytrek"],
            "NTRK2": ["Vitrakvi", "Rozlytrek"],
            "NTRK3": ["Vitrakvi", "Rozlytrek"],
            "RET": ["Retevmo", "Gavreto"],
            "MET": ["Tabrecta", "Tepmetko"],
            "FGFR2": ["Pemazyre"],
            "FGFR3": ["Balversa"],
        }

        return known_mappings.get(gene, [])

    def parse_approval_data(
        self, approval_record: dict[str, Any], gene: str
    ) -> dict[str, Any] | None:
        """Parse FDA approval record into structured format.

        Extracts key information like drug name, indication, approval date,
        and biomarker information from the FDA Drug Label API response.

        Args:
            approval_record: Raw FDA API response record from /drug/label.json
            gene: Gene symbol for context

        Returns:
            Structured approval data or None if insufficient data
        """
        try:
            # Extract drug names from openfda section
            brand_name = None
            generic_name = None
            approval_date = None
            marketing_status = "Prescription"  # Drug labels are for approved prescription drugs

            if "openfda" in approval_record:
                openfda = approval_record["openfda"]

                # Brand name
                if "brand_name" in openfda:
                    brand_names = openfda["brand_name"]
                    brand_name = brand_names[0] if isinstance(brand_names, list) else brand_names

                # Generic name
                if "generic_name" in openfda:
                    generic_names = openfda["generic_name"]
                    generic_name = generic_names[0] if isinstance(generic_names, list) else generic_names

                # Application number can give us approval info
                if "application_number" in openfda:
                    app_nums = openfda["application_number"]
                    # Extract year from application number if available (format: NDA021743 or BLA125377)
                    if isinstance(app_nums, list) and app_nums:
                        # The format varies, so we'll just note it exists
                        pass

            # Extract indications_and_usage text
            indications = approval_record.get("indications_and_usage", [])
            if isinstance(indications, list):
                indication_text = " ".join(indications)
            else:
                indication_text = str(indications)

            # Only return if we have minimum required data (drug name)
            if brand_name or generic_name:
                return {
                    "drug_name": brand_name or generic_name,
                    "brand_name": brand_name,
                    "generic_name": generic_name,
                    "indication": indication_text[:1800] if indication_text else None,  # Full indication for multi-indication drugs
                    "approval_date": approval_date,  # Not available in label endpoint
                    "marketing_status": marketing_status,
                    "gene": gene,
                }

            return None

        except Exception:
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None