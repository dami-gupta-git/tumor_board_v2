"""Core assessment engine combining API and LLM services.

ARCHITECTURE:
    VariantInput → Normalize → MyVariantClient + FDAClient + CGIClient + CIViCClient → Evidence → LLMService → Assessment

Orchestrates the pipeline with async concurrency for single and batch processing.

Key Design:
- Async context manager for HTTP session lifecycle
- Sequential per-variant, parallel across variants (asyncio.gather)
- Batch exceptions captured, not raised
- Stateless with no shared state
- Variant normalization before API calls for better evidence matching
- FDA drug approval data fetched in parallel with MyVariant data
- CGI biomarkers provide explicit FDA/NCCN approval status
- CIViC Assertions provide curated AMP/ASCO/CAP tier classifications with NCCN guidelines
"""

import asyncio
from tumorboard.api.myvariant import MyVariantClient
from tumorboard.api.fda import FDAClient
from tumorboard.api.cgi import CGIClient
from tumorboard.api.oncotree import OncoTreeClient
from tumorboard.api.vicc import VICCClient
from tumorboard.api.civic import CIViCClient
from tumorboard.llm.service import LLMService
from tumorboard.models.assessment import ActionabilityAssessment
from tumorboard.models.evidence.cgi import CGIBiomarkerEvidence
from tumorboard.models.evidence.civic import CIViCAssertionEvidence
from tumorboard.models.evidence.fda import FDAApproval
from tumorboard.models.evidence.vicc import VICCEvidence
from tumorboard.models.variant import VariantInput
from tumorboard.utils import normalize_variant


