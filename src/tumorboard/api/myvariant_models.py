"""Pydantic models for MyVariant.info API responses."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DbSNPGene(BaseModel):
    """Gene information from dbSNP."""

    geneid: int | None = None


class DbSNPData(BaseModel):
    """dbSNP data structure."""

    rsid: str | None = None
    gene: DbSNPGene | None = None


class ClinVarRCV(BaseModel):
    """ClinVar RCV record."""

    accession: str | None = None
    clinical_significance: str | None = None


class ClinVarData(BaseModel):
    """ClinVar data structure."""

    variant_id: int | str | None = None
    rcv: list[ClinVarRCV] | None = None


class CosmicData(BaseModel):
    """COSMIC data structure."""

    cosmic_id: str | None = None


class SnpEffAnn(BaseModel):
    """SnpEff annotation structure."""

    effect: str | None = None
    feature_id: str | None = None


class SnpEffData(BaseModel):
    """SnpEff data structure."""

    ann: SnpEffAnn | list[SnpEffAnn] | None = None


class PolyPhen2Hdiv(BaseModel):
    """PolyPhen2 HDIV data structure."""

    pred: str | None = None


class PolyPhen2Data(BaseModel):
    """PolyPhen2 data structure."""

    hdiv: PolyPhen2Hdiv | None = None


class CaddData(BaseModel):
    """CADD data structure."""

    phred: float | str | None = None


class DbNSFPData(BaseModel):
    """dbNSFP data structure."""

    polyphen2: PolyPhen2Data | None = None
    cadd: CaddData | None = None


class GnomadAF(BaseModel):
    """gnomAD allele frequency structure."""

    af: float | str | None = None


class GnomadExome(BaseModel):
    """gnomAD exome data structure."""

    af: GnomadAF | None = None


class MyVariantHit(BaseModel):
    """Single hit from MyVariant API response.

    This model uses Pydantic's automatic JSON parsing instead of
    manual extraction, making the code cleaner and more maintainable.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Variant identifier
    id: str = Field(alias="_id")

    # Database data
    dbsnp: DbSNPData | None = None
    clinvar: ClinVarData | list[ClinVarData] | None = None
    cosmic: CosmicData | list[CosmicData] | None = None
    snpeff: SnpEffData | None = None
    dbnsfp: DbNSFPData | None = None
    gnomad_exome: GnomadExome | None = None
    cadd: CaddData | None = None

    # HGVS notations
    hgvs: str | list[str] | None = None

    # Gene ID
    entrezgene: int | str | None = None

    # CIViC and other evidence (kept as dict for existing parsers)
    civic: dict[str, Any] | list[dict[str, Any]] | None = None


class MyVariantResponse(BaseModel):
    """MyVariant API response structure."""

    took: int | None = None
    total: int = 0  # Default to 0 if not provided
    max_score: float | None = None
    hits: list[MyVariantHit] = Field(default_factory=list)
