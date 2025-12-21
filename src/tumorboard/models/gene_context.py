"""Gene context and role determination from multiple sources.

This module provides a fast, API-independent baseline for gene context that
can always provide therapeutic guidance even when CIViC/OncoKB APIs fail
or return no data for a specific variant.

The key insight is that gene role (DDR vs oncogene vs TSG) fundamentally
determines how we interpret variants:
- DDR genes: LOF → potential PARP/platinum sensitivity
- Oncogenes: Need specific activating mutations (hotspots)
- TSGs: LOF confirms pathogenicity but usually not directly targetable
"""

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Any


# =============================================================================
# GENE CLASS CONFIGURATION
# =============================================================================
# This replaces gene_classes.yaml - all gene class data is now inline

GENE_CLASS_CONFIG: dict[str, Any] = {
    # DNA Damage Repair (DDR) genes
    # Loss-of-function in these genes creates synthetic lethality with PARP inhibitors
    # and increases sensitivity to platinum-based chemotherapy
    "ddr": {
        "description": "DNA Damage Repair genes with therapeutic implications via synthetic lethality",
        "genes": [
            "ATM", "BRCA1", "BRCA2", "PALB2", "CHEK2", "RAD51C", "RAD51D",
            "BRIP1", "FANCA", "RAD51B", "BARD1", "CDK12", "NBN", "RAD50", "MRE11",
            # Additional DDR genes from curated list
            "RAD51", "FANCC", "FANCD2", "FANCE", "FANCF", "FANCG", "FANCI",
            "FANCL", "FANCM", "ATR", "CHEK1", "BLM", "WRN", "RECQL4",
        ],
        "therapeutic_implications": {
            "drugs": [
                "PARP inhibitors (olaparib, rucaparib, niraparib, talazoparib)",
                "Platinum agents (cisplatin, carboplatin)",
            ],
            "mechanism": (
                "Loss-of-function mutations in DDR genes impair homologous recombination "
                "repair, creating synthetic lethality with PARP inhibition. These tumors "
                "are also typically platinum-sensitive."
            ),
        },
        "tier_rules": {
            "conflicting_evidence": "II-C",
            "sensitivity_only": "II-D",
            "preclinical_only": "II-D",
        },
    },
    # Mismatch Repair (MMR) genes
    # Loss leads to MSI-H phenotype which predicts immunotherapy response
    "mmr": {
        "description": "Mismatch Repair genes - loss leads to MSI-H and immunotherapy sensitivity",
        "genes": ["MLH1", "MSH2", "MSH6", "PMS2", "EPCAM"],
        "therapeutic_implications": {
            "drugs": [
                "Immune checkpoint inhibitors (pembrolizumab, nivolumab, ipilimumab)",
            ],
            "mechanism": (
                "Loss of MMR function leads to microsatellite instability (MSI-H), "
                "increased tumor mutational burden, and neoantigen formation. "
                "MSI-H tumors have FDA-approved tumor-agnostic indication for pembrolizumab."
            ),
        },
        "tier_rules": {
            "conflicting_evidence": "II-C",
            "sensitivity_only": "II-B",
            "preclinical_only": "II-D",
        },
    },
    # Splicing Factor genes
    # Recurrent mutations in MDS/AML with emerging therapeutic implications
    "splicing": {
        "description": "Splicing factor genes with diagnostic/prognostic significance in MDS/AML",
        "genes": ["SF3B1", "SRSF2", "U2AF1", "ZRSR2"],
        "therapeutic_implications": {
            "drugs": [
                "Luspatercept (SF3B1-mutant MDS)",
                "Splicing modulators (investigational)",
            ],
            "mechanism": (
                "Splicing factor mutations are defining features of MDS subtypes. "
                "SF3B1 mutations predict response to luspatercept and favorable prognosis."
            ),
        },
        "tier_rules": {
            "conflicting_evidence": "II-C",
            "sensitivity_only": "II-C",
            "preclinical_only": "III-C",
        },
    },
}