class AssessmentEngine:
    """
    Engine for variant assessment.

    Uses async/await patterns to enable concurrent processing of multiple variants,
    significantly improving performance for batch assessments.
    """

    def __init__(self, llm_model: str = "gpt-4o-mini", llm_temperature: float = 0.1, enable_logging: bool = True, enable_vicc: bool = True, enable_civic_assertions: bool = True):
        self.myvariant_client = MyVariantClient()
        self.fda_client = FDAClient()
        self.cgi_client = CGIClient()
        self.oncotree_client = OncoTreeClient()
        self.vicc_client = VICCClient() if enable_vicc else None
        self.civic_client = CIViCClient() if enable_civic_assertions else None
        self.enable_vicc = enable_vicc
        self.enable_civic_assertions = enable_civic_assertions
        self.llm_service = LLMService(model=llm_model, temperature=llm_temperature, enable_logging=enable_logging)

    async def __aenter__(self):
        """
        Initialize HTTP client session for connection pooling.

        Use with 'async with' syntax to ensure proper resource cleanup.
        """
        await self.myvariant_client.__aenter__()
        await self.fda_client.__aenter__()
        await self.oncotree_client.__aenter__()
        if self.vicc_client:
            await self.vicc_client.__aenter__()
        if self.civic_client:
            await self.civic_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close HTTP client session to prevent resource leaks."""
        await self.myvariant_client.__aexit__(exc_type, exc_val, exc_tb)
        await self.fda_client.__aexit__(exc_type, exc_val, exc_tb)
        await self.oncotree_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.vicc_client:
            await self.vicc_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.civic_client:
            await self.civic_client.__aexit__(exc_type, exc_val, exc_tb)

    async def assess_variant(self, variant_input: VariantInput) -> ActionabilityAssessment:
        """Assess a single variant.

        Chains multiple async operations:
        1. Normalize variant notation (V600E, Val600Glu, p.V600E → V600E)
        2. Validate variant type (only SNPs and small indels allowed)
        3. Fetch evidence from MyVariant API and FDA API in parallel
        4. Send combined evidence to LLM for assessment

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

        # Step 2.5: Resolve tumor type using OncoTree (e.g., NSCLC → Non-Small Cell Lung Cancer)
        # This helps match user input to FDA indication text and CIViC evidence
        resolved_tumor_type = variant_input.tumor_type
        if variant_input.tumor_type:
            try:
                resolved = await self.oncotree_client.resolve_tumor_type(variant_input.tumor_type)
                if resolved != variant_input.tumor_type:
                    print(f"  Resolved tumor type: {variant_input.tumor_type} → {resolved}")
                    resolved_tumor_type = resolved
            except Exception as e:
                print(f"  Warning: OncoTree resolution failed: {str(e)}")
                resolved_tumor_type = variant_input.tumor_type

        # Step 3: Fetch evidence from MyVariant, FDA, CGI, VICC, and CIViC APIs in parallel
        # This improves performance by running all API calls concurrently
        async def fetch_vicc():
            if self.vicc_client:
                return await self.vicc_client.fetch_associations(
                    gene=variant_input.gene,
                    variant=normalized_variant,
                    tumor_type=resolved_tumor_type,
                    max_results=15,
                )
            return []

        async def fetch_civic_assertions():
            if self.civic_client:
                return await self.civic_client.fetch_assertions(
                    gene=variant_input.gene,
                    variant=normalized_variant,
                    tumor_type=resolved_tumor_type,
                    max_results=20,
                )
            return []

        evidence, fda_approvals_raw, cgi_biomarkers_raw, vicc_associations_raw, civic_assertions_raw = await asyncio.gather(
            self.myvariant_client.fetch_evidence(
                gene=variant_input.gene,
                variant=normalized_variant,  # Use normalized variant for API query
            ),
            self.fda_client.fetch_drug_approvals(
                gene=variant_input.gene,
                variant=normalized_variant,
            ),
            asyncio.to_thread(
                self.cgi_client.fetch_biomarkers,
                variant_input.gene,
                normalized_variant,
                resolved_tumor_type,
            ),
            fetch_vicc(),
            fetch_civic_assertions(),
            return_exceptions=True
        )

        # Handle exceptions from parallel calls
        if isinstance(evidence, Exception):
            print(f"  Warning: MyVariant API failed: {str(evidence)}")
            # Create empty evidence object
            from tumorboard.models.evidence import Evidence
            evidence = Evidence(
                variant_id=f"{variant_input.gene}:{normalized_variant}",
                gene=variant_input.gene,
                variant=normalized_variant,
            )

        if isinstance(fda_approvals_raw, Exception):
            print(f"  Warning: FDA API failed: {str(fda_approvals_raw)}")
            fda_approvals_raw = []

        if isinstance(cgi_biomarkers_raw, Exception):
            print(f"  Warning: CGI biomarkers failed: {str(cgi_biomarkers_raw)}")
            cgi_biomarkers_raw = []

        if isinstance(vicc_associations_raw, Exception):
            print(f"  Warning: VICC MetaKB API failed: {str(vicc_associations_raw)}")
            vicc_associations_raw = []

        if isinstance(civic_assertions_raw, Exception):
            print(f"  Warning: CIViC Assertions API failed: {str(civic_assertions_raw)}")
            civic_assertions_raw = []

        # Parse FDA approval data and add to evidence
        if fda_approvals_raw:
            fda_approvals = []
            for approval_record in fda_approvals_raw:
                # Pass variant to extract clinical_studies mentions for variants like G719X
                parsed = self.fda_client.parse_approval_data(
                    approval_record, variant_input.gene, normalized_variant
                )
                if parsed:
                    fda_approvals.append(FDAApproval(**parsed))
            evidence.fda_approvals = fda_approvals

        # Add CGI biomarkers to evidence
        if cgi_biomarkers_raw:
            cgi_evidence = []
            for biomarker in cgi_biomarkers_raw:
                cgi_evidence.append(CGIBiomarkerEvidence(
                    gene=biomarker.gene,
                    alteration=biomarker.alteration,
                    drug=biomarker.drug,
                    drug_status=biomarker.drug_status,
                    association=biomarker.association,
                    evidence_level=biomarker.evidence_level,
                    source=biomarker.source,
                    tumor_type=biomarker.tumor_type,
                    fda_approved=biomarker.is_fda_approved(),
                ))
            evidence.cgi_biomarkers = cgi_evidence

        # Add VICC MetaKB associations to evidence
        if vicc_associations_raw:
            vicc_evidence = []
            for assoc in vicc_associations_raw:
                vicc_evidence.append(VICCEvidence(
                    description=assoc.description,
                    gene=assoc.gene,
                    variant=assoc.variant,
                    disease=assoc.disease,
                    drugs=assoc.drugs,
                    evidence_level=assoc.evidence_level,
                    response_type=assoc.response_type,
                    source=assoc.source,
                    publication_url=assoc.publication_url,
                    oncogenic=assoc.oncogenic,
                    is_sensitivity=assoc.is_sensitivity(),
                    is_resistance=assoc.is_resistance(),
                    oncokb_level=assoc.get_oncokb_level(),
                ))
            evidence.vicc = vicc_evidence

        # Add CIViC Assertions to evidence (curated AMP/ASCO/CAP tier classifications)
        if civic_assertions_raw:
            civic_assertions_evidence = []
            for assertion in civic_assertions_raw:
                civic_assertions_evidence.append(CIViCAssertionEvidence(
                    assertion_id=assertion.assertion_id,
                    name=assertion.name,
                    amp_level=assertion.amp_level,
                    amp_tier=assertion.get_amp_tier(),
                    amp_level_letter=assertion.get_amp_level(),
                    assertion_type=assertion.assertion_type,
                    significance=assertion.significance,
                    status=assertion.status,
                    molecular_profile=assertion.molecular_profile,
                    disease=assertion.disease,
                    therapies=assertion.therapies,
                    fda_companion_test=assertion.fda_companion_test,
                    nccn_guideline=assertion.nccn_guideline,
                    description=assertion.description,
                    is_sensitivity=assertion.is_sensitivity(),
                    is_resistance=assertion.is_resistance(),
                ))
            evidence.civic_assertions = civic_assertions_evidence

        # Step 4: Assess with LLM (must run sequentially since it depends on evidence)
        # Use original variant notation for display/reporting
        # Use resolved tumor type for evidence filtering and FDA matching
        assessment = await self.llm_service.assess_variant(
            gene=variant_input.gene,
            variant=variant_input.variant,  # Keep original for display
            tumor_type=resolved_tumor_type,  # Use resolved tumor type
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
