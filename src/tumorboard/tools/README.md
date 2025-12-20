# TumorBoard Command-Line Tools

This directory contains command-line utilities for TumorBoard.

## Variant Normalization Tool

Normalizes variant notations across different formats to standard representations.

### Supported Input Formats

- **One-letter amino acid codes**: `V600E`
- **Three-letter amino acid codes**: `Val600Glu`
- **HGVS protein notation**: `p.V600E`, `p.Val600Glu`
- **Structural variants**: `fusion`, `amplification`
- **Indels**: `del`, `ins`, `dup`, `fs`

### Usage

```bash
# Single variant normalization
python -m tumorboard.tools.normalize_variant BRAF V600E
python -m tumorboard.tools.normalize_variant BRAF Val600Glu
python -m tumorboard.tools.normalize_variant BRAF p.V600E
python -m tumorboard.tools.normalize_variant ALK fusion

# Different output formats
python -m tumorboard.tools.normalize_variant BRAF V600E --format json   # Default
python -m tumorboard.tools.normalize_variant BRAF V600E --format table  # Human-readable
python -m tumorboard.tools.normalize_variant BRAF V600E --format tsv    # Tab-separated

# Batch processing
python -m tumorboard.tools.normalize_variant --batch variants.txt
echo "BRAF,V600E" | python -m tumorboard.tools.normalize_variant --stdin

# Quiet mode (just normalized output)
python -m tumorboard.tools.normalize_variant EGFR L858R --quiet
```

### Output Fields

| Field | Description |
|-------|-------------|
| `gene` | Normalized gene symbol (uppercase) |
| `variant_original` | Original input |
| `variant_normalized` | Normalized form (e.g., Val600Glu → V600E) |
| `variant_type` | Classification (missense, nonsense, frameshift, deletion, insertion, fusion, amplification, etc.) |
| `hgvs_protein` | HGVS protein notation (p.V600E) |
| `position` | Amino acid position |
| `is_allowed_type` | Whether it's a SNP/small indel (supported by the system) |
| `protein_change` | Detailed breakdown (ref_aa, alt_aa, long_form) |
| `query_formats` | Pre-formatted queries for MyVariant, VICC, CIViC APIs |

### Examples

**JSON output (default):**
```bash
$ python -m tumorboard.tools.normalize_variant BRAF Val600Glu
{
  "gene": "BRAF",
  "variant_original": "Val600Glu",
  "variant_normalized": "V600E",
  "variant_type": "missense",
  "protein_change": {
    "short_form": "V600E",
    "hgvs_protein": "p.V600E",
    "long_form": "VAL600GLU",
    "position": 600,
    "ref_aa": "V",
    "alt_aa": "E",
    "is_missense": true
  },
  "hgvs_protein": "p.V600E",
  "position": 600,
  "is_allowed_type": true,
  "query_formats": {
    "myvariant": "BRAF p.V600E",
    "vicc": "BRAF V600E",
    "civic": "BRAF V600E"
  }
}
```

**Table output:**
```bash
$ python -m tumorboard.tools.normalize_variant BRAF p.V600E --format table
============================================================
Gene:             BRAF
Original:         p.V600E
Normalized:       V600E
Type:             missense
HGVS Protein:     p.V600E
Position:         600
Allowed Type:     True
Ref AA:           V
Alt AA:           E
Long Form:        VAL600GLU
----------------------------------------
Query Formats:
  MyVariant:      BRAF p.V600E
  VICC:           BRAF V600E
  CIViC:          BRAF V600E
============================================================
```

**Batch processing with TSV output:**
```bash
$ echo -e "BRAF,V600E\nEGFR,L858R\nKRAS,G12C\nALK,fusion" | python -m tumorboard.tools.normalize_variant --stdin --format tsv
gene    variant_original    variant_normalized    variant_type    hgvs_protein    position    is_allowed_type    ref_aa    alt_aa
BRAF    V600E               V600E                 missense        p.V600E         600         True               V         E
EGFR    L858R               L858R                 missense        p.L858R         858         True               L         R
KRAS    G12C                G12C                  missense        p.G12C          12          True               G         C
ALK     fusion              fusion                fusion                                      False
```

### Batch File Format

Create a file with one variant per line (comma, tab, or space-separated):

```
# variants.txt
BRAF,V600E
EGFR,L858R
KRAS,G12C
ALK,fusion
# Comments start with #
```

Then run:
```bash
python -m tumorboard.tools.normalize_variant --batch variants.txt
```
