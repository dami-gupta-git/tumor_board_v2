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