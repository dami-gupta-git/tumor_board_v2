
# TumorBoardLite

TumorBoardLite aggregates evidence from genomic databases to classify individual cancer variants using AMP/ASCO/CAP 
tiers. It is a research‑only variant‑centric tool, not an FDA‑cleared clinical decision support system or medical 
device, and must not be used for direct patient care.[2]


**Current Validation Performance (research datasets)**  
- 91% accuracy | 94% Tier I F1 score on curated SNP/indel‑focused benchmarks  
- 74–75% accuracy on a 47‑case comprehensive benchmark including fusions, CNVs, and complex biomarkers 
- (see `benchmarks/README.md` for details)

**TL;DR**  
Precision oncology depends on expert molecular tumor boards to determine whether genetic variants found in tumors are 
clinically “actionable” (e.g., FDA‑approved therapies or guideline‑backed biomarkers). This is a complex, manual 
process requiring synthesis of evidence from multiple databases and the clinical context.[3]

TumorBoardLite automates part of this workflow by aggregating evidence from key genomic and drug‑labeling databases 
(CIViC, ClinVar, COSMIC, FDA, CGI, VICC MetaKB, ClinicalTrials.gov, Semantic Scholar, AlphaMissense, etc.). 
It applies a pragmatic AMP/ASCO/CAP‑inspired decision tree (including Tier II scenarios and Tier III sub‑levels), 
and produces standardized tier assignments with confidence scores and human‑readable rationales. 
An LLM wrapper explains decision making and synthesizes the evidence.

A built‑in validation framework benchmarks predictions against expert‑labeled “gold‑standard” variant classifications 
using several curated datasets (original 15‑case, SNP‑only, and 47‑case comprehensive sets).

> **Critical Disclaimer**  
> - This tool provides **variant‑level guidance only**, not definitive clinical recommendations or treatment plans.
> - It implements a **partial, approximate operationalization** of the 2017 AMP/ASCO/CAP somatic variant guidelines, 
> not a complete or authoritative implementation.[3]
> - It is **not** an FDA‑cleared clinical decision support tool or medical device and is intended for 
> **research, education, and prototyping only**, not for direct patient care.[2][4]

Note: Currently, this tool fully supports only single nucleotide polymorphisms (SNPs) and small insertions/deletions 
(indels) for tiering. Structural variants (fusions, amplifications, large deletions, copy‑number changes, 
splice variants) are not tiered and represent many common real‑world biomarkers that tumor boards routinely act on.

**Coming Soon (roadmap)**  
- New evidence sources: SpliceAI, TCGA prevalence  
- Patient VCF Files: End‑to‑end pipeline from VCF upload → variant prioritization → comprehensive 
clinical‑style reports with trial matching (research only)
(see `ROADMAP.md` for details)
***

## Overview

TumorBoardLite models (and simplifies) the expert application of the AMP/ASCO/CAP 4‑tier classification 
system for somatic variants.[3]

Available interfaces:  
- **Streamlit Web App**: Single‑container web interface for interactive assessments  
- **Command‑Line Interface (CLI)**: Python CLI for batch processing, benchmarking, and automation

### Key Features

- **Evidence Aggregation**: CIViC, ClinVar, COSMIC, MyVariant.info, FDA openFDA drug labels, Cancer Genome 
- Interpreter (CGI) biomarkers, VICC MetaKB, Semantic Scholar, ClinicalTrials.gov, AlphaMissense, gnomAD‑backed annotations.
- **VICC MetaKB Integration**: Harmonized clinical interpretations from CIViC, CGI, JAX‑CKB, OncoKB, PMKB, 
MolecularMatch, including evidence levels and response types.
- **Literature Search & Extraction**:  
  - Semantic Scholar/PubMed search with tumor‑aware queries.
  - LLM‑based extraction of resistance/sensitivity profiles, evidence levels, and literature‑based tier recommendations.
- **Clinical Trials Matching**: Active trial search from ClinicalTrials.gov with variant‑specific enrollment 
detection and phase/status filtering.
- **LLM Tiering & Rationale**: LLM‑augmented AMP/ASCO/CAP tier assignment with confidence scores and multi‑paragraph 
rationales.
- **Smart Evidence Prioritization**: Tumor‑specific sensitivity evidence first, explicit resistance markers, 
variant‑class rules (e.g., BRAF V600‑only approvals, EGFR extracellular exclusions) via `variant_classes.yaml`.
- **Validation Framework**: Built‑in benchmarking against curated gold‑standard datasets, with confusion matrices, 
per‑tier precision/recall/F1, and “tier distance” metrics.
- **Multi‑LLM Support**: OpenAI, Anthropic, Google Gemini, Groq via `litellm`; models are configurable per run.

