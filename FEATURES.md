# TumorBoard Features

Detailed feature documentation for TumorBoard v2.

## Core Capabilities

### Variant Processing
- **SNP/Small Indel Focus**: Specialized support for point mutations, small insertions, deletions, and frameshifts
- **Variant Type Validation**: Automatically validates and rejects unsupported variant types (fusions, amplifications, etc.)
- **Variant Normalization**: Automatically standardizes variant notations (Val600Glu → V600E, p.V600E → V600E) for better API matching

### Evidence Aggregation
- **Multi-Source Evidence**: Fetches from MyVariant.info, FDA openFDA, CGI biomarkers, VICC MetaKB, Semantic Scholar, and ClinicalTrials.gov
- **FDA Drug Approvals**: FDA-approved oncology drugs with companion diagnostics and biomarker-based indications
- **CGI Biomarkers**: Cancer Genome Interpreter biomarkers with explicit FDA/NCCN approval status
- **VICC MetaKB Integration**: Harmonized evidence from 6 major cancer variant knowledgebases (CIViC, CGI, JAX-CKB, OncoKB, PMKB, MolecularMatch)
- **Literature Search**: LLM-powered paper relevance scoring and knowledge extraction from Semantic Scholar/PubMed
- **Clinical Trials**: Active trial matching from ClinicalTrials.gov with variant-specific detection

### Tier Classification
- **Deterministic Tiers**: Tier classification computed in code (`get_tier_hint()`), not by LLM - ensures reproducibility
- **LLM Narrative Only**: LLM generates clinical explanations for pre-computed tiers
- **80%+ Accuracy**: Validated against gold standard dataset (up from ~50% with prompt-only approach)
- **~95% Tier I Recall**: High sensitivity for FDA-approved actionable variants

### Oncogene Mutation Classes
- **BRAF Class I (V600)**: RAS-independent monomers → V600 inhibitors (vemurafenib, dabrafenib)
- **BRAF Class II (G469A, K601E, etc.)**: RAS-independent dimers → MEK inhibitors, NOT V600 inhibitors
- **BRAF Class III (D594G, etc.)**: Kinase-impaired, RAS-dependent → context-dependent therapy
- **Tumor-Specific Notes**: e.g., BRAF V600E in CRC requires encorafenib + cetuximab (not BRAF monotherapy)

### Pathway-Actionable TSGs
Unlike generic tumor suppressors, these TSGs activate druggable pathways when lost:
- **PTEN**: LOF → PI3K/AKT/mTOR activation → alpelisib, capivasertib
- **VHL**: LOF → HIF stabilization → belzutifan (FDA-approved for VHL-associated RCC)
- **NF1**: LOF → RAS/MAPK activation → selumetinib (FDA-approved for NF1 plexiform neurofibromas)
- **TSC1/TSC2**: LOF → mTOR activation → everolimus

### Variant-Class Validation
- **BRAF V600 specificity**: G469A does NOT match V600E approvals
- **EGFR extracellular domain exclusions**: R108K, A289V excluded from TKI approvals (not responsive)
- **KRAS G12C vs generic**: G12C matches sotorasib; G12D matches anti-EGFR exclusion
- **KIT exon mapping**: V560D → exon 11 approvals; D816V → imatinib resistance

### Evidence Prioritization
- **PREDICTIVE first**: Therapeutic evidence prioritized over prognostic
- **Tumor-type filtering**: Evidence filtered by patient's tumor type
- **Evidence level sorting**: A > B > C > D > E
- **PREDICTIVE vs PROGNOSTIC distinction**: Literature analysis distinguishes actionable resistance from survival-only prognosis

### Annotations & Identifiers
- **Database IDs**: COSMIC, dbSNP, ClinVar, NCBI Gene, HGVS notations
- **Functional Annotations**: SnpEff effects, PolyPhen2 predictions, CADD scores, gnomAD frequencies
- **AlphaMissense**: Pathogenicity predictions with scores

## Output Features

### Pretty Box Reports
- Rich-formatted CLI output with colored tier indicators
- HGVS notation, database IDs, and functional scores
- Soft-wrapped clinical narratives
- Therapy recommendations highlighted

### Multiple Output Formats
- CLI pretty-print with Rich panels
- JSON export for programmatic use
- Batch processing with progress indicators

## Technical Features

- **Validation Framework**: Built-in benchmarking against gold standard datasets with per-tier metrics
- **Multiple LLM Support**: OpenAI, Anthropic, Google, Groq via litellm
- **Async Throughout**: Fast, concurrent processing for batch assessments
- **Rich CLI**: Command-line interface with Typer
- **Streamlit Interface**: Modern single-container web app

## Architecture Highlights

- **Preprocessing-Heavy**: Complex tier logic in testable Python code, not LLM prompts
- **Fallback Chains**: CIViC GraphQL, ClinVar E-utilities when primary sources fail
- **Connection Pooling**: httpx async client with retry/backoff
- **Type Safety**: Pydantic models throughout
