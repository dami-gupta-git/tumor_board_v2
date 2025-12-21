"""LLM service for variant actionability narrative generation."""

import json
import re
from litellm import acompletion
from tumorboard.llm.prompts import create_narrative_prompt
from tumorboard.models import Evidence
from tumorboard.models.assessment import ActionabilityAssessment, ActionabilityTier

from tumorboard.utils.logging_config import get_logger


def extract_tier_from_hint(tier_hint: str) -> tuple[str, str]:
    """Extract tier level and sublevel from tier hint string.

    Args:
        tier_hint: The tier hint from Evidence.get_tier_hint()

    Returns:
        Tuple of (tier, sublevel) e.g., ("Tier I", "B") or ("Tier II", "A")
    """
    # Match patterns like "TIER I-A", "TIER II-B", "TIER III-C", etc.
    match = re.search(r'TIER\s+(I{1,3}|IV)[-\s]?([A-D])?', tier_hint, re.IGNORECASE)
    if match:
        tier_num = match.group(1).upper()
        sublevel = match.group(2).upper() if match.group(2) else ""
        return f"Tier {tier_num}", sublevel
    return "Tier III", ""  # Default to Tier III if no match


class LLMService:
    """LLM service for generating variant actionability narratives.

    The tier classification is determined deterministically by Evidence.get_tier_hint().
    The LLM's role is only to generate a clear, readable explanation of the classification.
    """

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.0, enable_logging: bool = False):
        self.model = model
        self.temperature = temperature
        self.enable_logging = enable_logging
        self.logger = get_logger(enable_console_logging=enable_logging) if enable_logging else None

    async def assess_variant(
        self,
        gene: str,
        variant: str,
        tumor_type: str | None,
        evidence: Evidence,
    ) -> ActionabilityAssessment:
        """Assess variant using deterministic tier + LLM narrative.

        The tier is computed deterministically from evidence.
        The LLM generates a human-readable explanation of why.
        """
        # Step 1: Get deterministic tier classification
        tier_hint = evidence.get_tier_hint(tumor_type=tumor_type)
        tier, sublevel = extract_tier_from_hint(tier_hint)
        full_tier = f"{tier}-{sublevel}" if sublevel else tier

        # Step 2: Get evidence summary for context
        evidence_summary = evidence.summary_compact(tumor_type=tumor_type)

        # Step 3: Create narrative prompt
        messages = create_narrative_prompt(
            gene=gene,
            variant=variant,
            tumor_type=tumor_type,
            tier=full_tier,
            tier_reason=tier_hint,
            evidence_summary=evidence_summary,
        )

        # Step 4: Call LLM for narrative generation
        completion_kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": 1000,
        }

        # Use JSON mode for OpenAI models
        if "gpt" in self.model.lower():
            completion_kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await acompletion(**completion_kwargs)
            raw_content = response.choices[0].message.content.strip()

            # Parse JSON response
            content = raw_content
            if content.startswith("```"):
                parts = content.split("```")
                content = parts[1] if len(parts) > 1 else parts[0]
                if content.lower().startswith("json"):
                    content = content[4:].lstrip()

            data = json.loads(content)

            # Build assessment with deterministic tier + LLM narrative
            assessment = ActionabilityAssessment(
                gene=gene,
                variant=variant,
                tumor_type=tumor_type,
                tier=ActionabilityTier(tier),  # Use deterministic tier
                confidence_score=self._tier_to_confidence(tier, sublevel),
                summary=data.get("summary", tier_hint),
                rationale=data.get("rationale", tier_hint),
                evidence_strength=self._tier_to_strength(tier),
                clinical_trials_available=bool(evidence.clinical_trials),
                recommended_therapies=[],  # Could be populated from evidence
                references=data.get("key_evidence", []),
                **evidence.model_dump(include={
                    'cosmic_id', 'ncbi_gene_id', 'dbsnp_id', 'clinvar_id',
                    'clinvar_clinical_significance', 'clinvar_accession',
                    'hgvs_genomic', 'hgvs_protein', 'hgvs_transcript',
                    'snpeff_effect', 'polyphen2_prediction', 'cadd_score', 'gnomad_exome_af',
                    'alphamissense_score', 'alphamissense_prediction',
                    'transcript_id', 'transcript_consequence'
                })
            )

            return assessment

        except Exception as e:
            # On LLM failure, return assessment with tier hint as narrative
            return ActionabilityAssessment(
                gene=gene,
                variant=variant,
                tumor_type=tumor_type,
                tier=ActionabilityTier(tier),
                confidence_score=self._tier_to_confidence(tier, sublevel),
                summary=tier_hint,
                rationale=f"LLM narrative generation failed: {str(e)}. Classification based on: {tier_hint}",
                evidence_strength=self._tier_to_strength(tier),
                clinical_trials_available=bool(evidence.clinical_trials),
                recommended_therapies=[],
                references=[],
                **evidence.model_dump(include={
                    'cosmic_id', 'ncbi_gene_id', 'dbsnp_id', 'clinvar_id',
                    'clinvar_clinical_significance', 'clinvar_accession',
                    'hgvs_genomic', 'hgvs_protein', 'hgvs_transcript',
                    'snpeff_effect', 'polyphen2_prediction', 'cadd_score', 'gnomad_exome_af',
                    'alphamissense_score', 'alphamissense_prediction',
                    'transcript_id', 'transcript_consequence'
                })
            )

    def _tier_to_confidence(self, tier: str, sublevel: str) -> float:
        """Map tier to confidence score."""
        confidence_map = {
            ("Tier I", "A"): 0.95,
            ("Tier I", "B"): 0.85,
            ("Tier I", ""): 0.90,
            ("Tier II", "A"): 0.80,
            ("Tier II", "B"): 0.72,
            ("Tier II", "C"): 0.68,
            ("Tier II", "D"): 0.62,
            ("Tier II", ""): 0.70,
            ("Tier III", "A"): 0.50,
            ("Tier III", "B"): 0.45,
            ("Tier III", "C"): 0.40,
            ("Tier III", "D"): 0.35,
            ("Tier III", ""): 0.42,
            ("Tier IV", ""): 0.95,
        }
        return confidence_map.get((tier, sublevel), 0.50)

    def _tier_to_strength(self, tier: str) -> str:
        """Map tier to evidence strength."""
        if "I" in tier and "II" not in tier and "III" not in tier:
            return "Strong"
        elif "II" in tier:
            return "Moderate"
        else:
            return "Weak"
