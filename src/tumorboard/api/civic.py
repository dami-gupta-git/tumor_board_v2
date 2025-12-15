"""CIViC (Clinical Interpretation of Variants in Cancer) GraphQL API client.

ARCHITECTURE:
    Gene + Variant → CIViC GraphQL API → AMP/ASCO/CAP Assertions with NCCN guidelines

CIViC provides curated clinical interpretations with:
- AMP/ASCO/CAP tier classifications (Tier I/II Level A/B/C/D)
- FDA companion test status
- NCCN guideline references
- Assertion types: PREDICTIVE, PROGNOSTIC, DIAGNOSTIC, ONCOGENIC

Key Design:
- GraphQL API for flexible querying
- Assertions are curated summaries with AMP tier assignments
- Complements CGI and VICC by providing guideline-backed tiers
- Free and open source (no license required unlike OncoKB)
"""

from typing import Any

import httpx

from tumorboard.constants import TUMOR_TYPE_MAPPINGS


class CIViCError(Exception):
    """Exception raised for CIViC API errors."""
    pass


class CIViCAssertion:
    """A curated assertion from CIViC database.

    Assertions represent the clinical significance of a molecular profile
    in a specific disease context, with AMP/ASCO/CAP tier classification.
    """

    def __init__(
        self,
        assertion_id: int,
        name: str,
        amp_level: str | None,
        assertion_type: str,  # PREDICTIVE, PROGNOSTIC, DIAGNOSTIC, ONCOGENIC
        assertion_direction: str,  # SUPPORTS, DOES_NOT_SUPPORT
        significance: str,  # SENSITIVITYRESPONSE, RESISTANCE, ONCOGENIC, etc.
        status: str,  # ACCEPTED, SUBMITTED, REJECTED
        molecular_profile: str,
        disease: str,
        therapies: list[str],
        fda_companion_test: bool | None,
        nccn_guideline: str | None,
        description: str | None = None,
    ):
        self.assertion_id = assertion_id
        self.name = name
        self.amp_level = amp_level
        self.assertion_type = assertion_type
        self.assertion_direction = assertion_direction
        self.significance = significance
        self.status = status
        self.molecular_profile = molecular_profile
        self.disease = disease
        self.therapies = therapies
        self.fda_companion_test = fda_companion_test
        self.nccn_guideline = nccn_guideline
        self.description = description

    def get_amp_tier(self) -> str | None:
        """Extract AMP tier from amp_level (e.g., 'TIER_I_LEVEL_A' -> 'Tier I')."""
        if not self.amp_level:
            return None
        if "TIER_I" in self.amp_level:
            return "Tier I"
        elif "TIER_II" in self.amp_level:
            return "Tier II"
        elif "TIER_III" in self.amp_level:
            return "Tier III"
        elif "TIER_IV" in self.amp_level:
            return "Tier IV"
        return None

    def get_amp_level(self) -> str | None:
        """Extract AMP level from amp_level (e.g., 'TIER_I_LEVEL_A' -> 'A')."""
        if not self.amp_level:
            return None
        if "LEVEL_A" in self.amp_level:
            return "A"
        elif "LEVEL_B" in self.amp_level:
            return "B"
        elif "LEVEL_C" in self.amp_level:
            return "C"
        elif "LEVEL_D" in self.amp_level:
            return "D"
        return None

    def is_sensitivity(self) -> bool:
        """Check if this represents a sensitivity/response assertion."""
        if not self.significance:
            return False
        sig_upper = self.significance.upper()
        return any(term in sig_upper for term in ["SENSITIV", "RESPONSE"])

    def is_resistance(self) -> bool:
        """Check if this represents a resistance assertion."""
        if not self.significance:
            return False
        return "RESIST" in self.significance.upper()

    def is_accepted(self) -> bool:
        """Check if assertion has been accepted (vs submitted/rejected)."""
        return self.status == "ACCEPTED"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "assertion_id": self.assertion_id,
            "name": self.name,
            "amp_level": self.amp_level,
            "amp_tier": self.get_amp_tier(),
            "amp_level_letter": self.get_amp_level(),
            "assertion_type": self.assertion_type,
            "assertion_direction": self.assertion_direction,
            "significance": self.significance,
            "status": self.status,
            "molecular_profile": self.molecular_profile,
            "disease": self.disease,
            "therapies": self.therapies,
            "fda_companion_test": self.fda_companion_test,
            "nccn_guideline": self.nccn_guideline,
            "description": self.description,
            "is_sensitivity": self.is_sensitivity(),
            "is_resistance": self.is_resistance(),
        }


