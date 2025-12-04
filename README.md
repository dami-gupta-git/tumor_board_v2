# TumorBoard v2
An LLM-powered cancer variant actionability assessment tool with a built-in validation framework. 

**Current Validation Performance: 70% accuracy | 92% Tier I F1 score**

**TL;DR**:  
In precision oncology, determining whether a variant identified in a patient’s tumor is clinically “actionable” — i.e., whether an FDA-approved therapy or guideline exists for that specific alteration — is a complex process performed by expert molecular tumor boards.

This research tool mimics that decision-making workflow. It aggregates evidence from leading genomic databases (CIViC, ClinVar, COSMIC) and FDA drug-labeling data, then employs large language models to assign standardized AMP/ASCO/CAP actionability tiers (Tier I = strongest evidence for clinical action; Tier IV = benign/likely benign). All reasoning steps and evidence sources are fully logged for transparency and auditability. A separate validation framework benchmarks these assigned tiers against specified expert‑curated “gold‑standard” classifications.  
 
**Important** : This tool currently only supports SNPs and small indels.

**NOTE** : This is a research prototype exploring whether LLMs can approximate molecular tumor‑board decision‑making; strictly not for clinical use.


### Coming Soon TL;DR – The Real AI Tumor Board

- Full RAG stack (PubMed, ClinicalTrials.gov, NCCN/ESMO guidelines,..)  
- New evidence sources: AlphaMissense, SpliceAI, TCGA prevalence, gnomAD filtering  
- Patient VCF Files. From single-variant → whole patient genome: VCF upload → variant prioritization → comprehensive clinical reports + trial matching  
- Two-phase agentic architecture:  
  → Collaborative phase: parallel specialized agents (Literature, Pathways, Trials, Guidelines, etc.)  
  → Adversarial phase: Advocate vs. Skeptic debate → Arbiter assigns final tier  
  → Configurable meta-rules decide who speaks when, when to dig deeper, and when to escalate  
  → Semantic embeddings and a knowledge graph to store and retrieve the history of agent debates

The result: higher accuracy, transparent debate traces, and reasoning that closely resembles a real multidisciplinary panel.

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

- **Evidence Aggregation**: Fetches from CIViC, ClinVar, COSMIC, and FDA drug approvals
- **LLM Tiering**: Assigns AMP/ASCO/CAP tiers with confidence scores and rationale
- **Validation Framework**: Built-in benchmarking against gold standard datasets
- **Multi-LLM Support**: OpenAI, Anthropic, Google, Groq via litellm

See **[Full Feature List](FEATURES.md)** for variant normalization, functional annotations, and more.


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

### Enhanced Evidence Sources
AlphaMissense, SpliceAI, gnomAD, TCGA prevalence data, and ClinicalTrials.gov integration.

### RAG Pipeline
Indexed PubMed abstracts, clinical trial matching, NCCN/ESMO guideline retrieval, and variant lookups for rare mutations.

### Agentic AI Architecture
Two-phase multi-agent system: collaborative evidence gathering (Literature, Trials, Pathways agents) followed by adversarial debate (Advocate vs Skeptic → Arbiter assigns final tier).

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

Automatically standardizes variant notations (`Val600Glu` → `V600E`, `p.V600E` → `V600E`) for better database matching. Supports SNPs and small indels; rejects fusions, amplifications, and other structural variants.

See **[Variant Normalization Details](VARIANT_NORMALIZATION.md)** for supported formats and programmatic usage.

## Variant Annotations

Extracts COSMIC, dbSNP, ClinVar IDs, HGVS notations, PolyPhen2/CADD scores, gnomAD frequencies, and FDA drug approvals from MyVariant.info.

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

---

**Note**: This tool is for research purposes only. Clinical decisions should always be made by qualified healthcare professionals.
