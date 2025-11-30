"""Evidence data models from external databases."""

from typing import Any

from pydantic import BaseModel, Field

from tumorboard.models.annotations import VariantAnnotations


class CIViCEvidence(BaseModel):
    """Evidence from CIViC (Clinical Interpretations of Variants in Cancer)."""

    evidence_type: str | None = None
    evidence_level: str | None = None
    evidence_direction: str | None = None
    clinical_significance: str | None = None
    disease: str | None = None
    drugs: list[str] = Field(default_factory=list)
    description: str | None = None
    source: str | None = None
    rating: int | None = None


class ClinVarEvidence(BaseModel):
    """Evidence from ClinVar."""

    clinical_significance: str | None = None
    review_status: str | None = None
    conditions: list[str] = Field(default_factory=list)
    last_evaluated: str | None = None
    variation_id: str | None = None


class COSMICEvidence(BaseModel):
    """Evidence from COSMIC (Catalogue of Somatic Mutations in Cancer)."""

    mutation_id: str | None = None
    primary_site: str | None = None
    site_subtype: str | None = None
    primary_histology: str | None = None
    histology_subtype: str | None = None
    sample_count: int | None = None
    mutation_somatic_status: str | None = None


class Evidence(VariantAnnotations):
    """Aggregated evidence from multiple sources."""

    variant_id: str
    gene: str
    variant: str

    # Evidence from databases
    civic: list[CIViCEvidence] = Field(default_factory=list)
    clinvar: list[ClinVarEvidence] = Field(default_factory=list)
    cosmic: list[COSMICEvidence] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)

    def has_evidence(self) -> bool:
        """Check if any evidence was found."""
        return bool(self.civic or self.clinvar or self.cosmic)

    def summary(self) -> str:
        """Generate a text summary of all evidence."""
        lines = [f"Evidence for {self.gene} {self.variant}:\n"]

        if self.civic:
            lines.append(f"CIViC Evidence ({len(self.civic)} entries):")
            for idx, ev in enumerate(self.civic[:5], 1):  # Limit to top 5
                lines.append(f"  {idx}. {ev.evidence_type or 'Unknown type'}")
                if ev.disease:
                    lines.append(f"     Disease: {ev.disease}")
                if ev.drugs:
                    lines.append(f"     Drugs: {', '.join(ev.drugs)}")
                if ev.clinical_significance:
                    lines.append(f"     Significance: {ev.clinical_significance}")
                if ev.description:
                    lines.append(f"     Description: {ev.description[:200]}...")
            lines.append("")

        if self.clinvar:
            lines.append(f"ClinVar Evidence ({len(self.clinvar)} entries):")
            for idx, ev in enumerate(self.clinvar[:5], 1):
                lines.append(f"  {idx}. Significance: {ev.clinical_significance or 'Unknown'}")
                if ev.conditions:
                    lines.append(f"     Conditions: {', '.join(ev.conditions)}")
                if ev.review_status:
                    lines.append(f"     Review Status: {ev.review_status}")
            lines.append("")

        if self.cosmic:
            lines.append(f"COSMIC Evidence ({len(self.cosmic)} entries):")
            for idx, ev in enumerate(self.cosmic[:5], 1):
                lines.append(f"  {idx}. Primary Site: {ev.primary_site or 'Unknown'}")
                if ev.primary_histology:
                    lines.append(f"     Histology: {ev.primary_histology}")
                if ev.sample_count:
                    lines.append(f"     Sample Count: {ev.sample_count}")
            lines.append("")

        return "\n".join(lines) if len(lines) > 1 else "No evidence found."
