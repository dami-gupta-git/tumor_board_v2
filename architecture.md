# TumorBoard Architecture

> An LLM-powered cancer variant actionability assessment system with async processing, evidence aggregation, and validation framework.

## Table of Contents
- [System Overview](#system-overview)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Key Design Patterns](#key-design-patterns)
- [Module Details](#module-details)
- [Technology Stack](#technology-stack)
- [Performance Characteristics](#performance-characteristics)

## System Overview

TumorBoard is designed to automate cancer variant actionability assessment by combining:
1. **Evidence Aggregation** from multiple genomic databases (CIViC, ClinVar, COSMIC, VICC MetaKB, CGI) and FDA drug approvals
2. **Variant Normalization** for standardized representation across formats
3. **LLM Assessment** to interpret evidence and assign AMP/ASCO/CAP tier classifications
4. **Validation Framework** for benchmarking accuracy against gold standards

### Architectural Principles
- **Async-First**: Non-blocking I/O throughout the pipeline for high-throughput processing
- **Stateless Operations**: No shared state between assessments enables parallel execution
- **Type Safety**: Pydantic models enforce schema validation at all boundaries
- **Separation of Concerns**: Clear boundaries between data fetching, normalization, assessment, and validation

## Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Interface                            │
│                    (Typer + asyncio.run)                        │
└───────────────┬─────────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────────┐
│                     AssessmentEngine                              │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Orchestrates: Normalize → Fetch → Assess               │    │
│  │  • Context Manager: HTTP session lifecycle              │    │
│  │  • Concurrency: asyncio.gather for batch processing     │    │
│  │  • Error Handling: Graceful degradation                 │    │
│  └──────────────────────────────────────────────────────────┘    │
└───────┬───────────────────────┬──────────────────────┬───────────┘
        │                       │                      │
        ▼                       ▼                      ▼
┌──────────────┐   ┌─────────────────┐  ┌──────────────┐  ┌──────────────┐
│   Variant    │   │  MyVariantClient│  │  FDAClient   │  │  LLMService  │
│ Normalizer   │   │  (API Client)   │  │  (API Client)│  │  (litellm)   │
└──────────────┘   └─────────────────┘  └──────────────┘  └──────────────┘
        │                    │                   │                 │
        │                    └─────────┬─────────┘                 │
        │                              ▼                           │
        │                    ┌─────────────────┐                  │
        │                    │  Evidence       │                  │
        │                    │  Aggregation    │                  │
        │                    │  + FDA Approvals│                  │
        │                    └─────────────────┘                  │
        │                       │                      │
        └───────────────────────┴──────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ ActionabilityAssessment│
                    │   (AMP/ASCO/CAP Tier)  │
                    └───────────────────────┘
```

## Data Flow

### Single Variant Assessment Pipeline

```
User Input (gene, variant, tumor_type)
         │
         ▼
┌─────────────────────────────────┐
│  1. Variant Normalization       │
│  Val600Glu → V600E              │
│  Classify: missense/deletion/etc│
│  Validate: Only SNPs/indels     │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  2. Evidence Fetching (Parallel)│
│  MyVariant API Query +          │
│  FDA openFDA API Query:         │
│  • Multiple search strategies   │
│  • CIViC fallback (GraphQL)     │
│  • ClinVar fallback (E-utilities)│
│  • FDA drug approvals by gene   │
│  • Connection pooling (httpx)   │
│  • Retry w/ exponential backoff │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  3. Evidence Parsing            │
│  • CIViC evidence items         │
│  • ClinVar clinical significance│
│  • COSMIC mutation data         │
│  • FDA drug approvals           │
│  • Functional annotations       │
│  • Tumor-type prioritization    │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  4. Evidence Summary Generation │
│  • Prioritize PREDICTIVE+drugs  │
│  • Filter by tumor type         │
│  • Sort by evidence level (A>B) │
│  • Limit to top N items         │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  5. LLM Assessment              │
│  • Structured prompt generation │
│  • Temperature=0.1 (low random) │
│  • JSON response format         │
│  • FDA-approved rules in prompt │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  6. Tier Assignment             │
│  ActionabilityAssessment:       │
│  • Tier (I/II/III/IV)          │
│  • Confidence score (0-1)       │
│  • Recommended therapies        │
│  • Rationale                    │
│  • Evidence strength            │
└─────────────────────────────────┘
```

### Batch Processing Flow

```
Input: List[VariantInput]
         │
         ▼
┌──────────────────────────────────┐
│  asyncio.gather(*tasks)          │
│  Concurrent execution:           │
│  ┌──────┐ ┌──────┐ ┌──────┐    │
│  │Task 1│ │Task 2│ │Task N│    │
│  └───┬──┘ └───┬──┘ └───┬──┘    │
│      └─────────┼─────────┘       │
└────────────────┼──────────────────┘
                 │
                 ▼
         Event Loop Multiplexing
         (I/O-bound operations)
                 │
                 ▼
    ┌────────────────────────┐
    │  Results Collection    │
    │  • Capture exceptions  │
    │  • Filter valid results│
    └────────────────────────┘
```

## Key Design Patterns

### 1. Async Context Manager Pattern
```python
async with AssessmentEngine() as engine:
    assessment = await engine.assess_variant(variant)
# HTTP session automatically cleaned up
```

**Benefits:**
- Ensures proper resource cleanup
- Connection pooling for performance
- Prevents resource leaks

### 2. Retry with Exponential Backoff
```python
@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def _query(...):
    # API call
```

**Benefits:**
- Resilience against transient failures
- Reduces API rate limit errors
- Graceful degradation

### 3. Evidence Prioritization Strategy
```python
# Sort order:
1. PREDICTIVE evidence with drugs (sorted by evidence level)
2. Tumor-type-specific evidence
3. Other PREDICTIVE evidence
4. Remaining evidence
```

**Benefits:**
- Most actionable evidence first
- Tumor-context awareness
- Reduces noise in LLM input

### 4. Fallback Chain Pattern
```python
# Try MyVariant API
result = await myvariant_client.query(...)
if not result.hits:
    # Fallback to CIViC GraphQL
    civic_evidence = await fetch_civic_fallback(...)
    # Fallback to ClinVar E-utilities
    clinvar_data = await fetch_clinvar_fallback(...)
```

**Benefits:**
- Maximizes evidence coverage
- Handles database gaps
- Improves recall

## Module Details

### 1. CLI Layer (`cli.py`)
**Purpose:** Command-line interface for user interaction

**Key Features:**
- Three commands: `assess`, `batch`, `validate`
- Typer framework for type-safe argument parsing
- `asyncio.run()` bridge between sync CLI → async engine
- JSON output support

**Technology:**
- Typer (CLI framework)
- asyncio (async execution)
- dotenv (environment configuration)

### 2. Assessment Engine (`engine.py`)
**Purpose:** Core orchestration layer

**Pipeline:**
```
VariantInput → Normalize → MyVariantClient → Evidence → LLMService → Assessment
```

**Key Methods:**
- `assess_variant()`: Single variant assessment (sequential steps)
- `batch_assess()`: Concurrent processing with `asyncio.gather()`

**Design:**
- Async context manager for HTTP session lifecycle
- Stateless (no shared state between assessments)
- Error handling: Exceptions captured, not raised in batch mode

### 3. Variant Normalization (`utils/variant_normalization.py`)
**Purpose:** Standardize variant representations

**Capabilities:**
- **Format Conversion:**
  - One-letter → Three-letter amino acids
  - HGVS notation parsing (`p.V600E`, `p.Val600Glu`)
  - Case-insensitive input
- **Variant Classification:**
  - Missense, nonsense, frameshift
  - Insertion, deletion, duplication
  - Fusion, amplification (rejected)
- **Validation:**
  - Only SNPs and small indels allowed
  - Structural variants rejected with clear errors

**Algorithms:**
- Regex pattern matching for variant types
- Amino acid conversion dictionaries (3→1, 1→3)
- Position extraction for coordinate-based lookups

### 4. MyVariant API Client (`api/myvariant.py`)
**Purpose:** Evidence aggregation from genomic databases

**Data Sources:**
- **CIViC:** Clinical evidence with therapy recommendations
- **ClinVar:** Germline/somatic variant pathogenicity
- **COSMIC:** Somatic mutation catalog
- **gnomAD:** Population allele frequencies
- **SnpEff/PolyPhen2/CADD:** Functional predictions

### 4a. FDA API Client (`api/fda.py`)
**Purpose:** FDA drug approval data with biomarker indications

**Data Sources:**
- **FDA openFDA API:** Drugs@FDA database via `/drug/label.json` endpoint
- **Full prescribing information:** Indications, clinical studies, dosing, warnings
- **Companion Diagnostics:** Drugs approved with specific biomarker requirements

**Search Strategy:**
1. **Full-text search:** `{gene} AND {variant}` across all label fields
   - Finds variants in `clinical_studies` section (e.g., G719X, S768I, L861Q in afatinib label)
   - More effective than field-specific searches for uncommon mutations
2. **Fallback:** `indications_and_usage:{gene}` if no variant-specific results

**Why Full-Text Search:**
- FDA labels often use generic language in indications (e.g., "non-resistant EGFR mutations")
- Specific variants like G719X only appear in `clinical_studies` section
- Full-text search finds matches in any field without enumerating all possible fields

**Features:**
- Searches by gene and variant with gene alias support (ERBB2→HER2, etc.)
- Extracts brand names, generic names, and indication text
- Connection pooling and retry with exponential backoff
- Parallel execution with MyVariant client (via asyncio.gather)

**Query Strategies:**
1. `GENE p.VARIANT` (protein notation)
2. `GENE:VARIANT` (colon-separated)
3. `GENE VARIANT` (space-separated)
4. CIViC GraphQL fallback (for fusions, poorly-indexed variants)
5. ClinVar E-utilities fallback (when MyVariant lacks ClinVar data)

**Features:**
- HTTP connection pooling (httpx.AsyncClient)
- Retry with exponential backoff (tenacity)
- Pydantic parsing for type safety
- CIViC API v2 support (molecularProfiles + evidenceItems)

**Special Handling:**
- Detects fusions/amplifications and queries gene-level profiles
- Queries both specific variant AND gene-level MUTATION profiles
- Example: `BRAF V600E` + `BRAF MUTATION` (captures FDA approvals)

### 4b. CGI Client (`api/cgi.py`)
**Purpose:** Cancer Genome Interpreter biomarkers database

**Data Sources:**
- **CGI Biomarkers TSV:** Curated variant-drug associations with explicit FDA/NCCN status

**Features:**
- Downloads and caches biomarkers TSV file (7-day cache)
- Variant pattern matching (wildcards like `G719.` match `G719S`, `G719A`, etc.)
- Tumor type matching using centralized mappings
- Explicit FDA approval status for each biomarker

### 4c. VICC MetaKB Client (`api/vicc.py`)
**Purpose:** Harmonized evidence from multiple cancer variant knowledgebases

**Data Sources:**
- **VICC MetaKB API v1:** Aggregates and harmonizes clinical interpretations from:
  - CIViC (Clinical Interpretations of Variants in Cancer)
  - CGI (Cancer Genome Interpreter)
  - JAX-CKB (Jackson Laboratory Clinical Knowledgebase)
  - OncoKB
  - PMKB (Precision Medicine Knowledgebase)
  - MolecularMatch

**Features:**
- Lucene query syntax for flexible variant search
- Evidence levels: A (validated), B (clinical), C (case study), D (preclinical)
- Response types: Sensitivity/Responsive, Resistant, or OncoKB levels (1A, 1B, 2A, etc.)
- Source attribution for provenance tracking
- Tumor type filtering with centralized mappings
- Sensitivity/resistance classification

**API Endpoint:**
- `GET /api/v1/associations?q=GENE+VARIANT&size=N`

### 5. LLM Service (`llm/service.py`)
**Purpose:** LLM-based variant assessment

**Model Support:**
- OpenAI: gpt-4, gpt-4o, gpt-4o-mini
- Anthropic: Claude 3 Haiku/Sonnet/Opus
- Google: Gemini Pro/1.5 Pro
- Groq: Llama 3.1, Mixtral

**Configuration:**
- Temperature: 0.0-0.1 (low randomness for determinism)
- Max tokens: 2000
- JSON response mode (OpenAI models)

**Prompt Engineering:**
- System message: Expert oncologist role + AMP/ASCO/CAP guidelines
- User message: Evidence summary + classification instructions
- Embedded FDA-approved rules (BRAF V600E in melanoma, etc.)

**Output Parsing:**
- Handles markdown code blocks
- Robust JSON extraction
- Maps to `ActionabilityAssessment` Pydantic model

### 6. Evidence Models (`models/evidence.py`)
**Purpose:** Type-safe evidence representation

**Models:**
- `CIViCEvidence`: Therapy recommendations, evidence levels
- `ClinVarEvidence`: Pathogenicity classifications
- `COSMICEvidence`: Somatic mutation prevalence
- `FDAApproval`: FDA drug approval information (brand name, generic name, indication, approval date, marketing status)
- `CGIBiomarkerEvidence`: CGI variant-drug associations with FDA/NCCN approval status
- `VICCEvidence`: Harmonized interpretations from VICC MetaKB with sensitivity/resistance classification
- `Evidence`: Aggregated multi-source evidence including FDA approvals, CGI biomarkers, and VICC associations

**Evidence Summary Method:**
- Prioritizes PREDICTIVE evidence with drugs
- Filters by tumor type when provided
- Sorts by evidence level (A > B > C > D > E)
- Limits output (default: 15 items)

### 7. Assessment Models (`models/assessment.py`)
**Purpose:** Actionability tier representation

**AMP/ASCO/CAP Tiers:**
- **Tier I:** Strong clinical significance (FDA-approved, guidelines)
- **Tier II:** Potential significance (clinical trials, case reports)
- **Tier III:** Unknown significance (preclinical evidence)
- **Tier IV:** Benign/likely benign

**ActionabilityAssessment:**
- Extends `VariantAnnotations` (inherits database IDs, HGVS, functional annotations)
- Includes: tier, confidence_score, summary, rationale
- Recommended therapies with evidence levels
- References and clinical trial availability

### 8. Validator (`validation/validator.py`)
**Purpose:** Benchmarking against gold standard datasets

**Workflow:**
```
Gold Standard JSON → Load → Assess Each Variant → Compare Tiers → Metrics
```

**Concurrency Control:**
- Semaphore for max concurrent validations (default: 3)
- `asyncio.gather()` with exception handling

**Metrics Computed:**
- Overall accuracy
- Per-tier precision, recall, F1
- Confusion matrix
- Tier distance (how far off predictions are)

**Validation Result:**
- Expected vs. predicted tier
- Confidence score
- Full assessment details

## Technology Stack

### Core Dependencies
- **Python 3.13:** Modern async/await features
- **Pydantic 2.x:** Schema validation and serialization
- **httpx:** Async HTTP client with connection pooling
- **litellm:** Unified LLM API (OpenAI, Anthropic, Google, Groq)
- **tenacity:** Retry with exponential backoff
- **typer:** Type-safe CLI framework

### APIs & Data Sources
- **MyVariant.info:** Aggregated variant annotations
- **CIViC GraphQL API:** Clinical evidence (v2)
- **NCBI E-utilities:** ClinVar fallback queries
- **FDA openFDA API:** Drug approval data with biomarker indications
- **CGI Biomarkers:** Cancer Genome Interpreter variant-drug associations
- **VICC MetaKB:** Harmonized evidence from CIViC, CGI, JAX-CKB, OncoKB, PMKB, MolecularMatch

### Development Tools
- **pytest:** Testing framework
- **black:** Code formatting
- **ruff:** Fast Python linting

### Deployment
- **Docker:** Streamlit web app containerization
- **Docker Compose:** Single-command deployment

## Performance Characteristics

### Throughput
- **Single variant:** ~2-5 seconds (API + LLM)
- **Batch (10 variants):** ~5-10 seconds (concurrent)
- **Validation (30 variants):** ~30-60 seconds (concurrency=3)

### Bottlenecks
1. **LLM API latency:** Dominant factor (1-3s per variant)
2. **MyVariant API:** Fast (~200-500ms per query)
3. **CIViC fallback:** Slower (~1-2s for GraphQL queries)

### Optimization Strategies
- **Connection pooling:** Reuse HTTP connections across requests
- **Concurrent processing:** `asyncio.gather()` for I/O-bound operations
- **Evidence caching:** Future enhancement (not yet implemented)
- **Prompt optimization:** Limit evidence to top 15 items

### Resource Usage
- **Memory:** Low (~50-100MB for typical workloads)
- **CPU:** Minimal (I/O-bound, not CPU-bound)
- **Network:** Moderate (API calls for evidence + LLM)

## Validation Performance

**Current Metrics (gpt-4o-mini, SNPs/indels only):**
- Overall accuracy: 70%
- Tier I F1 score: 87%
- Tier II F1 score: Lower (fewer training examples)

**Improvement Strategies (Applied):**
1. ✅ Evidence prioritization (PREDICTIVE + drugs first)
2. ✅ Tumor-type filtering in evidence summary
3. ✅ FDA-approved rules embedded in LLM prompt
4. ✅ Low temperature (0.1) for determinism
5. 🔄 Multi-agent architecture (planned)
6. 🔄 Ensemble LLM voting (planned)

## Future Architecture Enhancements

### 1. RAG with Elasticsearch

Persistent vector store for semantic search over domain knowledge (PubMed, trials, guidelines).

```
┌─────────────────────────────────────────────────────────────┐
│                    Elasticsearch Cluster                     │
│  Index: pubmed        Index: trials        Index: guidelines │
│  ├── abstract         ├── title            ├── section       │
│  ├── embedding        ├── embedding        ├── embedding     │
│  └── gene             └── nct_id           └── cancer_type   │
└─────────────────────────────────────────────────────────────┘
                              │
          Query: "BRAF V600E" │
                              ▼
                    Hybrid Search (kNN + keyword)
                              │
                              ▼
                    Top-K → Inject into LLM prompt
```

**Docker Setup:**
```yaml
elasticsearch:
  image: elasticsearch:8.11.0
  volumes:
    - es_data:/usr/share/elasticsearch/data  # persists across restarts
```

**Use Cases:**
- Rare variants: PubMed case reports when CIViC has no data
- Trial matching: Surface relevant ClinicalTrials.gov entries
- Guidelines: Retrieve NCCN sections by cancer type

### 2. Adversarial Multi-Agent Architecture

Two-phase: collaborative evidence gathering, then adversarial decision-making.

```
┌─────────────────────────────────────────────────────────────┐
│                  COLLABORATIVE PHASE                        │
│   [Literature Agent]  [Trial Agent]  [Pathway Agent]        │
│              └────────────┼────────────┘                    │
│                           ▼                                 │
│                  Shared Evidence Pool                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  ADVERSARIAL PHASE                          │
│   [Advocate]              vs              [Skeptic]         │
│   "Tier I because..."                     "But consider..." │
│                           ▼                                 │
│                      [Arbiter]                              │
│                  Weighs both, assigns tier                  │
└─────────────────────────────────────────────────────────────┘
```

**Why Adversarial:**
| Problem | Solution |
|---------|----------|
| LLM overconfidence | Skeptic challenges weak evidence |
| Hallucinated citations | Skeptic demands verification |
| Tier inflation | Advocate must defend claims |

**Implementation:**
```python
# Parallel execution
advocate, skeptic = await asyncio.gather(
    llm.invoke("Argue FOR high actionability..."),
    llm.invoke("Argue AGAINST, what's missing?...")
)
# Sequential arbiter
tier = await llm.invoke(f"Advocate: {advocate}\nSkeptic: {skeptic}\nAssign tier.")
```

**Benefits:**
- Explainability: debate transcript shows reasoning
- Calibrated confidence: arbiter sees argument strength
- Mimics real tumor boards: specialists debate before consensus

### 3. VCF Processing Pipeline
```
VCF Upload → Variant Calling QC → Prioritization → Batch Assessment → Report
```

**Features:**
- Whole-exome/genome support
- Germline vs. somatic filtering
- Pathogenicity-based ranking
- Comprehensive patient reports

### 4. Enhanced Evidence Sources
```
Current: MyVariant (CIViC, ClinVar, COSMIC)
    ↓
Future:  + AlphaMissense (pathogenicity)
         + SpliceAI (splice impact)
         + PubMed (LLM-powered literature search)
         + ClinicalTrials.gov (trial matching)
         + TCGA (mutation prevalence)
```

## Design Trade-offs

### 1. Async vs. Sync
**Choice:** Async throughout
- **Pro:** High-throughput batch processing, non-blocking I/O
- **Con:** More complex code (async/await propagation)

### 2. Pydantic Strict Mode
**Choice:** Relaxed validation (allow extra fields)
- **Pro:** Robust to API schema changes
- **Con:** Less strict validation (silent field additions)

### 3. Evidence Limit (15 items)
**Choice:** Limit evidence passed to LLM
- **Pro:** Reduced cost, faster inference, avoids truncation
- **Con:** May miss edge-case evidence

### 4. SNPs/Indels Only
**Choice:** Reject fusions/amplifications
- **Pro:** Focused scope, better accuracy, clear boundaries
- **Con:** Limited coverage (but intentional design choice)

## Security Considerations

### API Key Management
- Environment variables (`.env` files)
- Never committed to git (`.gitignore`)
- Docker secrets support (Streamlit app)

### Input Validation
- Pydantic models enforce types
- Variant type validation (only SNPs/indels)
- Gene symbol normalization (uppercase)

### Rate Limiting
- Retry with exponential backoff
- Concurrency limits (semaphore in validation)
- Connection pooling (prevents socket exhaustion)

## Testing Strategy

### Unit Tests
- Variant normalization logic
- Evidence parsing (CIViC, ClinVar, COSMIC)
- Tier assignment logic

### Integration Tests
- MyVariant API queries (live or mocked)
- LLM assessment end-to-end
- Validation pipeline

### Validation Tests
- Gold standard benchmarking
- Per-tier metrics tracking
- Regression detection

## Deployment Architectures

### 1. CLI Tool (pip install)
```
User Machine → pip install → tumorboard CLI → APIs
```

### 2. Streamlit Web App (Docker)
```
Docker Container (Streamlit + Backend) → APIs
         ↑
    User Browser
```

### 3. API Service (Future)
```
FastAPI Server → Load Balancer → Workers → APIs
         ↑
    REST Clients
```

## Code Organization

```
tumor_board_v2/
├── src/tumorboard/
│   ├── __init__.py           # Package initialization
│   ├── cli.py                # CLI commands (Typer)
│   ├── engine.py             # Core orchestration
│   │
│   ├── api/                  # External API clients
│   │   ├── myvariant.py      # MyVariant API client
│   │   ├── myvariant_models.py  # API response models
│   │   ├── fda.py            # FDA openFDA API client
│   │   ├── cgi.py            # CGI biomarkers client
│   │   └── vicc.py           # VICC MetaKB client
│   │
│   ├── llm/                  # LLM integration
│   │   ├── service.py        # LLM assessment service
│   │   └── prompts.py        # Prompt templates
│   │
│   ├── models/               # Pydantic data models
│   │   ├── variant.py        # Variant input model
│   │   ├── evidence.py       # Evidence models
│   │   ├── assessment.py     # Assessment output
│   │   ├── validation.py     # Validation models
│   │   └── annotations.py    # Shared annotation fields
│   │
│   ├── utils/                # Utility modules
│   │   └── variant_normalization.py  # Normalization logic
│   │
│   └── validation/           # Validation framework
│       └── validator.py      # Gold standard validator
│
├── tests/                    # Test suite
├── benchmarks/               # Gold standard datasets
├── streamlit/                # Web interface
└── pyproject.toml            # Project configuration
```

## Summary

TumorBoard's architecture balances:
- **Performance:** Async I/O, connection pooling, concurrent processing
- **Reliability:** Retry logic, fallback chains, graceful degradation
- **Maintainability:** Type safety, clear separation of concerns, modular design
- **Extensibility:** Plugin architecture for new LLMs, data sources, and agents

The system is designed as a research tool for exploring LLM capabilities in clinical decision-making, with a validation framework to continuously measure and improve accuracy.
