"""Ensembl VEP API client for variant normalization and annotation.

This module provides variant normalization using the Ensembl Variant Effect Predictor (VEP)
REST API. It converts protein notation (e.g., ATM E1978K) to HGVS genomic notation
(e.g., chr11:g.108236086G>A) and retrieves functional predictions.

The primary use case is to enable MyVariant.info queries that would otherwise fail
because MyVariant requires HGVS genomic notation for functional prediction lookups.
"""

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import httpx

logger = logging.getLogger(__name__)

VEP_API_URL = "https://rest.ensembl.org/vep/human/hgvs"

# Amino acid 1-letter to 3-letter code mapping
AA_1_TO_3 = {
    'A': 'Ala', 'C': 'Cys', 'D': 'Asp', 'E': 'Glu', 'F': 'Phe',
    'G': 'Gly', 'H': 'His', 'I': 'Ile', 'K': 'Lys', 'L': 'Leu',
    'M': 'Met', 'N': 'Asn', 'P': 'Pro', 'Q': 'Gln', 'R': 'Arg',
    'S': 'Ser', 'T': 'Thr', 'V': 'Val', 'W': 'Trp', 'Y': 'Tyr',
    '*': 'Ter', 'X': 'Xaa'
}

# Reverse mapping for parsing VEP responses
AA_3_TO_1 = {v: k for k, v in AA_1_TO_3.items()}


@dataclass
class VEPAnnotation:
    """Functional annotations from VEP.

    Contains genomic coordinates, HGVS notations, and functional predictions
    from PolyPhen-2, SIFT, CADD, etc.
    """
    # Genomic location
    hgvs_genomic: str | None = None
    hgvs_transcript: str | None = None
    chromosome: str | None = None
    position: int | None = None
    ref_allele: str | None = None
    alt_allele: str | None = None

    # Functional predictions
    polyphen_prediction: str | None = None  # "benign", "possibly_damaging", "probably_damaging"
    polyphen_score: float | None = None
    sift_prediction: str | None = None  # "tolerated", "deleterious"
    sift_score: float | None = None
    cadd_phred: float | None = None
    cadd_raw: float | None = None

    # AlphaMissense (if available)
    alphamissense_prediction: str | None = None
    alphamissense_score: float | None = None

    # Consequence
    consequence_terms: list[str] = field(default_factory=list)
    impact: str | None = None  # "HIGH", "MODERATE", "LOW", "MODIFIER"
    biotype: str | None = None

    # Transcript info
    transcript_id: str | None = None
    gene_id: str | None = None
    protein_id: str | None = None

    # For re-querying MyVariant
    myvariant_query: str | None = None  # HGVS genomic notation for MyVariant

    # Original input
    input_notation: str | None = None

    def is_predicted_damaging(self, cadd_threshold: float = 20.0) -> bool:
        """Check if variant is predicted to be damaging.

        Uses multiple prediction sources:
        - PolyPhen-2: "probably_damaging" or "possibly_damaging"
        - SIFT: "deleterious"
        - CADD: phred score >= threshold (default 20)
        - AlphaMissense: "likely_pathogenic" or "ambiguous"

        Returns True if ANY predictor suggests damaging effect.
        """
        polyphen_damaging = self.polyphen_prediction in [
            "probably_damaging", "possibly_damaging"
        ]
        sift_damaging = self.sift_prediction == "deleterious"
        cadd_damaging = self.cadd_phred is not None and self.cadd_phred >= cadd_threshold
        alphamissense_damaging = self.alphamissense_prediction in [
            "likely_pathogenic", "ambiguous"
        ]

        return polyphen_damaging or sift_damaging or cadd_damaging or alphamissense_damaging

    def get_prediction_summary(self) -> str:
        """Get a human-readable summary of predictions."""
        parts = []

        if self.polyphen_prediction:
            score_str = f" ({self.polyphen_score:.2f})" if self.polyphen_score else ""
            parts.append(f"PolyPhen2: {self.polyphen_prediction}{score_str}")

        if self.sift_prediction:
            score_str = f" ({self.sift_score:.2f})" if self.sift_score else ""
            parts.append(f"SIFT: {self.sift_prediction}{score_str}")

        if self.cadd_phred:
            parts.append(f"CADD: {self.cadd_phred:.1f}")

        if self.alphamissense_prediction:
            score_str = f" ({self.alphamissense_score:.2f})" if self.alphamissense_score else ""
            parts.append(f"AlphaMissense: {self.alphamissense_prediction}{score_str}")

        return "; ".join(parts) if parts else "No predictions available"


