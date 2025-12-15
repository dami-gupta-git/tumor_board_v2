"""VICC MetaKB client for harmonized cancer variant interpretations.

ARCHITECTURE:
    Gene + Variant → VICC MetaKB API → Harmonized evidence from CIViC, CGI, JAX, OncoKB, PMKB

The VICC (Variant Interpretation for Cancer Consortium) Meta-Knowledgebase aggregates
and harmonizes clinical interpretations from multiple cancer variant knowledgebases:
- CIViC (Clinical Interpretations of Variants in Cancer)
- Cancer Genome Interpreter (CGI)
- JAX-CKB (Jackson Laboratory Clinical Knowledgebase)
- OncoKB
- PMKB (Precision Medicine Knowledgebase)
- MolecularMatch

Key Design:
- Lucene query syntax for flexible variant matching
- Evidence levels: A (validated), B (clinical), C (case study), D (preclinical)
- Response types: Responsive/Sensitivity, Resistant, 1A/1B/2A/2B/etc (OncoKB-style)
- Sources attributed to original KB for provenance tracking
"""

from typing import Any

import httpx

from tumorboard.constants import TUMOR_TYPE_MAPPINGS


class VICCError(Exception):
    """Exception raised for VICC MetaKB-related errors."""

    pass


class VICCAssociation:
    """A clinical interpretation association from VICC MetaKB.

    Represents harmonized evidence linking a variant to a drug/disease with
    clinical significance and evidence level.
    """

    def __init__(
        self,
        description: str,
        gene: str,
        variant: str | None,
        disease: str,
        drugs: list[str],
        evidence_level: str | None,  # A, B, C, D
        response_type: str | None,  # Responsive, Resistant, Sensitivity, 1A, etc.
        source: str,  # civic, cgi, jax, oncokb, pmkb
        publication_url: str | list[str] | None = None,  # Can be string or list
        oncogenic: str | None = None,
    ):
        self.description = description
        self.gene = gene
        self.variant = variant
        self.disease = disease
        self.drugs = drugs
        self.evidence_level = evidence_level
        self.response_type = response_type
        self.source = source
        self.publication_url = publication_url
        self.oncogenic = oncogenic

    def is_sensitivity(self) -> bool:
        """Check if this represents a sensitivity/response association."""
        if not self.response_type:
            return False
        rt_upper = self.response_type.upper()
        return any(term in rt_upper for term in ["SENSITIV", "RESPONSE", "RESPONSIVE"])

    def is_resistance(self) -> bool:
        """Check if this represents a resistance association."""
        if not self.response_type:
            return False
        return "RESIST" in self.response_type.upper()

    def get_oncokb_level(self) -> str | None:
        """Extract OncoKB-style level if present (1A, 1B, 2A, 2B, 3A, 3B, 4, R1, R2)."""
        if not self.response_type:
            return None
        # OncoKB uses levels like 1A, 1B, 2A, 2B, 3A, 3B, 4, R1, R2
        import re
        match = re.match(r'^([1234][AB]?|R[12])$', self.response_type.upper())
        if match:
            return match.group(1)
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "description": self.description,
            "gene": self.gene,
            "variant": self.variant,
            "disease": self.disease,
            "drugs": self.drugs,
            "evidence_level": self.evidence_level,
            "response_type": self.response_type,
            "source": self.source,
            "publication_url": self.publication_url,
            "oncogenic": self.oncogenic,
            "is_sensitivity": self.is_sensitivity(),
            "is_resistance": self.is_resistance(),
            "oncokb_level": self.get_oncokb_level(),
        }


