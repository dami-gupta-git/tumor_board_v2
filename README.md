# TumorBoardLite
An tool for assessing cancer variant actionability with integrated validation. Performs evidence‑driven 
AMP/ASCO/CAP tiering. Includes with a validation framework to benchmark against gold standard datasets.

**Current Validation Performance: 91% accuracy | 94% Tier I F1 score**

**TL;DR**:
Precision oncology depends on expert molecular tumor boards to determine whether genetic variants found in
tumors are clinically 'actionable'—that is, whether they have associated FDA-approved therapies or clinical
guidelines. This is a complex, manual process involving synthesis of evidence from multiple databases.

TumorBoardLite automates and mimics this expert workflow by aggregating evidence from key genomic and drug-labeling
databases (e.g. CIViC, ClinVar, COSMIC, FDA). It applies an explicit AMP/ASCO/CAP decision tree (including Tier II
scenarios and Tier III sub‑levels), and produces standardized tier assignments with confidence scores and
human‑readable rationales. There is an LLM wrapper that explains decision making and provides detailed evidence.

A built-in validation framework benchmarks predictions against expert-labeled "gold-standard" variant classifications.

**Important**: This tool provides guidelines for individual variants, not comprehensive clinical recommendations. It assesses variants in isolation and does not account for patient context, co-occurring mutations, prior treatments, or the full clinical picture that informs real tumor board decisions. See [Limitations & Shortcomings](#limitations--shortcomings) for details.

Note: Currently, this tool supports only single nucleotide polymorphisms (SNPs) and small insertions/deletions (indels).  
It is a research prototype and is not intended for clinical use.  

**Coming Soon**
- New evidence sources: SpliceAI, TCGA prevalence
- Patient VCF Files: Supports analysis from single variants to whole patient exomes/genomes by uploading VCF files, performing variant prioritization, and generating comprehensive clinical reports with trial matching.

### Quick Start (Docker)

```bash
git clone https://github.com/dami-gupta-git/tumor_board_v2
cd tumor_board_v2
cp .env.example .env  

# Add your API keys to .env
cd streamlit
docker compose up --build

# Open http://localhost:8501
```
See **[Streamlit App Guide](streamlit/README.md)** for full details on the web interface.

  
### Screenshots
**Web UI**  
![alt text](image-5.png)  
 
**Validator**  
![alt text](image-6.png)


## Overview

TumorBoard models the expert application of the **AMP/ASCO/CAP 4-tier classification system**.

Available in two interfaces:
- **Streamlit Web App**: Modern single-container web interface
- **Command-Line Interface**: Python CLI tool for batch processing and automation

### Key Features

- **Evidence Aggregation**: Fetches from CIViC, ClinVar, COSMIC, FDA drug approvals, CGI Biomarkers, VICC MetaKB, Semantic Scholar, ClinicalTrials.gov, and AlphaMissense
- **VICC MetaKB Integration**: Harmonized evidence from 6 major cancer variant knowledgebases (CIViC, CGI, JAX-CKB, OncoKB, PMKB, MolecularMatch)
- **Semantic Scholar Literature Search**: Research literature with citation metrics, influential citations, and AI-generated paper summaries (TLDR) for resistance mutations and emerging evidence
- **LLM-Based Literature Knowledge Extraction**: Structured extraction of resistance/sensitivity profiles from papers with tier recommendations
- **Clinical Trials Matching**: Active trial search from ClinicalTrials.gov with variant-specific enrollment detection
- **LLM Tiering**: Assigns AMP/ASCO/CAP tiers with confidence scores and rationale
- **Smart Evidence Prioritization**: Surfaces tumor-specific sensitivity evidence first; correctly interprets resistance markers
- **Validation Framework**: Built-in benchmarking against gold standard datasets
- **Multi-LLM Support**: OpenAI, Anthropic, Google, Groq via litellm

See **[Full Feature List](FEATURES.md)** for variant normalization, functional annotations, and more.


## Why This Tool Exists

Molecular tumor boards face significant challenges:

Variant classification for tumor boards is:

1. Resource Intensive: Manual variant review is slow, requiring deep expertise and coordination.
2. Incomplete: No single database fully covers all variants or tumor contexts.
3. Fragmented: Evidence is scattered across multiple sources, demanding extensive manual integration.
4. Rapidly Evolving: Clinical evidence, trials, and approvals constantly change, challenging up-to-date assessments.  

TumorBoard tackles these challenges by automating evidence synthesis and triaging variant actionability with 
AI, aiming to improve speed, coverage, and transparency.


## Limitations & Shortcomings

**This tool provides guidelines, not definitive clinical recommendations.** It is a research prototype intended to assist—not replace—expert molecular tumor board review.

### What This Tool Does NOT Do

| Limitation | Description |
|------------|-------------|
| **No Big Picture Analysis** | Assesses variants in isolation. Does not consider the patient's full mutational profile, co-occurring mutations, tumor mutation burden (TMB), or how multiple variants interact. |
| **No Patient Context** | Ignores prior treatments, treatment history, disease stage, performance status, comorbidities, and patient preferences that influence real-world therapy selection. |
| **No Clonal Architecture** | Does not distinguish primary driver mutations from subclonal or resistance mutations that emerge during treatment. |
| **No Germline vs Somatic** | Does not differentiate inherited germline variants from acquired somatic mutations—critical for hereditary cancer syndromes. |
| **No Combination Therapy Logic** | Cannot reason about drug combinations, sequencing of therapies, or optimal treatment order. |
| **No Resistance Trajectory** | Does not predict which resistance mechanisms may emerge on a given therapy. |
| **Limited Structural Variants** | Only supports SNPs and small indels. Fusions, amplifications, large deletions, and copy number changes are not supported. |

### Technical Limitations

- **LLM Hallucination**: LLMs may fabricate evidence or misinterpret database results
- **Database Coverage**: Evidence quality depends on what's curated in CIViC, ClinVar, COSMIC, etc.
- **Novel Variants**: Rare or newly discovered variants may have minimal or no database coverage
- **Tumor Type Matching**: Tumor type names must match database conventions (e.g., "NSCLC" vs "Non-Small Cell Lung Cancer")
- **Context Windows**: Very long evidence summaries may be truncated before LLM processing
- **Real-Time Data**: Evidence reflects database snapshots; new FDA approvals or guideline changes may not be immediately reflected

### When Expert Review is Essential

- Variants with conflicting evidence across databases
- Resistance mutations requiring treatment sequencing decisions
- Cases requiring consideration of patient-specific factors
- Any variant that will inform actual clinical decision-making

**This tool is for research purposes only.** Clinical decisions should always be made by qualified healthcare professionals with access to the full clinical picture.

## Summary Roadmap

### Enhanced Evidence Sources
SpliceAI and TCGA prevalence data. AlphaMissense pathogenicity predictions, PubMed literature search, and ClinicalTrials.gov matching are now integrated.

### Patient-Level Analysis
VCF upload, whole-exome/genome processing, variant prioritization, and comprehensive clinical report generation.

See **[Full Roadmap](ROADMAP.md)** for detailed feature descriptions and implementation plans.

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

---

**Option 2: CLI Tool (Requires pip install)**

Use the command-line interface for batch processing and validation:

```bash
# 1. Clone and install
git clone https://github.com/dami-gupta-git/tumor_board_v2
cd tumor_board_v2
pip install -e .

# 2. Set API key
export OPENAI_API_KEY="your-key-here"

# 3. Use CLI commands
tumorboard assess BRAF V600E --tumor "Melanoma" --no-log
tumorboard batch benchmarks/sample_batch.json --no-log
tumorboard validate benchmarks/gold_standard.json --no-log
```

**Alternative Large Language Models:**
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

## LLM Decision Logging

All LLM decisions are logged to `./logs/llm_decisions_YYYYMMDD.jsonl` (enabled by default, disable with `--no-log`). Captures request details, tier decisions, confidence scores, rationale, and errors.

See **[Logging Documentation](logging.md)** for log format, analysis examples with Python/jq, and best practices.

## CLI Reference

| Command | Description |
|---------|-------------|
| `tumorboard assess BRAF V600E --tumor Melanoma` | Assess single variant |
| `tumorboard batch variants.json` | Process multiple variants |
| `tumorboard validate gold_standard.json` | Benchmark against gold standard |

See **[Full CLI Documentation](CLI.md)** for all options, output formats, and alternative model configuration.

See **[Batch Processing & Validation](BATCH_PROCESSING.md)** for detailed batch assessment, validation framework, and gold standard creation.

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


## Literature Knowledge Extraction

TumorBoard uses a multi-stage LLM pipeline to extract structured clinical knowledge from research literature:

### How It Works

1. **Tumor-Specific Literature Search**: Searches Semantic Scholar/PubMed with tumor-type-aware queries (e.g., "KIT D816V resistance GIST" instead of generic "cancer")

2. **Relevance Filtering**: LLM scores each paper's relevance (0-1) to the specific gene/variant/tumor context, filtering out papers about different tumor types or variants

3. **Structured Knowledge Extraction**: LLM analyzes relevant papers to extract:
   - **Mutation type**: Primary (driver) vs. secondary (resistance/acquired)
   - **Resistance profile**: Drugs the variant causes resistance to, with evidence level
   - **Sensitivity profile**: Drugs the variant may respond to, including IC50 values
   - **Tier recommendation**: Literature-based AMP/ASCO/CAP tier with rationale

### Example: KIT D816V in GIST

```
Literature Knowledge (confidence: 90%):
  Mutation Type: secondary (resistance)
  Resistant to: imatinib (clinical), sorafenib (preclinical)
  Sensitive to: PLX9486 (preclinical), dasatinib (in vitro, IC50: 37-79 nM)
  Tier recommendation: II
  Rationale: Resistance marker excluding standard GIST therapies
```

This enables correct classification of complex cases where structured databases may have incomplete or conflicting information.

### Configuration

The variant-specific configuration in `src/tumorboard/config/variant_classes.yaml` includes:
- IC50 resistance/sensitivity profiles for known mutations
- Special rules for tumor-type-specific handling (e.g., D816V behaves differently in GIST vs. mastocytosis)
- Literature references (PMIDs) supporting the classification

## Variant Normalization

Automatically standardizes variant notations (`Val600Glu` → `V600E`, `p.V600E` → `V600E`) for better database matching. Supports SNPs and small indels; rejects fusions, amplifications, and other structural variants.

See **[Variant Normalization Details](VARIANT_NORMALIZATION.md)** for supported formats and programmatic usage.

## Variant Annotations

Extracts COSMIC, dbSNP, ClinVar IDs, HGVS notations, PolyPhen2/CADD scores, gnomAD frequencies, AlphaMissense pathogenicity predictions, and FDA drug approvals from MyVariant.info.

See **[Variant Annotations Details](VARIANT_ANNOTATIONS.md)** for the full list of extracted fields.

## Configuration

**Models:** OpenAI (gpt-4o-mini), Anthropic, Google Gemini, Groq via litellm
**Data:** MyVariant.info (CIViC, ClinVar, COSMIC) + FDA openFDA API


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
- [VICC MetaKB](https://search.cancervariants.org/) | [CGI Biomarkers](https://www.cancergenomeinterpreter.org/biomarkers)
- [Semantic Scholar API](https://www.semanticscholar.org/product/api) | [ClinicalTrials.gov API](https://clinicaltrials.gov/data-api/api)

---

**Note**: This tool is for research purposes only. Clinical decisions should always be made by qualified healthcare professionals.
