"""Flask REST API for TumorBoard variant assessment."""

import asyncio
import logging
import os
from typing import Any

from asgiref.wsgi import WsgiToAsgi
from flask import Flask, jsonify, request
from flask_cors import CORS

from tumorboard.api.myvariant import MyVariantClient
from tumorboard.engine import AssessmentEngine
from tumorboard.models.variant import VariantInput

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create Flask app
flask_app = Flask(__name__)

# Enable CORS for Angular frontend
CORS(flask_app, resources={r"/api/*": {"origins": "*"}})


def get_engine() -> AssessmentEngine:
    """Get or create AssessmentEngine instance."""
    return AssessmentEngine()


@flask_app.route("/api/health", methods=["GET"])
def health_check() -> tuple[dict[str, str], int]:
    """Health check endpoint.

    Returns:
        Health status response
    """
    return jsonify({"status": "healthy", "service": "TumorBoard API"}), 200


@flask_app.route("/api/assess", methods=["POST"])
def assess_variant() -> tuple[dict[str, Any], int]:
    """Assess a variant for clinical actionability.

    Request body:
        {
            "gene": "BRAF",
            "variant": "V600E",
            "tumor_type": "Melanoma"  # optional
        }

    Returns:
        Assessment results with tier, confidence, and evidence
    """
    try:
        # Validate request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        # Validate required fields
        if "gene" not in data or "variant" not in data:
            return jsonify({"error": "Both 'gene' and 'variant' are required"}), 400

        # Create variant input
        variant_input = VariantInput(
            gene=data["gene"],
            variant=data["variant"],
            tumor_type=data.get("tumor_type"),
        )

        # Run assessment
        logger.info(f"Assessing variant: {variant_input.gene} {variant_input.variant}")
        engine = get_engine()
        assessment = asyncio.run(engine.assess_variant(variant_input))

        # Convert to dict for JSON response
        response = {
            "variant": {
                "gene": assessment.gene,
                "variant": assessment.variant,
                "tumor_type": assessment.tumor_type,
            },
            "assessment": {
                "tier": assessment.tier,
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

        logger.info(f"Assessment complete: {assessment.tier}, {assessment.confidence_score:.1%} confidence")
        return jsonify(response), 200

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Assessment failed: {str(e)}", exc_info=True)
        return jsonify({"error": f"Assessment failed: {str(e)}"}), 500


@flask_app.route("/api/evidence/<gene>/<variant>", methods=["GET"])
def get_evidence(gene: str, variant: str) -> tuple[dict[str, Any], int]:
    """Get raw evidence for a variant from MyVariant.info.

    Args:
        gene: Gene symbol (e.g., BRAF)
        variant: Variant notation (e.g., V600E)

    Returns:
        Raw evidence from MyVariant.info API
    """

    async def fetch_evidence_async() -> Any:
        """Helper to run async code."""
        async with MyVariantClient() as client:
            return await client.fetch_evidence(gene, variant)

    try:
        logger.info(f"Fetching evidence for: {gene} {variant}")
        evidence = asyncio.run(fetch_evidence_async())

        # Convert Evidence model to dict
        response = {
            "variant_id": evidence.variant_id,
            "gene": evidence.gene,
            "variant": evidence.variant,
            "identifiers": {
                "cosmic_id": evidence.cosmic_id,
                "ncbi_gene_id": evidence.ncbi_gene_id,
                "dbsnp_id": evidence.dbsnp_id,
                "clinvar_id": evidence.clinvar_id,
            },
            "hgvs": {
                "genomic": evidence.hgvs_genomic,
                "protein": evidence.hgvs_protein,
                "transcript": evidence.hgvs_transcript,
            },
            "clinvar": {
                "clinical_significance": evidence.clinvar_clinical_significance,
                "accession": evidence.clinvar_accession,
            },
            "annotations": {
                "snpeff_effect": evidence.snpeff_effect,
                "polyphen2_prediction": evidence.polyphen2_prediction,
                "cadd_score": evidence.cadd_score,
                "gnomad_exome_af": evidence.gnomad_exome_af,
            },
            "transcript": {
                "id": evidence.transcript_id,
                "consequence": evidence.transcript_consequence,
            },
            "civic_evidence_count": len(evidence.civic),
            "clinvar_evidence_count": len(evidence.clinvar),
            "cosmic_evidence_count": len(evidence.cosmic),
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Failed to fetch evidence: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to fetch evidence: {str(e)}"}), 500


@flask_app.errorhandler(404)
def not_found(error: Any) -> tuple[dict[str, str], int]:
    """Handle 404 errors."""
    return jsonify({"error": "Endpoint not found"}), 404


@flask_app.errorhandler(500)
def internal_error(error: Any) -> tuple[dict[str, str], int]:
    """Handle 500 errors."""
    logger.error(f"Internal server error: {str(error)}", exc_info=True)
    return jsonify({"error": "Internal server error"}), 500


# Wrap Flask app with ASGI adapter for async support
app = WsgiToAsgi(flask_app)


if __name__ == "__main__":
    # Get port from environment or default to 5000
    port = int(os.environ.get("PORT", 5000))

    # Run Flask app directly (for development)
    flask_app.run(
        host="0.0.0.0",
        port=port,
        debug=os.environ.get("FLASK_ENV") == "development",
    )
