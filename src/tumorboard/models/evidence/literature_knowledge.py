"""Literature-extracted knowledge models."""

from pydantic import BaseModel, Field


class DrugResistance(BaseModel):
    """Drug resistance information extracted from literature."""
    drug: str = Field(..., description="Drug name")
    evidence: str = Field("unknown", description="Evidence level: in vitro, preclinical, clinical, FDA-labeled")
    mechanism: str | None = Field(None, description="Mechanism of resistance if known")
    is_predictive: bool = Field(True, description="True if PREDICTIVE resistance (affects drug selection), False if just prognostic")


class DrugSensitivity(BaseModel):
    """Drug sensitivity information extracted from literature."""
    drug: str = Field(..., description="Drug name")
    evidence: str = Field("unknown", description="Evidence level: in vitro, preclinical, clinical, FDA-labeled")
    ic50_nM: str | None = Field(None, description="IC50 value if reported")


class TierRecommendation(BaseModel):
    """Tier recommendation from literature analysis."""
    tier: str = Field("III", description="Recommended tier: I, II, III, or IV")
    rationale: str = Field("", description="Rationale for tier recommendation")


class LiteratureKnowledge(BaseModel):
    """Structured knowledge extracted from literature about a variant.

    This represents synthesized findings from multiple papers analyzed
    by LLM to extract clinically actionable information.
    """

    mutation_type: str = Field(
        "unknown",
        description="primary (driver), secondary (acquired/resistance), both, or unknown"
    )

    is_prognostic_only: bool = Field(
        False,
        description="True if variant is ONLY prognostic (affects survival) but does NOT predict response to specific drugs"
    )

    resistant_to: list[DrugResistance] = Field(
        default_factory=list,
        description="Drugs this variant causes resistance to"
    )

    sensitive_to: list[DrugSensitivity] = Field(
        default_factory=list,
        description="Drugs this variant may respond to"
    )

    clinical_significance: str = Field(
        "",
        description="Summary of clinical implications"
    )

    evidence_level: str = Field(
        "None",
        description="Highest evidence level: FDA-approved, Phase 3, Phase 2, Preclinical, Case reports, None"
    )

    tier_recommendation: TierRecommendation = Field(
        default_factory=lambda: TierRecommendation(tier="III", rationale="Unknown"),
        description="Recommended AMP/ASCO/CAP tier based on literature"
    )

    references: list[str] = Field(
        default_factory=list,
        description="PMIDs supporting the findings"
    )

    key_findings: list[str] = Field(
        default_factory=list,
        description="Most important findings from literature"
    )

    confidence: float = Field(
        0.0,
        description="Confidence score 0-1 for extraction quality"
    )

    def get_resistance_drugs(self, predictive_only: bool = False) -> list[str]:
        """Get list of drug names this variant is resistant to.

        Args:
            predictive_only: If True, only return drugs with PREDICTIVE resistance
                           (affects drug selection), not prognostic associations.
        """
        if predictive_only:
            return [r.drug for r in self.resistant_to if r.is_predictive]
        return [r.drug for r in self.resistant_to]

    def get_sensitivity_drugs(self) -> list[str]:
        """Get list of drug names this variant may respond to."""
        return [s.drug for s in self.sensitive_to]

    def is_resistance_marker(self, predictive_only: bool = True) -> bool:
        """Check if this variant is primarily a resistance marker.

        Args:
            predictive_only: If True (default), only count PREDICTIVE resistance
                           (affects drug selection), not prognostic associations.
        """
        if self.is_prognostic_only:
            return False
        if predictive_only:
            return any(r.is_predictive for r in self.resistant_to)
        return len(self.resistant_to) > 0

    def has_therapeutic_options(self) -> bool:
        """Check if there are potential therapeutic options."""
        return len(self.sensitive_to) > 0

    def format_summary(self) -> str:
        """Format a human-readable summary of the extracted knowledge."""
        lines = []

        if self.mutation_type != "unknown":
            lines.append(f"Mutation Type: {self.mutation_type}")

        if self.resistant_to:
            drugs = ", ".join(f"{r.drug} ({r.evidence})" for r in self.resistant_to)
            lines.append(f"Resistant to: {drugs}")

        if self.sensitive_to:
            drugs = ", ".join(f"{s.drug} ({s.evidence})" for s in self.sensitive_to)
            lines.append(f"Potentially sensitive to: {drugs}")

        if self.clinical_significance:
            lines.append(f"Clinical Significance: {self.clinical_significance}")

        if self.key_findings:
            lines.append("Key Findings:")
            for finding in self.key_findings[:3]:
                lines.append(f"  • {finding}")

        if self.tier_recommendation.tier:
            lines.append(f"Literature-based Tier: {self.tier_recommendation.tier}")
            if self.tier_recommendation.rationale:
                lines.append(f"  Rationale: {self.tier_recommendation.rationale}")

        if self.references:
            lines.append(f"References: {', '.join(self.references[:5])}")

        return "\n".join(lines)
