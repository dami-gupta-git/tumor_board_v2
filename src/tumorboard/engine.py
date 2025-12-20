"""Core assessment engine combining API and LLM services.

ARCHITECTURE:
    VariantInput → Normalize → MyVariantClient + FDAClient + CGIClient + CIViCClient + SemanticScholar/PubMed → Evidence → LLMService → Assessment

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
- Semantic Scholar literature search with citation metrics and AI summaries (TLDR)
- PubMed fallback when Semantic Scholar rate limit (429) is hit
"""

import asyncio
from tumorboard.api.myvariant import MyVariantClient
from tumorboard.api.fda import FDAClient
from tumorboard.api.cgi import CGIClient
from tumorboard.api.oncotree import OncoTreeClient
from tumorboard.api.vicc import VICCClient
from tumorboard.api.civic import CIViCClient
from tumorboard.api.clinicaltrials import ClinicalTrialsClient
from tumorboard.api.pubmed import PubMedClient, PubMedArticle
from tumorboard.api.semantic_scholar import SemanticScholarClient, SemanticScholarRateLimitError
from tumorboard.llm.service import LLMService
from tumorboard.models.assessment import ActionabilityAssessment
from tumorboard.models.evidence.cgi import CGIBiomarkerEvidence
from tumorboard.models.evidence.civic import CIViCAssertionEvidence
from tumorboard.models.evidence.clinical_trials import ClinicalTrialEvidence
from tumorboard.models.evidence.fda import FDAApproval
from tumorboard.models.evidence.pubmed import PubMedEvidence
from tumorboard.models.evidence.vicc import VICCEvidence
from tumorboard.models.variant import VariantInput
from tumorboard.utils import normalize_variant