class GeneClassConfig:
    """Configuration for gene class properties and tier rules."""

    def __init__(self, config: dict[str, Any]):
        self._config = config
        self._gene_to_class: dict[str, str] = {}

        # Build reverse mapping: gene -> class name
        for class_name, class_config in config.items():
            if isinstance(class_config, dict) and 'genes' in class_config:
                for gene in class_config['genes']:
                    self._gene_to_class[gene.upper()] = class_name

    def get_gene_class(self, gene: str) -> str | None:
        """Get the class name for a gene (e.g., 'ddr', 'mmr', 'splicing')."""
        return self._gene_to_class.get(gene.upper())

    def is_ddr_gene(self, gene: str) -> bool:
        """Check if a gene is a DNA Damage Repair gene."""
        return self.get_gene_class(gene) == 'ddr'

    def is_mmr_gene(self, gene: str) -> bool:
        """Check if a gene is a Mismatch Repair gene."""
        return self.get_gene_class(gene) == 'mmr'

    def is_splicing_gene(self, gene: str) -> bool:
        """Check if a gene is a splicing factor gene."""
        return self.get_gene_class(gene) == 'splicing'

    def get_genes_in_class(self, class_name: str) -> list[str]:
        """Get all genes in a specific class."""
        class_config = self._config.get(class_name, {})
        return class_config.get('genes', [])

    def get_therapeutic_drugs(self, gene: str) -> list[str]:
        """Get therapeutic drugs/classes for a gene's class."""
        class_name = self.get_gene_class(gene)
        if not class_name:
            return []

        class_config = self._config.get(class_name, {})
        implications = class_config.get('therapeutic_implications', {})
        return implications.get('drugs', [])

    def get_tier_for_evidence_pattern(self, gene: str, pattern: str) -> str | None:
        """Get the tier recommendation based on evidence pattern.

        Args:
            gene: Gene symbol
            pattern: One of 'conflicting_evidence', 'sensitivity_only', 'preclinical_only'

        Returns:
            Tier string (e.g., 'II-C', 'II-D') or None if not configured
        """
        class_name = self.get_gene_class(gene)
        if not class_name:
            return None

        class_config = self._config.get(class_name, {})
        tier_rules = class_config.get('tier_rules', {})
        return tier_rules.get(pattern)

    def get_class_description(self, gene: str) -> str | None:
        """Get the description for a gene's class."""
        class_name = self.get_gene_class(gene)
        if not class_name:
            return None

        class_config = self._config.get(class_name, {})
        return class_config.get('description')

    def get_therapeutic_mechanism(self, gene: str) -> str | None:
        """Get the therapeutic mechanism explanation for a gene's class."""
        class_name = self.get_gene_class(gene)
        if not class_name:
            return None

        class_config = self._config.get(class_name, {})
        implications = class_config.get('therapeutic_implications', {})
        return implications.get('mechanism')


@lru_cache(maxsize=1)
def load_gene_classes() -> GeneClassConfig:
    """Load gene class configuration.

    Returns:
        GeneClassConfig instance with loaded configuration.
    """
    return GeneClassConfig(GENE_CLASS_CONFIG)


class GeneRole(Enum):
    """Functional role of a gene in cancer."""
    ONCOGENE = "oncogene"
    TSG = "tumor_suppressor"
    TSG_PATHWAY_ACTIONABLE = "tsg_pathway_actionable"  # TSGs where LOF activates druggable pathway
    FUSION = "fusion"
    DDR = "ddr"  # DNA Damage Repair - special therapeutic handling
    UNKNOWN = "unknown"


