"""ClinicalTrials.gov API client for fetching clinical trial data.

ARCHITECTURE:
    Gene + Variant + Tumor Type → ClinicalTrials.gov API v2 → Active trials

Fetches recruiting clinical trials for cancer biomarkers to support
Tier II classification for variants with active investigational therapies.

Key Design:
- Async HTTP with connection pooling (httpx.AsyncClient)
- Searches by gene+variant keyword and cancer type
- Filters for recruiting/active trials only
- Returns structured trial information
"""

from typing import Any
from dataclasses import dataclass

import httpx


class ClinicalTrialsError(Exception):
    """Exception raised for ClinicalTrials.gov API errors."""
    pass


@dataclass
class ClinicalTrial:
    """A clinical trial from ClinicalTrials.gov."""

    nct_id: str
    title: str
    status: str  # RECRUITING, ACTIVE_NOT_RECRUITING, etc.
    phase: str | None
    conditions: list[str]
    interventions: list[str]
    brief_summary: str | None
    eligibility_criteria: str | None
    sponsor: str | None
    url: str

    def is_recruiting(self) -> bool:
        """Check if trial is actively recruiting."""
        return self.status in ['RECRUITING', 'ENROLLING_BY_INVITATION']

    def is_active(self) -> bool:
        """Check if trial is active (recruiting or not)."""
        return self.status in [
            'RECRUITING',
            'ENROLLING_BY_INVITATION',
            'ACTIVE_NOT_RECRUITING',
            'NOT_YET_RECRUITING'
        ]

    def mentions_variant(self, variant: str, gene: str | None = None) -> bool:
        """Check if trial mentions the specific variant for the given gene.

        Args:
            variant: Variant notation (e.g., "G12D", "V600E")
            gene: Gene symbol (e.g., "NRAS", "BRAF"). If provided, ensures
                  the variant is mentioned in context of this gene to avoid
                  false positives (e.g., KRAS G12D trial matching NRAS G12D query).
        """
        variant_upper = variant.upper()
        gene_upper = gene.upper() if gene else None

        # Combine all text to search
        search_texts = [self.title.upper()]
        if self.eligibility_criteria:
            search_texts.append(self.eligibility_criteria.upper())
        if self.brief_summary:
            search_texts.append(self.brief_summary.upper())

        full_text = " ".join(search_texts)

        # If gene is provided, check for gene+variant pattern to avoid cross-gene matches
        # e.g., "KRAS G12D" should not match for NRAS G12D query
        if gene_upper:
            # Check for explicit gene+variant pattern (e.g., "NRAS G12D", "NRAS-G12D", "NRAS:G12D")
            gene_variant_patterns = [
                f"{gene_upper} {variant_upper}",
                f"{gene_upper}-{variant_upper}",
                f"{gene_upper}:{variant_upper}",
                f"{gene_upper}({variant_upper})",
            ]

            for pattern in gene_variant_patterns:
                if pattern in full_text:
                    return True

            # Also check if the gene is mentioned AND the variant is mentioned
            # but make sure no OTHER gene is mentioned with this variant
            if gene_upper in full_text and variant_upper in full_text:
                # Check for other common genes that might have the same variant
                other_genes = ['KRAS', 'NRAS', 'HRAS', 'BRAF', 'EGFR', 'PIK3CA']
                other_genes = [g for g in other_genes if g != gene_upper]

                # If another gene is explicitly paired with this variant, don't match
                for other_gene in other_genes:
                    other_patterns = [
                        f"{other_gene} {variant_upper}",
                        f"{other_gene}-{variant_upper}",
                        f"{other_gene}:{variant_upper}",
                        f"{other_gene}({variant_upper})",
                    ]
                    if any(p in full_text for p in other_patterns):
                        # Another gene is paired with this variant - don't match
                        return False

                # Gene and variant both present, no conflicting gene-variant pair found
                return True

            return False

        # Legacy behavior when no gene specified - just check for variant
        return variant_upper in full_text

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'nct_id': self.nct_id,
            'title': self.title,
            'status': self.status,
            'phase': self.phase,
            'conditions': self.conditions,
            'interventions': self.interventions,
            'brief_summary': self.brief_summary[:500] if self.brief_summary else None,
            'sponsor': self.sponsor,
            'url': self.url,
        }