class AssessmentEngine:
    """
    Engine for variant assessment.

    Uses async/await patterns to enable concurrent processing of multiple variants,
    significantly improving performance for batch assessments.
    """

    def __init__(self, llm_model: str = "gpt-4o-mini", llm_temperature: float = 0.1, enable_logging: bool = True, enable_vicc: bool = True, enable_civic_assertions: bool = True, enable_clinical_trials: bool = True, enable_semantic_scholar: bool = True):
        self.myvariant_client = MyVariantClient()
        self.fda_client = FDAClient()
        self.cgi_client = CGIClient()
        self.oncotree_client = OncoTreeClient()
        self.vicc_client = VICCClient() if enable_vicc else None
        self.civic_client = CIViCClient() if enable_civic_assertions else None
        self.clinical_trials_client = ClinicalTrialsClient() if enable_clinical_trials else None
        self.semantic_scholar_client = SemanticScholarClient() if enable_semantic_scholar else None
        self.pubmed_client = PubMedClient() if enable_semantic_scholar else None  # Fallback for rate limits
        self.enable_vicc = enable_vicc
        self.enable_civic_assertions = enable_civic_assertions
        self.enable_clinical_trials = enable_clinical_trials
        self.enable_semantic_scholar = enable_semantic_scholar
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
        if self.clinical_trials_client:
            await self.clinical_trials_client.__aenter__()
        if self.semantic_scholar_client:
            await self.semantic_scholar_client.__aenter__()
        if self.pubmed_client:
            await self.pubmed_client.__aenter__()
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
        if self.clinical_trials_client:
            await self.clinical_trials_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.semantic_scholar_client:
            await self.semantic_scholar_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.pubmed_client:
            await self.pubmed_client.__aexit__(exc_type, exc_val, exc_tb)

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

        async def fetch_clinical_trials():
            if self.clinical_trials_client:
                return await self.clinical_trials_client.search_trials(
                    gene=variant_input.gene,
                    variant=normalized_variant,
                    tumor_type=resolved_tumor_type,
                    recruiting_only=True,
                    max_results=10,
                )
            return []

        async def fetch_literature():
            """Fetch literature from Semantic Scholar, falling back to PubMed on rate limit.

            Searches both resistance literature AND general variant literature to capture:
            - Resistance papers (e.g., EGFR C797S osimertinib resistance)
            - Mechanistic papers (e.g., TP53 R175H promoting proliferation)
            - Therapeutic studies not framed as "resistance"
            """
            if self.semantic_scholar_client:
                try:
                    # Search both resistance AND general variant literature
                    resistance_papers, variant_papers = await asyncio.gather(
                        self.semantic_scholar_client.search_resistance_literature(
                            gene=variant_input.gene,
                            variant=normalized_variant,
                            tumor_type=resolved_tumor_type,
                            max_results=3,
                        ),
                        self.semantic_scholar_client.search_variant_literature(
                            gene=variant_input.gene,
                            variant=normalized_variant,
                            tumor_type=resolved_tumor_type,
                            max_results=3,
                        ),
                    )
                    # Merge and deduplicate by paper_id
                    seen_ids = set()
                    merged_papers = []
                    for paper in resistance_papers + variant_papers:
                        if paper.paper_id not in seen_ids:
                            seen_ids.add(paper.paper_id)
                            merged_papers.append(paper)
                    # Return tuple: (papers, source)
                    return (merged_papers[:6], "semantic_scholar")
                except SemanticScholarRateLimitError:
                    print("  Semantic Scholar rate limit hit, falling back to PubMed...")
                    # Fall back to PubMed with both search types
                    if self.pubmed_client:
                        resistance_articles, variant_articles = await asyncio.gather(
                            self.pubmed_client.search_resistance_literature(
                                gene=variant_input.gene,
                                variant=normalized_variant,
                                tumor_type=resolved_tumor_type,
                                max_results=3,
                            ),
                            self.pubmed_client.search_variant_literature(
                                gene=variant_input.gene,
                                variant=normalized_variant,
                                tumor_type=resolved_tumor_type,
                                max_results=3,
                            ),
                        )
                        # Merge and deduplicate by pmid
                        seen_pmids = set()
                        merged_articles = []
                        for article in resistance_articles + variant_articles:
                            if article.pmid not in seen_pmids:
                                seen_pmids.add(article.pmid)
                                merged_articles.append(article)
                        return (merged_articles[:6], "pubmed")
            elif self.pubmed_client:
                # Only PubMed available - search both types
                resistance_articles, variant_articles = await asyncio.gather(
                    self.pubmed_client.search_resistance_literature(
                        gene=variant_input.gene,
                        variant=normalized_variant,
                        max_results=3,
                    ),
                    self.pubmed_client.search_variant_literature(
                        gene=variant_input.gene,
                        variant=normalized_variant,
                        tumor_type=resolved_tumor_type,
                        max_results=3,
                    ),
                )
                # Merge and deduplicate
                seen_pmids = set()
                merged_articles = []
                for article in resistance_articles + variant_articles:
                    if article.pmid not in seen_pmids:
                        seen_pmids.add(article.pmid)
                        merged_articles.append(article)
                return (merged_articles[:6], "pubmed")
            return ([], None)

        evidence, fda_approvals_raw, cgi_biomarkers_raw, vicc_associations_raw, civic_assertions_raw, clinical_trials_raw, literature_raw = await asyncio.gather(
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
            fetch_clinical_trials(),
            fetch_literature(),
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

        if isinstance(clinical_trials_raw, Exception):
            print(f"  Warning: ClinicalTrials.gov API failed: {str(clinical_trials_raw)}")
            clinical_trials_raw = []

        if isinstance(literature_raw, Exception):
            print(f"  Warning: Literature search failed: {str(literature_raw)}")
            literature_raw = ([], None)

        # Unpack literature result (papers/articles, source)
        literature_items, literature_source = literature_raw if isinstance(literature_raw, tuple) else ([], None)

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

        # Add clinical trials to evidence
        if clinical_trials_raw:
            clinical_trials_evidence = []
            for trial in clinical_trials_raw:
                # Check if trial mentions the specific variant for this gene
                # Pass gene to avoid false positives (e.g., KRAS G12D matching NRAS G12D query)
                variant_specific = trial.mentions_variant(normalized_variant, gene=variant_input.gene)
                clinical_trials_evidence.append(ClinicalTrialEvidence(
                    nct_id=trial.nct_id,
                    title=trial.title,
                    status=trial.status,
                    phase=trial.phase,
                    conditions=trial.conditions,
                    interventions=trial.interventions,
                    sponsor=trial.sponsor,
                    url=trial.url,
                    variant_specific=variant_specific,
                ))
            evidence.clinical_trials = clinical_trials_evidence

        # Add literature to evidence (from Semantic Scholar or PubMed fallback)
        # Use LLM-based relevance scoring to filter and enrich papers
        if literature_items:
            pubmed_evidence = []

            # Score all papers in parallel for efficiency
            async def score_and_convert_paper(paper_or_article, source: str):
                """Score paper relevance and convert to PubMedEvidence."""
                if source == "semantic_scholar":
                    paper = paper_or_article
                    title = paper.title
                    abstract = paper.abstract
                    tldr = paper.tldr
                else:
                    article = paper_or_article
                    title = article.title
                    abstract = article.abstract
                    tldr = None

                # Use LLM to score relevance
                relevance = await self.llm_service.score_paper_relevance(
                    title=title,
                    abstract=abstract,
                    tldr=tldr,
                    gene=variant_input.gene,
                    variant=normalized_variant,
                    tumor_type=resolved_tumor_type,
                )

                # Skip papers that aren't relevant to this specific context
                if not relevance["is_relevant"]:
                    print(f"    Filtered out: {title[:60]}... (score: {relevance['relevance_score']:.2f}, reason: {relevance['key_finding'][:80]})")
                    return None

                print(f"    Relevant: {title[:60]}... (score: {relevance['relevance_score']:.2f}, signal: {relevance['signal_type']})")

                # Use LLM-extracted signal type and drugs instead of keyword matching
                signal_type = relevance["signal_type"]
                drugs_mentioned = relevance["drugs_mentioned"]

                if source == "semantic_scholar":
                    url = f"https://pubmed.ncbi.nlm.nih.gov/{paper.pmid}/" if paper.pmid else f"https://www.semanticscholar.org/paper/{paper.paper_id}"
                    return PubMedEvidence(
                        pmid=paper.pmid or paper.paper_id,
                        title=paper.title,
                        abstract=paper.abstract or "",
                        authors=[],
                        journal=paper.venue or "",
                        year=str(paper.year) if paper.year else None,
                        doi=None,
                        url=url,
                        signal_type=signal_type,
                        drugs_mentioned=drugs_mentioned,
                        citation_count=paper.citation_count,
                        influential_citation_count=paper.influential_citation_count,
                        tldr=relevance["key_finding"] or paper.tldr,  # Use LLM-extracted finding if available
                        is_open_access=paper.is_open_access,
                        open_access_pdf_url=paper.open_access_pdf_url,
                        semantic_scholar_id=paper.paper_id,
                    )
                else:
                    return PubMedEvidence(
                        pmid=article.pmid,
                        title=article.title,
                        abstract=article.abstract,
                        authors=article.authors,
                        journal=article.journal,
                        year=article.year,
                        doi=article.doi,
                        url=article.url,
                        signal_type=signal_type,
                        drugs_mentioned=drugs_mentioned,
                        citation_count=None,
                        influential_citation_count=None,
                        tldr=relevance["key_finding"],  # Use LLM-extracted finding
                        is_open_access=None,
                        open_access_pdf_url=None,
                        semantic_scholar_id=None,
                    )

            # Process all papers in parallel
            scored_papers = await asyncio.gather(*[
                score_and_convert_paper(item, literature_source)
                for item in literature_items
            ])

            # Filter out None results (non-relevant papers)
            pubmed_evidence = [p for p in scored_papers if p is not None]

            evidence.pubmed_articles = pubmed_evidence

            # Extract structured knowledge from relevant papers
            if pubmed_evidence:
                print(f"  Extracting structured knowledge from {len(pubmed_evidence)} relevant papers...")
                paper_contents = [
                    {
                        "title": p.title,
                        "abstract": p.abstract,
                        "tldr": p.tldr,
                        "pmid": p.pmid,
                        "url": p.url,
                    }
                    for p in pubmed_evidence
                ]

                knowledge_data = await self.llm_service.extract_variant_knowledge(
                    gene=variant_input.gene,
                    variant=normalized_variant,
                    tumor_type=resolved_tumor_type,
                    paper_contents=paper_contents,
                )

                # Convert to LiteratureKnowledge model
                from tumorboard.models.evidence.literature_knowledge import (
                    LiteratureKnowledge, DrugResistance, DrugSensitivity, TierRecommendation
                )

                evidence.literature_knowledge = LiteratureKnowledge(
                    mutation_type=knowledge_data.get("mutation_type", "unknown"),
                    resistant_to=[
                        DrugResistance(**r) if isinstance(r, dict) else DrugResistance(drug=str(r))
                        for r in knowledge_data.get("resistant_to", [])
                    ],
                    sensitive_to=[
                        DrugSensitivity(**s) if isinstance(s, dict) else DrugSensitivity(drug=str(s))
                        for s in knowledge_data.get("sensitive_to", [])
                    ],
                    clinical_significance=knowledge_data.get("clinical_significance", ""),
                    evidence_level=knowledge_data.get("evidence_level", "None"),
                    tier_recommendation=TierRecommendation(
                        **knowledge_data.get("tier_recommendation", {"tier": "III", "rationale": ""})
                    ),
                    references=knowledge_data.get("references", []),
                    key_findings=knowledge_data.get("key_findings", []),
                    confidence=knowledge_data.get("confidence", 0.0),
                )

                # Log extracted knowledge
                if evidence.literature_knowledge.confidence > 0.5:
                    print(f"    Literature Knowledge (confidence: {evidence.literature_knowledge.confidence:.2f}):")
                    if evidence.literature_knowledge.resistant_to:
                        drugs = ", ".join(evidence.literature_knowledge.get_resistance_drugs())
                        print(f"      Resistant to: {drugs}")
                    if evidence.literature_knowledge.sensitive_to:
                        drugs = ", ".join(evidence.literature_knowledge.get_sensitivity_drugs())
                        print(f"      Sensitive to: {drugs}")
                    print(f"      Tier recommendation: {evidence.literature_knowledge.tier_recommendation.tier}")

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