See **`FEATURES.md`** for details on variant normalization, functional annotations, and additional capabilities.

***

## Why This Tool Exists

Molecular tumor boards face several challenges in variant interpretation and actionability assessment:[5][6]

1. **Resource‑Intensive**: Manual variant review is slow and requires coordination among domain experts.  
2. **Incomplete Coverage**: No single database covers all variants, tumor contexts, or resistance mechanisms.  
3. **Fragmented Evidence**: Clinically relevant evidence is scattered across multiple structured and unstructured sources.  
4. **Rapidly Evolving Landscape**: New clinical trials, approvals, and guidelines appear frequently, 
making it difficult to stay current.  

TumorBoardLite aims to **automate evidence aggregation and triage** for variant actionability with AI, improving speed, 
transparency, and standardization of variant‑level reasoning in a research setting.

***

### Enhanced Evidence Sources

Planned and in‑progress enhancements include:
- SpliceAI splice‑impact predictions  
- TCGA prevalence and cohort‑level statistics  
- Additional PubMed integrations and improved mutation‑class literature search  
- Expanded trial matching heuristics (e.g., region/center filters)  

### Patient‑Level Analysis

Research roadmap for patient‑level workflows:
- VCF upload and preprocessing (multi‑sample VCF support)  
- Variant prioritization engine combining tier, pathogenicity, and prevalence  
- Comprehensive per‑patient reports summarizing prioritized variants, trials, and informational content (not treatment plans)  

See **`ROADMAP.md`** for detailed features and implementation status.

***

## Getting Started

### Option 1: Web Application (Docker – Recommended)

Use the Streamlit web interface with minimal local setup:

```bash
# 1. Clone repo
git clone https://github.com/dami-gupta-git/tumor_board_v2
cd tumor_board_v2

# 2. Configure API keys
cp .env.example .env
# Edit .env with your API keys (OpenAI, Anthropic, etc.)

# 3. Start the app
cd streamlit
docker compose up --build

# 4. Open in browser
# http://localhost:8501
```

See **`streamlit/README.md`** for full details on the web interface.

### Option 2: CLI Tool (pip install)

Use the command‑line interface for batch processing and validation:

```bash
# 1. Clone and install
git clone https://github.com/dami-gupta-git/tumor_board_v2
cd tumor_board_v2
pip install -e .

# 2. Set API key(s)
export OPENAI_API_KEY="your-key-here"

# 3. Run CLI commands
tumorboard assess BRAF V600E --tumor "Melanoma" --no-log
tumorboard batch benchmarks/sample_batch.json --no-log
tumorboard validate benchmarks/gold_standard.json --no-log
```

**Alternative LLMs** (via `litellm`):

```bash
# Anthropic Claude 3 Haiku
export ANTHROPIC_API_KEY="your-key-here"
tumorboard assess BRAF V600E --model claude-3-haiku-20240307

# Google Gemini
export GOOGLE_API_KEY="your-key-here"
tumorboard assess BRAF V600E --model gemini/gemini-1.5-pro

# Groq LLaMA
export GROQ_API_KEY="your-key-here"
tumorboard assess BRAF V600E --model groq/llama-3.1-70b-versatile
```

***

## LLM Decision Logging

All LLM‑related activity is logged by default to JSONL files in `./logs/llm_decisions_YYYYMMDD.jsonl`. Logs include:

- Variant and tumor context  
- Model, prompts, and responses  
- Tier decisions and confidence scores  
- Evidence snippets and error details  

You can disable logging per command with `--no-log`. See **`logging.md`** for log schema, analysis examples, and privacy recommendations.

***

## CLI Reference

| Command | Description |
|---------|-------------|
| `tumorboard assess BRAF V600E --tumor Melanoma` | Assess a single variant (research‑only tier and rationale) |
| `tumorboard batch variants.json` | Process multiple variants concurrently |
| `tumorboard validate benchmarks/gold_standard*.json` | Benchmark against gold‑standard datasets |

See **`CLI.md`** for all options, output formats, and model configuration. See **`BATCH_PROCESSING.md`** for details on batch assessment, validation metrics, and gold‑standard dataset creation.

***

## AMP/ASCO/CAP Tier System (Simplified)

Conceptual mapping (high‑level summary of the 4‑tier system):[3]

- **Tier I**: Strong clinical significance  
  - FDA‑approved therapies for the specific variant and tumor type  
  - Professional guideline recommendations  
  - Strong clinical trial evidence  

- **Tier II**: Potential clinical significance  
  - FDA‑approved therapies in other tumor types (off‑label scenarios)  
  - Early‑phase clinical trial evidence  
  - Predictive resistance markers that affect therapy choice  

