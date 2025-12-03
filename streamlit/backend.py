"""
Backend logic for TumorBoard Streamlit app.

Integrates with the existing tumorboard package for:
- Variant assessment (single and batch)
- Validation against gold standard
- Evidence gathering from MyVariant.info
"""

import asyncio
from typing import Any, Dict, List, Optional, Callable

from tumorboard.api.myvariant import MyVariantClient
from tumorboard.engine import AssessmentEngine
from tumorboard.models.variant import VariantInput
from tumorboard.validation.validator import Validator


async def assess_variant(
    gene: str,
    variant: str,
    tumor_type: Optional[str] = None,
    model: str = "gpt-4o-mini",
    temperature: float = 0.1
) -> Dict[str, Any]:
    """
    Assess a single variant for clinical actionability.

    Args:
        gene: Gene symbol (e.g., BRAF)
        variant: Variant notation (e.g., V600E)
        tumor_type: Optional tumor type (e.g., Melanoma)
        model: LLM model to use
        temperature: LLM temperature (0.0-1.0)

    Returns:
        Dict containing assessment results with tier, confidence, identifiers, etc.
    """
    try:
        # Create assessment engine
        engine = AssessmentEngine(llm_model=model, llm_temperature=temperature)

        # Create variant input
        variant_input = VariantInput(
            gene=gene,
            variant=variant,
            tumor_type=tumor_type
        )

        # Run assessment
        async with engine:
            assessment = await engine.assess_variant(variant_input)

        # Convert to dict for JSON serialization
        return {
            "variant": {
                "gene": assessment.gene,
                "variant": assessment.variant,
                "tumor_type": assessment.tumor_type,
            },
            "assessment": {
                "tier": assessment.tier.value,
                "confidence": assessment.confidence_score,
                "rationale": assessment.rationale,
                "summary": assessment.summary,
                "evidence_strength": assessment.evidence_strength,
            },
            "identifiers": {
                "cosmic_id": assessment.cosmic_id,
                "ncbi_gene_id": assessment.ncbi_gene_id,
                "dbsnp_id": assessment.dbsnp_id,
                "clinvar_id": assessment.clinvar_id,
            },
            "hgvs": {
                "genomic": assessment.hgvs_genomic,
                "protein": assessment.hgvs_protein,
                "transcript": assessment.hgvs_transcript,
            },
            "clinvar": {
                "clinical_significance": assessment.clinvar_clinical_significance,
                "accession": assessment.clinvar_accession,
            },
            "annotations": {
                "snpeff_effect": assessment.snpeff_effect,
                "polyphen2_prediction": assessment.polyphen2_prediction,
                "cadd_score": assessment.cadd_score,
                "gnomad_exome_af": assessment.gnomad_exome_af,
            },
            "transcript": {
                "id": assessment.transcript_id,
                "consequence": assessment.transcript_consequence,
            },
            "recommended_therapies": [
                {
                    "drug_name": therapy.drug_name,
                    "evidence_level": therapy.evidence_level,
                    "approval_status": therapy.approval_status,
                    "clinical_context": therapy.clinical_context,
                }
                for therapy in assessment.recommended_therapies
            ],
        }

    except Exception as e:
        return {"error": f"Assessment failed: {str(e)}"}


