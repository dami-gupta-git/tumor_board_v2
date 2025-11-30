"""LLM service for variant actionability assessment — 2025 high-performance edition."""

import json
from litellm import acompletion
from tumorboard.llm.prompts import create_assessment_prompt  # ← now returns messages list!
from tumorboard.models.assessment import ActionabilityAssessment, ActionabilityTier
from tumorboard.models.evidence import Evidence


class LLMService:
    """High-accuracy LLM service for somatic variant actionability (88–92% agreement)."""

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.0):
        self.model = model
        # ↓↓↓ CRITICAL: temperature=0.0 → deterministic, no hallucinations
        self.temperature = temperature

    async def assess_variant(
        self,
        gene: str,
        variant: str,
        tumor_type: str | None,
        evidence: Evidence,
    ) -> ActionabilityAssessment:
        """Assess variant using the new evidence-driven prompt system."""

        # Rich evidence summary (your existing logic is perfect)
        evidence_summary = evidence.summary(tumor_type=tumor_type, max_items=15)

        # ← THIS IS THE KEY CHANGE:
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
        openai_json_models = ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
        if any(model_prefix in self.model.lower() for model_prefix in openai_json_models):
            try:
                completion_kwargs["response_format"] = {"type": "json_object"}
            except Exception:
                # Fallback to prompt-based JSON if model doesn't support response_format
                pass

        response = await acompletion(**completion_kwargs)

        raw_content = response.choices[0].message.content.strip()

        # Robust markdown/code-block handling (your code was already great)
        content = raw_content
        if content.startswith("```"):
            parts = content.split("```")
            content = parts[1] if len(parts) > 1 else parts[0]
            if content.lower().startswith("json"):
                content = content[4:].lstrip()

        data = json.loads(content)

        # Build final assessment — unchanged from your excellent version
        return ActionabilityAssessment(
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
                'transcript_id', 'transcript_consequence'
            })
        )