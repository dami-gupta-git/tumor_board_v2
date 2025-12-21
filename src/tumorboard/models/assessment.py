"""Assessment and actionability models."""

import textwrap
from enum import Enum

from pydantic import BaseModel, Field, field_validator
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

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
        """Pretty report output with Rich formatting and soft-wrapping."""
        console = Console(width=80, force_terminal=True)

        # Build content sections
        tumor_display = self.tumor_type if self.tumor_type else "Not specified"

        # Header line
        header = f"[bold cyan]{self.gene} {self.variant}[/bold cyan]  |  Tumor: [italic]{tumor_display}[/italic]"

        # Tier with color coding
        tier_colors = {
            "Tier I": "bold green",
            "Tier II": "bold yellow",
            "Tier III": "bold red",
            "Tier IV": "dim",
            "Unknown": "dim",
        }
        tier_style = tier_colors.get(self.tier.value, "white")
        tier_line = f"[{tier_style}]{self.tier.value}[/{tier_style}]  |  Confidence: {self.confidence_score:.1%}"

        content_lines = [header, tier_line, ""]

        # Add identifiers if available
        identifiers = []
        if self.cosmic_id:
            identifiers.append(f"COSMIC: {self.cosmic_id}")
        if self.ncbi_gene_id:
            identifiers.append(f"NCBI: {self.ncbi_gene_id}")
        if self.dbsnp_id:
            identifiers.append(f"dbSNP: {self.dbsnp_id}")
        if self.clinvar_id:
            identifiers.append(f"ClinVar: {self.clinvar_id}")
        if identifiers:
            content_lines.append(f"[dim]IDs:[/dim] {' | '.join(identifiers)}")

        # Add HGVS notations if available (compact)
        if self.hgvs_protein:
            content_lines.append(f"[dim]HGVS:[/dim] {self.hgvs_protein}")

        # Add ClinVar significance if available
        if self.clinvar_clinical_significance:
            content_lines.append(f"[dim]ClinVar:[/dim] {self.clinvar_clinical_significance}")

        # Add key functional annotations if available
        annotations = []
        if self.alphamissense_prediction:
            am_display = {"P": "Pathogenic", "B": "Benign", "A": "Ambiguous"}.get(
                self.alphamissense_prediction, self.alphamissense_prediction
            )
            score_str = f" ({self.alphamissense_score:.2f})" if self.alphamissense_score else ""
            annotations.append(f"AlphaMissense: {am_display}{score_str}")
        if self.cadd_score is not None:
            annotations.append(f"CADD: {self.cadd_score:.2f}")
        if annotations:
            content_lines.append(f"[dim]Scores:[/dim] {' | '.join(annotations)}")

        # Clinical narrative - soft-wrapped
        content_lines.append("")
        wrapped_summary = textwrap.fill(self.summary, width=74)
        content_lines.append(wrapped_summary)

        # Therapies section
        if self.recommended_therapies:
            content_lines.append("")
            therapy_names = ", ".join([t.drug_name for t in self.recommended_therapies])
            wrapped_therapies = textwrap.fill(f"Therapies: {therapy_names}", width=74)
            content_lines.append(f"[bold green]{wrapped_therapies}[/bold green]")

        # Join all content
        content = "\n".join(content_lines)

        # Create panel with box styling
        panel = Panel(
            content,
            title="[bold white]Variant Assessment[/bold white]",
            border_style="blue",
            padding=(1, 2),
        )

        # Render to string
        with console.capture() as capture:
            console.print(panel)

        return capture.get()