# =============================================================================
# PATHWAY-ACTIONABLE TUMOR SUPPRESSORS
# =============================================================================
# These TSGs are special: LOF doesn't just confirm pathogenicity, it activates
# a downstream pathway that IS druggable. Unlike generic TSGs, these have
# FDA-approved therapies based on the TSG loss itself.
#
# Key distinction:
# - Generic TSG (e.g., RB1, APC): LOF = pathogenic but not directly targetable
# - Pathway-actionable TSG (e.g., PTEN): LOF = pathway activation = druggable
#
# Per AMP/ASCO/CAP 2017:
# - In high-prevalence tumors: Tier I-B (FDA-approved or well-powered studies)
# - In other tumors: Tier II-A (FDA approval in different tumor type)

PATHWAY_ACTIONABLE_TSGS: dict[str, dict] = {
    "PTEN": {
        "pathway": "PI3K/AKT/mTOR",
        "mechanism": "PTEN loss → unrestrained PI3K signaling → AKT/mTOR activation",
        "drugs": ["alpelisib", "capivasertib", "everolimus", "ipatasertib"],
        "high_prevalence_tumors": ["endometrial", "endometrium", "prostate", "breast", "glioblastoma", "gbm"],
        "fda_context": "Capivasertib (TRUQAP) FDA-approved for PIK3CA/AKT1/PTEN-altered breast cancer",
    },
    "TSC1": {
        "pathway": "mTOR",
        "mechanism": "TSC1 loss → mTORC1 hyperactivation → cell growth/proliferation",
        "drugs": ["everolimus", "sirolimus", "temsirolimus"],
        "high_prevalence_tumors": ["renal", "kidney", "bladder", "subependymal giant cell astrocytoma", "sega"],
        "fda_context": "Everolimus FDA-approved for TSC-associated tumors",
    },
    "TSC2": {
        "pathway": "mTOR",
        "mechanism": "TSC2 loss → mTORC1 hyperactivation → cell growth/proliferation",
        "drugs": ["everolimus", "sirolimus", "temsirolimus"],
        "high_prevalence_tumors": ["renal", "kidney", "bladder", "subependymal giant cell astrocytoma", "sega"],
        "fda_context": "Everolimus FDA-approved for TSC-associated tumors",
    },
    "NF1": {
        "pathway": "RAS/MAPK",
        "mechanism": "NF1 loss → unrestrained RAS signaling → MEK/ERK activation",
        "drugs": ["selumetinib", "trametinib", "binimetinib", "cobimetinib"],
        "high_prevalence_tumors": ["neurofibroma", "plexiform neurofibroma", "mpnst", "glioma", "melanoma"],
        "fda_context": "Selumetinib FDA-approved for NF1-associated plexiform neurofibromas",
    },
    "STK11": {
        "pathway": "AMPK/mTOR",
        "mechanism": "STK11/LKB1 loss → AMPK inactivation → mTOR activation, metabolic dysregulation",
        "drugs": ["everolimus", "metformin"],
        "high_prevalence_tumors": ["lung", "nsclc", "non-small cell lung", "cervical"],
        "fda_context": "Emerging evidence for mTOR inhibitors; also negative predictor for immunotherapy",
    },
    "VHL": {
        "pathway": "HIF",
        "mechanism": "VHL loss → HIF stabilization → VEGF/angiogenesis activation",
        "drugs": ["belzutifan", "axitinib", "pazopanib", "cabozantinib"],
        "high_prevalence_tumors": ["renal", "kidney", "clear cell renal", "ccRCC", "hemangioblastoma"],
        "fda_context": "Belzutifan FDA-approved for VHL-associated tumors including RCC",
    },
}


# =============================================================================
# ONCOGENE MUTATION CLASSES
# =============================================================================
# Some oncogenes have distinct mutation classes with different therapeutic profiles.
# Unlike simple hotspot detection, mutation class determines mechanism of action
# and drug sensitivity.
#
# BRAF is the canonical example:
# - Class I (V600): RAS-independent monomers → V600 inhibitors work
# - Class II (non-V600 activating): RAS-independent dimers → MEK inhibitors, not V600 inhibitors
# - Class III (kinase-impaired): RAS-dependent → context-dependent
#
# Per AMP/ASCO/CAP 2017:
# - Class II/III in tumors with FDA approval (NSCLC): Tier I
# - Class II/III in other tumors with evidence: Tier II

