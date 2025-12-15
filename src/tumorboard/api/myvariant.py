"""MyVariant.info API client for fetching variant evidence.

ARCHITECTURE:
    Gene + Variant → MyVariant.info API → Evidence (CIViC/ClinVar/COSMIC)

Aggregates variant information from multiple databases for LLM assessment.

Key Design:
- Async HTTP with connection pooling (httpx.AsyncClient)
- Retry with exponential backoff (tenacity)
- Structured parsing to typed Evidence models
- Context manager for session cleanup
"""

import re
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from tumorboard.api.myvariant_models import MyVariantHit, MyVariantResponse

from tumorboard.models.evidence.civic import  CIViCEvidence
from tumorboard.models.evidence.clinvar import ClinVarEvidence
from tumorboard.models.evidence.cosmic import COSMICEvidence
from tumorboard.models.evidence.evidence import Evidence


class MyVariantAPIError(Exception):
    """Exception raised for MyVariant API errors."""

    pass


class MyVariantClient:
    """Client for MyVariant.info API with CIViC fallback.

    MyVariant.info aggregates variant annotations from multiple sources
    including CIViC, ClinVar, COSMIC, and more.

    When MyVariant returns no evidence, falls back to direct CIViC API
    queries to handle fusions, amplifications, and poorly-indexed variants.
    """

    BASE_URL = "https://myvariant.info/v1"
    CIVIC_API = "https://civicdb.org/api"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = 3,
    ) -> None:
        """Initialize the MyVariant client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "MyVariantClient":
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
    async def _query(self, query: str, fields: list[str] | None = None) -> dict[str, Any]:
        """Execute a query against MyVariant API.

        Args:
            query: Query string (e.g., "BRAF:V600E" or "chr7:140453136")
            fields: Specific fields to retrieve

        Returns:
            API response as dictionary

        Raises:
            MyVariantAPIError: If the API request fails
        """
        client = self._get_client()
        params: dict[str, str] = {"q": query}

        if fields:
            params["fields"] = ",".join(fields)

        response = await client.get(f"{self.BASE_URL}/query", params=params)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise MyVariantAPIError(f"API error: {data['error']}")

        return data

    async def get_variant(self, variant_id: str) -> dict[str, Any]:
        """Get variant by ID.

        Args:
            variant_id: Variant identifier (HGVS, dbSNP, etc.)

        Returns:
            Variant data
        """
        client = self._get_client()
        response = await client.get(f"{self.BASE_URL}/variant/{variant_id}")
        response.raise_for_status()
        return response.json()

    def _parse_civic_evidence(self, civic_data: dict[str, Any] | list[Any]) -> list[CIViCEvidence]:
        """Parse CIViC data into evidence objects.

        Supports both old API format (evidence_items) and new API format (molecularProfiles).

        Args:
            civic_data: Raw CIViC data from API

        Returns:
            List of CIViC evidence objects
        """
        evidence_list: list[CIViCEvidence] = []

        # Handle both single dict and list of dicts
        items = civic_data if isinstance(civic_data, list) else [civic_data]

        for item in items:
            if not isinstance(item, dict):
                continue

            # NEW API FORMAT: molecularProfiles with nested evidenceItems
            if "molecularProfiles" in item:
                for mp in item.get("molecularProfiles", []):
                    if not isinstance(mp, dict):
                        continue
                    for ev_item in mp.get("evidenceItems", []):
                        # Extract disease name
                        disease_data = ev_item.get("disease", {})
                        disease = disease_data.get("name") if isinstance(disease_data, dict) else None

                        # Extract therapies (new API uses "therapies" instead of "drugs")
                        therapies = ev_item.get("therapies", [])
                        drugs = [t.get("name", "") for t in therapies if isinstance(t, dict)]

                        evidence_list.append(
                            CIViCEvidence(
                                evidence_type=ev_item.get("evidenceType"),  # camelCase in new API
                                evidence_level=ev_item.get("evidenceLevel"),  # camelCase in new API
                                evidence_direction=ev_item.get("evidenceDirection"),
                                clinical_significance=ev_item.get("significance"),  # "significance" in new API
                                disease=disease,
                                drugs=drugs,
                                description=ev_item.get("description"),
                                source=ev_item.get("source", {}).get("name")
                                if isinstance(ev_item.get("source"), dict)
                                else None,
                                rating=ev_item.get("rating"),
                            )
                        )
            # OLD API FORMAT: evidence_items
            elif "evidence_items" in item:
                for ev_item in item.get("evidence_items", []):
                    evidence_list.append(
                        CIViCEvidence(
                            evidence_type=ev_item.get("evidence_type"),
                            evidence_level=ev_item.get("evidence_level"),
                            evidence_direction=ev_item.get("evidence_direction"),
                            clinical_significance=ev_item.get("clinical_significance"),
                            disease=ev_item.get("disease", {}).get("name")
                            if isinstance(ev_item.get("disease"), dict)
                            else None,
                            drugs=[
                                drug.get("name", "")
                                for drug in ev_item.get("drugs", [])
                                if isinstance(drug, dict)
                            ],
                            description=ev_item.get("description"),
                            source=ev_item.get("source", {}).get("name")
                            if isinstance(ev_item.get("source"), dict)
                            else None,
                            rating=ev_item.get("rating"),
                        )
                    )
            else:
                # Direct evidence object (legacy format)
                evidence_list.append(
                    CIViCEvidence(
                        evidence_type=item.get("evidence_type"),
                        evidence_level=item.get("evidence_level"),
                        evidence_direction=item.get("evidence_direction"),
                        clinical_significance=item.get("clinical_significance"),
                        disease=item.get("disease"),
                        drugs=item.get("drugs", []) if isinstance(item.get("drugs"), list) else [],
                        description=item.get("description"),
                        source=item.get("source"),
                        rating=item.get("rating"),
                    )
                )

        return evidence_list

    def _parse_clinvar_evidence(
        self, clinvar_data: dict[str, Any] | list[Any]
    ) -> list[ClinVarEvidence]:
        """Parse ClinVar data into evidence objects.

        Args:
            clinvar_data: Raw ClinVar data from API

        Returns:
            List of ClinVar evidence objects
        """
        evidence_list: list[ClinVarEvidence] = []

        # Handle both single dict and list of dicts
        items = clinvar_data if isinstance(clinvar_data, list) else [clinvar_data]

        for item in items:
            if not isinstance(item, dict):
                continue

            # Extract clinical significance
            clin_sig = item.get("clinical_significance")
            if isinstance(clin_sig, list):
                clin_sig = ", ".join(str(s) for s in clin_sig)

            # Extract conditions
            conditions = []
            if "conditions" in item:
                cond_data = item["conditions"]
                if isinstance(cond_data, list):
                    for cond in cond_data:
                        if isinstance(cond, dict):
                            conditions.append(cond.get("name", ""))
                        else:
                            conditions.append(str(cond))
                elif isinstance(cond_data, dict):
                    conditions.append(cond_data.get("name", ""))

            evidence_list.append(
                ClinVarEvidence(
                    clinical_significance=str(clin_sig) if clin_sig else None,
                    review_status=item.get("review_status"),
                    conditions=conditions,
                    last_evaluated=item.get("last_evaluated"),
                    variation_id=str(item.get("variation_id")) if "variation_id" in item else None,
                )
            )

        return evidence_list

    def _parse_cosmic_evidence(
        self, cosmic_data: dict[str, Any] | list[Any]
    ) -> list[COSMICEvidence]:
        """Parse COSMIC data into evidence objects.

        Args:
            cosmic_data: Raw COSMIC data from API

        Returns:
            List of COSMIC evidence objects
        """
        evidence_list: list[COSMICEvidence] = []

        # Handle both single dict and list of dicts
        items = cosmic_data if isinstance(cosmic_data, list) else [cosmic_data]

        for item in items:
            if not isinstance(item, dict):
                continue

            evidence_list.append(
                COSMICEvidence(
                    mutation_id=item.get("mutation_id"),
                    primary_site=item.get("primary_site"),
                    site_subtype=item.get("site_subtype"),
                    primary_histology=item.get("primary_histology"),
                    histology_subtype=item.get("histology_subtype"),
                    sample_count=item.get("sample_count"),
                    mutation_somatic_status=item.get("mutation_somatic_status"),
                )
            )

        return evidence_list

    def _extract_from_hit(
        self, hit: MyVariantHit, gene: str, variant: str
    ) -> Evidence:
        """Extract Evidence fields from a parsed MyVariantHit using Pydantic models.

        This method uses Pydantic's automatic parsing instead of manual nested
        dictionary navigation, making it cleaner and more maintainable.

        Args:
            hit: Parsed MyVariant API hit
            gene: Gene symbol
            variant: Variant notation

        Returns:
            Evidence object with all extracted fields
        """
        # Extract database identifiers using Pydantic models
        cosmic_id = None
        if hit.cosmic:
            cosmic_data = hit.cosmic if isinstance(hit.cosmic, list) else [hit.cosmic]
            if cosmic_data and cosmic_data[0].cosmic_id:
                cosmic_id = cosmic_data[0].cosmic_id

        ncbi_gene_id = None
        if hit.entrezgene:
            ncbi_gene_id = str(hit.entrezgene)
        elif hit.dbsnp and hit.dbsnp.gene and hit.dbsnp.gene.geneid:
            ncbi_gene_id = str(hit.dbsnp.gene.geneid)

        dbsnp_id = None
        if hit.dbsnp and hit.dbsnp.rsid:
            rsid = hit.dbsnp.rsid
            dbsnp_id = f"rs{rsid}" if not rsid.startswith("rs") else rsid

        # Extract ClinVar data
        clinvar_id = None
        clinvar_clinical_significance = None
        clinvar_accession = None
        if hit.clinvar:
            clinvar_list = hit.clinvar if isinstance(hit.clinvar, list) else [hit.clinvar]
            if clinvar_list:
                first_clinvar = clinvar_list[0]
                if first_clinvar.variant_id:
                    clinvar_id = str(first_clinvar.variant_id)
                # Extract from rcv array
                if first_clinvar.rcv and len(first_clinvar.rcv) > 0:
                    first_rcv = first_clinvar.rcv[0]
                    if first_rcv.clinical_significance:
                        clinvar_clinical_significance = first_rcv.clinical_significance
                    if first_rcv.accession:
                        clinvar_accession = first_rcv.accession

        # Extract HGVS notations
        hgvs_genomic = None
        hgvs_protein = None
        hgvs_transcript = None

        # Use variant id as genomic HGVS if it looks like HGVS
        if hit.id and (hit.id.startswith("chr") or hit.id.startswith("NC_")):
            hgvs_genomic = hit.id

        if hit.hgvs:
            hgvs_list = [hit.hgvs] if isinstance(hit.hgvs, str) else hit.hgvs
            for hgvs in hgvs_list:
                if hgvs.startswith("chr") or hgvs.startswith("NC_"):
                    hgvs_genomic = hgvs
                elif ":p." in hgvs and not hgvs_protein:
                    hgvs_protein = hgvs
                elif ":c." in hgvs and not hgvs_transcript:
                    hgvs_transcript = hgvs

        # Extract functional annotations using Pydantic models
        snpeff_effect = None
        transcript_id = None
        transcript_consequence = None
        if hit.snpeff and hit.snpeff.ann:
            ann = hit.snpeff.ann
            ann_data = ann if isinstance(ann, list) else [ann]
            if ann_data:
                first_ann = ann_data[0]
                snpeff_effect = first_ann.effect
                transcript_id = first_ann.feature_id
                transcript_consequence = first_ann.effect

        polyphen2_prediction = None
        if hit.dbnsfp and hit.dbnsfp.polyphen2 and hit.dbnsfp.polyphen2.hdiv:
            pred = hit.dbnsfp.polyphen2.hdiv.pred
            # Handle both string and list[str] from API
            if isinstance(pred, list):
                polyphen2_prediction = pred[0] if pred else None
            else:
                polyphen2_prediction = pred

        cadd_score = None
        # Try dbnsfp first, then top-level cadd
        if hit.dbnsfp and hit.dbnsfp.cadd and hit.dbnsfp.cadd.phred:
            try:
                cadd_score = float(hit.dbnsfp.cadd.phred)
            except (ValueError, TypeError):
                pass
        if cadd_score is None and hit.cadd and hit.cadd.phred:
            try:
                cadd_score = float(hit.cadd.phred)
            except (ValueError, TypeError):
                pass

        gnomad_exome_af = None
        if hit.gnomad_exome and hit.gnomad_exome.af and hit.gnomad_exome.af.af:
            try:
                gnomad_exome_af = float(hit.gnomad_exome.af.af)
            except (ValueError, TypeError):
                pass

        # Extract AlphaMissense prediction
        alphamissense_score = None
        alphamissense_prediction = None
        if hit.dbnsfp and hit.dbnsfp.alphamissense:
            am = hit.dbnsfp.alphamissense
            # Handle score (can be float or list[float])
            if am.score is not None:
                try:
                    if isinstance(am.score, list):
                        alphamissense_score = float(am.score[0]) if am.score else None
                    else:
                        alphamissense_score = float(am.score)
                except (ValueError, TypeError):
                    pass
            # Handle prediction (can be str or list[str])
            if am.pred is not None:
                if isinstance(am.pred, list):
                    alphamissense_prediction = am.pred[0] if am.pred else None
                else:
                    alphamissense_prediction = am.pred

        # Parse evidence using existing parsers (CIViC, ClinVar, COSMIC)
        civic_evidence = []
        if hit.civic:
            civic_evidence = self._parse_civic_evidence(hit.civic)

        clinvar_evidence = []
        if hit.clinvar:
            # Convert back to dict for existing parser
            clinvar_data = hit.clinvar
            if isinstance(clinvar_data, list):
                clinvar_evidence = self._parse_clinvar_evidence([c.model_dump() for c in clinvar_data])
            else:
                clinvar_evidence = self._parse_clinvar_evidence(clinvar_data.model_dump())

        cosmic_evidence = []
        if hit.cosmic:
            # Convert back to dict for existing parser
            cosmic_data = hit.cosmic
            if isinstance(cosmic_data, list):
                cosmic_evidence = self._parse_cosmic_evidence([c.model_dump() for c in cosmic_data])
            else:
                cosmic_evidence = self._parse_cosmic_evidence(cosmic_data.model_dump())

        return Evidence(
            variant_id=hit.id,
            gene=gene,
            variant=variant,
            cosmic_id=cosmic_id,
            ncbi_gene_id=ncbi_gene_id,
            dbsnp_id=dbsnp_id,
            clinvar_id=clinvar_id,
            clinvar_clinical_significance=clinvar_clinical_significance,
            clinvar_accession=clinvar_accession,
            hgvs_genomic=hgvs_genomic,
            hgvs_protein=hgvs_protein,
            hgvs_transcript=hgvs_transcript,
            snpeff_effect=snpeff_effect,
            polyphen2_prediction=polyphen2_prediction,
            cadd_score=cadd_score,
            gnomad_exome_af=gnomad_exome_af,
            alphamissense_score=alphamissense_score,
            alphamissense_prediction=alphamissense_prediction,
            transcript_id=transcript_id,
            transcript_consequence=transcript_consequence,
            civic=civic_evidence,
            clinvar=clinvar_evidence,
            cosmic=cosmic_evidence,
            raw_data=hit.model_dump(by_alias=True),
        )

    async def fetch_tumor_types(self, gene: str, variant: str) -> list[str]:
        """
        Fetch associated tumor types from CIViC for a given gene and variant.

        This is useful for UI autocomplete/typeahead features to suggest
        relevant tumor types based on available evidence.

        Args:
            gene: Gene symbol (e.g., "BRAF", "EGFR")
            variant: Variant notation (e.g., "V600_E", "L858R")

        Returns:
            List of unique tumor/disease names from CIViC evidence
        """
        gene = gene.upper()
        variant_clean = variant.strip().upper()

        # Construct molecular profile name
        if any(kw in variant_clean for kw in ["FUSION", "FUS", "REARRANGEMENT"]):
            mp_name = f"{gene} FUSION"
        elif any(kw in variant_clean for kw in ["AMP", "AMPLIFICATION", "OVEREXPRESSION"]):
            mp_name = f"{gene} AMPLIFICATION"
        else:
            mp_name = f"{gene} {variant_clean}"

        client = self._get_client()

        try:
            # GraphQL query to fetch disease names
            query = """
            query($name: String!) {
              molecularProfiles(name: $name) {
                nodes {
                  evidenceItems {
                    nodes {
                      disease {
                        name
                      }
                    }
                  }
                }
              }
            }
            """

            response = await client.post(
                f"{self.CIVIC_API}/graphql",
                json={"query": query, "variables": {"name": mp_name}},
            )

            if response.status_code != 200:
                return []

            data = response.json()
            profiles = data.get("data", {}).get("molecularProfiles", {}).get("nodes", [])

            # Extract unique disease names
            tumor_types = set()
            for profile in profiles:
                evidence_items = profile.get("evidenceItems", {}).get("nodes", [])
                for item in evidence_items:
                    disease = item.get("disease", {})
                    if disease and disease.get("name"):
                        tumor_types.add(disease["name"])

            return sorted(list(tumor_types))

        except Exception:
            # Silently return empty list on error
            return []

    async def _fetch_clinvar_fallback(self, gene: str, variant: str) -> dict[str, Any] | None:
        """
        Fallback to fetch ClinVar data directly from NCBI E-utilities when MyVariant doesn't have it.

        Uses NCBI's E-utilities API to search ClinVar for the variant.

        Args:
            gene: Gene symbol (e.g., "EGFR")
            variant: Variant notation (e.g., "L858R")

        Returns:
            ClinVar data dict with variant_id, clinical_significance, and accession if found
        """
        try:
            client = self._get_client()

            # Search ClinVar using NCBI E-utilities
            # Use [gene] field and simple text search for variant
            search_term = f"{gene}[gene] AND {variant}"
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            search_params = {
                "db": "clinvar",
                "term": search_term,
                "retmode": "json",
                "retmax": 1
            }

            search_response = await client.get(search_url, params=search_params)
            if search_response.status_code != 200:
                return None

            search_data = search_response.json()
            id_list = search_data.get("esearchresult", {}).get("idlist", [])

            if not id_list:
                return None

            # Fetch summary for the variant
            variant_id = id_list[0]
            summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            summary_params = {
                "db": "clinvar",
                "id": variant_id,
                "retmode": "json"
            }

            summary_response = await client.get(summary_url, params=summary_params)
            if summary_response.status_code != 200:
                return None

            summary_data = summary_response.json()
            result = summary_data.get("result", {}).get(variant_id, {})

            # Extract relevant fields
            clinical_significance = result.get("clinical_significance", {}).get("description")
            accession = result.get("accession")

            if clinical_significance or accession:
                return {
                    "variant_id": variant_id,
                    "clinical_significance": clinical_significance,
                    "accession": accession
                }

            return None

        except Exception:
            return None

    async def _fetch_civic_fallback(
        self, gene: str, variant: str
    ) -> list[CIViCEvidence]:
        """
        Fallback to direct CIViC GraphQL API when MyVariant returns no evidence.

        Handles fusions, amplifications, and poorly-indexed variants using CIViC V2 GraphQL API.

        Queries both specific variant profiles (e.g., "BRAF V600E") and gene-level profiles
        (e.g., "BRAF MUTATION") to capture broader therapeutic evidence.

        Args:
            gene: Gene symbol (e.g., "ERBB2", "ALK")
            variant: Variant notation (e.g., "amplification", "fusion", "R132H")

        Returns:
            List of CIViC evidence objects
        """
        gene = gene.upper()
        variant_clean = variant.strip().upper()

        # Detect variant type and construct molecular profile names to query
        # We'll query both specific variant and gene-level MUTATION profiles
        mp_names = []

        if any(kw in variant_clean for kw in ["FUSION", "FUS", "REARRANGEMENT"]):
            mp_names = [f"{gene} FUSION"]
        elif any(kw in variant_clean for kw in ["AMP", "AMPLIFICATION", "OVEREXPRESSION"]):
            mp_names = [f"{gene} AMPLIFICATION"]
        else:
            # For SNPs/indels: query specific variant, codon-level, AND gene-level MUTATION
            # Example: ["NRAS Q61K", "NRAS Q61", "NRAS MUTATION"]
            # CIViC often has evidence at codon level (e.g., Q61 covers Q61K/L/R/H)
            mp_names = [
                f"{gene} {variant_clean}",  # Specific variant (e.g., NRAS Q61K)
            ]

            # Extract codon-level variant (e.g., Q61K -> Q61, V600E -> V600)
            # Pattern: letter + digits + optional letter(s) at end
            codon_match = re.match(r'^([A-Z])(\d+)[A-Z]*$', variant_clean)
            if codon_match:
                codon_variant = f"{codon_match.group(1)}{codon_match.group(2)}"
                if codon_variant != variant_clean:  # Only add if different
                    mp_names.append(f"{gene} {codon_variant}")  # Codon level (e.g., NRAS Q61)

            mp_names.append(f"{gene} MUTATION")  # Gene-level profile (often has FDA approvals)

        client = self._get_client()
        all_civic_evidence = []

        # GraphQL query for molecular profiles and evidence
        query = """
        query($name: String!) {
          molecularProfiles(name: $name) {
            nodes {
              id
              name
              evidenceItems {
                nodes {
                  id
                  evidenceType
                  evidenceLevel
                  evidenceDirection
                  significance
                  description
                  disease {
                    name
                  }
                  therapies {
                    id
                    name
                  }
                  source {
                    sourceType
                  }
                }
              }
            }
          }
        }
        """

        try:
            # Query all molecular profile names (specific + gene-level)
            for mp_name in mp_names:
                response = await client.post(
                    f"{self.CIVIC_API}/graphql",
                    json={"query": query, "variables": {"name": mp_name}},
                )

                if response.status_code != 200:
                    continue

                data = response.json()
                profiles = data.get("data", {}).get("molecularProfiles", {}).get("nodes", [])

                if not profiles:
                    continue

                # Parse evidence items from all matching profiles
                for profile in profiles:
                    evidence_items = profile.get("evidenceItems", {}).get("nodes", [])

                    for item in evidence_items:
                        # Extract disease name
                        disease_data = item.get("disease", {})
                        disease = disease_data.get("name") if disease_data else None

                        # Extract therapies
                        therapies = item.get("therapies", [])
                        drugs = [t.get("name", "") for t in therapies if isinstance(t, dict)]

                        # Map GraphQL field names to Evidence model fields
                        all_civic_evidence.append(
                            CIViCEvidence(
                                evidence_type=item.get("evidenceType"),  # camelCase in GraphQL
                                evidence_level=item.get("evidenceLevel"),
                                evidence_direction=item.get("evidenceDirection"),
                                clinical_significance=item.get("significance"),
                                disease=disease,
                                drugs=drugs,
                                description=item.get("description"),
                                source=item.get("source", {}).get("sourceType")
                                if isinstance(item.get("source"), dict)
                                else None,
                                rating=None,  # Rating not in V2 API
                            )
                        )

            return all_civic_evidence

        except Exception as e:
            # Log error but don't fail - return empty evidence
            return []

    async def fetch_evidence(self, gene: str, variant: str) -> Evidence:
        """Fetch evidence for a variant from multiple sources.

        Args:
            gene: Gene symbol (e.g., "BRAF")
            variant: Variant notation (e.g., "V600E")

        Returns:
            Aggregated evidence from all sources

        Raises:
            MyVariantAPIError: If the API request fails
        """
        # Request specific fields from CIViC, ClinVar, COSMIC, and identifiers
        fields = [
            "civic",
            "clinvar",
            "cosmic",
            "dbsnp",
            "cadd",
            "entrezgene",  # NCBI Gene ID
            "cosmic.cosmic_id",  # COSMIC mutation ID
            "clinvar.variant_id",  # ClinVar variation ID
            "clinvar.rcv",  # ClinVar RCV records (contains clinical_significance and accession)
            "dbsnp.rsid",  # dbSNP rs number
            "hgvs",  # HGVS notations (genomic, protein, transcript)
            "snpeff",  # SnpEff effect prediction
            "dbnsfp.polyphen2.hdiv.pred",  # PolyPhen2 prediction
            "dbnsfp.cadd.phred",  # CADD phred score
            "dbnsfp.alphamissense",  # AlphaMissense pathogenicity prediction
            "gnomad_exome.af.af",  # gnomAD exome allele frequency
            "vcf.alt",  # VCF alternative allele
            "vcf.ref",  # VCF reference allele
        ]

        try:
            # Try multiple query strategies to find the variant
            # Strategy 1: Gene with protein notation (e.g., "BRAF p.V600E")
            # This works best with MyVariant API
            protein_notation = f"p.{variant}" if not variant.startswith("p.") else variant
            query = f"{gene} {protein_notation}"
            result = await self._query(query, fields=fields)

            # Strategy 2: If no hits, try simple gene:variant (e.g., "BRAF:V600E")
            if result.get("total", 0) == 0:
                query = f"{gene}:{variant}"
                result = await self._query(query, fields=fields)

            # Strategy 3: If still no hits, try searching by gene name and variant without prefix
            if result.get("total", 0) == 0:
                query = f"{gene} {variant}"
                result = await self._query(query, fields=fields)

            # Parse response using Pydantic
            parsed_response = MyVariantResponse(**result)

            if not parsed_response.hits:
                # No data found in MyVariant - try CIViC and ClinVar fallbacks
                civic_fallback = await self._fetch_civic_fallback(gene, variant)
                clinvar_fallback = await self._fetch_clinvar_fallback(gene, variant)

                # Extract ClinVar data from fallback
                clinvar_id = None
                clinvar_significance = None
                clinvar_accession = None
                if clinvar_fallback:
                    clinvar_id = clinvar_fallback.get("variant_id")
                    clinvar_significance = clinvar_fallback.get("clinical_significance")
                    clinvar_accession = clinvar_fallback.get("accession")

                # Return evidence with fallback data
                return Evidence(
                    variant_id=f"{gene}:{variant}",
                    gene=gene,
                    variant=variant,
                    cosmic_id=None,
                    ncbi_gene_id=None,
                    dbsnp_id=None,
                    clinvar_id=clinvar_id,
                    clinvar_clinical_significance=clinvar_significance,
                    clinvar_accession=clinvar_accession,
                    hgvs_genomic=None,
                    hgvs_protein=None,
                    hgvs_transcript=None,
                    snpeff_effect=None,
                    polyphen2_prediction=None,
                    cadd_score=None,
                    gnomad_exome_af=None,
                    alphamissense_score=None,
                    alphamissense_prediction=None,
                    transcript_id=None,
                    transcript_consequence=None,
                    civic=civic_fallback,  # Use CIViC fallback evidence
                    clinvar=[],
                    cosmic=[],
                    raw_data=result,
                )

            # Use the first hit (most relevant) and extract using Pydantic models
            first_hit = parsed_response.hits[0]
            evidence = self._extract_from_hit(first_hit, gene, variant)

            # If MyVariant returned no CIViC evidence, try CIViC fallback
            if not evidence.civic:
                civic_fallback = await self._fetch_civic_fallback(gene, variant)
                if civic_fallback:
                    # Update evidence with CIViC fallback data
                    evidence.civic = civic_fallback

            # If MyVariant returned no ClinVar data, try ClinVar fallback
            if not evidence.clinvar_id and not evidence.clinvar_clinical_significance:
                clinvar_fallback = await self._fetch_clinvar_fallback(gene, variant)
                if clinvar_fallback:
                    # Update evidence with ClinVar fallback data
                    evidence.clinvar_id = clinvar_fallback.get("variant_id")
                    evidence.clinvar_clinical_significance = clinvar_fallback.get("clinical_significance")
                    evidence.clinvar_accession = clinvar_fallback.get("accession")

            return evidence

        except MyVariantAPIError:
            raise
        except Exception as e:
            raise MyVariantAPIError(f"Failed to parse evidence: {str(e)}")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