class CIViCClient:
    """Client for CIViC GraphQL API.

    CIViC (Clinical Interpretation of Variants in Cancer) provides
    curated clinical interpretations with AMP/ASCO/CAP tier assignments.

    API Documentation: https://griffithlab.github.io/civic-v2/
    GraphQL Endpoint: https://civicdb.org/api/graphql
    """

    GRAPHQL_URL = "https://civicdb.org/api/graphql"
    DEFAULT_TIMEOUT = 30.0

    # GraphQL query for assertions
    ASSERTIONS_QUERY = """
    query GetAssertions($molecularProfileName: String, $first: Int) {
        assertions(molecularProfileName: $molecularProfileName, first: $first) {
            nodes {
                id
                name
                ampLevel
                assertionType
                assertionDirection
                significance
                status
                description
                therapies {
                    name
                }
                disease {
                    name
                }
                molecularProfile {
                    name
                }
                fdaCompanionTest
                nccnGuideline {
                    name
                }
            }
        }
    }
    """

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        """Initialize the CIViC client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        """Initialize HTTP client session."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close HTTP client session."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get the HTTP client, creating one if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    def _tumor_matches(self, civic_disease: str, tumor_type: str | None) -> bool:
        """Check if CIViC disease matches user tumor type.

        Args:
            civic_disease: Disease string from CIViC
            tumor_type: User-provided tumor type

        Returns:
            True if tumor types match
        """
        if not tumor_type:
            return True  # No filter

        civic_lower = civic_disease.lower() if civic_disease else ""
        tumor_lower = tumor_type.lower()

        # Direct substring match
        if tumor_lower in civic_lower or civic_lower in tumor_lower:
            return True

        # Check tumor type mappings
        for abbrev, full_names in TUMOR_TYPE_MAPPINGS.items():
            # Check if tumor matches this mapping (either as abbrev or substring match)
            tumor_matches_mapping = (
                tumor_lower == abbrev or
                any(tumor_lower in name for name in full_names) or
                any(name in tumor_lower for name in full_names)
            )
            if tumor_matches_mapping:
                # Check if civic disease matches any full name
                if any(name in civic_lower for name in full_names):
                    return True

        return False

    def _parse_assertion(self, node: dict[str, Any]) -> CIViCAssertion | None:
        """Parse a GraphQL assertion node into an assertion object.

        Args:
            node: Raw assertion node from GraphQL response

        Returns:
            CIViCAssertion or None if parsing fails
        """
        try:
            # Extract therapies
            therapies = []
            for therapy in node.get("therapies", []):
                if therapy.get("name"):
                    therapies.append(therapy["name"])

            # Extract disease
            disease = node.get("disease", {}).get("name", "")

            # Extract molecular profile
            molecular_profile = node.get("molecularProfile", {}).get("name", "")

            # Extract NCCN guideline
            nccn = node.get("nccnGuideline")
            nccn_guideline = nccn.get("name") if nccn else None

            return CIViCAssertion(
                assertion_id=node.get("id"),
                name=node.get("name", ""),
                amp_level=node.get("ampLevel"),
                assertion_type=node.get("assertionType", ""),
                assertion_direction=node.get("assertionDirection", ""),
                significance=node.get("significance", ""),
                status=node.get("status", ""),
                molecular_profile=molecular_profile,
                disease=disease,
                therapies=therapies,
                fda_companion_test=node.get("fdaCompanionTest"),
                nccn_guideline=nccn_guideline,
                description=node.get("description"),
            )

        except Exception:
            return None

    async def fetch_assertions(
        self,
        gene: str,
        variant: str | None = None,
        tumor_type: str | None = None,
        max_results: int = 50,
    ) -> list[CIViCAssertion]:
        """Fetch CIViC assertions for a gene/variant combination.

        Args:
            gene: Gene symbol (e.g., "EGFR")
            variant: Optional variant notation (e.g., "L858R")
            tumor_type: Optional tumor type to filter results
            max_results: Maximum number of results to return

        Returns:
            List of CIViCAssertion objects
        """
        client = self._get_client()

        # Build search term for molecular profile
        search_term = gene.upper()
        if variant:
            clean_variant = variant.replace("p.", "").upper()
            search_term = f"{gene.upper()} {clean_variant}"

        # Execute GraphQL query
        variables = {
            "molecularProfileName": search_term,
            "first": max_results * 2,  # Fetch extra to account for filtering
        }

        try:
            response = await client.post(
                self.GRAPHQL_URL,
                json={
                    "query": self.ASSERTIONS_QUERY,
                    "variables": variables,
                },
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            raise CIViCError(f"CIViC API request failed: {e}")
        except Exception as e:
            raise CIViCError(f"Failed to parse CIViC response: {e}")

        # Check for GraphQL errors
        if "errors" in data:
            raise CIViCError(f"GraphQL errors: {data['errors']}")

        # Parse assertions
        assertions = []
        nodes = data.get("data", {}).get("assertions", {}).get("nodes", [])

        for node in nodes:
            assertion = self._parse_assertion(node)
            if assertion is None:
                continue

            # Filter by tumor type if specified
            if tumor_type and not self._tumor_matches(assertion.disease, tumor_type):
                continue

            # Check if molecular profile contains our variant
            if variant:
                clean_variant = variant.replace("p.", "").upper()
                if clean_variant not in assertion.molecular_profile.upper():
                    continue

            assertions.append(assertion)

            if len(assertions) >= max_results:
                break

        return assertions

    async def fetch_predictive_assertions(
        self,
        gene: str,
        variant: str | None = None,
        tumor_type: str | None = None,
        max_results: int = 25,
    ) -> list[CIViCAssertion]:
        """Fetch only PREDICTIVE assertions (therapy response).

        Args:
            gene: Gene symbol
            variant: Optional variant notation
            tumor_type: Optional tumor type filter
            max_results: Maximum results

        Returns:
            List of predictive assertions
        """
        all_assertions = await self.fetch_assertions(gene, variant, tumor_type, max_results * 2)
        return [a for a in all_assertions if a.assertion_type == "PREDICTIVE"][:max_results]

    async def fetch_tier_i_assertions(
        self,
        gene: str,
        variant: str | None = None,
        tumor_type: str | None = None,
    ) -> list[CIViCAssertion]:
        """Fetch only Tier I (Level A or B) assertions.

        These represent the strongest clinical evidence for actionability.

        Args:
            gene: Gene symbol
            variant: Optional variant notation
            tumor_type: Optional tumor type filter

        Returns:
            List of Tier I assertions
        """
        all_assertions = await self.fetch_assertions(gene, variant, tumor_type, max_results=50)
        return [a for a in all_assertions if a.get_amp_tier() == "Tier I"]

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
