"""Variant data models."""

from pydantic import BaseModel, ConfigDict, Field


class VariantInput(BaseModel):
    """Input for variant assessment."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "gene": "BRAF",
                "variant": "V600E",
                "tumor_type": "Melanoma",
            }
        }
    )

    gene: str = Field(..., description="Gene symbol (e.g., BRAF)")
    variant: str = Field(..., description="Variant notation (e.g., V600E)")
    tumor_type: str | None = Field(None, description="Tumor type (e.g., Melanoma)")

    def to_hgvs(self) -> str:
        """Convert to HGVS-like notation for API queries."""
        return f"{self.gene}:{self.variant}"