class ClinicalTrialsClient:
    """Client for ClinicalTrials.gov API v2.

    Uses the modern v2 API (launched March 2024) to search for
    clinical trials by gene, variant, and cancer type.

    API Documentation: https://clinicaltrials.gov/data-api/api
    """

    BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_PAGE_SIZE = 20

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        """Initialize the ClinicalTrials client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ClinicalTrialsClient":
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

    def _build_search_query(
        self,
        gene: str,
        variant: str | None = None,
        tumor_type: str | None = None,
    ) -> str:
        """Build search query string.

        Args:
            gene: Gene symbol (e.g., "KRAS")
            variant: Optional variant notation (e.g., "G12D")
            tumor_type: Optional tumor type (e.g., "Pancreatic Cancer")

        Returns:
            Search query string
        """
        # Build query parts
        parts = [gene.upper()]

        if variant:
            # Add variant in multiple formats for better matching
            variant_clean = variant.upper().replace('P.', '')
            parts.append(variant_clean)
            # Also try gene+variant concatenated (e.g., "KRASG12D")
            parts.append(f"{gene.upper()}{variant_clean}")

        # Join with OR for broader matching
        query = ' OR '.join(parts)

        return query

    def _parse_study(self, study: dict[str, Any]) -> ClinicalTrial | None:
        """Parse a study from the API response.

        Args:
            study: Raw study data from API

        Returns:
            ClinicalTrial object or None if parsing fails
        """
        try:
            protocol = study.get('protocolSection', {})

            # Identification
            id_module = protocol.get('identificationModule', {})
            nct_id = id_module.get('nctId', '')
            title = id_module.get('briefTitle', '') or id_module.get('officialTitle', '')

            # Status
            status_module = protocol.get('statusModule', {})
            status = status_module.get('overallStatus', 'UNKNOWN')

            # Design - phase
            design_module = protocol.get('designModule', {})
            phases = design_module.get('phases', [])
            phase = phases[0] if phases else None

            # Conditions
            conditions_module = protocol.get('conditionsModule', {})
            conditions = conditions_module.get('conditions', [])

            # Interventions
            arms_module = protocol.get('armsInterventionsModule', {})
            interventions_list = arms_module.get('interventions', [])
            interventions = [
                i.get('name', '')
                for i in interventions_list
                if i.get('name')
            ]

            # Description
            desc_module = protocol.get('descriptionModule', {})
            brief_summary = desc_module.get('briefSummary', '')

            # Eligibility
            eligibility_module = protocol.get('eligibilityModule', {})
            eligibility_criteria = eligibility_module.get('eligibilityCriteria', '')

            # Sponsor
            sponsor_module = protocol.get('sponsorCollaboratorsModule', {})
            lead_sponsor = sponsor_module.get('leadSponsor', {})
            sponsor = lead_sponsor.get('name', '')

            # Build URL
            url = f"https://clinicaltrials.gov/study/{nct_id}"

            return ClinicalTrial(
                nct_id=nct_id,
                title=title,
                status=status,
                phase=phase,
                conditions=conditions,
                interventions=interventions,
                brief_summary=brief_summary,
                eligibility_criteria=eligibility_criteria,
                sponsor=sponsor,
                url=url,
            )
        except Exception:
            return None

    async def search_trials(
        self,
        gene: str,
        variant: str | None = None,
        tumor_type: str | None = None,
        recruiting_only: bool = True,
        max_results: int = 10,
    ) -> list[ClinicalTrial]:
        """Search for clinical trials by gene/variant/tumor type.

        Args:
            gene: Gene symbol (e.g., "KRAS")
            variant: Optional variant notation (e.g., "G12D")
            tumor_type: Optional tumor type filter
            recruiting_only: If True, only return recruiting trials
            max_results: Maximum number of results

        Returns:
            List of ClinicalTrial objects
        """
        client = self._get_client()

        # Build query
        query = self._build_search_query(gene, variant, tumor_type)

        # Build parameters
        params: dict[str, Any] = {
            'query.term': query,
            'pageSize': min(max_results * 2, 50),  # Fetch extra for filtering
            'countTotal': 'true',
            'format': 'json',
        }

        # Add condition filter if tumor type specified
        if tumor_type:
            params['query.cond'] = tumor_type

        # Filter by status if recruiting only
        if recruiting_only:
            params['filter.overallStatus'] = 'RECRUITING|ENROLLING_BY_INVITATION|NOT_YET_RECRUITING'
        else:
            params['filter.overallStatus'] = 'RECRUITING|ENROLLING_BY_INVITATION|NOT_YET_RECRUITING|ACTIVE_NOT_RECRUITING'

        try:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            # Don't fail the pipeline on clinical trials API error
            print(f"ClinicalTrials.gov API warning: {e}")
            return []
        except Exception as e:
            print(f"ClinicalTrials.gov parse warning: {e}")
            return []

        # Parse studies
        studies = data.get('studies', [])
        trials = []

        for study in studies:
            trial = self._parse_study(study)
            if trial is None:
                continue

            # Filter by variant mention if variant specified
            # Pass gene to avoid false positives (e.g., KRAS G12D matching NRAS G12D query)
            if variant and not trial.mentions_variant(variant, gene=gene):
                # Still include if it mentions the gene prominently
                if gene.upper() not in trial.title.upper():
                    continue

            trials.append(trial)

            if len(trials) >= max_results:
                break

        return trials

    async def search_variant_specific_trials(
        self,
        gene: str,
        variant: str,
        tumor_type: str | None = None,
        max_results: int = 5,
    ) -> list[ClinicalTrial]:
        """Search for trials that specifically mention the variant.

        This is more restrictive than search_trials - only returns
        trials where the variant is explicitly mentioned.

        Args:
            gene: Gene symbol
            variant: Variant notation (required)
            tumor_type: Optional tumor type filter
            max_results: Maximum results

        Returns:
            List of variant-specific trials
        """
        # First get general trials
        all_trials = await self.search_trials(
            gene=gene,
            variant=variant,
            tumor_type=tumor_type,
            recruiting_only=True,
            max_results=max_results * 3,  # Fetch more to filter
        )

        # Filter to only those mentioning the variant for this gene
        variant_specific = [
            t for t in all_trials
            if t.mentions_variant(variant, gene=gene)
        ]

        return variant_specific[:max_results]

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
