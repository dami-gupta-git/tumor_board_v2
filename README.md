# TumorBoard v2
An LLM-powered cancer variant actionability assessment tool with a built-in validation framework.

**⚠️ Important: This tool currently only supports SNPs and small indels (missense, nonsense, insertions, deletions, frameshifts). Fusions, amplifications, and other structural variants are not supported.**

**Current Validation Performance: 70% accuracy | 87% Tier I F1 score** *(on SNP/indel variants only)*

**TL;DR**:
Molecular tumor boards manually review cancer variants to assign clinical actionability—a time-consuming process
requiring expert panels. This research tool automates that workflow by fetching variant evidence from genomic databases
(CIViC, ClinVar, COSMIC) and using LLMs to assign AMP/ASCO/CAP tier classifications, mimicking expert judgment.
Includes a validation framework to benchmark LLM accuracy against gold-standard classifications.
This is a research prototype exploring whether LLMs can approximate clinical decision-making; not for actual clinical use.

**Note**: This tool is specifically designed for SNPs and small indels. Other variant types (fusions, amplifications, splice variants, etc.) are intentionally excluded to maintain focus and accuracy on point mutations.

TumorBoard includes a clean, modern Streamlit web interface:

- **Single Container**: No separate frontend/backend - one Docker command starts everything
- **Interactive UI**: Three-tab interface for single variants, batch processing, and validation
- **Multiple LLM Providers**: OpenAI, Anthropic (Claude), Google (Gemini), Groq via LiteLLM
- **Real-time Results**: See comprehensive annotations and LLM analysis with confidence scores
- **Batch Processing**: Upload CSV files for concurrent variant assessment
- **Validation Framework**: Built-in gold standard validation with per-tier metrics
- **🐳 Docker Ready**: One-command deployment with Docker Compose

### Quick Start with Streamlit

```bash
# 1. Set your API keys
cd streamlit
cp .env.example .env
# Edit .env with your API keys

# 2. Start the app
docker compose up --build

# 3. Open in browser
open http://localhost:8501
```

**Features:**
- **Single Variant Tab**: Assess individual variants with full evidence and therapy recommendations
- **Batch Upload Tab**: Process CSV files with multiple variants
- **Validation Tab**: Run gold standard benchmarking

👉 **[Streamlit App Guide](streamlit/README.md)**

## Overview

TumorBoard combines clinical evidence from multiple genomic databases (CIViC, ClinVar, COSMIC) and FDA drug approval data. It then uses large language models to approximate expert application of the **AMP/ASCO/CAP 4-tier classification system**.

Available in two interfaces:
- **Streamlit Web App**: Modern single-container web interface (recommended)
- **Command-Line Interface**: Python CLI tool for batch processing and automation

### Key Features

- **SNP/Small Indel Focus**: Specialized support for point mutations, small insertions, deletions, and frameshifts
- **Variant Type Validation**: Automatically validates and rejects unsupported variant types (fusions, amplifications, etc.)
- **Variant Normalization**: Automatically standardizes variant notations (Val600Glu → V600E, p.V600E → V600E) for better API matching
- **Evidence Aggregation**: Automatically fetches variant evidence from MyVariant.info API and FDA drug approval data
- **FDA Drug Approvals**: Fetches FDA-approved oncology drugs with companion diagnostics and biomarker-based indications
- **Database Identifiers**: Extracts COSMIC, dbSNP, ClinVar, NCBI Gene IDs, and HGVS notations
- **Functional Annotations**: SnpEff effects, PolyPhen2 predictions, CADD scores, gnomAD frequencies
- **LLM Assessment**: Uses LLMs to interpret evidence and assign actionability tiers
- **Evidence Prioritization**: Intelligent ranking of PREDICTIVE evidence with tumor-type-specific filtering
- **Validated Performance**: 73.33% overall accuracy on SNP/indel gold standard dataset
- **Validation Framework**: Built-in benchmarking against gold standard datasets with per-tier metrics
- **Multiple LLM Support**: Works with OpenAI, Anthropic, Google, Groq via litellm
- **Async Throughout**: Fast, concurrent processing for batch assessments
- **Rich CLI**: Command-line interface with progress indicators
- **Streamlit Interface**: Modern single-container web app with three-tab interface

## Why This Tool Exists

Molecular tumor boards face significant challenges:

1. **Resource Intensive**: Expert panels must manually review variants and apply
   classification frameworks - a time-consuming process requiring coordinated expertise.
2. **Coverage Gaps**: Curated databases like CIViC don't cover every variant-tumor
   combination, especially rare or novel variants.
3. **Evidence Fragmentation**: Relevant evidence is scattered across multiple
   databases (CIViC, ClinVar, COSMIC), requiring manual synthesis.
4. **Rapid Evolution**: New trials and approvals constantly change variant
   actionability.



