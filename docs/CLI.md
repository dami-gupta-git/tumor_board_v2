# TumorBoard CLI Reference

Complete command-line interface documentation for TumorBoard v2.

## Commands

### `assess` - Single Variant

Fetch variant evidence and assign an AMP/ASCO/CAP tier classification.

```bash
tumorboard assess <GENE> <VARIANT> [OPTIONS]

Options:
  -t, --tumor TEXT         Tumor type (optional, e.g., "Melanoma")
  -m, --model TEXT         LLM model [default: gpt-4o-mini]
  --temperature FLOAT      LLM temperature (0.0-1.0) [default: 0.1]
  -o, --output PATH        Save to JSON file
```

Example output:
```
Assessing BRAF V600E in Melanoma...

Variant: BRAF V600E | Tumor: Melanoma
Tier: Tier I | Confidence: 95.0%
Identifiers: COSMIC: COSM476 | NCBI Gene: 673 | dbSNP: rs113488022 | ClinVar: 13961
HGVS: Genomic: chr7:g.140453136A>T
ClinVar: Significance: Pathogenic | Accession: RCV000013961
Annotations: Effect: missense_variant | PolyPhen2: D | CADD: 32.00 | gnomAD AF: 0.000004
Transcript: ID: NM_004333.4 | Consequence: missense_variant

BRAF V600E is a well-established actionable mutation in melanoma...

Therapies: Vemurafenib, Dabrafenib
```

**Note**: Database identifiers, functional annotations, and transcript information are automatically extracted from MyVariant.info when available and displayed in both console output and JSON files.

### `batch` - Multiple Variants

Process multiple variants concurrently from a JSON file.

```bash
tumorboard batch <INPUT_FILE> [OPTIONS]

Options:
  -o, --output PATH        Output file [default: results.json]
  -m, --model TEXT         LLM model [default: gpt-4o-mini]
  --temperature FLOAT      LLM temperature (0.0-1.0) [default: 0.1]
```

Input format: `[{"gene": "BRAF", "variant": "V600E", "tumor_type": "Melanoma"}, ...]`

### `validate` - Test Accuracy

Benchmark LLM performance against gold standard datasets.

```bash
tumorboard validate <GOLD_STANDARD_FILE> [OPTIONS]

Options:
  -m, --model TEXT         LLM model [default: gpt-4o-mini]
  --temperature FLOAT      LLM temperature (0.0-1.0) [default: 0.1]
  -o, --output PATH        Save detailed results
  -c, --max-concurrent N   Concurrent validations [default: 3]
  --no-log                 Switch off logging 
```

Provides:
- Overall accuracy and per-tier precision/recall/F1
- Failure analysis showing where and why mistakes occur
- Tier distance metrics

Gold standard format: `{"entries": [{"gene": "BRAF", "variant": "V600E", "tumor_type": "Melanoma", "expected_tier": "Tier I", ...}]}`
