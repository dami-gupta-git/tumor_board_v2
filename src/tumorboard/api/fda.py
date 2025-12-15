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

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from tumorboard.constants import GENE_ALIASES


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
        if gene_upper in GENE_ALIASES:
            genes_to_search.extend(GENE_ALIASES[gene_upper])

        try:
            # Clean variant notation
            variant_clean = None
            if variant:
                variant_clean = variant.strip().upper()
                # Remove common prefixes
                for prefix in ["P.", "C.", "G."]:
                    if variant_clean.startswith(prefix):
                        variant_clean = variant_clean[2:]

            # Strategy 1: Search for gene + variant together (full-text search across all fields)
            # This finds variants in clinical_studies, indications, and other label sections
            if variant_clean:
                # Build list of search terms: exact variant + codon-level patterns
                # e.g., for G719S, search for "G719S", "G719X" (FDA often uses X for any amino acid)
                import re
                search_variants = [variant_clean]

                # Extract codon position for pattern-based search
                # Matches patterns like G719S, L858R, V600E, etc.
                codon_match = re.match(r'^([A-Z])(\d+)([A-Z])$', variant_clean)
                if codon_match:
                    # Add codon-level pattern with X (FDA convention for any amino acid)
                    # e.g., "G719X" for G719S - this is how FDA labels often describe variant classes
                    codon_x_pattern = codon_match.group(1) + codon_match.group(2) + "X"
                    search_variants.append(codon_x_pattern)

                for search_gene in genes_to_search:
                    for search_var in search_variants:
                        # Full-text search: finds G719X in any field (clinical_studies, indications, etc.)
                        search_query = f'{search_gene} AND {search_var}'
                        result = await self._query_drugsfda(search_query, limit=15)
                        for r in result.get("results", []):
                            drug_id = r.get("openfda", {}).get("brand_name", [""])[0]
                            if drug_id and drug_id not in seen_drugs:
                                seen_drugs.add(drug_id)
                                approvals.append(r)

            # Strategy 2: If no results with variant, search for just gene in indications
            if not approvals:
                for search_gene in genes_to_search:
                    gene_search = f'indications_and_usage:{search_gene}'
                    result = await self._query_drugsfda(gene_search, limit=15)
                    for r in result.get("results", []):
                        drug_id = r.get("openfda", {}).get("brand_name", [""])[0]
                        if drug_id and drug_id not in seen_drugs:
                            seen_drugs.add(drug_id)
                            approvals.append(r)

            return approvals[:10]  # Return top 10 most relevant

        except Exception as e:
            # Return empty list on error, don't fail the whole pipeline
            print(f"FDA API warning: {str(e)}")
            return []

    def parse_approval_data(
        self, approval_record: dict[str, Any], gene: str, variant: str | None = None
    ) -> dict[str, Any] | None:
        """Parse FDA approval record into structured format.

        Extracts key information like drug name, indication, approval date,
        and biomarker information from the FDA Drug Label API response.

        Args:
            approval_record: Raw FDA API response record from /drug/label.json
            gene: Gene symbol for context
            variant: Optional variant to search for in clinical_studies section

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

            # Check if variant is explicitly mentioned in indications (e.g., T790M for TAGRISSO)
            variant_in_indications = False
            indication_variant_note = None
            if variant:
                import re
                variant_upper = variant.upper()
                indication_upper = indication_text.upper()

                if variant_upper in indication_upper:
                    variant_in_indications = True
                    # Extract the specific indication sentence for this variant
                    idx = indication_upper.find(variant_upper)
                    # Find the bullet point or sentence containing this variant
                    start = indication_text.rfind("•", 0, idx)
                    if start == -1:
                        start = max(0, idx - 100)
                    end = indication_text.find("•", idx + len(variant_upper))
                    if end == -1:
                        end = min(len(indication_text), idx + 300)
                    indication_variant_note = f"[FDA APPROVED FOR {variant_upper}: {indication_text[start:end].strip()}]"

            # Check clinical_studies for variant-specific approval info
            # This is important for variants like G719X, S768I, L861Q that are mentioned
            # in clinical studies but not in the generic indications text
            clinical_studies_note = None
            if variant:
                import re
                clinical_studies = approval_record.get("clinical_studies", [])
                if isinstance(clinical_studies, list):
                    clinical_text = " ".join(clinical_studies)
                else:
                    clinical_text = str(clinical_studies) if clinical_studies else ""

                variant_upper = variant.upper()
                clinical_text_upper = clinical_text.upper()

                # Build search patterns: exact variant + codon-level pattern with wildcard
                # e.g., for G719S: search for "G719S", "G719X", "G719A", etc.
                search_patterns = [variant_upper]
                codon_match = re.match(r'^([A-Z])(\d+)([A-Z])$', variant_upper)
                if codon_match:
                    # Add codon pattern with X wildcard (e.g., "G719X" for G719S)
                    codon_pattern = codon_match.group(1) + codon_match.group(2) + "X"
                    search_patterns.append(codon_pattern)

                # Search for any matching pattern
                found_pattern = None
                found_idx = -1
                for pattern in search_patterns:
                    if pattern in clinical_text_upper:
                        found_pattern = pattern
                        found_idx = clinical_text_upper.find(pattern)
                        break

                if found_pattern and found_idx >= 0:
                    # Extract a relevant snippet around the variant mention
                    start = max(0, found_idx - 100)
                    end = min(len(clinical_text), found_idx + 200)
                    snippet = clinical_text[start:end].strip()
                    # Clean up the snippet
                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(clinical_text):
                        snippet = snippet + "..."
                    clinical_studies_note = f"[Clinical studies mention {found_pattern} (variant class includes {variant}): {snippet}]"

            # Only return if we have minimum required data (drug name)
            if brand_name or generic_name:
                # Build indication text with variant-specific context prominently displayed
                full_indication = ""

                # If variant is in indications (strongest evidence), put that first
                if indication_variant_note:
                    full_indication = indication_variant_note + "\n\n"

                # Add truncated full indication
                full_indication += indication_text[:1500] if indication_text else ""

                # Add clinical studies note if variant was found there (but not in indications)
                if clinical_studies_note and not variant_in_indications:
                    full_indication = f"{full_indication}\n\n{clinical_studies_note}"

                return {
                    "drug_name": brand_name or generic_name,
                    "brand_name": brand_name,
                    "generic_name": generic_name,
                    "indication": full_indication[:2500] if full_indication else None,
                    "approval_date": approval_date,  # Not available in label endpoint
                    "marketing_status": marketing_status,
                    "gene": gene,
                    "variant_in_indications": variant_in_indications,
                    "variant_in_clinical_studies": clinical_studies_note is not None,
                }

            return None

        except Exception:
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None