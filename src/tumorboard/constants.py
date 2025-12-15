"""Centralized constants and mappings for TumorBoard.

This module consolidates all hardcoded mappings used across the codebase:
- Gene aliases (different nomenclatures for the same gene)
- Tumor type mappings (abbreviations to full names)
- Amino acid codes
- Variant type classifications

Centralizing these makes maintenance easier and ensures consistency.
"""

# =============================================================================
# GENE ALIASES
# =============================================================================
# Maps gene symbols to their alternative names used in different databases
# FDA labels, CIViC, CGI, etc. may use different nomenclature

GENE_ALIASES: dict[str, list[str]] = {
    "ERBB2": ["HER2", "NEU"],
    "HER2": ["ERBB2", "NEU"],
    "EGFR": ["HER1", "ERBB1"],
    "ERBB1": ["EGFR", "HER1"],
    "HER1": ["EGFR", "ERBB1"],
    "MET": ["HGFR"],
    "KIT": ["CD117", "C-KIT"],
    "PDGFRA": ["CD140A"],
    "PDGFRB": ["CD140B"],
}


# =============================================================================
# TUMOR TYPE MAPPINGS
# =============================================================================
# Maps tumor type abbreviations to their full names and synonyms
# Used for matching user input to database entries (CGI, FDA, CIViC)

TUMOR_TYPE_MAPPINGS: dict[str, list[str]] = {
    # Lung
    "nsclc": ["non-small cell lung", "nsclc", "lung non-small cell", "lung adenocarcinoma", "lung squamous", "lung non-small cell carcinoma"],
    "l": ["lung", "non-small cell lung", "nsclc", "small cell lung", "lung carcinoma"],
    "sclc": ["small cell lung", "sclc"],
    "luad": ["lung adenocarcinoma", "luad"],
    "lusc": ["lung squamous", "lusc", "squamous cell lung"],

    # Colorectal
    "crc": ["colorectal", "colon", "crc", "rectal", "rectum"],
    "coad": ["colon adenocarcinoma", "coad"],
    "read": ["rectal adenocarcinoma", "read", "rectum"],
    "coread": ["colorectal", "colon", "rectal", "colorectal adenocarcinoma", "crc"],  # CGI uses COREAD

    # Melanoma
    "mel": ["melanoma", "mel", "cutaneous melanoma", "skin melanoma"],
    "skcm": ["skin cutaneous melanoma", "skcm", "melanoma"],

    # Breast
    "bc": ["breast", "bc", "breast cancer", "breast carcinoma"],
    "brca": ["breast carcinoma", "brca", "breast cancer"],
    "idc": ["invasive ductal carcinoma", "idc", "breast ductal"],
    "ilc": ["invasive lobular carcinoma", "ilc", "breast lobular"],

    # Thyroid
    "atc": ["anaplastic thyroid", "atc", "thyroid anaplastic"],
    "thca": ["thyroid carcinoma", "thca", "thyroid cancer"],
    "ptc": ["papillary thyroid", "ptc"],

    # Gastrointestinal
    "gist": ["gastrointestinal stromal", "gist"],
    "stad": ["stomach adenocarcinoma", "stad", "gastric"],
    "esca": ["esophageal carcinoma", "esca", "esophageal"],
    "paad": ["pancreatic adenocarcinoma", "paad", "pancreatic", "pancreas"],
    "lihc": ["liver hepatocellular", "lihc", "hepatocellular", "hcc"],
    "chol": ["cholangiocarcinoma", "chol", "bile duct"],

    # Genitourinary
    "prad": ["prostate adenocarcinoma", "prad", "prostate"],
    "blca": ["bladder carcinoma", "blca", "bladder", "urothelial"],
    "rcc": ["renal cell carcinoma", "rcc", "kidney"],
    "ccrcc": ["clear cell renal", "ccrcc", "kidney clear cell"],

    # Gynecologic
    "ov": ["ovarian", "ov", "ovary"],
    "ucec": ["uterine corpus endometrial", "ucec", "endometrial", "uterine"],
    "cesc": ["cervical squamous", "cesc", "cervical"],

    # Head and Neck
    "hnsc": ["head and neck squamous", "hnsc", "head neck"],

    # Brain
    "gbm": ["glioblastoma", "gbm", "glioblastoma multiforme"],
    "lgg": ["low grade glioma", "lgg", "glioma"],

    # Hematologic
    "aml": ["acute myeloid leukemia", "aml"],
    "cml": ["chronic myeloid leukemia", "cml"],
    "all": ["acute lymphoblastic leukemia", "all"],
    "cll": ["chronic lymphocytic leukemia", "cll"],
    "dlbcl": ["diffuse large b-cell lymphoma", "dlbcl"],
    "mm": ["multiple myeloma", "mm", "myeloma"],
}


# =============================================================================
# PRIORITY TUMOR TYPES FOR UI
# =============================================================================
# OncoTree codes for commonly assessed tumor types
# These appear first in UI dropdowns/autocomplete

PRIORITY_TUMOR_CODES: list[str] = [
    # Lung
    "NSCLC", "LUAD", "LUSC", "SCLC",
    # Breast
    "BRCA", "IDC", "ILC",
    # Colorectal
    "CRC", "COAD", "READ",
    # Melanoma
    "MEL", "SKCM",
    # Pancreatic
    "PAAD",
    # Prostate
    "PRAD",
    # Ovarian
    "OV",
    # Glioblastoma
    "GBM",
    # Bladder
    "BLCA",
    # Kidney
    "RCC", "CCRCC",
    # Head and Neck
    "HNSC",
    # Gastric
    "STAD",
    # Liver
    "LIHC",
    # Thyroid
    "THCA",
    # Endometrial
    "UCEC",
    # Hematologic
    "AML", "CML",
]


# =============================================================================
# AMINO ACID CODES
# =============================================================================
# Standard amino acid code conversions (3-letter to 1-letter and vice versa)

AMINO_ACID_3TO1: dict[str, str] = {
    'ALA': 'A', 'CYS': 'C', 'ASP': 'D', 'GLU': 'E', 'PHE': 'F',
    'GLY': 'G', 'HIS': 'H', 'ILE': 'I', 'LYS': 'K', 'LEU': 'L',
    'MET': 'M', 'ASN': 'N', 'PRO': 'P', 'GLN': 'Q', 'ARG': 'R',
    'SER': 'S', 'THR': 'T', 'VAL': 'V', 'TRP': 'W', 'TYR': 'Y',
    'TER': '*', 'STP': '*', 'STOP': '*',  # Stop codons
    'SEC': 'U',  # Selenocysteine (rare)
    'PYL': 'O',  # Pyrrolysine (rare)
}

AMINO_ACID_1TO3: dict[str, str] = {v: k for k, v in AMINO_ACID_3TO1.items() if v not in ('*',)}
AMINO_ACID_1TO3['*'] = 'TER'  # Prefer TER for stop codon


# =============================================================================
# VARIANT TYPE CLASSIFICATIONS
# =============================================================================
# Variant types allowed for SNP/small indel analysis

ALLOWED_VARIANT_TYPES: set[str] = {
    'missense',
    'nonsense',
    'insertion',
    'deletion',
    'frameshift',
}

# Variant types that are structural (not supported in current system)
STRUCTURAL_VARIANT_TYPES: set[str] = {
    'fusion',
    'amplification',
    'deletion_large',
    'rearrangement',
    'copy_number',
    'truncating',
    'splice',
}