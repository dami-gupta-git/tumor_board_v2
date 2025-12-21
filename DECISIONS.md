# TumorBoard Technical Decisions

This document tracks key technical decisions in the variant classification system, which implements the **2017 AMP/ASCO/CAP Guidelines** for somatic variant interpretation.

---

## Architecture Overview

### Preprocessing-Driven Tier Classification

**Location:** `src/tumorboard/models/evidence/evidence.py`

The system uses a **preprocessing-heavy architecture** where complex tier logic is computed in code before LLM evaluation:

```
Evidence Collection → Preprocessing (get_tier_hint) → LLM Validation → Final Assessment
```

**Rationale:**
- Complex tier logic is better expressed in testable code than natural language prompts
- Preprocessing catches errors LLM would miss (variant-class matching, FDA validation)
- LLM focuses on synthesis and edge cases, not rule application
- Achieved 80%+ accuracy vs ~50% with prompt-only approach

---

## AMP/ASCO/CAP Tier System

### Tier Definitions

| Tier | Definition | Evidence Requirements |
|------|------------|----------------------|
| **I-A** | FDA-approved OR professional guidelines | FDA label, NCCN/ASCO guidelines, CIViC Level A |
| **I-B** | Well-powered studies, guidelines pending | CIViC Level B, molecular subtype-defining |
| **II-A** | FDA-approved in DIFFERENT tumor type | Off-label potential |
| **II-B** | Well-powered studies, no guidelines | Strong evidence, no FDA/NCCN |
| **II-C** | Strong prognostic with established value | Level A/B/C prognostic evidence |
| **II-D** | Active trials OR resistance without alternative | Clinical trials enrolling |
| **III-A** | Actionable elsewhere, zero evidence in tumor | Cross-tumor extrapolation |
| **III-B** | VUS in established cancer gene | Unknown functional impact |
| **III-C** | Case reports (n<5) OR preclinical only | Insufficient human data |
| **III-D** | No evidence at all | Truly unknown |
| **IV** | Benign/likely benign | ClinVar benign classification |

---

## Core Classification Logic

### Decision Flow (`get_tier_hint`)