async def batch_assess_variants(
    variants: List[Dict[str, str]],
    model: str = "gpt-4o-mini",
    temperature: float = 0.1,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[Dict[str, Any]]:
    """
    Assess multiple variants concurrently.

    Args:
        variants: List of dicts with 'gene', 'variant', and optional 'tumor_type'
        model: LLM model to use
        temperature: LLM temperature (0.0-1.0)
        progress_callback: Optional callback(current, total) for progress updates

    Returns:
        List of assessment results
    """
    try:
        # Create assessment engine
        engine = AssessmentEngine(llm_model=model, llm_temperature=temperature)

        # Create variant inputs
        variant_inputs = [
            VariantInput(
                gene=v['gene'],
                variant=v['variant'],
                tumor_type=v.get('tumor_type')
            )
            for v in variants
        ]

        # Run batch assessment
        async with engine:
            # Process with progress tracking
            results = []
            for i, variant_input in enumerate(variant_inputs):
                if progress_callback:
                    progress_callback(i + 1, len(variant_inputs))

                try:
                    assessment = await engine.assess_variant(variant_input)

                    # Convert to dict
                    result = {
                        "variant": {
                            "gene": assessment.gene,
                            "variant": assessment.variant,
                            "tumor_type": assessment.tumor_type,
                        },
                        "assessment": {
                            "tier": assessment.tier.value,
                            "confidence": assessment.confidence_score,
                            "rationale": assessment.rationale,
                            "summary": assessment.summary,
                            "evidence_strength": assessment.evidence_strength,
                        },
                        "identifiers": {
                            "cosmic_id": assessment.cosmic_id,
                            "ncbi_gene_id": assessment.ncbi_gene_id,
                            "dbsnp_id": assessment.dbsnp_id,
                            "clinvar_id": assessment.clinvar_id,
                        },
                        "recommended_therapies": [
                            {
                                "drug_name": therapy.drug_name,
                                "evidence_level": therapy.evidence_level,
                                "approval_status": therapy.approval_status,
                                "clinical_context": therapy.clinical_context,
                            }
                            for therapy in assessment.recommended_therapies
                        ],
                    }
                    results.append(result)

                except Exception as e:
                    results.append({
                        "variant": {
                            "gene": variant_input.gene,
                            "variant": variant_input.variant,
                            "tumor_type": variant_input.tumor_type,
                        },
                        "error": str(e)
                    })

            return results

    except Exception as e:
        return [{"error": f"Batch assessment failed: {str(e)}"}]


async def validate_gold_standard(
    gold_standard_path: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.1
) -> Dict[str, Any]:
    """
    Validate LLM performance against gold standard dataset.

    Args:
        gold_standard_path: Path to gold standard JSON file
        model: LLM model to use
        temperature: LLM temperature (0.0-1.0)

    Returns:
        Dict containing validation metrics (accuracy, per-tier metrics, etc.)
    """
    try:
        # Create assessment engine
        engine = AssessmentEngine(llm_model=model, llm_temperature=temperature)

        # Create validator
        validator = Validator(engine=engine)

        # Run validation
        async with engine:
            metrics = await validator.validate_from_file(
                gold_standard_path=gold_standard_path,
                max_concurrent=3
            )

        # Convert to dict for JSON serialization
        return {
            "overall_accuracy": metrics.accuracy,
            "total_cases": metrics.total_cases,
            "correct_predictions": metrics.correct_predictions,
            "average_confidence": metrics.average_confidence,
            "per_tier_metrics": {
                tier_name: {
                    "precision": tier_metrics.precision,
                    "recall": tier_metrics.recall,
                    "f1_score": tier_metrics.f1_score,
                    "true_positives": tier_metrics.true_positives,
                    "false_positives": tier_metrics.false_positives,
                    "false_negatives": tier_metrics.false_negatives,
                }
                for tier_name, tier_metrics in metrics.tier_metrics.items()
            },
            "failure_analysis": metrics.failure_analysis,
        }

    except FileNotFoundError:
        return {"error": f"Gold standard file not found: {gold_standard_path}"}
    except Exception as e:
        return {"error": f"Validation failed: {str(e)}"}


# Future feature placeholders

async def fetch_esmfold_structure(gene: str) -> str:
    """
    Fetch protein structure from ESMFold API.

    TODO: Implement ESMFold integration
    - Call ESMFold API with gene sequence
    - Return PDB format string for visualization
    - Cache results to avoid repeated API calls

    Returns:
        PDB format string
    """
    raise NotImplementedError("ESMFold integration coming soon")


async def predict_splice_impact(
    gene: str,
    variant: str,
    hgvs_genomic: str
) -> Dict[str, Any]:
    """
    Run SpliceAI predictions for variant.

    TODO: Implement SpliceAI integration
    - Load SpliceAI model
    - Run predictions for genomic position
    - Return acceptor/donor gain/loss scores

    Returns:
        Dict with splice scores and positions
    """
    raise NotImplementedError("SpliceAI integration coming soon")


async def fetch_tumor_type_suggestions(gene: str, variant: str) -> List[str]:
    """
    Fetch tumor type suggestions from CIViC and OncoTree for gene+variant autocomplete.

    Combines:
    1. CIViC evidence-based tumor types (specific to this variant)
    2. OncoTree standardized codes and names (comprehensive catalog)

    Args:
        gene: Gene symbol (e.g., "BRAF")
        variant: Variant notation (e.g., "V600E")

    Returns:
        List of tumor/disease types in format "CODE - Name" or just "Name"
    """
    try:
        if not gene or not variant:
            return []

        from tumorboard.api.oncotree import OncoTreeClient

        # Fetch from both sources in parallel
        async with MyVariantClient() as civic_client:
            async with OncoTreeClient() as oncotree_client:
                civic_types, oncotree_formatted = await asyncio.gather(
                    civic_client.fetch_tumortypes(gene, variant),
                    oncotree_client.get_tumor_type_names_for_ui(),
                    return_exceptions=True
                )

        # Handle errors gracefully
        if isinstance(civic_types, Exception):
            civic_types = []
        if isinstance(oncotree_formatted, Exception):
            oncotree_formatted = []

        # Combine results: CIViC first (variant-specific), then OncoTree (comprehensive)
        combined = []

        # Add CIViC tumor types (evidence-based for this variant)
        if civic_types:
            combined.extend(civic_types)

        # Add OncoTree codes and names (comprehensive catalog)
        # OncoTree types are already prioritized (common cancers first)
        if oncotree_formatted:
            # Add top 50 OncoTree types (includes all common cancers)
            combined.extend(oncotree_formatted[:50])

        # Remove duplicates while preserving order
        seen = set()
        unique_types = []
        for tumor_type in combined:
            tumor_type_upper = tumor_type.upper()
            if tumor_type_upper not in seen:
                seen.add(tumor_type_upper)
                unique_types.append(tumor_type)

        return unique_types

    except Exception:
        # Return empty list on error
        return []


async def run_agent_workflow(
    gene: str,
    variant: str,
    tumor_type: str
) -> Dict[str, Any]:
    """
    Execute multi-agent analysis workflow.

    TODO: Implement LangGraph/CrewAI agentic workflow
    - Evidence gathering agent (MyVariant.info)
    - Structure prediction agent (ESMFold)
    - Splice analysis agent (SpliceAI)
    - Literature search agent (PubMed)
    - Synthesis agent (LLM summary)

    Returns:
        Comprehensive analysis report
    """
    raise NotImplementedError("Agentic workflow coming soon")