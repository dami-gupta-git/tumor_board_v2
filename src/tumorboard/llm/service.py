"""LLM service for variant actionability assessment — 2025 high-performance edition."""

import json
from litellm import acompletion
from tumorboard.llm.prompts import create_assessment_prompt  # ← now returns messages list!
from tumorboard.models import Evidence
from tumorboard.models.assessment import ActionabilityAssessment, ActionabilityTier

from tumorboard.utils.logging_config import get_logger


class LLMService:
    """High-accuracy LLM service for somatic variant actionability."""

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.0, enable_logging: bool = True):
        self.model = model
        # ↓↓↓ CRITICAL: temperature=0.0 → deterministic, no hallucinations
        self.temperature = temperature
        self.enable_logging = enable_logging
        self.logger = get_logger() if enable_logging else None

    async def assess_variant(
        self,
        gene: str,
        variant: str,
        tumor_type: str | None,
        evidence: Evidence,
    ) -> ActionabilityAssessment:
        """Assess variant using the new evidence-driven prompt system."""

        # Pre-processed summary header with stats and conflict detection
        evidence_header = evidence.format_evidence_summary_header(tumor_type=tumor_type)

        # Drug-level aggregation REPLACES detailed VICC/CIViC when we have many entries
        # This significantly reduces prompt size while preserving key information
        drug_summary = evidence.format_drug_aggregation_summary(tumor_type=tumor_type)

        # Only include detailed evidence for FDA approvals and CGI biomarkers
        # (these are compact and contain critical tier-determining info)
        evidence_details = evidence.summary_compact(tumor_type=tumor_type)

        # Combine header + drug summary + compact details
        evidence_summary = evidence_header + drug_summary + evidence_details

        # Log the request
        request_id = None
        if self.logger:
            request_id = self.logger.log_llm_request(
                gene=gene,
                variant=variant,
                tumor_type=tumor_type,
                evidence_summary=evidence_summary,
                model=self.model,
                temperature=self.temperature,
            )

        # New create_assessment_prompt returns full messages list with system + user roles
        messages = create_assessment_prompt(gene, variant, tumor_type, evidence_summary)

        # Build completion kwargs - conditionally add response_format for compatible models
        completion_kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": 2000,
        }

        # Only use response_format for OpenAI models that support JSON mode
        # Supported: gpt-4-turbo, gpt-4o, gpt-4o-mini, gpt-3.5-turbo-1106+
        # Not supported: Claude models, open-source models, older OpenAI models
        openai_json_models = ["gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
        if any(model_prefix in self.model.lower() for model_prefix in openai_json_models):
            try:
                completion_kwargs["response_format"] = {"type": "json_object"}
            except Exception:
                # Fallback to prompt-based JSON if model doesn't support response_format
                pass

        try:
            response = await acompletion(**completion_kwargs)

            raw_content = response.choices[0].message.content.strip()

            print(raw_content)
            # Robust markdown/code-block handling (your code was already great)
            content = raw_content
            if content.startswith("```"):
                parts = content.split("```")
                content = parts[1] if len(parts) > 1 else parts[0]
                if content.lower().startswith("json"):
                    content = content[4:].lstrip()

            data = json.loads(content)

            # Build final assessment — unchanged from your excellent version
            assessment = ActionabilityAssessment(
                gene=gene,
                variant=variant,
                tumor_type=tumor_type,
                tier=ActionabilityTier(data.get("tier", "Unknown")),
                confidence_score=float(data.get("confidence_score", 0.5)),
                summary=data.get("summary", "No summary provided."),
                rationale=data.get("rationale", "No rationale provided."),
                evidence_strength=data.get("evidence_strength"),
                clinical_trials_available=bool(data.get("clinical_trials_available", False)),
                recommended_therapies=data.get("recommended_therapies", []),
                references=data.get("references", []),
                **evidence.model_dump(include={
                    'cosmic_id', 'ncbi_gene_id', 'dbsnp_id', 'clinvar_id',
                    'clinvar_clinical_significance', 'clinvar_accession',
                    'hgvs_genomic', 'hgvs_protein', 'hgvs_transcript',
                    'snpeff_effect', 'polyphen2_prediction', 'cadd_score', 'gnomad_exome_af',
                    'alphamissense_score', 'alphamissense_prediction',
                    'transcript_id', 'transcript_consequence'
                })
            )

            # Log the successful response
            if self.logger:
                self.logger.log_llm_response(
                    request_id=request_id or "unknown",
                    gene=gene,
                    variant=variant,
                    tumor_type=tumor_type,
                    tier=assessment.tier.value,
                    confidence_score=assessment.confidence_score,
                    summary=assessment.summary,
                    rationale=assessment.rationale,
                    evidence_strength=assessment.evidence_strength,
                    recommended_therapies=[
                        {
                            "drug_name": therapy.drug_name,
                            "evidence_level": therapy.evidence_level,
                            "approval_status": therapy.approval_status,
                            "clinical_context": therapy.clinical_context,
                        }
                        for therapy in assessment.recommended_therapies
                    ],
                    references=assessment.references,
                    raw_response=raw_content[:500],  # Log first 500 chars of raw response
                )

                # Log a human-readable decision summary
                self.logger.log_decision_summary(
                    gene=gene,
                    variant=variant,
                    tumor_type=tumor_type,
                    tier=assessment.tier.value,
                    confidence_score=assessment.confidence_score,
                    key_evidence=assessment.references[:5],  # Top 5 references
                    decision_rationale=assessment.rationale,
                )

            return assessment

        except Exception as e:
            # Log the error
            if self.logger:
                self.logger.log_llm_error(
                    request_id=request_id or "unknown",
                    gene=gene,
                    variant=variant,
                    error=e,
                )
            # Re-raise the exception
            raise

    async def score_paper_relevance(
        self,
        title: str,
        abstract: str | None,
        tldr: str | None,
        gene: str,
        variant: str,
        tumor_type: str | None,
    ) -> dict:
        """Score a paper's relevance to a specific gene/variant/tumor context.

        Uses LLM to determine if a paper is actually relevant to the specific
        clinical context, extracting key findings about resistance/sensitivity.

        Args:
            title: Paper title
            abstract: Paper abstract (may be None)
            tldr: AI-generated summary from Semantic Scholar (may be None)
            gene: Gene symbol (e.g., "KIT")
            variant: Variant notation (e.g., "D816V")
            tumor_type: Tumor type (e.g., "GIST", "Gastrointestinal Stromal Tumor")

        Returns:
            dict with keys:
                - relevance_score: float 0-1 (1 = directly about this variant in this tumor)
                - is_relevant: bool (True if score >= 0.6)
                - signal_type: "resistance", "sensitivity", "mixed", "prognostic", or "unclear"
                - drugs_mentioned: list of drug names affected by this variant
                - key_finding: one sentence summary of the paper's relevance
                - confidence: float 0-1 for the extraction confidence
        """
        # Use the best available text
        text_content = tldr or abstract or ""
        if not text_content:
            return {
                "relevance_score": 0.0,
                "is_relevant": False,
                "signal_type": "unclear",
                "drugs_mentioned": [],
                "key_finding": "No abstract or summary available",
                "confidence": 0.0,
            }

        tumor_context = tumor_type or "cancer (unspecified)"

        system_prompt = """You are an expert oncology literature analyst. Your task is to evaluate whether a scientific paper is relevant to understanding a specific gene variant in a specific tumor type.

Be INCLUSIVE for clinically relevant papers:
- Papers about the SAME EXON or SAME CODON are highly relevant (e.g., exon 17 papers for D816V)
- Papers about drugs targeting this mutation class are relevant (e.g., avapritinib for KIT mutations in GIST)
- Papers about resistance mechanisms in this tumor type are relevant
- Papers about related variants in the SAME gene and SAME tumor are relevant

Be STRICT only about tumor type:
- A paper about KIT D816V in mastocytosis is NOT relevant if we're asking about GIST
- A paper about a completely different gene is NOT relevant

CRITICAL - Distinguish PREDICTIVE vs PROGNOSTIC signals:
- PREDICTIVE (resistance/sensitivity): Paper shows variant PREDICTS response or resistance to a SPECIFIC drug
  → "Patients with KRAS mutations should not receive cetuximab" = PREDICTIVE resistance
  → "EGFR L858R predicts response to erlotinib" = PREDICTIVE sensitivity
- PROGNOSTIC: Paper shows variant is associated with OUTCOMES (survival, recurrence) but NOT specific drug response
  → "SMAD4 loss associated with worse survival" = PROGNOSTIC (not resistance!)
  → "TP53 mutations predict poor prognosis" = PROGNOSTIC
  → "Patients with X had shorter median survival on chemotherapy" = PROGNOSTIC (not drug-specific)

Return valid JSON only, no markdown."""

        user_prompt = f"""Evaluate this paper's relevance to {gene} {variant} in {tumor_context}:

TITLE: {title}

CONTENT: {text_content[:1500]}

Return JSON with these exact fields:
{{
    "relevance_score": <float 0-1, see scoring guide below>,
    "signal_type": "<see definitions below>",
    "is_predictive_biomarker": <true if paper shows this variant predicts response to a SPECIFIC targeted therapy, false otherwise>,
    "drugs_mentioned": [<list of specific drug names mentioned in relation to this gene/variant>],
    "key_finding": "<one sentence: what does this paper say that's relevant to {gene} {variant} in {tumor_context}?>",
    "confidence": <float 0-1 for how confident you are in this assessment>
}}

signal_type definitions:
- "resistance": Variant causes PREDICTIVE resistance to a specific drug (e.g., "should not receive", "no benefit from", "contraindicated")
- "sensitivity": Variant PREDICTS response to a specific drug (e.g., "responds to", "sensitive to")
- "mixed": Both resistance to some drugs and sensitivity to others
- "prognostic": About outcomes/survival but NOT specific drug response (e.g., "worse prognosis", "shorter survival")
- "unclear": Cannot determine from abstract

Scoring guide:
- 1.0: Directly studies {gene} {variant} in {tumor_context}
- 0.9: Studies drugs targeting {gene} mutations (including {variant}) in {tumor_context}
- 0.8: Studies {gene} exon/codon mutations in {tumor_context} that include {variant}'s class
- 0.7: Studies {gene} resistance mechanisms in {tumor_context}
- 0.6: Studies {gene} {variant} in a related tumor context
- 0.4: Mentions {gene} mutations but different tumor type entirely
- 0.2: Studies {gene} but completely different mutation class
- 0.0: Not relevant to {gene} or {tumor_context}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Use a fast, cheap model for this screening task
        screening_model = "gpt-4o-mini"

        try:
            response = await acompletion(
                model=screening_model,
                messages=messages,
                temperature=0.0,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content.strip()

            # Handle markdown code blocks if present
            if content.startswith("```"):
                parts = content.split("```")
                content = parts[1] if len(parts) > 1 else parts[0]
                if content.lower().startswith("json"):
                    content = content[4:].lstrip()

            data = json.loads(content)

            # Normalize and validate response
            relevance_score = float(data.get("relevance_score", 0.0))
            relevance_score = max(0.0, min(1.0, relevance_score))

            return {
                "relevance_score": relevance_score,
                "is_relevant": relevance_score >= 0.6,
                "signal_type": data.get("signal_type", "unclear"),
                "drugs_mentioned": data.get("drugs_mentioned", []),
                "key_finding": data.get("key_finding", ""),
                "confidence": float(data.get("confidence", 0.5)),
            }

        except Exception as e:
            # On error, return low confidence result
            print(f"Paper relevance scoring error: {e}")
            return {
                "relevance_score": 0.5,  # Uncertain
                "is_relevant": False,
                "signal_type": "unclear",
                "drugs_mentioned": [],
                "key_finding": f"Error during analysis: {str(e)[:100]}",
                "confidence": 0.0,
            }

    async def extract_variant_knowledge(
        self,
        gene: str,
        variant: str,
        tumor_type: str,
        paper_contents: list[dict],
    ) -> dict:
        """Extract structured knowledge about a variant from multiple papers.

        Uses LLM to synthesize information from paper abstracts/TLDRs into
        structured knowledge about the variant's clinical significance.

        Args:
            gene: Gene symbol (e.g., "KIT")
            variant: Variant notation (e.g., "D816V")
            tumor_type: Tumor type (e.g., "GIST", "Gastrointestinal Stromal Tumor")
            paper_contents: List of dicts with keys: title, abstract, tldr, pmid, url

        Returns:
            dict with structured knowledge:
                - mutation_type: "primary" (driver) or "secondary" (resistance/acquired)
                - resistant_to: list of drugs this variant causes resistance to
                - sensitive_to: list of drugs this variant may respond to
                - clinical_significance: summary of clinical implications
                - evidence_level: "FDA-approved", "Phase 3", "Phase 2", "Preclinical", "Case reports"
                - tier_recommendation: "I", "II", "III", or "IV" with rationale
                - references: list of PMIDs supporting the findings
                - confidence: 0-1 score for extraction confidence
        """
        if not paper_contents:
            return {
                "mutation_type": "unknown",
                "resistant_to": [],
                "sensitive_to": [],
                "clinical_significance": "No literature available for analysis",
                "evidence_level": "None",
                "tier_recommendation": {"tier": "III", "rationale": "Insufficient evidence"},
                "references": [],
                "confidence": 0.0,
            }

        # Format paper contents for the prompt
        papers_text = []
        for i, paper in enumerate(paper_contents[:5], 1):  # Limit to 5 papers
            content = paper.get("tldr") or paper.get("abstract") or ""
            pmid = paper.get("pmid", "Unknown")
            title = paper.get("title", "Untitled")
            papers_text.append(f"""
Paper {i} (PMID: {pmid}):
Title: {title}
Content: {content[:1000]}
""")

        papers_combined = "\n".join(papers_text)

        system_prompt = """You are an expert oncology researcher synthesizing knowledge from scientific literature.

Your task is to extract structured, clinically actionable information about a specific gene variant from research papers.

CRITICAL DISTINCTION - PREDICTIVE vs PROGNOSTIC:
- PREDICTIVE resistance: Variant causes lack of response to a SPECIFIC TARGETED THERAPY
  → Example: "KRAS mutations predict no response to cetuximab" (cetuximab targets EGFR, KRAS bypasses it)
  → Example: "EGFR T790M causes resistance to erlotinib" (acquired mutation in drug target)
  → These affect treatment SELECTION - clinically actionable (Tier II)

- PROGNOSTIC markers: Variant associated with worse OUTCOMES but not specific drug response
  → Example: "SMAD4 loss associated with worse survival" (tumor suppressor loss = aggressive disease)
  → Example: "TP53 mutations predict poor prognosis"
  → Example: "Patients with X had shorter survival on chemotherapy" (not drug-specific!)
  → These do NOT affect treatment SELECTION - NOT actionable (Tier III)

A TRUE resistance marker means: "Do NOT give Drug X to patients with this variant"
A prognostic marker means: "Patients with this variant have worse outcomes regardless of treatment"

Be PRECISE and EVIDENCE-BASED:
- Only report findings that are directly supported by the papers provided
- Distinguish between in vitro/preclinical and clinical evidence
- Note the strength of evidence (case reports vs. clinical trials)
- If papers disagree, note the conflict

Return valid JSON only, no markdown."""

        user_prompt = f"""Extract structured knowledge about {gene} {variant} in {tumor_type} from these papers:

{papers_combined}

Return JSON with these exact fields:
{{
    "mutation_type": "<'primary' if this is a driver mutation, 'secondary' if it's an acquired resistance mutation, 'both' if it can be either, 'unknown' if unclear>",

    "is_prognostic_only": <true if this variant is ONLY prognostic (affects survival prediction) but does NOT predict response to specific drugs, false if it affects drug selection>,

    "resistant_to": [
        {{"drug": "<drug name>", "evidence": "<in vitro|preclinical|clinical|FDA-labeled>", "mechanism": "<brief mechanism if known>", "is_predictive": <true if this is PREDICTIVE resistance to a targeted therapy, false if just prognostic association>}}
    ],

    "sensitive_to": [
        {{"drug": "<drug name>", "evidence": "<in vitro|preclinical|clinical|FDA-labeled>", "ic50_nM": "<IC50 if reported, else null>"}}
    ],

    "clinical_significance": "<2-3 sentence summary of what this variant means clinically for {tumor_type} patients>",

    "evidence_level": "<'FDA-approved' if there's FDA approval for this variant in this tumor, 'Phase 3' if phase 3 trial data, 'Phase 2', 'Preclinical', 'Case reports', or 'None'>",

    "tier_recommendation": {{
        "tier": "<see tier guide below>",
        "rationale": "<one sentence explaining the tier recommendation based on AMP/ASCO/CAP guidelines>"
    }},

    "references": ["<PMID1>", "<PMID2>"],

    "key_findings": [
        "<Most important finding 1>",
        "<Most important finding 2>"
    ],

    "confidence": <0.0-1.0 based on how confident you are in these extractions>
}}

TIER GUIDE for {gene} {variant} in {tumor_type}:
- Tier I: FDA-approved therapy exists FOR this variant in this tumor
- Tier II: PREDICTIVE resistance marker (affects which targeted therapy to use) OR off-label evidence of benefit
- Tier III: PROGNOSTIC only (affects prognosis prediction but not drug selection), OR unknown significance
- Tier IV: Benign variant

CRITICAL:
- Focus ONLY on evidence relevant to {tumor_type}, not other cancer types
- "Worse survival on chemotherapy" is PROGNOSTIC, not resistance (Tier III, not II)
- Only classify as Tier II resistance if papers show this variant specifically EXCLUDES a targeted therapy option
- Tumor suppressors (TP53, SMAD4, PTEN loss) are usually PROGNOSTIC, not resistance markers"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await acompletion(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.0,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content.strip()

            # Handle markdown code blocks if present
            if content.startswith("```"):
                parts = content.split("```")
                content = parts[1] if len(parts) > 1 else parts[0]
                if content.lower().startswith("json"):
                    content = content[4:].lstrip()

            data = json.loads(content)

            # Normalize and validate response
            return {
                "mutation_type": data.get("mutation_type", "unknown"),
                "resistant_to": data.get("resistant_to", []),
                "sensitive_to": data.get("sensitive_to", []),
                "clinical_significance": data.get("clinical_significance", ""),
                "evidence_level": data.get("evidence_level", "None"),
                "tier_recommendation": data.get("tier_recommendation", {"tier": "III", "rationale": "Unknown"}),
                "references": data.get("references", []),
                "key_findings": data.get("key_findings", []),
                "confidence": float(data.get("confidence", 0.5)),
            }

        except Exception as e:
            print(f"Variant knowledge extraction error: {e}")
            return {
                "mutation_type": "unknown",
                "resistant_to": [],
                "sensitive_to": [],
                "clinical_significance": f"Error during extraction: {str(e)[:100]}",
                "evidence_level": "None",
                "tier_recommendation": {"tier": "III", "rationale": "Extraction failed"},
                "references": [],
                "key_findings": [],
                "confidence": 0.0,
            }