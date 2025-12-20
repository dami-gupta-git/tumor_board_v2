"""FDA Drug Label API client for querying by brand name.

ARCHITECTURE:
    Drug Brand Name → openFDA Label API → Indication text with biomarker context

This module provides a cleaner approach to FDA label retrieval by querying
directly by brand name rather than broad gene searches.

Key Design:
- Query by brand_name for precise label retrieval
- Extract biomarker context from indications
- Detect exclusion vs inclusion patterns for variants
- Async HTTP with connection pooling (httpx.AsyncClient)
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import httpx


class FDALabelError(Exception):
    """Exception raised for FDA Label API errors."""
    pass


@dataclass
class DrugLabelResult:
    """Result from querying a drug label."""

    brand_name: str
    generic_name: str | None
    indications: str
    biomarker_context: str | None
    effective_date: str | None
    full_label: dict[str, Any]

    def mentions_biomarker(self, biomarker: str) -> bool:
        """Check if indications mention the biomarker."""
        return biomarker.lower() in self.indications.lower()

    def get_indication_for_tumor(self, tumor_type: str) -> str | None:
        """Extract indication text relevant to a specific tumor type."""
        tumor_lower = tumor_type.lower()
        indications_lower = self.indications.lower()

        if tumor_lower not in indications_lower:
            return None

        # Find the section mentioning this tumor type
        idx = indications_lower.find(tumor_lower)
        start = max(0, idx - 100)
        end = min(len(self.indications), idx + 300)

        return self.indications[start:end]


class FDALabelClient:
    """Client for querying FDA drug labels by brand name.

    Uses the openFDA Label API which provides full prescribing information
    including indications, contraindications, and clinical studies.

    API Documentation: https://open.fda.gov/apis/drug/label/
    """

    BASE_URL = "https://api.fda.gov/drug/label.json"
    DEFAULT_TIMEOUT = 15.0
    DEFAULT_RETRIES = 3
    DEFAULT_BACKOFF = 1.0

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        backoff: float = DEFAULT_BACKOFF,
    ):
        """Initialize the FDA Label client.

        Args:
            timeout: Request timeout in seconds
            retries: Number of retry attempts per search term
            backoff: Base backoff time in seconds (exponential)
        """
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "FDALabelClient":
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

    async def query_drug_label(
        self,
        brand_name: str | None = None,
        generic_name: str | None = None,
        biomarker: str | None = None,
        limit: int = 5,
    ) -> DrugLabelResult | None:
        """Query openFDA Drug Labeling API.

        Provide either brand_name (e.g., "Tibsovo" or "TIBSOVO") or generic_name
        (e.g., "ivosidenib").

        Args:
            brand_name: Drug brand name
            generic_name: Drug generic name
            biomarker: Optional biomarker to extract context for
            limit: Maximum number of results

        Returns:
            DrugLabelResult or None if not found
        """
        client = self._get_client()

        # Build search query - try multiple variations
        search_terms = []
        if brand_name:
            search_terms.extend([
                f'openfda.brand_name:"{brand_name}"',
                f'openfda.brand_name:{brand_name}',  # Partial match
                f'openfda.brand_name.exact:"{brand_name.upper()}"'
            ])
        if generic_name:
            search_terms.extend([
                f'openfda.generic_name:"{generic_name}"',
                f'openfda.generic_name:{generic_name}'
            ])

        if not search_terms:
            raise ValueError("Provide at least brand_name or generic_name.")

        # Try each search term until one works
        for search_query in search_terms:
            params = {"search": search_query, "limit": limit}

            for attempt in range(self.retries):
                try:
                    response = await client.get(self.BASE_URL, params=params)
                    if response.status_code != 200:
                        raise httpx.HTTPStatusError(
                            f"HTTP {response.status_code}",
                            request=response.request,
                            response=response
                        )

                    data = response.json()
                    if 'results' not in data or len(data['results']) == 0:
                        raise ValueError("No results for this search term.")

                    # Success - process the latest/most relevant label
                    label = data['results'][0]
                    indications_raw = label.get('indications_and_usage', ['No indications found'])

                    indications_text = ""
                    for item in indications_raw:
                        if isinstance(item, str):
                            indications_text += item + "\n"
                        elif isinstance(item, dict):
                            indications_text += json.dumps(item) + "\n"

                    indications_text = indications_text.strip()

                    # Extract biomarker context if provided
                    biomarker_context = None
                    if biomarker:
                        lower_text = indications_text.lower()
                        if biomarker.lower() in lower_text:
                            start = max(0, lower_text.find(biomarker.lower()) - 150)
                            end = min(len(indications_text), lower_text.find(biomarker.lower()) + len(biomarker) + 150)
                            biomarker_context = indications_text[start:end]
                        else:
                            biomarker_context = f"No direct mention of {biomarker} (may be covered broadly under gene name)."

                    # Get generic name from openfda
                    openfda = label.get("openfda", {})
                    generic_names = openfda.get("generic_name", [])
                    found_generic = generic_names[0] if generic_names else None

                    # Get brand name from openfda
                    brand_names = openfda.get("brand_name", [])
                    found_brand = brand_names[0] if brand_names else (brand_name or "Unknown")

                    return DrugLabelResult(
                        brand_name=found_brand,
                        generic_name=found_generic,
                        indications=indications_text,
                        biomarker_context=biomarker_context,
                        effective_date=label.get('effective_time', 'Unknown'),
                        full_label=label,
                    )

                except Exception:
                    if attempt < self.retries - 1:
                        await asyncio.sleep(self.backoff * (2 ** attempt))

        return None

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Convenience function for one-off queries
async def query_drug_label(
    brand_name: str | None = None,
    generic_name: str | None = None,
    biomarker: str | None = None,
) -> DrugLabelResult | None:
    """Query FDA label for a drug by brand name or generic name.

    Args:
        brand_name: Drug brand name (e.g., "Tibsovo")
        generic_name: Drug generic name (e.g., "ivosidenib")
        biomarker: Optional biomarker to check (e.g., "IDH1", "R132C")

    Returns:
        DrugLabelResult or None
    """
    async with FDALabelClient() as client:
        return await client.query_drug_label(brand_name, generic_name, biomarker)
