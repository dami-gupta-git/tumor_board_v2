"""Variant data models."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    @field_validator('variant')
    @classmethod
    def validate_variant_type(cls, v: str, info) -> str:
        """Validate that the variant is a SNP or small indel."""
        if 'gene' in info.data:
            from tumorboard.utils.variant_normalization import normalize_variant, VariantNormalizer
            gene = info.data['gene']
            normalized = normalize_variant(gene, v)
            variant_type = normalized['variant_type']

            # Only allow SNPs and small indels
            if variant_type not in VariantNormalizer.ALLOWED_VARIANT_TYPES:
                raise ValueError(
                    f"Variant type '{variant_type}' is not supported. "
                    f"Only SNPs and small indels are allowed (missense, nonsense, insertion, deletion, frameshift). "
                    f"Variant '{v}' is classified as '{variant_type}'."
                )
        return v

    def to_hgvs(self) -> str:
        """Convert to HGVS-like notation for API queries."""
        return f"{self.gene}:{self.variant}"