- **Tier III**: Unknown or uncertain significance  
  - Preclinical‑only evidence or mixed/conflicting results  
  - Prognostic‑only markers that do not directly affect treatment selection  

- **Tier IV**: Benign / likely benign  
  - Known benign polymorphisms  
  - Variants with no oncogenic or clinical evidence  

TumorBoardLite uses a more granular internal scheme (I‑A/B, II‑A/B/C/D, III‑A/B/C/D) for reasoning, which is collapsed to the 4‑tier output.

***

## Variant Normalization & Annotations

- **Variant Normalization**  
  - Normalizes multiple protein‑level notations (`Val600Glu`, `p.V600E`, `v600e`) to canonical forms 
(e.g., `V600E`) for reliable evidence matching.
  - Fully supports missense, nonsense, small insertions/deletions, and frameshifts; rejects fusions, amplifications, 
“exon X deletion,” and other structural events.
  - See **`VARIANT_NORMALIZATION.md`** for supported formats and programmatic usage.  

- **Variant Annotations**  
  - Extracts COSMIC, dbSNP, ClinVar IDs, HGVS notations, PolyPhen‑2/SIFT/CADD, gnomAD frequencies, AlphaMissense scores, 
and FDA approvals via MyVariant.info and other APIs.
  - See **`VARIANT_ANNOTATIONS.md`** for the full list of fields.  

***

## Configuration

- **Models**: OpenAI (default `gpt-4o-mini`), Anthropic, Google Gemini, Groq, configured via environment variables and `litellm`.
- **Data Sources**: MyVariant.info (CIViC, ClinVar, COSMIC), FDA openFDA API, VEP REST API, VICC MetaKB, CGI Biomarkers, Semantic Scholar, ClinicalTrials.gov, gnomAD, AlphaMissense.

***

## Limitations & Shortcomings

**This tool provides guidelines, not definitive clinical recommendations.** It is a research prototype intended to assist—not replace—expert molecular tumor board review.

### Clinical Scope: What This Tool Does NOT Do

| Limitation | Description |
|-----------|-------------|
| **No Big Picture Analysis** | Assesses variants in isolation. Does not consider the full mutational profile, co‑occurring mutations, tumor mutation burden (TMB), MSI/TMB biomarkers, or interactions between multiple variants. |
| **No Patient Context** | Ignores prior treatments, treatment history, disease stage, performance status, comorbidities, and patient preferences that drive real‑world therapy choices. |
| **No Clonal Architecture** | Does not distinguish primary driver mutations from subclonal or acquired resistance mutations that emerge during therapy. |
| **No Germline vs Somatic Handling** | Does not differentiate inherited germline variants from acquired somatic mutations, which is critical for hereditary cancer syndromes and genetic counseling. |
| **No Combination / Sequencing Logic** | Cannot reason about combination regimens, sequencing of targeted therapies, or optimal treatment order across lines of therapy. |
| **No Resistance Trajectory Modeling** | Does not predict which resistance mechanisms may emerge on a given therapy or how to anticipate next‑line options. |
| **Limited Structural Variant Support** | Tiering is designed around SNPs and small indels. Fusions, amplifications, large deletions, copy‑number changes, splice variants, and complex structural variants are not currently tiered and many standard‑of‑care biomarkers fall into these categories. |

### Guideline & Validation Scope

- **Partial AMP/ASCO/CAP Implementation**  
  - The decision logic is a **pragmatic approximation** of the AMP/ASCO/CAP somatic variant interpretation guideline 
  and does not cover every nuance, edge case, or tumor‑specific rule described in the full guideline.[3]
  - Internal sub‑tiers (I‑A/B, II‑A/B/C/D, III‑A/B/C/D) are used for confidence and reasoning but are collapsed to 
the public 4‑tier output, which hides some distinctions in evidence strength/type.

- **Limited and Non‑Representative Validation**  
  - Reported metrics (e.g., 91% accuracy, 94% Tier I F1) are based on small curated datasets with limited tumor‑type 
  and gene diversity and are not representative of all real‑world variants.
  - A 47‑case comprehensive benchmark includes fusions, CNVs, and complex biomarkers and yields lower accuracy 
  (~74–75%), reflecting the difficulty of full MTB coverage.
  - Generalization to rare variants, unusual tumor types, noisy clinical notes, or non‑canonical inputs 
  is unknown and has not been clinically validated.

### Technical Limitations

- **LLM Hallucinations & Model Drift**  
  - LLMs may fabricate evidence, misinterpret database results, or overstate the strength of associations, despite guardrails.[7]
  - Behavior is **not stable across models or versions**: GPT‑4o, Claude, Gemini, and other models can generate different rationales and occasionally different tiers for the same case.[4]
  - Prompt or model updates can change outputs over time, even if the code and inputs remain constant.  

