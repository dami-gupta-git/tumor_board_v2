"""Clinical trial evidence models."""

from pydantic import BaseModel, Field


class ClinicalTrialEvidence(BaseModel):
    """Clinical trial information for a variant."""

    nct_id: str = Field(..., description="ClinicalTrials.gov NCT ID")
    title: str = Field(..., description="Trial title")
    status: str = Field(..., description="Recruitment status")
    phase: str | None = Field(None, description="Trial phase (e.g., PHASE1, PHASE2)")
    conditions: list[str] = Field(default_factory=list, description="Cancer types/conditions")
    interventions: list[str] = Field(default_factory=list, description="Drug/treatment names")
    sponsor: str | None = Field(None, description="Lead sponsor")
    url: str = Field(..., description="ClinicalTrials.gov URL")
    variant_specific: bool = Field(False, description="True if variant explicitly mentioned")

    def is_phase2_or_later(self) -> bool:
        """Check if trial is Phase 2 or later."""
        if not self.phase:
            return False
        phase_upper = self.phase.upper()
        return any(p in phase_upper for p in ['PHASE2', 'PHASE3', 'PHASE 2', 'PHASE 3', 'PHASE4', 'PHASE 4'])

    def is_phase1(self) -> bool:
        """Check if trial is Phase 1."""
        if not self.phase:
            return False
        phase_upper = self.phase.upper()
        return 'PHASE1' in phase_upper or 'PHASE 1' in phase_upper

    def get_drug_names(self) -> list[str]:
        """Extract drug names from interventions."""
        # Filter out non-drug interventions
        drugs = []
        for intervention in self.interventions:
            # Skip common non-drug interventions
            intervention_lower = intervention.lower()
            if any(skip in intervention_lower for skip in [
                'placebo', 'observation', 'standard of care', 'best supportive',
                'radiation', 'surgery', 'biopsy', 'imaging'
            ]):
                continue
            drugs.append(intervention)
        return drugs
