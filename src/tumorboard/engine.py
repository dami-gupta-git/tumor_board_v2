"""Core assessment engine combining API and LLM services.

ARCHITECTURE:
    VariantInput → MyVariantClient → Evidence → LLMService → Assessment

Orchestrates the pipeline with async concurrency for single and batch processing.

Key Design:
- Async context manager for HTTP session lifecycle
- Sequential per-variant, parallel across variants (asyncio.gather)
- Batch exceptions captured, not raised
- Stateless with no shared state
"""

import asyncio
from tumorboard.api.myvariant import MyVariantClient
from tumorboard.llm.service import LLMService
from tumorboard.models.assessment import ActionabilityAssessment
from tumorboard.models.variant import VariantInput


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

        Chains two async operations sequentially:
        1. Fetch evidence from MyVariant API
        2. Send evidence to LLM for assessment

        The 'await' keyword yields control during I/O, allowing other tasks to run.
        """
        # Fetch evidence from MyVariant API
        evidence = await self.myvariant_client.fetch_evidence(
            gene=variant_input.gene,
            variant=variant_input.variant,
        )

        # Assess with LLM (must run sequentially since it depends on evidence)
        assessment = await self.llm_service.assess_variant(
            gene=variant_input.gene,
            variant=variant_input.variant,
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