ONCOGENE_MUTATION_CLASSES: dict[str, dict] = {
    "BRAF": {
        "class_i": {
            "name": "Class I (V600)",
            "variants": ["V600E", "V600K", "V600D", "V600R", "V600M", "V600G"],
            "mechanism": "RAS-independent monomer signaling",
            "drugs": ["vemurafenib", "dabrafenib", "encorafenib"],
            "fda_tumors": ["melanoma", "nsclc", "lung", "colorectal", "thyroid", "hairy cell leukemia"],
            "note": "Standard V600-specific inhibitors are effective",
            "tumor_specific": {
                "colorectal": "Encorafenib + cetuximab (Braftovi + Erbitux) is FDA-approved standard-of-care for BRAF V600E mCRC. BRAF inhibitor monotherapy is ineffective in CRC due to EGFR feedback.",
                "melanoma": "Dabrafenib + trametinib or encorafenib + binimetinib are FDA-approved first-line for BRAF V600 melanoma.",
            },
        },
        "class_ii": {
            "name": "Class II (non-V600 activating)",
            # These variants signal as RAS-independent dimers
            # They are RESISTANT to V600-specific inhibitors but SENSITIVE to MEK inhibitors
            "variants": [
                "G469A", "G469V", "G469E", "G469R", "G469S",  # Glycine-rich loop
                "K601E", "K601N", "K601T",  # Activation loop
                "L597Q", "L597R", "L597S", "L597V",  # Catalytic loop
                "G464V", "G464E", "G464R",  # P-loop
                "G466V", "G466E", "G466A", "G466R",  # P-loop
                "N581S", "N581I", "N581K",  # Catalytic loop
                "F595L",  # DFG motif
                "A598V", "A598T",
                "T599I", "T599_V600insT",
                "V600_K601delinsE",
            ],
            "mechanism": "RAS-independent dimer signaling - RESISTANT to V600 inhibitors",
            "drugs": ["trametinib", "binimetinib", "cobimetinib", "selumetinib", "encorafenib + binimetinib"],
            "fda_tumors": ["nsclc", "lung"],  # 2024 FDA approval for encorafenib + binimetinib
            "fda_context": "Encorafenib + binimetinib FDA-approved for BRAF Class II/III NSCLC (2024)",
            "note": "V600 inhibitors cause paradoxical pathway activation - use MEK inhibitors",
        },
        "class_iii": {
            "name": "Class III (kinase-impaired)",
            # These have impaired kinase activity but still activate MAPK via RAS
            "variants": [
                "D594G", "D594N", "D594E", "D594H", "D594A", "D594V",  # Kinase-dead
                "G596R", "G596D", "G596C",
            ],
            "mechanism": "Kinase-impaired, RAS-dependent signaling",
            "drugs": ["trametinib", "binimetinib", "cobimetinib"],
            "fda_tumors": ["nsclc", "lung"],
            "fda_context": "Encorafenib + binimetinib FDA-approved for BRAF Class II/III NSCLC (2024)",
            "note": "Only effective in RAS-wildtype tumors; check KRAS/NRAS status",
        },
    },
}


def get_oncogene_mutation_class(gene: str, variant: str) -> dict | None:
    """Determine if an oncogene variant belongs to a known mutation class.

    Args:
        gene: Gene symbol (case-insensitive)
        variant: Variant notation (e.g., V600E, G469A)

    Returns:
        Dict with class info (name, mechanism, drugs, fda_tumors) or None if not classified
    """
    gene_upper = gene.upper()
    variant_upper = variant.upper()

    # Strip common prefixes
    if variant_upper.startswith("P."):
        variant_upper = variant_upper[2:]

    gene_classes = ONCOGENE_MUTATION_CLASSES.get(gene_upper)
    if not gene_classes:
        return None

    # Check each class
    for class_key, class_info in gene_classes.items():
        if variant_upper in class_info.get("variants", []):
            return {
                "gene": gene_upper,
                "variant": variant_upper,
                "class_key": class_key,
                "class_name": class_info["name"],
                "mechanism": class_info["mechanism"],
                "drugs": class_info["drugs"],
                "fda_tumors": class_info.get("fda_tumors", []),
                "fda_context": class_info.get("fda_context"),
                "note": class_info.get("note"),
                "tumor_specific": class_info.get("tumor_specific", {}),
            }

    return None


