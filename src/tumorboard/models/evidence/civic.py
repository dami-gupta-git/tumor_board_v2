from pydantic import BaseModel, Field

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





class CIViCAssertionEvidence(BaseModel):
    """Evidence from CIViC Assertions (curated AMP/ASCO/CAP classifications)."""

    assertion_id: int | None = None
    name: str | None = None
    amp_level: str | None = None
    amp_tier: str | None = None
    amp_level_letter: str | None = None
    assertion_type: str | None = None
    significance: str | None = None
    status: str | None = None
    molecular_profile: str | None = None
    disease: str | None = None
    therapies: list[str] = Field(default_factory=list)
    fda_companion_test: bool | None = None
    nccn_guideline: str | None = None
    description: str | None = None
    is_sensitivity: bool = False
    is_resistance: bool = False