3. **Prompt Engineering (50%)**: Embedded explicit FDA-approved variant rules directly in the LLM
   system prompt. This was the most impactful change—the LLM had the evidence but needed explicit
   domain knowledge to interpret it correctly.


## Disclaimer

**Limitations:**
- LLMs may hallucinate or misinterpret evidence 
- Pattern matching ≠ expert clinical judgment  
- Requires validation against gold standards (hence the built-in framework)
- Evidence quality: Depends on database coverage
- Novel variants: Limited data for rare variants
- Context windows: Very long evidence may be truncated

**This tool is for research purposes only.** Clinical decisions should always
be made by qualified healthcare professionals.

## Coming Soon

We're actively working on enhancing TumorBoard with additional features:

### 📊 Enhanced Evidence Sources

- **AlphaMissense Integration**: Pathogenicity predictions for missense variants using Google DeepMind's AlphaMissense scores
- **SpliceAI Annotations**: Splice variant impact predictions to better assess variants affecting RNA splicing
- **LLM-Powered Literature Search**: Automated PubMed searches with LLM-based evidence synthesis for real-time literature review
- **ESMFold Integration**: Protein Structure predictions and visualization
- **Clinical Trials Matching**: Integration with ClinicalTrials.gov API to identify relevant ongoing trials for specific variant-tumor combinations
- **gnomAD Integration**: Filter out population noise
- **TCGA Data**: Real somatic mutation frequency and cancer-type prevalence across 11,000+ tumors to confirm driver status


### 🤖 Agentic AI Architecture

Moving beyond single-LLM assessments to a **collaborative multi-agent system**:

- **Systematic Review Agent**: Automated literature review following PRISMA guidelines with citation network analysis
- **Mechanistic Reasoning Agent**: Deep analysis of biological mechanisms, pathway interactions, and molecular consequences
- **Citation Graph Agent**: Network analysis of scientific evidence, identifying consensus patterns and research frontiers
- **Consensus Orchestrator**: Synthesizes insights from specialized agents, resolving conflicts and producing unified assessments
- **Ensemble LLM**: Multi-model consensus approach using different LLMs (GPT-4, Claude, Gemini) to cross-validate findings and reduce hallucination

This agentic approach mimics real tumor board dynamics where multiple specialists contribute domain expertise.

### 🧬 Patient-Level Genomic Analysis

- **VCF File Upload & Processing**: Direct import of patient VCF (Variant Call Format) files for comprehensive multi-variant analysis
- **Whole-Exome/Genome Support**: Process entire patient genomic profiles, not just individual variants
- **Variant Prioritization Engine**: Automatic ranking of variants by clinical actionability, filtering germline/somatic, and pathogenicity scores
- **Patient Report Generation**: Comprehensive clinical reports summarizing all actionable findings, therapy recommendations, and clinical trial eligibility
- **Cohort Analysis**: Compare variant profiles across multiple patients to identify patterns and treatment response correlations

Transform from single-variant lookups to full patient-level precision oncology workflows.

## Getting Started

### Pick Your Interface

**Option 1: Web Application (Docker - Recommended)**

Use the Streamlit web interface with zero local setup:

```bash
# 1. Set API keys
cd streamlit
cp .env.example .env
# Edit .env with your API keys

# 2. Start the app
docker compose up --build

# 3. Open http://localhost:8501
```

**That's it!** No pip install, no dependencies. Docker handles everything.

---

**Option 2: CLI Tool (Requires pip install)**

Use the command-line interface for batch processing and validation:

```bash
# 1. Clone and install
git clone <repository-url>
cd tumor_board_v2
pip install -e .

# 2. Set API key
export OPENAI_API_KEY="your-key-here"

# 3. Use CLI commands
tumorboard assess BRAF V600E --tumor "Melanoma"
tumorboard batch benchmarks/sample_batch.json
tumorboard validate benchmarks/gold_standard.json
```

**Alternative Models:**
```bash
# Use Anthropic Claude 3 Haiku
export ANTHROPIC_API_KEY="your-key-here"
tumorboard assess BRAF V600E --model claude-3-haiku-20240307

# Use Google Gemini
export GOOGLE_API_KEY="your-key-here"
tumorboard assess BRAF V600E --model gemini/gemini-1.5-pro

# Use Groq Llama
export GROQ_API_KEY="your-key-here"
tumorboard assess BRAF V600E --model groq/llama-3.1-70b-versatile
```

**Note:** Claude 3 Opus and Sonnet models require higher-tier Anthropic API access. Claude 3 Haiku is available on all API tiers.

## LLM Decision Logging

TumorBoard includes comprehensive logging of all LLM decisions to help you track, audit, and analyze variant assessments. Logging is **enabled by default** and captures structured data about every assessment.

### Quick Start