def is_oncogene_class_fda_tumor(gene: str, variant: str, tumor_type: str | None) -> bool:
    """Check if tumor type has FDA approval for this oncogene mutation class.

    Args:
        gene: Gene symbol
        variant: Variant notation
        tumor_type: Patient's tumor type

    Returns:
        True if FDA approval exists for this mutation class in this tumor type
    """
    if not tumor_type:
        return False

    class_info = get_oncogene_mutation_class(gene, variant)
    if not class_info:
        return False

    tumor_lower = tumor_type.lower()
    for fda_tumor in class_info.get("fda_tumors", []):
        if fda_tumor in tumor_lower or tumor_lower in fda_tumor:
            return True

    return False


@dataclass
class GeneContext:
    """Context about a gene from multiple sources."""
    gene: str
    is_cancer_gene: bool
    role: GeneRole
    source: str  # Where we got this info

    # Therapeutic context
    has_therapeutic_evidence: bool = False
    therapeutic_summary: str | None = None


# DNA Damage Repair genes - these have special therapeutic implications
# Source: PMID 32958822, PMID 29320312 (HRD gene reviews)
DDR_GENES = {
    # Core HRR genes
    "BRCA1", "BRCA2", "PALB2", "RAD51", "RAD51B", "RAD51C", "RAD51D",
    "BRIP1", "BARD1", "FANCA", "FANCC", "FANCD2", "FANCE", "FANCF",
    "FANCG", "FANCI", "FANCL", "FANCM",
    # Other DDR genes
    "ATM", "ATR", "CHEK1", "CHEK2", "NBN", "MRE11", "RAD50",
    "BLM", "WRN", "RECQL4",
    # MMR genes (different pathway but also DDR)
    "MLH1", "MSH2", "MSH6", "PMS2", "EPCAM",
}

# Oncogenes - gain-of-function mutations matter
# Source: OncoKB, COSMIC CGC
ONCOGENES = {
    "KRAS", "NRAS", "HRAS", "BRAF", "EGFR", "ERBB2", "MET", "ALK",
    "ROS1", "RET", "NTRK1", "NTRK2", "NTRK3", "FGFR1", "FGFR2",
    "FGFR3", "FGFR4", "PIK3CA", "AKT1", "MTOR", "KIT", "PDGFRA",
    "ABL1", "JAK2", "MPL", "CALR", "FLT3", "IDH1", "IDH2", "NPM1",
    "CTNNB1", "SMO", "PTPN11", "RAC1", "RHOA", "MAP2K1", "MAP2K2",
    "ARAF", "RAF1", "ERBB3", "ERBB4", "DDR2", "ESR1", "AR", "GNA11",
    "GNAQ", "SF3B1", "U2AF1", "SRSF2", "MYD88", "CXCR4", "BTK",
}

