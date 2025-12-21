# Batch Processing & Validation

TumorBoard supports batch assessment of multiple variants and validation against gold standard datasets.

## Batch Assessment

Process multiple variants in a single run with concurrent execution.

### CLI Batch (JSON Input)

```bash
tumorboard batch <INPUT_FILE> [OPTIONS]

Options:
  -o, --output PATH        Output file [default: results.json]
  -m, --model TEXT         LLM model [default: gpt-4o-mini]
  --temperature FLOAT      LLM temperature (0.0-1.0) [default: 0.1]
  --no-log                 Disable LLM decision logging
```

**Input format** (`variants.json`):
```json
[
  {"gene": "BRAF", "variant": "V600E", "tumor_type": "Melanoma"},
  {"gene": "EGFR", "variant": "L858R", "tumor_type": "NSCLC"},
  {"gene": "KRAS", "variant": "G12C", "tumor_type": "Lung Adenocarcinoma"}
]
```

**Example:**
```bash
tumorboard batch variants.json -o results.json --no-log
```

### Streamlit Batch (CSV Upload)

Upload a CSV file through the web interface's "Batch Upload" tab.

**Input format** (`variants.csv`):
```csv
gene,variant,tumor_type
BRAF,V600E,Melanoma
EGFR,L858R,NSCLC
KRAS,G12C,Lung Adenocarcinoma
TP53,R248W,Breast Cancer
```

- **Required columns**: `gene`, `variant`
- **Optional column**: `tumor_type`

The web interface provides:
- Real-time progress tracking
- Download results as CSV or JSON
- Visual tier distribution summary

### Output Format

Both CLI and Streamlit produce results with the same structure:

```json
{
  "gene": "BRAF",
  "variant": "V600E",
  "tumor_type": "Melanoma",
  "assessment": {
    "tier": "Tier I",
    "confidence": 0.95,
    "rationale": "BRAF V600E is FDA-approved...",
    "therapies": ["Vemurafenib", "Dabrafenib"],
    "evidence_strength": "Strong"
  },
  "annotations": {
    "cosmic_id": "COSM476",
    "clinvar_significance": "Pathogenic",
    "hgvs_genomic": "chr7:g.140453136A>T"
  }
}
```

## Validation Framework

Benchmark TumorBoard's accuracy against expert-labeled gold standard datasets.

### CLI Validation

```bash
tumorboard validate <GOLD_STANDARD_FILE> [OPTIONS]

Options:
  -m, --model TEXT         LLM model [default: gpt-4o-mini]
  --temperature FLOAT      LLM temperature (0.0-1.0) [default: 0.1]
  -o, --output PATH        Save detailed results to JSON
  -c, --max-concurrent N   Concurrent validations [default: 3]
  --no-log                 Disable LLM decision logging
```

**Example:**
```bash
tumorboard validate benchmarks/gold_standard.json -o validation_results.json --no-log
```

### Streamlit Validation

Use the "Validation" tab in the web interface to:
1. Select a gold standard file from the `benchmarks/` directory
2. Choose LLM model and settings
3. Run validation with progress tracking
4. View detailed metrics and failure analysis

### Gold Standard Format

```json
{
  "entries": [
    {
      "gene": "BRAF",
      "variant": "V600E",
      "tumor_type": "Melanoma",
      "expected_tier": "Tier I",
      "notes": "FDA-approved: vemurafenib, dabrafenib"
    },
    {
      "gene": "TP53",
      "variant": "R248W",
      "tumor_type": "Breast Cancer",
      "expected_tier": "Tier III",
      "notes": "Prognostic only, no approved therapies"
    }
  ]
}
```

**Required fields:**
- `gene`: Gene symbol
- `variant`: Variant notation
- `expected_tier`: One of `Tier I`, `Tier II`, `Tier III`, `Tier IV`

**Optional fields:**
- `tumor_type`: Cancer type context
- `notes`: Explanation for expected tier (useful for debugging)

### Validation Metrics

The validation framework reports:

| Metric | Description |
|--------|-------------|
| **Overall Accuracy** | Percentage of correct tier predictions |
| **Per-Tier Precision** | Correct predictions / Total predictions for each tier |
| **Per-Tier Recall** | Correct predictions / Total expected for each tier |
| **Per-Tier F1 Score** | Harmonic mean of precision and recall |
| **Confusion Matrix** | Predicted vs. expected tier breakdown |
| **Tier Distance** | Average distance between predicted and expected tiers |

**Example output:**
```
Validation Results (n=50)
─────────────────────────
Overall Accuracy: 91.0%

Per-Tier Metrics:
  Tier I:   Precision=0.94  Recall=0.95  F1=0.94
  Tier II:  Precision=0.88  Recall=0.85  F1=0.86
  Tier III: Precision=0.89  Recall=0.92  F1=0.90
  Tier IV:  Precision=1.00  Recall=0.80  F1=0.89

Failures (5):
  EGFR T790M in NSCLC: Expected Tier II, Got Tier I
  ...
```

### Creating Gold Standard Datasets

1. **Expert curation**: Have domain experts classify variants using AMP/ASCO/CAP guidelines
2. **Source from literature**: Use published variant classifications from peer-reviewed studies
3. **Cross-reference databases**: Validate against CIViC, OncoKB, or institutional classifications

**Tips:**
- Include a mix of all four tiers
- Cover common and rare variants
- Include edge cases (resistance mutations, tumor-type-specific actionability)
- Document rationale in `notes` field for debugging

## Performance Considerations

### Rate Limits

External APIs have rate limits that may affect batch processing:
- **MyVariant.info**: Generally permissive, but large batches may need throttling
- **FDA openFDA**: 40 requests/minute without API key, 240/minute with key
- **Semantic Scholar**: 100 requests/5 minutes
- **ClinicalTrials.gov**: No published limits, but be respectful

### Concurrency Settings

- **CLI batch**: Processes variants concurrently (default behavior)
- **CLI validate**: Use `-c/--max-concurrent` to control parallelism (default: 3)
- **Streamlit**: Uses async processing with reasonable defaults

For large batches (100+ variants), consider:
- Running during off-peak hours
- Breaking into smaller batches
- Using `--max-concurrent 2` for validation to avoid rate limits

### Caching

Evidence fetching results are cached during a session to avoid redundant API calls. The same variant queried multiple times will reuse cached evidence.

## Sample Files

Sample batch and gold standard files are available in the repository:

- `benchmarks/sample_batch.json` - Example batch input
- `benchmarks/gold_standard.json` - Validation dataset
- `sample_batch.csv` - Example CSV for Streamlit upload
