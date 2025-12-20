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
    biomarker_approved: bool  # True if biomarker is in positive context
    biomarker_excluded: bool  # True if biomarker is in exclusion context
    tumor_types: list[str]  # Tumor types mentioned in indications
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

    # Known oncology drugs with their biomarker associations
    # This serves as a curated lookup for common queries
    ONCOLOGY_DRUG_BIOMARKERS: dict[str, dict] = {
        # KIT D816V drugs
        "AYVAKIT": {
            "gene": "KIT",
            "variants": ["D816V", "D816"],
            "tumor_types": ["systemic mastocytosis", "asm", "sm-ahn", "mcl"],
            "biomarker_approved": True,
        },
        "RYDAPT": {
            "gene": "KIT",
            "variants": ["D816V", "D816"],
            "tumor_types": ["systemic mastocytosis", "asm"],
            "biomarker_approved": True,
        },
        "GLEEVEC": {
            "gene": "KIT",
            "variants": ["D816V"],
            "tumor_types": ["gist", "gastrointestinal stromal"],
            "biomarker_excluded": True,  # "without D816V"
            "note": "Approved for GIST but EXCLUDES D816V mutations",
        },
        "IMATINIB": {
            "gene": "KIT",
            "variants": ["D816V"],
            "tumor_types": ["gist", "gastrointestinal stromal", "systemic mastocytosis"],
            "biomarker_excluded": True,  # "without D816V" for SM
        },
        # EGFR T790M drugs
        "TAGRISSO": {
            "gene": "EGFR",
            "variants": ["T790M"],
            "tumor_types": ["nsclc", "non-small cell lung cancer"],
            "biomarker_approved": True,
        },
        # BRAF V600 drugs
        "TAFINLAR": {
            "gene": "BRAF",
            "variants": ["V600E", "V600K"],
            "tumor_types": ["melanoma", "nsclc", "anaplastic thyroid"],
            "biomarker_approved": True,
        },
        "ZELBORAF": {
            "gene": "BRAF",
            "variants": ["V600E"],
            "tumor_types": ["melanoma"],
            "biomarker_approved": True,
        },
        "BRAFTOVI": {
            "gene": "BRAF",
            "variants": ["V600E", "V600K"],
            "tumor_types": ["melanoma", "colorectal"],
            "biomarker_approved": True,
        },
        # KRAS G12C drugs
        "LUMAKRAS": {
            "gene": "KRAS",
            "variants": ["G12C"],
            "tumor_types": ["nsclc", "non-small cell lung cancer"],
            "biomarker_approved": True,
        },
        "KRAZATI": {
            "gene": "KRAS",
            "variants": ["G12C"],
            "tumor_types": ["nsclc", "non-small cell lung cancer"],
            "biomarker_approved": True,
        },
    }

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        """Initialize the FDA Label client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
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

    def _extract_tumor_types(self, indications: str) -> list[str]:
        """Extract tumor types mentioned in indications."""
        tumor_keywords = [
            "non-small cell lung cancer", "nsclc",
            "melanoma",
            "colorectal cancer", "colorectal",
            "breast cancer",
            "gastrointestinal stromal tumor", "gist",
            "systemic mastocytosis", "asm", "sm-ahn", "mcl",
            "thyroid cancer", "anaplastic thyroid",
            "renal cell carcinoma",
            "hepatocellular carcinoma",
            "pancreatic cancer",
            "ovarian cancer",
            "prostate cancer",
            "acute myeloid leukemia", "aml",
        ]

        indications_lower = indications.lower()
        found = []
        for tumor in tumor_keywords:
            if tumor in indications_lower:
                found.append(tumor)

        return list(set(found))

    def _check_biomarker_context(
        self,
        indications: str,
        biomarker: str
    ) -> tuple[bool, bool, str | None]:
        """Check if biomarker is approved or excluded in indications.

        Args:
            indications: Full indications text
            biomarker: Biomarker to check (e.g., "D816V")

        Returns:
            Tuple of (is_approved, is_excluded, context_snippet)
        """
        indications_lower = indications.lower()
        biomarker_lower = biomarker.lower()

        if biomarker_lower not in indications_lower:
            return False, False, None

        # Find the biomarker mention
        idx = indications_lower.find(biomarker_lower)
        context_start = max(0, idx - 150)
        context_end = min(len(indications), idx + len(biomarker) + 150)
        context = indications[context_start:context_end]
        context_lower = context.lower()

        # Check for exclusion patterns
        exclusion_patterns = [
            f"without the {biomarker_lower}",
            f"without {biomarker_lower}",
            f"no {biomarker_lower}",
            f"not {biomarker_lower}",
            f"excluding {biomarker_lower}",
            f"absence of {biomarker_lower}",
            f"negative for {biomarker_lower}",
            f"{biomarker_lower} mutation-negative",
            f"{biomarker_lower}-negative",
        ]

        is_excluded = any(pattern in context_lower for pattern in exclusion_patterns)

        # Check for positive/approval patterns
        approval_patterns = [
            f"with {biomarker_lower}",
            f"{biomarker_lower} mutation-positive",
            f"{biomarker_lower}-positive",
            f"positive for {biomarker_lower}",
            f"harboring {biomarker_lower}",
            f"expressing {biomarker_lower}",
        ]

        is_approved = any(pattern in context_lower for pattern in approval_patterns)

        # If mentioned but not explicitly excluded, consider it approved
        # (some labels just state the indication without "positive" language)
        if not is_excluded and not is_approved:
            # Check if it's in a resistance context
            resistance_patterns = [
                "not considered sensitive",
                "resistant to",
                "resistance to",
                "lack of response",
                "poor response",
            ]
            is_resistance = any(pattern in context_lower for pattern in resistance_patterns)
            if not is_resistance:
                is_approved = True

        return is_approved, is_excluded, context

    async def query_drug_label(
        self,
        brand_name: str,
        biomarker: str | None = None,
    ) -> DrugLabelResult | None:
        """Query FDA label for a specific drug by brand name.

        Args:
            brand_name: Drug brand name (e.g., "AYVAKIT", "TAGRISSO")
            biomarker: Optional biomarker to check context for (e.g., "D816V")

        Returns:
            DrugLabelResult or None if not found
        """
        client = self._get_client()

        params = {
            "search": f'openfda.brand_name:"{brand_name}"',
            "limit": 1
        }

        try:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise FDALabelError(f"FDA API error: {e}")
        except Exception as e:
            raise FDALabelError(f"Failed to query FDA API: {e}")

        if "results" not in data or len(data["results"]) == 0:
            return None

        label = data["results"][0]

        # Extract indications
        indications_raw = label.get("indications_and_usage", [])
        if isinstance(indications_raw, list):
            indications = " ".join(str(item) for item in indications_raw)
        else:
            indications = str(indications_raw)

        # Get generic name
        openfda = label.get("openfda", {})
        generic_names = openfda.get("generic_name", [])
        generic_name = generic_names[0] if generic_names else None

        # Extract tumor types
        tumor_types = self._extract_tumor_types(indications)

        # Check biomarker context if provided
        biomarker_context = None
        biomarker_approved = False
        biomarker_excluded = False

        if biomarker:
            biomarker_approved, biomarker_excluded, biomarker_context = \
                self._check_biomarker_context(indications, biomarker)

        return DrugLabelResult(
            brand_name=brand_name.upper(),
            generic_name=generic_name,
            indications=indications,
            biomarker_context=biomarker_context,
            biomarker_approved=biomarker_approved,
            biomarker_excluded=biomarker_excluded,
            tumor_types=tumor_types,
            full_label=label,
        )

    async def check_variant_approval(
        self,
        gene: str,
        variant: str,
        tumor_type: str,
    ) -> dict[str, Any]:
        """Check if a variant is approved for a tumor type across known drugs.

        This uses the curated ONCOLOGY_DRUG_BIOMARKERS lookup plus live API queries.

        Args:
            gene: Gene symbol (e.g., "KIT")
            variant: Variant notation (e.g., "D816V")
            tumor_type: Tumor type (e.g., "Systemic Mastocytosis")

        Returns:
            Dict with 'approved_drugs', 'excluded_drugs', and 'details'
        """
        gene_upper = gene.upper()
        variant_upper = variant.upper()
        tumor_lower = tumor_type.lower()

        approved_drugs: list[str] = []
        excluded_drugs: list[str] = []
        details: list[dict] = []

        # Check curated lookup first
        for drug_name, info in self.ONCOLOGY_DRUG_BIOMARKERS.items():
            if info.get("gene") != gene_upper:
                continue

            # Check if variant matches
            variants = info.get("variants", [])
            variant_match = any(
                v.upper() in variant_upper or variant_upper in v.upper()
                for v in variants
            )
            if not variant_match:
                continue

            # Check if tumor type matches
            drug_tumors = info.get("tumor_types", [])
            tumor_match = any(
                t in tumor_lower or tumor_lower in t
                for t in drug_tumors
            )
            if not tumor_match:
                continue

            # Determine if approved or excluded
            if info.get("biomarker_excluded"):
                excluded_drugs.append(drug_name)
                details.append({
                    "drug": drug_name,
                    "status": "excluded",
                    "note": info.get("note", "Biomarker explicitly excluded"),
                })
            elif info.get("biomarker_approved"):
                approved_drugs.append(drug_name)
                details.append({
                    "drug": drug_name,
                    "status": "approved",
                    "note": f"FDA-approved for {variant} in {tumor_type}",
                })

        # Query live API for drugs in approved/excluded lists
        for drug_name in approved_drugs + excluded_drugs:
            try:
                result = await self.query_drug_label(drug_name, biomarker=variant)
                if result:
                    # Update details with live context
                    for detail in details:
                        if detail["drug"] == drug_name:
                            detail["context"] = result.biomarker_context
                            detail["tumor_types"] = result.tumor_types
            except Exception:
                pass  # Continue even if live query fails

        return {
            "gene": gene,
            "variant": variant,
            "tumor_type": tumor_type,
            "approved_drugs": approved_drugs,
            "excluded_drugs": excluded_drugs,
            "has_approval": len(approved_drugs) > 0,
            "is_excluded": len(excluded_drugs) > 0 and len(approved_drugs) == 0,
            "details": details,
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Convenience function for one-off queries
async def query_drug_label(
    brand_name: str,
    biomarker: str | None = None,
) -> DrugLabelResult | None:
    """Query FDA label for a drug by brand name.

    Args:
        brand_name: Drug brand name (e.g., "AYVAKIT")
        biomarker: Optional biomarker to check (e.g., "D816V")

    Returns:
        DrugLabelResult or None
    """
    async with FDALabelClient() as client:
        return await client.query_drug_label(brand_name, biomarker)


async def check_variant_approval(
    gene: str,
    variant: str,
    tumor_type: str,
) -> dict[str, Any]:
    """Check if a variant is approved for a tumor type.

    Args:
        gene: Gene symbol
        variant: Variant notation
        tumor_type: Tumor type

    Returns:
        Dict with approval status and details
    """
    async with FDALabelClient() as client:
        return await client.check_variant_approval(gene, variant, tumor_type)