**Location:** [evidence.py:1119-1496](src/tumorboard/models/evidence/evidence.py#L1119-L1496)

The tier classification follows this priority order:

```
1. Benign check (ClinVar) → Tier IV
2. Molecular subtype-defining → Tier I-B
3. FDA approval FOR variant in tumor → Tier I-A/B
4. Literature-extracted knowledge → Tier I-B
5. Active variant-specific trials → Tier II-D
6. Investigational-only pairs → Tier III
7. Resistance without alternative → Tier II-D
8. Prognostic/diagnostic only → Tier II-C or III-C
9. FDA approval in different tumor → Tier II-A
10. Gene-level therapeutic evidence → Tier II-B/D
11. VUS in known cancer gene → Tier III-B
12. Default → Tier III-D
```

---

## Variant-Class Approval Matching

### Problem Solved

FDA approvals are often **variant-class-specific** (e.g., "BRAF V600" not "any BRAF mutation"). Without validation, non-V600 BRAF mutations would incorrectly claim V600-specific FDA approvals.

### Configuration

**Location:** [variant_classes.yaml](src/tumorboard/config/variant_classes.yaml)

```yaml
BRAF:
  require_explicit: true  # Must find V600 pattern to match
  classes:
    V600:
      patterns: ["v600", "v600e", "v600k"]
      variants: [V600E, V600K, V600D, V600R]

EGFR:
  classes:
    any_mutation:
      variants: ["*"]
      exclude_variants:
        - T790M     # Resistance mutations need explicit approval
        - R108K     # Extracellular domain - NOT responsive to TKIs
```

### Genes with Variant-Specific Rules

| Gene | Rule | Example |
|------|------|---------|
| **BRAF** | Only V600 variants match V600 approvals | G469A does NOT match V600E approvals |
| **KRAS** | G12C-specific vs generic RAS | G12C matches sotorasib; G12D matches anti-EGFR exclusion |
| **EGFR** | Common/uncommon/resistance classes | L858R matches generic; T790M needs explicit; R108K excluded |
| **KIT** | Exon mapping + resistance | V560D→exon 11; D816V causes imatinib resistance in GIST |
| **FGFR2** | Fusions only; point mutations are resistance | N549H is acquired resistance, not fusion approval |

### Extracellular Domain Exclusions

**Location:** [variant_classes.yaml:105-123](src/tumorboard/config/variant_classes.yaml#L105-L123)

EGFR extracellular domain mutations (exons 1-16) are explicitly excluded from TKI approvals:
- **NOT responsive** to gefitinib, erlotinib, osimertinib
- Primarily found in **glioblastoma**, not NSCLC
- Examples: R108K, A289V, G598V

---

## Investigational-Only Gene-Tumor Pairs

### Problem Solved

Despite explicit guidance, LLM would cite trial data and predict Tier I/II for combinations with **no approved therapy**.

### Implementation

**Location:** [evidence.py](src/tumorboard/models/evidence/evidence.py) - `is_investigational_only()`

Hardcoded pairs that always return Tier III:

| Gene | Tumor Type | Rationale |
|------|------------|-----------|
| KRAS | Pancreatic | No approved KRAS-targeted therapy |
| NRAS | Melanoma | No approved NRAS-targeted therapy |
| TP53 | Any | Prognostic only, not targetable |
| APC | Colorectal | Not directly targetable |
| VHL | Renal | Different mechanism than HIF-targeted therapies |
| SMAD4 | Pancreatic | Not targetable |
| ARID1A | Any | No approved therapy |

---

## Resistance Marker Classification

### Decision Logic

**Location:** [evidence.py](src/tumorboard/models/evidence/evidence.py) - `is_resistance_marker_without_targeted_therapy()`

| Scenario | Tier | Example |
|----------|------|---------|
| Resistance + FDA-approved alternative | **Tier I** | EGFR T790M → osimertinib |
| Resistance + no alternative | **Tier II-D** | EGFR C797S (no approved therapy) |
| Resistance excludes standard therapy | **Tier II** | KRAS in CRC excludes anti-EGFR |

### Sources Checked
- FDA labels for wild-type requirements
- CGI FDA-approved resistance markers
- VICC/CIViC resistance evidence (Level A/B only)

---

## Evidence Source Integration

### Priority Order for FDA Detection

1. **Explicit variant mention** in FDA indication text
2. **Gene + variant class validation** via variant_classes.yaml
3. **CIViC Level A/B** predictive evidence with tumor matching
4. **CIViC Assertions** with NCCN guideline references
5. **CGI FDA-approved** sensitivity biomarkers

### CIViC Assertions

**Location:** [civic.py](src/tumorboard/api/civic.py)

CIViC Assertions provide curated AMP/ASCO/CAP tier classifications:
- Expert-curated tier assignments
- FDA companion diagnostic status
- NCCN guideline references
- Used as authoritative tier source when available

### NCCN Guideline Detection

**Location:** [evidence.py](src/tumorboard/models/evidence/evidence.py) - `_get_nccn_guideline_for_tumor()`

Variants with NCCN guideline backing classify as Tier I-A even without explicit FDA label mention.

---

## Molecular Subtype-Defining Biomarkers

### Tier I-B Classification

**Location:** [evidence.py](src/tumorboard/models/evidence/evidence.py) - `is_molecular_subtype_defining()`

Some variants define molecular subtypes with Level A clinical utility:

| Variant | Tumor | Subtype | Clinical Impact |
|---------|-------|---------|-----------------|
| POLE P286R | Endometrial | POLE-ultramutated | Excellent prognosis, may de-escalate treatment |
| POLE V411L | Endometrial | POLE-ultramutated | Per TCGA 2013, NCCN/ESMO guidelines |

---

## Prognostic vs Therapeutic Classification

### Decision Logic

| Evidence Type | Strong (Level A/B/C) | Weak (Level D/E) |
|---------------|---------------------|------------------|
| **Therapeutic** | Tier I or II | Tier III |
| **Prognostic with treatment impact** | Tier I | Tier II-C |
| **Prognostic without treatment impact** | Tier II-C | Tier III-C |

### CIViC PREDICTIVE vs PROGNOSTIC Separation

**Location:** [evidence.py](src/tumorboard/models/evidence/evidence.py) - `summary_compact()`

PREDICTIVE and PROGNOSTIC assertions are presented separately:
- PREDICTIVE Tier I = therapy actionable
- PROGNOSTIC Tier I ≠ therapy actionable

---

## VUS Detection (Tier III-B)

### OncoKB Cancer Gene List

**Location:** [oncokb.py](src/tumorboard/api/oncokb.py)

Checks if variant is in a known cancer gene but lacks curated evidence:

1. Gene in OncoKB cancer gene list (or fallback list)
2. No Level A/B evidence for this specific variant
3. No CIViC assertions
4. No FDA approvals

**Impact:** VUS in established cancer genes (EGFR R108K) classified as Tier III-B, not Tier III-D.

---

## Evidence Processing

### Pre-Processing Statistics

**Location:** [evidence.py](src/tumorboard/models/evidence/evidence.py) - `format_evidence_summary_header()`

Before LLM evaluation:
1. Count sensitivity vs resistance entries by evidence level
2. Detect conflicts (same drug with both signals)
3. Determine dominant signal
4. Generate tier guidance header

### Drug-Level Aggregation

**Location:** [evidence.py](src/tumorboard/models/evidence/evidence.py) - `aggregate_evidence_by_drug()`

Multiple evidence entries per drug aggregated:
```
Before: 5 entries for Erlotinib (3 sens, 2 res across sources)
After:  Erlotinib: 3 sens (B:1, C:2), 2 res (C:2) → SENSITIVE [Level B]
```

### Low-Quality Minority Signal Filtering

**Location:** [evidence.py](src/tumorboard/models/evidence/evidence.py) - `filter_low_quality_minority_signals()`

If high-quality sensitivity (Level A/B) and only low-quality resistance (Level C/D, ≤2 entries):
- Drop the resistance entries
- Prevents case report noise from overriding established evidence

---

## Confidence Scoring

| Tier | Confidence Range |
|------|-----------------|
| I-A | 0.90-1.00 |
| I-B | 0.80-0.90 |
| II-A | 0.75-0.85 |
| II-B | 0.65-0.80 |
| II-C | 0.60-0.75 |
| II-D | 0.55-0.70 |
| III-A | 0.45-0.55 |
| III-B | 0.40-0.50 |
| III-C | 0.35-0.45 |
| III-D | 0.30-0.40 |
| IV | 0.90-1.00 |

---

## FDA Label Search Strategy

### Full-Text Search

**Location:** [fda.py](src/tumorboard/api/fda.py)

FDA labels often use generic language in `indications_and_usage` while specific variants appear in `clinical_studies`:

```python
# Strategy 1: Full-text search across all fields
search_query = f'{gene} AND {variant}'

# Strategy 2: Fall back to gene-only in indications
gene_search = f'indications_and_usage:{gene}'
```

**Impact:** Detects FDA approvals for uncommon EGFR mutations (G719X, S768I, L861Q) mentioned only in clinical studies section.

---

## CGI Biomarker Pattern Matching

### Position-Based Wildcards

**Location:** [cgi.py](src/tumorboard/api/cgi.py) - `_variant_matches()`

CGI uses position-based wildcard patterns:
- `KRAS:.12.,.13.` → any mutation at position 12 or 13
- `KRAS:.` → any KRAS mutation

Enables detection of KRAS G13D, G12D as resistance markers for cetuximab/panitumumab in CRC.

---

## LLM Integration

### System Prompt Design

**Location:** [prompts.py](src/tumorboard/llm/prompts.py)

The LLM receives:
1. Tier guidance computed by preprocessing
2. Evidence summary with statistics
3. Detailed evidence entries
4. Instructions to trust preprocessing unless evidence contradicts

```
YOUR ROLE:
1. Start with tier guidance as baseline
2. Review detailed evidence to verify
3. Check for conflicts or nuances
4. Assign final tier with justification

WHEN TO FOLLOW GUIDANCE:
✓ Evidence is consistent and unambiguous
✓ Preprocessing has validated FDA approval specificity

WHEN TO OVERRIDE GUIDANCE:
✗ Detailed evidence clearly contradicts
✗ Clinical context requires nuanced judgment
```

### Anti-Hallucination Safeguards

- Only cite FDA approvals explicitly in evidence
- Do NOT infer approval from sensitivity data alone
- If no FDA approval listed → Tier III, NOT Tier I
- Base decisions only on provided evidence, not training data

---

## Key Bug Fixes

### Later-Line Approval Classification

**Problem:** Later-line FDA approvals incorrectly downgraded to Tier II.

**Fix:** Later-line FDA approval is STILL Tier I if the biomarker IS the therapeutic indication:
- BRAF V600E in CRC → encorafenib+cetuximab (later-line but Tier I)
- PIK3CA in HR+ breast → alpelisib (after endocrine but Tier I)

### Compound Mutation Resistance Filtering

**Location:** [vicc.py](src/tumorboard/api/vicc.py) - `_is_compound_mutation_resistance()`

Filters resistance entries describing secondary/acquired mutations:
- "KIT D820A secondary mutation causes imatinib resistance in V560D patients"
- Should not penalize V560D itself (remains sensitive)

---

## Performance Metrics

| Architecture | Accuracy | Tier I Recall |
|--------------|----------|---------------|
| Prompt-only | ~52% | ~53% |
| Preprocessing-heavy | **80%+** | **~95%** |

---

## Guidelines Reference

Detailed tier classification rules are documented in:
- [guidelines/tier1.md](guidelines/tier1.md) - Tier I criteria
- [guidelines/tier2.md](guidelines/tier2.md) - Tier II criteria
- [guidelines/tier3.md](guidelines/tier3.md) - Tier III criteria
- [guidelines/tier4.md](guidelines/tier4.md) - Tier IV criteria