class VEPClient:
    """Client for Ensembl VEP REST API.

    Provides variant annotation including:
    - Genomic coordinate conversion (protein -> genomic HGVS)
    - Functional predictions (PolyPhen-2, SIFT, CADD)
    - Consequence prediction

    Rate limits: 15 requests/second without authentication token.
    """

    def __init__(self, timeout: float = 30.0, max_retries: int = 3):
        """Initialize VEP client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts for failed requests
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._cache: dict[str, VEPAnnotation | None] = {}

    async def annotate_variant(
        self,
        gene: str,
        variant: str,
        use_cache: bool = True
    ) -> VEPAnnotation | None:
        """Annotate a variant using VEP.

        Args:
            gene: Gene symbol (e.g., "ATM")
            variant: Protein notation (e.g., "E1978K", "p.E1978K", "p.Glu1978Lys")
            use_cache: Whether to use cached results

        Returns:
            VEPAnnotation with functional predictions, or None if failed
        """
        cache_key = f"{gene}:{variant}"

        if use_cache and cache_key in self._cache:
            logger.debug(f"VEP cache hit for {cache_key}")
            return self._cache[cache_key]

        # Build HGVS protein notation
        hgvs_p = self._build_hgvs_protein(gene, variant)
        if not hgvs_p:
            logger.warning(f"Could not build HGVS notation for {gene} {variant}")
            return None

        logger.info(f"Querying VEP for {hgvs_p}")

        result = await self._query_vep(hgvs_p)

        if use_cache:
            self._cache[cache_key] = result

        return result

    async def annotate_variants_batch(
        self,
        variants: list[tuple[str, str]],
        use_cache: bool = True
    ) -> dict[str, VEPAnnotation | None]:
        """Annotate multiple variants in a single request.

        VEP supports batch queries up to 200 variants per request.

        Args:
            variants: List of (gene, variant) tuples
            use_cache: Whether to use cached results

        Returns:
            Dict mapping "gene:variant" to VEPAnnotation
        """
        results: dict[str, VEPAnnotation | None] = {}
        to_query: list[tuple[str, str, str]] = []  # (gene, variant, hgvs_p)

        for gene, variant in variants:
            cache_key = f"{gene}:{variant}"

            if use_cache and cache_key in self._cache:
                results[cache_key] = self._cache[cache_key]
            else:
                hgvs_p = self._build_hgvs_protein(gene, variant)
                if hgvs_p:
                    to_query.append((gene, variant, hgvs_p))
                else:
                    results[cache_key] = None

        if not to_query:
            return results

        # Query VEP in batches of 200
        batch_size = 200
        for i in range(0, len(to_query), batch_size):
            batch = to_query[i:i + batch_size]
            hgvs_notations = [item[2] for item in batch]

            batch_results = await self._query_vep_batch(hgvs_notations)

            for (gene, variant, hgvs_p), annotation in zip(batch, batch_results):
                cache_key = f"{gene}:{variant}"
                results[cache_key] = annotation
                if use_cache:
                    self._cache[cache_key] = annotation

        return results

    def _build_hgvs_protein(self, gene: str, variant: str) -> str | None:
        """Build HGVS protein notation from gene and variant.

        Handles various input formats:
        - "E1978K" -> "ATM:p.Glu1978Lys"
        - "p.E1978K" -> "ATM:p.Glu1978Lys"
        - "p.Glu1978Lys" -> "ATM:p.Glu1978Lys"
        """
        variant = variant.strip()

        # Remove "p." prefix if present
        if variant.lower().startswith("p."):
            variant = variant[2:]

        # Check if already 3-letter notation (e.g., Glu1978Lys)
        if re.match(r'^[A-Z][a-z]{2}\d+[A-Z][a-z]{2}$', variant):
            return f"{gene}:p.{variant}"

        # Convert 1-letter to 3-letter (e.g., E1978K -> Glu1978Lys)
        match = re.match(r'^([A-Z*])(\d+)([A-Z*])$', variant.upper())
        if match:
            ref, pos, alt = match.groups()
            ref_3 = AA_1_TO_3.get(ref)
            alt_3 = AA_1_TO_3.get(alt)
            if ref_3 and alt_3:
                return f"{gene}:p.{ref_3}{pos}{alt_3}"

        # Handle frameshift notation (e.g., W288fs, L287fs*12)
        fs_match = re.match(r'^([A-Z])(\d+)fs', variant.upper())
        if fs_match:
            ref, pos = fs_match.groups()
            ref_3 = AA_1_TO_3.get(ref)
            if ref_3:
                return f"{gene}:p.{ref_3}{pos}fs"

        # Handle nonsense (e.g., R348*, Q61X)
        nonsense_match = re.match(r'^([A-Z])(\d+)([*X])$', variant.upper())
        if nonsense_match:
            ref, pos, stop = nonsense_match.groups()
            ref_3 = AA_1_TO_3.get(ref)
            if ref_3:
                return f"{gene}:p.{ref_3}{pos}Ter"

        # Handle deletion notation (e.g., E746_A750del)
        del_match = re.match(r'^([A-Z])(\d+)_([A-Z])(\d+)del$', variant.upper())
        if del_match:
            ref1, pos1, ref2, pos2 = del_match.groups()
            ref1_3 = AA_1_TO_3.get(ref1)
            ref2_3 = AA_1_TO_3.get(ref2)
            if ref1_3 and ref2_3:
                return f"{gene}:p.{ref1_3}{pos1}_{ref2_3}{pos2}del"

        logger.warning(f"Could not parse variant notation: {variant}")
        return None

    async def _query_vep(self, hgvs_notation: str) -> VEPAnnotation | None:
        """Query VEP API for a single variant."""
        results = await self._query_vep_batch([hgvs_notation])
        return results[0] if results else None

    async def _query_vep_batch(self, hgvs_notations: list[str]) -> list[VEPAnnotation | None]:
        """Query VEP API for multiple variants."""
        results: list[VEPAnnotation | None] = [None] * len(hgvs_notations)

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        VEP_API_URL,
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json"
                        },
                        json={
                            "hgvs_notations": hgvs_notations,
                            "protein": 1,
                            "variant_class": 1,
                            "numbers": 1,
                            "hgvs": 1,
                            "canonical": 1,
                            "mane": 1,
                        }
                    )

                    # Handle rate limiting
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 1))
                        logger.warning(f"VEP rate limited, waiting {retry_after}s")
                        import asyncio
                        await asyncio.sleep(retry_after)
                        continue

                    response.raise_for_status()
                    data = response.json()

                    if not data:
                        return results

                    # Map responses back to input order
                    response_map = {item.get("input"): item for item in data}

                    for i, notation in enumerate(hgvs_notations):
                        if notation in response_map:
                            results[i] = self._parse_vep_response(response_map[notation])

                    return results

            except httpx.TimeoutException:
                logger.warning(f"VEP timeout (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            except httpx.HTTPStatusError as e:
                logger.error(f"VEP HTTP error: {e.response.status_code}")
                if e.response.status_code >= 500:
                    # Server error - retry
                    if attempt < self.max_retries - 1:
                        import asyncio
                        await asyncio.sleep(2 ** attempt)
                else:
                    # Client error - don't retry
                    break
            except Exception as e:
                logger.error(f"VEP query failed: {e}")
                break

        return results

    def _parse_vep_response(self, data: dict[str, Any]) -> VEPAnnotation:
        """Parse VEP API response into VEPAnnotation."""
        # Get genomic location
        chrom = data.get("seq_region_name")
        start = data.get("start")
        allele_string = data.get("allele_string", "")

        ref, alt = None, None
        if "/" in allele_string:
            parts = allele_string.split("/")
            if len(parts) == 2:
                ref, alt = parts

        # Build HGVS genomic for MyVariant query
        myvariant_query = None
        if chrom and start and ref and alt:
            # Handle different variant types
            if ref == "-":
                # Insertion
                myvariant_query = f"chr{chrom}:g.{start}_{start+1}ins{alt}"
            elif alt == "-":
                # Deletion
                if len(ref) == 1:
                    myvariant_query = f"chr{chrom}:g.{start}del"
                else:
                    myvariant_query = f"chr{chrom}:g.{start}_{start+len(ref)-1}del"
            else:
                # SNV or complex
                myvariant_query = f"chr{chrom}:g.{start}{ref}>{alt}"

        # Get transcript consequences - prefer canonical/MANE
        consequences = data.get("transcript_consequences", [])

        # Priority: MANE Select > canonical > first protein-coding
        best_consequence = None
        for c in consequences:
            if c.get("mane_select"):
                best_consequence = c
                break
            if c.get("canonical") == 1 and not best_consequence:
                best_consequence = c
            if not best_consequence and c.get("biotype") == "protein_coding":
                best_consequence = c

        if not best_consequence and consequences:
            best_consequence = consequences[0]

        if not best_consequence:
            best_consequence = {}

        return VEPAnnotation(
            hgvs_genomic=myvariant_query,
            hgvs_transcript=best_consequence.get("hgvsc"),
            chromosome=chrom,
            position=start,
            ref_allele=ref,
            alt_allele=alt,
            polyphen_prediction=best_consequence.get("polyphen_prediction"),
            polyphen_score=best_consequence.get("polyphen_score"),
            sift_prediction=best_consequence.get("sift_prediction"),
            sift_score=best_consequence.get("sift_score"),
            cadd_phred=best_consequence.get("cadd_phred"),
            cadd_raw=best_consequence.get("cadd_raw"),
            alphamissense_prediction=best_consequence.get("alphamissense_prediction"),
            alphamissense_score=best_consequence.get("alphamissense_score"),
            consequence_terms=best_consequence.get("consequence_terms", []),
            impact=best_consequence.get("impact"),
            biotype=best_consequence.get("biotype"),
            transcript_id=best_consequence.get("transcript_id"),
            gene_id=best_consequence.get("gene_id"),
            protein_id=best_consequence.get("protein_id"),
            myvariant_query=myvariant_query,
            input_notation=data.get("input"),
        )

    def clear_cache(self):
        """Clear the annotation cache."""
        self._cache.clear()


# Convenience function for single variant lookup
async def annotate_variant(gene: str, variant: str) -> VEPAnnotation | None:
    """Convenience function to annotate a single variant.

    Creates a new VEPClient instance for each call (no caching across calls).
    For batch operations or caching, use VEPClient directly.
    """
    client = VEPClient()
    return await client.annotate_variant(gene, variant)