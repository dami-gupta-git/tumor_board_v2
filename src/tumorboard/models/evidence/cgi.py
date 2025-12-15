from pydantic import BaseModel, Field

class CGIBiomarkerEvidence(BaseModel):
    """Evidence from Cancer Genome Interpreter biomarkers database."""

    gene: str | None = None
    alteration: str | None = None
    drug: str | None = None
    drug_status: str | None = None
    association: str | None = None
    evidence_level: str | None = None
    source: str | None = None
    tumor_type: str | None = None
    fda_approved: bool = False