```bash
# Logging is enabled by default
tumorboard assess BRAF V600E --tumor melanoma

# Disable logging if needed
tumorboard assess BRAF V600E --tumor melanoma --no-log

# View logs (JSON Lines format)
cat logs/llm_decisions_20251203.jsonl
head -1 logs/llm_decisions_20251203.jsonl | python3 -m json.tool
```

### What Gets Logged

- **Request details**: Gene, variant, tumor type, model, temperature, evidence summary length
- **Response details**: Tier decision, confidence score, summary, rationale, recommended therapies, references
- **Error tracking**: Full context for any failures with error type and message

### Log File Location

Logs are saved to: `./logs/llm_decisions_YYYYMMDD.jsonl`

Each line is a complete JSON object capturing either:
- `llm_request`: Input parameters before LLM call
- `llm_response`: LLM decision with full assessment details
- `llm_error`: Any failures with error context

**Example log entry:**
```json
{
  "timestamp": "2025-12-03T01:15:41.616794",
  "event_type": "llm_response",
  "request_id": "EGFR_L858R_20251203_011531_329465",
  "output": {
    "gene": "EGFR",
    "variant": "L858R",
    "tier": "Tier I",
    "confidence_score": 0.95,
    "summary": "The EGFR L858R mutation is a well-established actionable variant...",
    "recommended_therapies": [...],
    "references": ["OncoKB Level A", "CIViC EID:1", "FDA approval 2023"]
  }
}
```

### Use Cases

- **Auditing**: Track all assessments for regulatory compliance
- **Quality Assurance**: Monitor confidence scores and identify low-confidence decisions
- **Research**: Analyze LLM performance patterns and accuracy trends over time
- **Validation**: Compare decisions against gold standards for benchmarking

**📖 Full Documentation:** See [logging.md](logging.md) for complete details on log format, analysis examples with Python/jq, and best practices.

## CLI Reference

### `assess` - Single Variant
Specify a single variant, then run this command to fetch variant evidence and use the LLM to assign an AMP/ASCO/CAP tier classification.

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
Specify a JSON file with variant details (gene, variant, tumor type), then run this command to process them concurrently and generate batch results.

```bash
tumorboard batch <INPUT_FILE> [OPTIONS]

Options:
  -o, --output PATH        Output file [default: results.json]
  -m, --model TEXT         LLM model [default: gpt-4o-mini]
  --temperature FLOAT      LLM temperature (0.0-1.0) [default: 0.1]
```

Input format: `[{"gene": "BRAF", "variant": "V600E", "tumor_type": "Melanoma"}, ...]`

### `validate` - Test Accuracy
Specify a gold standard dataset with known correct tier classifications, then run this command to benchmark the LLM's performance and identify where it agrees or disagrees with expert consensus—this is critical for evaluating reliability before using the tool for research.

Provides:
- Overall accuracy and per-tier precision/recall/F1
- Failure analysis showing where and why mistakes occur
- Tier distance metrics

```bash
tumorboard validate <GOLD_STANDARD_FILE> [OPTIONS]

Options:
  -m, --model TEXT         LLM model [default: gpt-4o-mini]
  --temperature FLOAT      LLM temperature (0.0-1.0) [default: 0.1]
  -o, --output PATH        Save detailed results
  -c, --max-concurrent N   Concurrent validations [default: 3]
```

Gold standard format: `{"entries": [{"gene": "BRAF", "variant": "V600E", "tumor_type": "Melanoma", "expected_tier": "Tier I", ...}]}`

## AMP/ASCO/CAP Tier System

- **Tier I**: Variants with strong clinical significance
  - FDA-approved therapies for specific variant + tumor type
  - Professional guideline recommendations
  - Strong evidence from clinical trials

- **Tier II**: Variants with potential clinical significance
  - FDA-approved therapies for different tumor types
  - Clinical trial evidence
  - Case reports or smaller studies

- **Tier III**: Variants of unknown clinical significance
  - Preclinical evidence only
  - Uncertain biological significance
  - Conflicting evidence

- **Tier IV**: Benign or likely benign variants
  - Known benign polymorphisms
  - No oncogenic evidence


## Variant Normalization

TumorBoard automatically normalizes variant notations to improve evidence matching across databases. This preprocessing step happens before fetching evidence from MyVariant.info.

### Supported Formats

The system handles multiple variant notation formats for **SNPs and small indels only**:

**✅ Supported - Protein Changes (Missense/Nonsense):**
- One-letter amino acid codes: `V600E`, `L858R`, `G12C`
- Three-letter amino acid codes: `Val600Glu`, `Leu858Arg`, `Gly12Cys`
- HGVS protein notation: `p.V600E`, `p.Val600Glu`
- Case-insensitive: `v600e`, `V600E`, `val600glu` all normalize to `V600E`