# Tumor suppressors - loss-of-function mutations matter
# Source: OncoKB, COSMIC CGC
TUMOR_SUPPRESSORS = {
    "TP53", "RB1", "PTEN", "APC", "CDKN2A", "CDKN2B", "CDKN1B",
    "NF1", "NF2", "VHL", "STK11", "KEAP1", "SMAD4", "FBXW7",
    "ARID1A", "ARID1B", "ARID2", "SMARCA4", "SMARCB1", "PBRM1",
    "BAP1", "SETD2", "KMT2A", "KMT2C", "KMT2D", "CREBBP", "EP300",
    "KDM6A", "ASXL1", "TET2", "DNMT3A", "WT1", "BCOR", "BCORL1",
    "PHF6", "STAG2", "RAD21", "SMC1A", "SMC3", "RUNX1", "GATA3",
    "RNF43", "ZNRF3", "AXIN1", "AXIN2", "CDH1", "MAP3K1", "CASP8",
    "HLA-A", "HLA-B", "B2M", "JAK1", "IFNGR1", "IFNGR2",
    "PTPRD", "PTPRT", "FAT1", "FAT4", "LATS1", "LATS2",
    "TSC1", "TSC2", "FLCN", "FH", "SDHB", "SDHC", "SDHD", "SDHA",
    "MAX", "MEN1", "DAXX", "ATRX", "CIC", "FUBP1", "NOTCH1",
    "NOTCH2", "TRAF7", "KLF4",
}

# Fusion genes - often rearrangements rather than point mutations
FUSION_GENES = {
    "ALK", "ROS1", "RET", "NTRK1", "NTRK2", "NTRK3",
    "FGFR2", "FGFR3", "NRG1", "BRAF", "MET", "EGFR",
    "PDGFRA", "PDGFRB", "ABL1", "JAK2", "FGFR1",
}


def get_pathway_actionable_info(gene: str) -> dict | None:
    """Get pathway-actionable TSG information if the gene qualifies.

    Args:
        gene: Gene symbol (case-insensitive)

    Returns:
        Dict with pathway, drugs, high_prevalence_tumors, etc. or None if not pathway-actionable
    """
    return PATHWAY_ACTIONABLE_TSGS.get(gene.upper())


def is_high_prevalence_tumor(gene: str, tumor_type: str | None) -> bool:
    """Check if tumor type is high-prevalence for a pathway-actionable TSG.

    Args:
        gene: Gene symbol
        tumor_type: Patient's tumor type

    Returns:
        True if this tumor type has high prevalence of the gene alteration
    """
    if not tumor_type:
        return False

    info = get_pathway_actionable_info(gene)
    if not info:
        return False

    tumor_lower = tumor_type.lower()
    for high_prev_tumor in info.get("high_prevalence_tumors", []):
        if high_prev_tumor in tumor_lower or tumor_lower in high_prev_tumor:
            return True

    return False


