from pydantic import BaseModel, Field

class VICCEvidence(BaseModel):
    """Evidence from VICC MetaKB (harmonized multi-KB interpretations)."""

    description: str | None = None
    gene: str | None = None
    variant: str | None = None
    disease: str | None = None
    drugs: list[str] = Field(default_factory=list)
    evidence_level: str | None = None
    response_type: str | None = None
    source: str | None = None
    publication_url: str | list[str] | None = None
    oncogenic: str | None = None
    is_sensitivity: bool = False
    is_resistance: bool = False
    oncokb_level: str | None = None
