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


class FDAApproval(BaseModel):
    """FDA drug approval information."""

    drug_name: str | None = None
    brand_name: str | None = None
    generic_name: str | None = None
    indication: str | None = None
    approval_date: str | None = None
    marketing_status: str | None = None
    gene: str | None = None


class Evidence(VariantAnnotations):
    """Aggregated evidence from multiple sources."""

    variant_id: str
    gene: str
    variant: str

    # Evidence from databases
    civic: list[CIViCEvidence] = Field(default_factory=list)
    clinvar: list[ClinVarEvidence] = Field(default_factory=list)
    cosmic: list[COSMICEvidence] = Field(default_factory=list)
    fda_approvals: list[FDAApproval] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)

    def has_evidence(self) -> bool:
        """Check if any evidence was found."""
        return bool(self.civic or self.clinvar or self.cosmic or self.fda_approvals)

    def summary(self, tumor_type: str | None = None, max_items: int = 15) -> str:
        """Generate a text summary of all evidence.

        Args:
            tumor_type: Optional tumor type to filter and prioritize evidence
            max_items: Maximum number of evidence items to include (default: 15)

        Returns:
            Formatted evidence summary
        """
        lines = [f"Evidence for {self.gene} {self.variant}:\n"]

        if self.civic:
            # Helper function to sort by evidence level (A > B > C > D > E > None)
            def evidence_level_key(ev):
                level_priority = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4}
                return level_priority.get(ev.evidence_level, 99)

            # Filter and prioritize CIViC evidence
            civic_evidence = list(self.civic)

            # Prioritize PREDICTIVE evidence with drugs, sorted by evidence level
            predictive_with_drugs = [e for e in civic_evidence
                                      if e.evidence_type == "PREDICTIVE" and e.drugs]
            predictive_with_drugs = sorted(predictive_with_drugs, key=evidence_level_key)

            # Then tumor-type-specific evidence if tumor type provided, sorted by evidence level
            tumor_specific = []
            if tumor_type:
                tumor_specific = [e for e in civic_evidence
                                  if e.disease and tumor_type.lower() in e.disease.lower()
                                  and e not in predictive_with_drugs]
                tumor_specific = sorted(tumor_specific, key=evidence_level_key)

            # Then other predictive evidence, sorted by evidence level
            other_predictive = [e for e in civic_evidence
                                if e.evidence_type == "PREDICTIVE"
                                and e not in predictive_with_drugs
                                and e not in tumor_specific]
            other_predictive = sorted(other_predictive, key=evidence_level_key)

            # Then rest, sorted by evidence level
            remaining = [e for e in civic_evidence
                         if e not in predictive_with_drugs
                         and e not in tumor_specific
                         and e not in other_predictive]
            remaining = sorted(remaining, key=evidence_level_key)

            # Combine in priority order
            prioritized = predictive_with_drugs + tumor_specific + other_predictive + remaining

            lines.append(f"CIViC Evidence ({len(self.civic)} entries, showing top {min(len(prioritized), max_items)}):")
            for idx, ev in enumerate(prioritized[:max_items], 1):
                lines.append(f"  {idx}. Type: {ev.evidence_type or 'Unknown'} | Level: {ev.evidence_level or 'N/A'}")
                if ev.disease:
                    lines.append(f"     Disease: {ev.disease}")
                if ev.drugs:
                    lines.append(f"     Drugs: {', '.join(ev.drugs)}")
                if ev.clinical_significance:
                    lines.append(f"     Significance: {ev.clinical_significance}")
                if ev.description:
                    # Include more of the description
                    desc = ev.description[:300] if len(ev.description) > 300 else ev.description
                    lines.append(f"     Description: {desc}...")
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

        if self.fda_approvals:
            lines.append(f"FDA Approved Drugs ({len(self.fda_approvals)} entries):")
            for idx, approval in enumerate(self.fda_approvals[:10], 1):
                drug_display = approval.brand_name or approval.generic_name or approval.drug_name
                lines.append(f"  {idx}. Drug: {drug_display}")
                if approval.approval_date:
                    lines.append(f"     Approval Date: {approval.approval_date}")
                if approval.marketing_status:
                    lines.append(f"     Status: {approval.marketing_status}")
                if approval.indication:
                    # Truncate long indications
                    indication = approval.indication[:600] if len(approval.indication) > 600 else approval.indication
                    lines.append(f"     Indication: {indication}...")
            lines.append("")

        return "\n".join(lines) if len(lines) > 1 else "No evidence found."