class VICCClient:
    """Client for VICC MetaKB API.

    The VICC Meta-Knowledgebase provides harmonized clinical interpretations
    from multiple cancer variant databases, enabling comprehensive evidence
    lookup across the ecosystem.

    API Documentation: https://search.cancervariants.org/api/v1/ui/
    """

    BASE_URL = "https://search.cancervariants.org/api/v1"
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_SIZE = 50  # Number of results per query

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        """Initialize the VICC client.

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

    def _build_query(self, gene: str, variant: str | None = None) -> str:
        """Build a Lucene query string for the VICC API.

        Args:
            gene: Gene symbol (e.g., "BRAF")
            variant: Optional variant notation (e.g., "V600E")

        Returns:
            Lucene query string
        """
        # Gene symbol search in feature names
        query_parts = [gene.upper()]

        if variant:
            # Remove p. prefix if present
            clean_variant = variant.replace("p.", "").upper()
            query_parts.append(clean_variant)

        return " AND ".join(query_parts)

    def _tumor_matches(self, vicc_disease: str, tumor_type: str | None) -> bool:
        """Check if VICC disease matches user tumor type.

        Args:
            vicc_disease: Disease string from VICC (may contain multiple terms)
            tumor_type: User-provided tumor type

        Returns:
            True if tumor types match
        """
        if not tumor_type:
            return True  # No filter

        vicc_lower = vicc_disease.lower() if vicc_disease else ""
        tumor_lower = tumor_type.lower()

        # Direct substring match
        if tumor_lower in vicc_lower or vicc_lower in tumor_lower:
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
                # Check if VICC disease matches any full name
                if any(name in vicc_lower for name in full_names):
                    return True

        return False

    def _parse_association(self, hit: dict[str, Any]) -> VICCAssociation | None:
        """Parse a VICC API hit into an association object.

        Args:
            hit: Raw hit from VICC API

        Returns:
            VICCAssociation or None if parsing fails
        """
        try:
            assoc = hit.get("association", {})
            features = hit.get("features", [])

            # Extract gene from features
            gene = ""
            variant = None
            for feature in features:
                if feature.get("geneSymbol"):
                    gene = feature["geneSymbol"]
                if feature.get("name"):
                    # Extract variant from name like "BRAF V600E"
                    name = feature["name"]
                    if gene and gene in name:
                        variant = name.replace(gene, "").strip()

            # Extract disease
            disease = hit.get("diseases", "") or ""

            # Extract drugs
            drugs = []
            drug_str = hit.get("drugs", "")
            if drug_str:
                # VICC concatenates drugs with spaces/commas
                drugs = [d.strip() for d in drug_str.replace(",", " ").split() if d.strip()]

            # Extract evidence info
            evidence_level = hit.get("evidence_label")  # A, B, C, D
            response_type = assoc.get("response_type")

            # Extract source from evidence
            source = "vicc"
            evidence_list = assoc.get("evidence", [])
            if evidence_list:
                for ev in evidence_list:
                    source_name = ev.get("evidenceType", {}).get("sourceName")
                    if source_name:
                        source = source_name.lower()
                        break

            # Extract publication
            publication_url = assoc.get("publication_url")

            # Extract oncogenic info
            oncogenic = assoc.get("oncogenic")

            # Extract description
            description = assoc.get("description", "")

            return VICCAssociation(
                description=description,
                gene=gene,
                variant=variant,
                disease=disease,
                drugs=drugs,
                evidence_level=evidence_level,
                response_type=response_type,
                source=source,
                publication_url=publication_url,
                oncogenic=oncogenic,
            )

        except Exception:
            return None

    def _is_compound_mutation_resistance(self, assoc: "VICCAssociation", variant: str | None) -> bool:
        """Check if resistance is due to a compound/secondary mutation, not the queried variant.

        Args:
            assoc: The VICC association to check
            variant: The variant being queried (e.g., "V560D")

        Returns:
            True if this is resistance from a secondary mutation, not the queried variant
        """
        if not variant or not assoc.is_resistance():
            return False

        desc_lower = assoc.description.lower() if assoc.description else ""

        # Check for indicators of secondary/compound mutations
        secondary_indicators = [
            "secondary mutation",
            "acquired mutation",
            "harboring " + variant.lower() + " and ",
            variant.lower() + " and " + assoc.gene.lower() if assoc.gene else "",
            "developed resistance",
            "resistance developed",
        ]

        for indicator in secondary_indicators:
            if indicator and indicator in desc_lower:
                return True

        return False

    async def fetch_associations(
        self,
        gene: str,
        variant: str | None = None,
        tumor_type: str | None = None,
        max_results: int = 50,
    ) -> list[VICCAssociation]:
        """Fetch clinical interpretation associations from VICC MetaKB.

        Args:
            gene: Gene symbol (e.g., "BRAF")
            variant: Optional variant notation (e.g., "V600E")
            tumor_type: Optional tumor type to filter results
            max_results: Maximum number of results to return

        Returns:
            List of VICCAssociation objects
        """
        client = self._get_client()

        # Build query
        query = self._build_query(gene, variant)

        # Make request
        url = f"{self.BASE_URL}/associations"
        params = {
            "q": query,
            "size": max_results,
        }

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            raise VICCError(f"VICC API request failed: {e}")
        except Exception as e:
            raise VICCError(f"Failed to parse VICC response: {e}")

        # Parse hits
        associations = []
        hits = data.get("hits", {}).get("hits", [])

        for hit in hits:
            assoc = self._parse_association(hit)
            if assoc is None:
                continue

            # Filter by tumor type if specified
            if tumor_type and not self._tumor_matches(assoc.disease, tumor_type):
                continue

            # Filter out resistance entries that are about secondary/compound mutations
            if self._is_compound_mutation_resistance(assoc, variant):
                continue

            associations.append(assoc)

        return associations

    async def fetch_sensitivity_associations(
        self,
        gene: str,
        variant: str | None = None,
        tumor_type: str | None = None,
        max_results: int = 25,
    ) -> list[VICCAssociation]:
        """Fetch only sensitivity/response associations.

        Args:
            gene: Gene symbol
            variant: Optional variant notation
            tumor_type: Optional tumor type filter
            max_results: Maximum results

        Returns:
            List of sensitivity associations
        """
        all_assocs = await self.fetch_associations(gene, variant, tumor_type, max_results * 2)
        return [a for a in all_assocs if a.is_sensitivity()][:max_results]

    async def fetch_resistance_associations(
        self,
        gene: str,
        variant: str | None = None,
        tumor_type: str | None = None,
        max_results: int = 25,
    ) -> list[VICCAssociation]:
        """Fetch only resistance associations.

        Args:
            gene: Gene symbol
            variant: Optional variant notation
            tumor_type: Optional tumor type filter
            max_results: Maximum results

        Returns:
            List of resistance associations
        """
        all_assocs = await self.fetch_associations(gene, variant, tumor_type, max_results * 2)
        return [a for a in all_assocs if a.is_resistance()][:max_results]
