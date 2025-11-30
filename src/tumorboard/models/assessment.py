"""Assessment and actionability models."""

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from tumorboard.models.annotations import VariantAnnotations


class ActionabilityTier(str, Enum):
    """AMP/ASCO/CAP clinical actionability tiers.

    Tier I: Variants with strong clinical significance
    Tier II: Variants with potential clinical significance
    Tier III: Variants with unknown clinical significance
    Tier IV: Variants deemed benign or likely benign
    """

    TIER_I = "Tier I"
    TIER_II = "Tier II"
    TIER_III = "Tier III"
    TIER_IV = "Tier IV"
    UNKNOWN = "Unknown"


class RecommendedTherapy(BaseModel):
    """Recommended therapy based on variant."""

    drug_name: str = Field(..., description="Name of the therapeutic agent")
    evidence_level: str | None = Field(None, description="Level of supporting evidence")
    approval_status: str | None = Field(None, description="FDA approval status for this indication")
    clinical_context: str | None = Field(
        None, description="Clinical context (e.g., first-line, resistant)"
    )


class ActionabilityAssessment(VariantAnnotations):
    """Complete actionability assessment for a variant."""

    gene: str
    variant: str
    tumor_type: str | None
    tier: ActionabilityTier = Field(..., description="AMP/ASCO/CAP tier classification")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the assessment (0-1)"
    )
    summary: str = Field(..., description="Human-readable summary of the assessment")
    recommended_therapies: list[RecommendedTherapy] = Field(default_factory=list)
    rationale: str = Field(..., description="Detailed rationale for tier assignment")
    evidence_strength: str | None = Field(
        None, description="Overall strength of evidence (Strong/Moderate/Weak)"
    )
    clinical_trials_available: bool = Field(
        default=False, description="Whether relevant clinical trials exist"
    )
    references: list[str] = Field(
        default_factory=list, description="Key references supporting the assessment"
    )

    def to_report(self) -> str:
        """Simple report output."""
        tumor_display = self.tumor_type if self.tumor_type else "Not specified"
        report = f"\nVariant: {self.gene} {self.variant} | Tumor: {tumor_display}\n"
        report += f"Tier: {self.tier.value} | Confidence: {self.confidence_score:.1%}\n"

        # Add identifiers if available
        identifiers = []
        if self.cosmic_id:
            identifiers.append(f"COSMIC: {self.cosmic_id}")
        if self.ncbi_gene_id:
            identifiers.append(f"NCBI Gene: {self.ncbi_gene_id}")
        if self.dbsnp_id:
            identifiers.append(f"dbSNP: {self.dbsnp_id}")
        if self.clinvar_id:
            identifiers.append(f"ClinVar: {self.clinvar_id}")

        if identifiers:
            report += f"Identifiers: {' | '.join(identifiers)}\n"

        # Add HGVS notations if available
        hgvs_notations = []
        if self.hgvs_protein:
            hgvs_notations.append(f"Protein: {self.hgvs_protein}")
        if self.hgvs_transcript:
            hgvs_notations.append(f"Transcript: {self.hgvs_transcript}")
        if self.hgvs_genomic:
            hgvs_notations.append(f"Genomic: {self.hgvs_genomic}")

        if hgvs_notations:
            report += f"HGVS: {' | '.join(hgvs_notations)}\n"

        # Add ClinVar details if available
        clinvar_details = []
        if self.clinvar_clinical_significance:
            clinvar_details.append(f"Significance: {self.clinvar_clinical_significance}")
        if self.clinvar_accession:
            clinvar_details.append(f"Accession: {self.clinvar_accession}")

        if clinvar_details:
            report += f"ClinVar: {' | '.join(clinvar_details)}\n"

        # Add functional annotations if available
        annotations = []
        if self.snpeff_effect:
            annotations.append(f"Effect: {self.snpeff_effect}")
        if self.polyphen2_prediction:
            annotations.append(f"PolyPhen2: {self.polyphen2_prediction}")
        if self.cadd_score is not None:
            annotations.append(f"CADD: {self.cadd_score:.2f}")
        if self.gnomad_exome_af is not None:
            annotations.append(f"gnomAD AF: {self.gnomad_exome_af:.6f}")

        if annotations:
            report += f"Annotations: {' | '.join(annotations)}\n"

        # Add transcript information if available
        transcript_info = []
        if self.transcript_id:
            transcript_info.append(f"ID: {self.transcript_id}")
        if self.transcript_consequence:
            transcript_info.append(f"Consequence: {self.transcript_consequence}")

        if transcript_info:
            report += f"Transcript: {' | '.join(transcript_info)}\n"

        report += f"\n{self.summary}\n"

        if self.recommended_therapies:
            report += f"\nTherapies: {', '.join([t.drug_name for t in self.recommended_therapies])}\n"

        return report