- **Evidence Coverage & API Failures**  
  - Evidence quality depends on what is curated in CIViC, ClinVar, COSMIC, MetaKB, CGI, and other upstream sources; gaps or biases in those resources propagate directly into the tool’s recommendations.
  - Network issues, rate limits, or upstream API/schema changes (VEP, MyVariant.info, openFDA, ClinicalTrials.gov, Semantic Scholar, MetaKB, CGI) can result in missing or incomplete annotations.
  - The system currently does **not reliably distinguish “no evidence exists” from “evidence temporarily unavailable,”** which may under‑ or over‑estimate a tier.  

- **Variant Normalization & Class Rules**  
  - The variant normalizer focuses on protein‑level SNPs and small indels and uses pattern‑based rules; unusual notations or exon‑level descriptions may be rejected or mis‑normalized.
  - Variant‑class rules (e.g., BRAF V600‑only approvals, EGFR extracellular domain exclusions, KIT exon‑specific behavior) are hand‑maintained in configuration files and cover only a subset of genes.
  - Exon‑level and domain‑level literature is only partially surfaced; foundational studies that speak to mutation classes (e.g., KIT exon 11) may be missed by variant‑token‑only searches.

- **Tumor Type Matching**  
  - Tumor type names must be mapped correctly to database conventions (e.g., “NSCLC” vs “Non‑Small Cell Lung Cancer” vs “Lung Adenocarcinoma”); mismatches can hide relevant evidence.

- **Context Windows & Truncation**  
  - Long evidence summaries and multi‑paper literature digests may be truncated before LLM processing due to context window limits, potentially dropping important details.[7]

### Regulatory, Privacy, and Governance

- **Not a Medical Device / CDS**  
  - This software has **not** undergone regulatory review and is **not** an FDA‑cleared clinical decision support system or medical device.[2][4]
  - Any use with real patient data should be confined to research, sandbox, or educational settings under appropriate institutional oversight.  

- **Logging & PHI**  
  - By default, LLM decisions and requests are logged to `./logs/llm_decisions_YYYYMMDD.jsonl`, including variant details, tumor types, and rationales.
  - When real patient data are used, this log content may qualify as Protected Health Information (PHI); users are responsible for de‑identification, secure storage, access control, and compliance with HIPAA/GDPR or local regulations.[8]

### When Expert Review is Essential

Expert molecular tumor board review is **mandatory** (not optional) in at least the following situations:[6]

- Variants with conflicting or sparse evidence across databases  
- Resistance mutations where treatment sequencing decisions are being considered  
- Cases requiring integration of patient‑specific factors (co‑mutations, prior therapies, comorbidities, trial eligibility)  
- **Any variant whose assessment will influence actual clinical decision‑making**  

This tool is for **research purposes only**. Clinical decisions must always be made by qualified healthcare professionals with access to the full clinical picture.

***


## Contributing

See **`CONTRIBUTING.md`** for development setup, coding standards, tests, and review process. Issues and pull requests are welcome.

***

## License & Citation

**Author:** Dami Gupta (dami.gupta@gmail.com)

**License:** MIT License (see `LICENSE`).

If you use TumorBoardLite in your research, please cite:

```bibtex
@software{tumorboard2025,
  author = {Gupta, Dami},
  title  = {TumorBoard: LLM-Powered Cancer Variant Actionability Assessment},
  year   = {2025},
  url    = {https://github.com/dami-gupta-git/tumor_board_v2}
}
```

***

## References

- AMP/ASCO/CAP Standards and Guidelines for Somatic Variant Interpretation and Reporting.[3]
- MyVariant.info, CIViC, ClinVar, COSMIC, VICC MetaKB, CGI Biomarkers.
- FDA openFDA, Drugs@FDA for drug and label data.
- Semantic Scholar API, ClinicalTrials.gov API for literature and trial evidence.

[1]: https://www.fda.gov/drugs/informationondrugs/ucm142438.htm
[2](https://www.hardianhealth.com/insights/regulatory-approval-for-medical-llms)
[3](https://pmc.ncbi.nlm.nih.gov/articles/PMC5707196/)
[4](https://www.nature.com/articles/s41746-025-01544-y)
[5](https://pmc.ncbi.nlm.nih.gov/articles/PMC7167859/)
[6](https://www.euformatics.com/blog-post/a-practical-guide-to-clinical-variant-interpretation)
[7](https://pmc.ncbi.nlm.nih.gov/articles/PMC12189880/)
[8](https://edenlab.io/blog/hipaa-compliant-ai-best-practices)