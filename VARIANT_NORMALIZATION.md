# Variant Normalization

TumorBoard automatically normalizes variant notations to improve evidence matching across databases. This preprocessing step happens before fetching evidence from MyVariant.info.

## Supported Formats

The system handles multiple variant notation formats for **SNPs and small indels only**:

**Supported - Protein Changes (Missense/Nonsense):**
- One-letter amino acid codes: `V600E`, `L858R`, `G12C`
- Three-letter amino acid codes: `Val600Glu`, `Leu858Arg`, `Gly12Cys`
- HGVS protein notation: `p.V600E`, `p.Val600Glu`
- Case-insensitive: `v600e`, `V600E`, `val600glu` all normalize to `V600E`

**Supported - Small Indels:**
- Small deletions: `185delAG`, `6174delT`, `del19`
- Small insertions: variants containing `ins`
- Frameshift: `L747fs`, `Q61fs*5`
- Nonsense: `R248*`, `Q61*`

**Not Supported - Structural Variants:**
- Fusions: `fusion`, `ALK fusion`, `EML4-ALK rearrangement` (will be rejected)
- Amplifications: `amplification`, `amp`, `overexpression` (will be rejected)
- Large deletions: `exon 19 deletion` (will be rejected)
- Splice variants: `exon 14 skipping`, `splice site` (will be rejected)
- Truncations: `truncating mutation`, `truncation` (will be rejected)

## How It Works

```python
# Example: Different formats normalize to the same canonical form
BRAF Val600Glu  → V600E (normalized, type: missense) ✅
BRAF p.V600E    → V600E (normalized, type: missense) ✅
EGFR Leu858Arg  → L858R (normalized, type: missense) ✅
BRCA1 185delAG  → 185delAG (type: deletion) ✅

# Unsupported variants are rejected
ALK fusion      → ❌ ValidationError: Variant type 'fusion' is not supported
ERBB2 amp       → ❌ ValidationError: Variant type 'amplification' is not supported
```

The normalization logs appear during assessment:

```bash
$ tumorboard assess BRAF Val600Glu --tumor Melanoma

Assessing BRAF Val600Glu in Melanoma...
  Normalized Val600Glu → V600E (type: missense)

# Unsupported variants show clear error messages
$ tumorboard assess ALK fusion
ValidationError: Variant type 'fusion' is not supported.
Only SNPs and small indels are allowed (missense, nonsense, insertion, deletion, frameshift).
```

## Benefits

- **Better Evidence Matching**: MyVariant.info and CIViC searches work better with canonical forms
- **Flexible Input**: Accept variants from reports in any notation format
- **Type Classification**: Automatically detects missense, fusion, amplification, etc.
- **Position Extraction**: Extracts protein positions for coordinate-based lookups
- **HGVS Conversion**: Converts to standard HGVS protein notation when possible

## Programmatic Usage

```python
from tumorboard.utils import normalize_variant, is_missense_variant, is_snp_or_small_indel, get_protein_position

# Full normalization
result = normalize_variant("BRAF", "Val600Glu")
# {'gene': 'BRAF', 'variant_normalized': 'V600E', 'variant_type': 'missense', ...}

# Check if supported variant type
is_supported = is_snp_or_small_indel("BRAF", "V600E")  # True
is_supported = is_snp_or_small_indel("ALK", "fusion")  # False
is_supported = is_snp_or_small_indel("BRCA1", "185delAG")  # True

# Check if missense
is_missense = is_missense_variant("BRAF", "V600E")  # True
is_missense = is_missense_variant("ALK", "fusion")  # False

# Extract position
position = get_protein_position("Val600Glu")  # 600
position = get_protein_position("p.L858R")    # 858
```
