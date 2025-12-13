"""OncoTree API client for fetching standardized tumor type classifications.

ARCHITECTURE:
    User Query → OncoTree API → Tumor Type Codes + Full Names

Provides both short codes (NSCLC, LUAD, MEL) and full names
(Non-Small Cell Lung Cancer, Lung Adenocarcinoma, Melanoma).

Key Design:
- Async HTTP with connection pooling (httpx.AsyncClient)
- Local caching to avoid repeated API calls
- Fuzzy matching for user input
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

from tumorboard.constants import PRIORITY_TUMOR_CODES


class OncoTreeAPIError(Exception):
    """Exception raised for OncoTree API errors."""

    pass


class OncoTreeClient:
    """Client for OncoTree API.

    OncoTree is MSK's cancer classification system providing:
    - Standardized tumor type codes (e.g., NSCLC, LUAD, MEL)
    - Full descriptive names
    - Hierarchical cancer classification
    - 868+ tumor types across 32 organ sites

    API Documentation: https://oncotree.mskcc.org/
    """

    BASE_URL = "https://oncotree.mskcc.org/api"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = 3,
    ) -> None:
        """Initialize the OncoTree client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None
        self._cache: dict[str, Any] = {}  # Simple in-memory cache

    async def __aenter__(self) -> "OncoTreeClient":
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
    async def _fetch_all_tumor_types(self) -> list[dict[str, Any]]:
        """Fetch all tumor types from OncoTree API.

        Returns:
            List of tumor type dictionaries with code, name, mainType, tissue, etc.

        Raises:
            OncoTreeAPIError: If the API request fails
        """
        # Check cache first
        if "all_tumor_types" in self._cache:
            return self._cache["all_tumor_types"]

        client = self._get_client()
        url = f"{self.BASE_URL}/tumorTypes"

        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            # Cache the result
            self._cache["all_tumor_types"] = data
            return data

        except httpx.HTTPStatusError as e:
            raise OncoTreeAPIError(f"HTTP error: {e}")
        except Exception as e:
            raise OncoTreeAPIError(f"Failed to fetch tumor types: {e}")

    async def get_tumor_type_by_code(self, code: str) -> dict[str, Any] | None:
        """Get a specific tumor type by its OncoTree code.

        Args:
            code: OncoTree code (e.g., "NSCLC", "LUAD", "MEL")

        Returns:
            Tumor type dictionary or None if not found
        """
        try:
            all_types = await self._fetch_all_tumor_types()
            code_upper = code.upper()

            for tumor_type in all_types:
                if tumor_type.get("code", "").upper() == code_upper:
                    return tumor_type

            return None

        except Exception:
            return None

    async def search_tumor_types(self, query: str) -> list[dict[str, Any]]:
        """Search tumor types by code or name (case-insensitive).

        Args:
            query: Search query (can be code or partial name)

        Returns:
            List of matching tumor types
        """
        try:
            all_types = await self._fetch_all_tumor_types()
            query_lower = query.lower()
            query_upper = query.upper()

            matches = []
            for tumor_type in all_types:
                code = tumor_type.get("code", "")
                name = tumor_type.get("name", "")
                main_type = tumor_type.get("mainType", "")

                # Match by code (exact or prefix) - case insensitive
                if code.upper() == query_upper or code.upper().startswith(query_upper):
                    matches.append(tumor_type)
                # Match by name (contains) - case insensitive
                elif query_lower in name.lower() or query_lower in main_type.lower():
                    matches.append(tumor_type)

            return matches

        except Exception:
            return []

    async def get_tumor_type_names_for_ui(self, query: str | None = None, limit: int | None = None) -> list[str]:
        """Get tumor type names formatted for UI display.

        Returns names in format: "Code - Full Name" (e.g., "NSCLC - Non-Small Cell Lung Cancer")

        Prioritizes commonly-used cancer types first, then alphabetical order.

        Args:
            query: Optional query to filter results
            limit: Optional limit on number of results (None = all results)

        Returns:
            List of formatted tumor type names
        """
        try:
            if query:
                tumor_types = await self.search_tumor_types(query)
            else:
                tumor_types = await self._fetch_all_tumor_types()

            print(f"Found {len(tumor_types)} tumor types")
            # Format as "CODE - Name" for easy matching
            formatted = []
            for tumor_type in tumor_types:
                code = tumor_type.get("code", "")
                name = tumor_type.get("name", "")
                if code and name:
                    formatted.append(f"{code} - {name}")

            # Separate into priority and non-priority using centralized constants
            priority = []
            non_priority = []

            for item in formatted:
                code = item.split(" - ")[0] if " - " in item else ""
                if code in PRIORITY_TUMOR_CODES:
                    priority.append(item)
                else:
                    non_priority.append(item)

            # Sort each group alphabetically
            priority.sort()
            non_priority.sort()

            # Combine: priority first, then rest
            result = priority + non_priority

            # Apply limit if specified
            if limit is not None:
                return result[:limit]

            return result

        except Exception:
            return []

    def parse_user_input(self, user_input: str) -> str:
        """Parse user input to extract tumor type.

        Handles formats:
        - "NSCLC" → "NSCLC"
        - "Non-Small Cell Lung Cancer" → "Non-Small Cell Lung Cancer"
        - "NSCLC - Non-Small Cell Lung Cancer" → "NSCLC"

        Args:
            user_input: Raw user input

        Returns:
            Cleaned tumor type string
        """
        if not user_input:
            return ""

        user_input = user_input.strip()

        # If format is "CODE - Name", extract the code
        if " - " in user_input:
            return user_input.split(" - ")[0].strip()

        return user_input

    async def resolve_tumor_type(self, user_input: str) -> str:
        """Resolve user input to a standardized tumor type name.

        Handles various input formats:
        - "NSCLC" → "Non-Small Cell Lung Cancer"
        - "Non-Small Cell Lung Cancer" → "Non-Small Cell Lung Cancer"
        - "NSCLC - Non-Small Cell Lung Cancer" → "Non-Small Cell Lung Cancer"
        - "nsclc" → "Non-Small Cell Lung Cancer" (case-insensitive)

        This helps match user input to FDA indication text and other databases.

        Args:
            user_input: Raw user input

        Returns:
            Standardized tumor type name (full name if OncoTree code found, else original input)
        """
        if not user_input:
            return ""

        user_input = user_input.strip()

        # If format is "CODE - Name", we already have both
        if " - " in user_input:
            parts = user_input.split(" - ", 1)
            if len(parts) == 2:
                return parts[1].strip()  # Return the full name

        # Try to match as OncoTree code
        tumor_type = await self.get_tumor_type_by_code(user_input)
        if tumor_type:
            return tumor_type.get("name", user_input)

        # If not found, return original input (might be a full name already)
        return user_input

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