def get_gene_context(gene: str) -> GeneContext:
    """Determine gene context from curated lists.

    This is fast (no API calls) and provides baseline context.
    Checks YAML config first (user-maintainable), then falls back to hardcoded lists.

    Args:
        gene: Gene symbol (case-insensitive)

    Returns:
        GeneContext with role and therapeutic implications
    """
    gene_upper = gene.upper()

    # Try YAML config first (user-maintainable, includes DDR/MMR/splicing)
    _config = load_gene_classes()
    if _config.is_ddr_gene(gene_upper):
        drugs = _config.get_therapeutic_drugs(gene_upper)
        drugs_str = ", ".join(drugs) if drugs else "platinum agents, PARP inhibitors"
        return GeneContext(
            gene=gene_upper,
            is_cancer_gene=True,
            role=GeneRole.DDR,
            source="gene_classes.yaml",
            has_therapeutic_evidence=True,
            therapeutic_summary=f"DDR gene - LOF may confer sensitivity to {drugs_str}",
        )

    if _config.is_mmr_gene(gene_upper):
        return GeneContext(
            gene=gene_upper,
            is_cancer_gene=True,
            role=GeneRole.DDR,  # MMR is a subtype of DDR
            source="gene_classes.yaml",
            has_therapeutic_evidence=True,
            therapeutic_summary="MMR gene - deficiency causes MSI-H, eligible for checkpoint inhibitors",
        )

    # Fall back to hardcoded DDR list (may have genes not in YAML)
    if gene_upper in DDR_GENES:
        return GeneContext(
            gene=gene_upper,
            is_cancer_gene=True,
            role=GeneRole.DDR,
            source="curated_ddr_list",
            has_therapeutic_evidence=True,
            therapeutic_summary="DDR gene - LOF may confer platinum/PARP inhibitor sensitivity",
        )

    # Check oncogenes
    if gene_upper in ONCOGENES:
        return GeneContext(
            gene=gene_upper,
            is_cancer_gene=True,
            role=GeneRole.ONCOGENE,
            source="curated_oncogene_list",
            has_therapeutic_evidence=True,
            therapeutic_summary="Oncogene - activating mutations may be targetable",
        )

    # Check pathway-actionable TSGs BEFORE generic TSGs
    # These are TSGs where LOF activates a druggable downstream pathway
    pathway_info = get_pathway_actionable_info(gene_upper)
    if pathway_info:
        drugs_str = ", ".join(pathway_info["drugs"][:3])
        return GeneContext(
            gene=gene_upper,
            is_cancer_gene=True,
            role=GeneRole.TSG_PATHWAY_ACTIONABLE,
            source="pathway_actionable_tsg",
            has_therapeutic_evidence=True,
            therapeutic_summary=(
                f"Pathway-actionable TSG - LOF activates {pathway_info['pathway']} pathway. "
                f"May confer sensitivity to {drugs_str}. {pathway_info.get('fda_context', '')}"
            ),
        )

    # Check generic TSGs (not pathway-actionable)
    if gene_upper in TUMOR_SUPPRESSORS:
        return GeneContext(
            gene=gene_upper,
            is_cancer_gene=True,
            role=GeneRole.TSG,
            source="curated_tsg_list",
            has_therapeutic_evidence=False,  # TSGs usually not directly targetable
            therapeutic_summary="Tumor suppressor - LOF mutations generally not directly targetable",
        )

    # Unknown gene
    return GeneContext(
        gene=gene_upper,
        is_cancer_gene=False,
        role=GeneRole.UNKNOWN,
        source="not_in_curated_lists",
    )


def is_likely_lof(variant: str) -> tuple[bool, str]:
    """Predict if variant is loss-of-function based on notation.

    Args:
        variant: Variant string (e.g., "R248*", "W288fs", "splice")

    Returns:
        Tuple of (is_lof, reason)
    """
    v = variant.upper()

    # Truncating variants - high confidence LOF
    if '*' in v:
        return True, "nonsense (stop codon)"
    if 'FS' in v or 'FRAMESHIFT' in v:
        return True, "frameshift"
    if 'DEL' in v and not any(c.isdigit() for c in v.replace('DEL', '')):
        # Large deletion (not just single AA deletion like "K27del")
        return True, "deletion"

    # Splice site variants
    if 'SPLICE' in v:
        return True, "splice site"

    # Check for splice notation patterns
    if v.startswith('C.') or v.startswith('IVS'):
        if any(p in v for p in ['+1', '+2', '-1', '-2', 'SPLICE']):
            return True, "splice site"

    return False, ""


def get_therapeutic_implication(gene_context: GeneContext, is_lof: bool) -> str | None:
    """Get therapeutic implication based on gene role and variant effect.

    Args:
        gene_context: Gene context from get_gene_context()
        is_lof: Is variant predicted loss-of-function?

    Returns:
        Therapeutic implication string, or None if no clear implication
    """
    if gene_context.role == GeneRole.DDR:
        if is_lof:
            return (
                f"{gene_context.gene} is a DNA Damage Repair gene. "
                "Loss-of-function may confer sensitivity to platinum agents and PARP inhibitors. "
                "Clinical benefit varies by gene (BRCA1/2 > PALB2 > ATM/CHEK2)."
            )
        else:
            return (
                f"{gene_context.gene} is a DNA Damage Repair gene, but this variant "
                "is not clearly loss-of-function. Therapeutic implications uncertain without functional data."
            )

    elif gene_context.role == GeneRole.ONCOGENE:
        if not is_lof:  # Oncogenes need GOF
            return (
                f"{gene_context.gene} is an oncogene. "
                "Activating mutations may be targetable - check for specific variant evidence."
            )
        else:
            return (
                f"{gene_context.gene} is an oncogene, but this appears to be a "
                "loss-of-function variant. Oncogene LOF is typically not therapeutically relevant."
            )

    elif gene_context.role == GeneRole.TSG:
        if is_lof:
            return (
                f"{gene_context.gene} is a tumor suppressor. "
                "Loss-of-function confirms pathogenicity but is generally not directly targetable. "
                "May have prognostic implications."
            )
        else:
            return None  # TSG without LOF = likely benign or VUS, no therapeutic relevance

    return None


