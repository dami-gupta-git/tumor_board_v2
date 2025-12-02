"""Core assessment engine combining API and LLM services.

ARCHITECTURE:
    VariantInput → Normalize → MyVariantClient → Evidence → LLMService → Assessment

Orchestrates the pipeline with async concurrency for single and batch processing.

Key Design:
- Async context manager for HTTP session lifecycle
- Sequential per-variant, parallel across variants (asyncio.gather)
- Batch exceptions captured, not raised
- Stateless with no shared state
- Variant normalization before API calls for better evidence matching
"""

import asyncio
from tumorboard.api.myvariant import MyVariantClient
from tumorboard.llm.service import LLMService
from tumorboard.models.assessment import ActionabilityAssessment
from tumorboard.models.variant import VariantInput
from tumorboard.utils import normalize_variant


class AssessmentEngine:
    """
    Engine for variant assessment.

    Uses async/await patterns to enable concurrent processing of multiple variants,
    significantly improving performance for batch assessments.
    """

    def __init__(self, llm_model: str = "gpt-4o-mini", llm_temperature: float = 0.1):
        self.myvariant_client = MyVariantClient()
        self.llm_service = LLMService(model=llm_model, temperature=llm_temperature)

    async def __aenter__(self):
        """
        Initialize HTTP client session for connection pooling.

        Use with 'async with' syntax to ensure proper resource cleanup.
        """
        await self.myvariant_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close HTTP client session to prevent resource leaks."""
        await self.myvariant_client.__aexit__(exc_type, exc_val, exc_tb)

    async def assess_variant(self, variant_input: VariantInput) -> ActionabilityAssessment:
        """Assess a single variant.

        Chains three async operations sequentially:
        1. Normalize variant notation (V600E, Val600Glu, p.V600E → V600E)
        2. Validate variant type (only SNPs and small indels allowed)
        3. Fetch evidence from MyVariant API using normalized variant
        4. Send evidence to LLM for assessment

        The 'await' keyword yields control during I/O, allowing other tasks to run.
        """
        # Step 1: Normalize variant notation for better API matching
        # Converts formats like Val600Glu or p.V600E to canonical V600E
        normalized = normalize_variant(variant_input.gene, variant_input.variant)
        normalized_variant = normalized['variant_normalized']
        variant_type = normalized['variant_type']

        # Step 2: Validate variant type - only SNPs and small indels allowed
        from tumorboard.utils.variant_normalization import VariantNormalizer
        if variant_type not in VariantNormalizer.ALLOWED_VARIANT_TYPES:
            raise ValueError(
                f"Variant type '{variant_type}' is not supported. "
                f"Only SNPs and small indels are allowed (missense, nonsense, insertion, deletion, frameshift). "
                f"Got variant: {variant_input.variant}"
            )

        # Log normalization if variant was transformed
        if normalized_variant != variant_input.variant:
            print(f"  Normalized {variant_input.variant} → {normalized_variant} (type: {variant_type})")

        # Step 2: Fetch evidence from MyVariant API using normalized variant
        evidence = await self.myvariant_client.fetch_evidence(
            gene=variant_input.gene,
            variant=normalized_variant,  # Use normalized variant for API query
        )

        # Step 3: Assess with LLM (must run sequentially since it depends on evidence)
        # Use original variant notation for display/reporting
        assessment = await self.llm_service.assess_variant(
            gene=variant_input.gene,
            variant=variant_input.variant,  # Keep original for display
            tumor_type=variant_input.tumor_type,
            evidence=evidence,
        )

        return assessment

    async def batch_assess(
        self, variants: list[VariantInput]
    ) -> list[ActionabilityAssessment]:
        """
        Assess multiple variants concurrently.

        Uses asyncio.gather() to process all variants in parallel. While waiting for
        I/O (API/LLM calls), the event loop switches between tasks - no threading needed.
        """
        
        # Create coroutines for each variant
        tasks = [self.assess_variant(variant) for variant in variants]

        # Run all tasks concurrently, capturing exceptions instead of raising
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and return successful assessments
        assessments = [r for r in results if not isinstance(r, Exception)]
        return assessments
