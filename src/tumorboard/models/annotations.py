"""Shared variant annotation models."""

from pydantic import BaseModel, Field


class VariantAnnotations(BaseModel):
    """Shared variant identifiers and annotations used across Evidence and Assessment models."""

    # Database identifiers
    cosmic_id: str | None = Field(None, description="COSMIC mutation ID")
    ncbi_gene_id: str | None = Field(None, description="NCBI Entrez Gene ID")
    dbsnp_id: str | None = Field(None, description="dbSNP rs number")
    clinvar_id: str | None = Field(None, description="ClinVar variation ID")
    clinvar_clinical_significance: str | None = Field(None, description="ClinVar clinical significance")
    clinvar_accession: str | None = Field(None, description="ClinVar accession number")
    hgvs_genomic: str | None = Field(None, description="HGVS genomic notation")
    hgvs_protein: str | None = Field(None, description="HGVS protein notation")
    hgvs_transcript: str | None = Field(None, description="HGVS transcript notation")

    # Functional annotations
    snpeff_effect: str | None = Field(None, description="SnpEff predicted effect")
    polyphen2_prediction: str | None = Field(None, description="PolyPhen2 HDIV prediction")
    cadd_score: float | None = Field(None, description="CADD phred score")
    gnomad_exome_af: float | None = Field(None, description="gnomAD exome allele frequency")

    # Transcript information
    transcript_id: str | None = Field(None, description="Reference transcript ID")
    transcript_consequence: str | None = Field(None, description="Transcript consequence")