def get_lof_assessment(
    variant: str,
    snpeff_effect: str | None = None,
    polyphen2_prediction: str | None = None,
    cadd_score: float | None = None,
    alphamissense_prediction: str | None = None,
) -> tuple[bool, str, str]:
    """Comprehensive LOF assessment using variant notation and predictions.

    Args:
        variant: Variant string
        snpeff_effect: SnpEff functional effect annotation
        polyphen2_prediction: PolyPhen-2 prediction
        cadd_score: CADD phred score
        alphamissense_prediction: AlphaMissense prediction

    Returns:
        Tuple of (is_lof, confidence, rationale)
        confidence: "high", "moderate", or "low"
    """
    reasons = []

    # Check for truncating variants (high confidence LOF)
    if snpeff_effect:
        effect_lower = snpeff_effect.lower()
        truncating_effects = [
            "frameshift", "stop_gained", "splice_donor", "splice_acceptor",
            "start_lost", "stop_lost", "transcript_ablation"
        ]
        if any(t in effect_lower for t in truncating_effects):
            return True, "high", f"truncating variant ({snpeff_effect})"

    # Check variant notation for truncating patterns
    is_truncating, truncating_reason = is_likely_lof(variant)
    if is_truncating:
        return True, "high", truncating_reason

    # For missense: check computational predictions
    damaging_predictions = 0
    tolerated_predictions = 0
    total_predictions = 0
    tolerated_reasons = []

    if polyphen2_prediction:
        total_predictions += 1
        pred_lower = polyphen2_prediction.lower()
        if "damaging" in pred_lower or pred_lower in ["d", "p"]:
            damaging_predictions += 1
            reasons.append(f"PolyPhen2: {polyphen2_prediction}")
        elif "benign" in pred_lower or pred_lower == "b":
            tolerated_predictions += 1
            tolerated_reasons.append(f"PolyPhen2: {polyphen2_prediction}")

    if cadd_score is not None:
        total_predictions += 1
        if cadd_score >= 20:  # CADD >= 20 is common damaging threshold
            damaging_predictions += 1
            reasons.append(f"CADD: {cadd_score:.1f}")
        elif cadd_score < 15:  # CADD < 15 suggests tolerated
            tolerated_predictions += 1
            tolerated_reasons.append(f"CADD: {cadd_score:.1f}")

    if alphamissense_prediction:
        total_predictions += 1
        pred_lower = alphamissense_prediction.lower()
        if pred_lower in ["pathogenic", "p", "likely_pathogenic"]:
            damaging_predictions += 1
            reasons.append(f"AlphaMissense: {alphamissense_prediction}")
        elif pred_lower in ["benign", "b", "likely_benign"]:
            tolerated_predictions += 1
            tolerated_reasons.append(f"AlphaMissense: {alphamissense_prediction}")

    # Build rationale - include tolerated predictions if no damaging ones
    if reasons:
        rationale = "; ".join(reasons)
    elif tolerated_reasons:
        rationale = "predicted tolerated: " + "; ".join(tolerated_reasons)
    else:
        rationale = "no functional predictions available"

    # Determine confidence based on concordance
    if total_predictions >= 2 and damaging_predictions >= 2:
        return True, "moderate", rationale
    elif total_predictions >= 1 and damaging_predictions >= 1:
        return True, "low", rationale
    else:
        return False, "low", rationale