**✅ Supported - Small Indels:**
- Small deletions: `185delAG`, `6174delT`, `del19`
- Small insertions: variants containing `ins`
- Frameshift: `L747fs`, `Q61fs*5`
- Nonsense: `R248*`, `Q61*`

**❌ Not Supported - Structural Variants:**
- Fusions: `fusion`, `ALK fusion`, `EML4-ALK rearrangement` (will be rejected)
- Amplifications: `amplification`, `amp`, `overexpression` (will be rejected)
- Large deletions: `exon 19 deletion` (will be rejected)
- Splice variants: `exon 14 skipping`, `splice site` (will be rejected)
- Truncations: `truncating mutation`, `truncation` (will be rejected)

### How It Works

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

### Benefits

- **Better Evidence Matching**: MyVariant.info and CIViC searches work better with canonical forms
- **Flexible Input**: Accept variants from reports in any notation format
- **Type Classification**: Automatically detects missense, fusion, amplification, etc.
- **Position Extraction**: Extracts protein positions for coordinate-based lookups
- **HGVS Conversion**: Converts to standard HGVS protein notation when possible

### Programmatic Usage

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

## Variant Annotations

TumorBoard automatically extracts comprehensive variant annotations from MyVariant.info and FDA drug approval data:

### Database Identifiers
- **COSMIC ID**: Catalogue of Somatic Mutations in Cancer identifier (e.g., COSM476)
- **NCBI Gene ID**: Entrez Gene identifier (e.g., 673 for BRAF)
- **dbSNP ID**: Reference SNP identifier (e.g., rs113488022)
- **ClinVar ID**: ClinVar variation identifier (e.g., 13961)
- **ClinVar Clinical Significance**: Pathogenicity classification (e.g., Pathogenic, Benign)
- **ClinVar Accession**: ClinVar record accession (e.g., RCV000013961)

### HGVS Notations
- **Genomic**: Chromosome-level notation (e.g., chr7:g.140453136A>T)
- **Protein**: Amino acid change notation (when available)
- **Transcript**: cDNA-level notation (when available)

### Functional Annotations
- **SnpEff Effect**: Predicted variant effect (e.g., missense_variant, stop_gained)
- **PolyPhen2**: Pathogenicity prediction (D=Damaging, P=Possibly damaging, B=Benign)
- **CADD Score**: Combined Annotation Dependent Depletion score (higher = more deleterious)
- **gnomAD AF**: Population allele frequency from gnomAD exomes (helps assess rarity)

### Transcript Information
- **Transcript ID**: Reference transcript identifier (e.g., NM_004333.4)
- **Consequence**: Effect on transcript (e.g., missense_variant, frameshift_variant)

### FDA Drug Approvals
- **Drug Names**: FDA-approved brand and generic drug names
- **Indications**: Specific cancer indications and biomarker requirements
- **Approval Dates**: When drugs were approved by FDA
- **Marketing Status**: Current prescription status

All annotations are included in:
- Console output (via the assessment report)
- JSON output files (when using `--output` flag)
- Batch processing results

**Note**: Annotation availability depends on database coverage. Not all variants have complete annotation in all databases.

## Configuration

**Supported Models:**
- OpenAI: gpt-4, gpt-4o, gpt-4o-mini (validated model)
- Anthropic: claude-3-haiku-20240307 (Opus/Sonnet require higher-tier API access)
- Google: gemini/gemini-1.5-pro, gemini/gemini-pro
- Groq: groq/llama-3.1-70b-versatile, groq/mixtral-8x7b-32768

**Data Sources:**
- MyVariant.info API (aggregates CIViC, ClinVar, COSMIC)
- FDA openFDA API (drug approvals with biomarker indications)
- Evidence prioritization with tumor-type filtering
- 73.33% validation accuracy on gold standard dataset

**Performance:**
- gpt-4o-mini: Best balance (validated at 73% accuracy)
- gpt-4: More accurate but higher cost
- Claude models: Good alternative with strong reasoning


## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and code quality guidelines.

## License & Citation

**Author:** Dami Gupta (dami.gupta@gmail.com)

**License:** MIT License

**Citation:** If you use TumorBoard in your research, please cite:

```bibtex
@software{tumorboard2025,
  author = {Gupta, Dami},
  title = {TumorBoard: LLM-Powered Cancer Variant Actionability Assessment},
  year = {2025},
  url = {https://github.com/dami-gupta-git/tumor_board_v2}
}
```

## References

- [AMP/ASCO/CAP Guidelines](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5707196/)
- [MyVariant.info](https://myvariant.info/) | [CIViC](https://civicdb.org/) | [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) | [COSMIC](https://cancer.sanger.ac.uk/cosmic)
- [FDA openFDA API](https://open.fda.gov/) | [Drugs@FDA](https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-data-files)

---

**Note**: This tool is for research purposes only. Clinical decisions should always be made by qualified healthcare professionals.
