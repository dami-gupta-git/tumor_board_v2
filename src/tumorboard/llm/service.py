"""LLM service for variant actionability assessment.

ARCHITECTURE:
-------------
This module is the "reasoning layer" in the TumorBoard pipeline:

    Evidence (from APIs) → LLMService → Structured Assessment

Functions:
1. Prompt Engineering: Formats evidence + instructions into LLM-optimized messages
2. Model Inference: Async calls to LLM providers via litellm abstraction layer
3. Response Parsing: Extracts structured JSON from LLM output (handles markdown wrapping)

Design Decisions:
---------------------
- Uses litellm for provider-agnostic LLM access (OpenAI, Anthropic, etc.)
- Low temperature (0.1) prioritizes determinism over creativity
- Forces JSON schema compliance for downstream processing reliability
- Stateless design: each assessment is independent (no conversation history)
- Async-native for concurrent batch processing
"""

import json
from litellm import acompletion
from tumorboard.llm.prompts import ACTIONABILITY_SYSTEM_PROMPT, create_assessment_prompt
from tumorboard.models.assessment import ActionabilityAssessment, ActionabilityTier
from tumorboard.models.evidence import Evidence


class LLMService:
    """Simple LLM service for variant assessment."""

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.1):
        self.model = model
        self.temperature = temperature

    async def assess_variant(
        self,
        gene: str,
        variant: str,
        tumor_type: str | None,
        evidence: Evidence,
    ) -> ActionabilityAssessment:
        """Assess variant using LLM."""

        # Create prompt
        evidence_summary = evidence.summary()
        user_prompt = create_assessment_prompt(gene, variant, tumor_type, evidence_summary)

        messages = [
            {"role": "system", "content": ACTIONABILITY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Call LLM
        response = await acompletion(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=2000,
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON - handle markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        data = json.loads(content)

        # Create assessment - inherit annotations from evidence
        return ActionabilityAssessment(
            gene=gene,
            variant=variant,
            tumor_type=tumor_type,
            tier=ActionabilityTier(data.get("tier", "Unknown")),
            confidence_score=data.get("confidence_score", 0.5),
            summary=data.get("summary", "No summary"),
            rationale=data.get("rationale", "No rationale"),
            evidence_strength=data.get("evidence_strength"),
            clinical_trials_available=data.get("clinical_trials_available", False),
            recommended_therapies=data.get("recommended_therapies", []),
            references=data.get("references", []),
            **evidence.model_dump(include={
                'cosmic_id', 'ncbi_gene_id', 'dbsnp_id', 'clinvar_id',
                'clinvar_clinical_significance', 'clinvar_accession',
                'hgvs_genomic', 'hgvs_protein', 'hgvs_transcript',
                'snpeff_effect', 'polyphen2_prediction', 'cadd_score', 'gnomad_exome_af',
                'transcript_id', 'transcript_consequence'
            })
        )
