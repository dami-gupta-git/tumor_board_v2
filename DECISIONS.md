# TumorBoard Technical Decisions

This document tracks key technical decisions made in the codebase, their rationale, and known limitations.

---

## Evidence Processing

### 1. Pre-Processing: Evidence Statistics and Conflict Detection

**Location:** `src/tumorboard/models/evidence.py` - `compute_evidence_stats()` and `format_evidence_summary_header()`

**Current Approach:** Before sending evidence to the LLM, we pre-compute statistics and detect conflicts:

1. **Count sensitivity vs resistance entries** with breakdown by evidence level (A/B/C/D)
2. **Detect conflicts** - same drug appearing with both sensitivity AND resistance signals
3. **Determine dominant signal** - 'sensitivity_only', 'resistance_only', 'sensitivity_dominant' (>80%), 'resistance_dominant' (>80%), or 'mixed'
4. **Generate summary header** that appears BEFORE detailed evidence

**Example Output:**
```
============================================================
EVIDENCE SUMMARY (Pre-processed)
============================================================
Sensitivity entries: 7 (88%) - Levels: A:1, B:3, C:3
Resistance entries: 1 (12%) - Levels: C:1
INTERPRETATION: Sensitivity evidence strongly predominates (88%). Minor resistance signals likely context-specific.
FDA STATUS: Has FDA-approved therapy associated with this gene.

CONFLICTS DETECTED:
  - Erlotinib: SENSITIVITY in lung adenocarcinoma, NSCLC (2 entries) vs RESISTANCE in lung cancer (1 entries)
============================================================
```

**Rationale:**
- LLMs can be confused by minority evidence appearing early in the list
- Explicit stats help the LLM weight evidence appropriately
- Conflict detection surfaces drugs with context-dependent responses (e.g., sensitive in melanoma, resistant in CRC)

**Integration:** Called in `src/tumorboard/llm/service.py` before creating the assessment prompt.

---

### 1b. Mixed Sensitivity/Resistance Evidence Ordering (Legacy)

**Location:** `src/tumorboard/models/evidence.py` lines 460-490

**Current Approach:** Interleave sensitivity and resistance evidence 1:1 when presenting to the LLM.

```python
# Interleave sensitivity and resistance
vicc_prioritized = []
for i in range(max(len(sensitivity), len(resistance))):
    if i < len(sensitivity):
        vicc_prioritized.append(sensitivity[i])
    if i < len(resistance):
        vicc_prioritized.append(resistance[i])
```

**Problem:** When evidence is heavily skewed (e.g., 7 sensitivity vs 1 resistance), the single resistance entry appears early in the list and gets outsized attention from the LLM.

**Mitigation:** The new pre-processing summary header (Decision #1) explicitly shows the evidence distribution, so the LLM knows that sensitivity predominates even if it sees resistance early in the detailed list.

---

### 2. Compound/Secondary Mutation Resistance Filtering

**Location:** `src/tumorboard/api/vicc.py` - `_is_compound_mutation_resistance()` method

**Current Approach:** Filter out VICC resistance entries that describe secondary/acquired mutations developing after treatment.

```python
def _is_compound_mutation_resistance(self, assoc, variant):
    """Check if resistance is due to a compound/secondary mutation, not the queried variant."""
    secondary_indicators = [
        "secondary mutation",
        "acquired mutation",
        "harboring " + variant.lower() + " and ",
        "developed resistance",
        "resistance developed",
    ]
    # Filter if description contains these indicators
```

**Rationale:** Evidence like "KIT D820A secondary mutation causes imatinib resistance in patients with KIT V560D" should not penalize V560D itself - V560D remains sensitive.

**Applied To:** KIT V560D in GIST was being incorrectly classified as Tier II due to resistance entries about compound mutations.

---

### 3. Resistance Markers as Tier I vs Tier II

**Location:** `src/tumorboard/llm/prompts.py` lines 127-146

**Current Approach:** Prompt guidance states resistance markers are "typically Tier II" unless there's an FDA-approved alternative.

**Problem:** Pure resistance markers like KRAS G12V in CRC (6 resistance entries, 0 sensitivity) are being classified as Tier II/III instead of Tier I.

**Clinical Reality:** KRAS mutations in CRC ARE Tier I because:
- They change standard-of-care (don't use anti-EGFR)
- Guidelines mandate RAS testing before anti-EGFR therapy
- This is well-established, FDA-relevant actionability

**Current Prompt Text:**
```
TIER II RESISTANCE MARKERS (most common):
- Resistance to standard-of-care targeted therapy → changes treatment decision

TIER I RESISTANCE MARKERS (rare):
- Resistance marker AND FDA-approved alternative therapy specifically for that resistance
```

**Known Gap:** The prompt doesn't clearly state that "well-established resistance markers mandated by guidelines" should be Tier I even without an alternative therapy.

---

## Data Source Integration

### 4. VICC MetaKB Integration (Optional)

**Location:** `src/tumorboard/engine.py` - `enable_vicc` parameter

**Current Approach:** VICC is enabled by default but can be disabled via `--no-vicc` flag.

**Benchmark Results:**
| Metric | With VICC | Without VICC |
|--------|-----------|--------------|
| Accuracy | 61.5% | 58.1% |
| Errors | 45 | 49 |
| Tier II F1 | 44.4% | 37.3% |

**Rationale:** VICC improves accuracy by ~3.4%, particularly for Tier II classification. However, it also introduces some noise from conflicting evidence.

---

### 5. FDA Label Interpretation for Protein Expression Biomarkers

**Location:** `src/tumorboard/llm/prompts.py` lines 103-106

**Current Approach:** Prompt guidance for handling FDA labels that use protein expression rather than specific mutations.

```
INTERPRETING FDA LABELS WITH PROTEIN EXPRESSION BIOMARKERS:
- Some FDA labels use protein expression (e.g., "Kit (CD117) positive") rather than specific mutations.
- When CIViC/OncoKB shows Level A evidence that a specific mutation confers sensitivity to an FDA-approved drug,
  AND the FDA label covers that gene/protein in the same tumor type, treat this as Tier I.
- Example: KIT mutations in GIST with imatinib - FDA approves for "Kit (CD117) positive GIST"
  and CIViC shows Level A sensitivity for KIT exon 11 mutations → Tier I.
```

**Rationale:** FDA labels often use broader biomarker language than the specific variants we assess. This guidance helps the LLM make the connection.

---

## Evidence Prioritization

### 6. CIViC Evidence Ordering

**Location:** `src/tumorboard/models/evidence.py` lines 165-255

**Current Approach:** Priority order for CIViC evidence:
1. Tumor-specific SENSITIVITY evidence
2. Tumor-specific RESISTANCE evidence
3. Other PREDICTIVE with drugs and SENSITIVITY
4. Other RESISTANCE evidence
5. Remaining evidence

Each category sorted by evidence level (A > B > C > D > E).

**Rationale:** Tumor-specific predictive evidence is most actionable. Sensitivity comes before resistance within each category.

---

### 7. VICC Evidence Ordering

**Location:** `src/tumorboard/models/evidence.py` lines 312-358

**Current Approach:**
1. Sort by evidence level (A > B > C > D)
2. Within level, sort by OncoKB level (1A > 1B > 2A > ... > R2)
3. Interleave sensitivity and resistance entries

**Known Issue:** 1:1 interleaving gives equal visual weight to minority evidence type (see Decision #1).

---

## Prompt Engineering

### 8. Evidence-Based Decision Making

**Location:** `src/tumorboard/llm/prompts.py` line 167

**Current Approach:** Explicit instruction to avoid hallucination:

```
CRITICAL: Always base your decision on the evidence summary provided below.
Never hallucinate drug approvals, resistance mechanisms, or trial results
that are not mentioned in the evidence. If evidence is insufficient, favor
Tier III (VUS) or Tier IV (benign/likely benign) rather than over-calling Tier I/II.
```

**Rationale:** LLMs may "know" about drug approvals from training data that aren't in our evidence. We want decisions based solely on retrieved evidence.

---

### 9. Sensitivity vs Resistance Response Type Interpretation

**Location:** `src/tumorboard/llm/prompts.py` lines 109-114

**Current Approach:**
```
INTERPRETING CIViC/CGI/OncoKB EVIDENCE SIGNIFICANCE:
- SENSITIVITY / SENSITIVITYRESPONSE / oncogenic driver with responsive therapy:
  - Drug may be effective; can be recommended at the appropriate tier.
- RESISTANCE:
  - Drug is unlikely to work; should NOT be recommended in that context.
- When a drug appears with both SENSITIVITY and RESISTANCE:
  - Carefully check tumor type, line of therapy, and combination vs monotherapy to decide which signal applies.
```

**Known Gap:** The guidance for mixed evidence is vague. Doesn't tell LLM how to handle when one signal overwhelmingly dominates.

---

## Gold Standard Considerations

### 10. Resistance Marker Classification in Gold Standard

**Observation:** Some entries in `benchmarks/gold_standard_snp_big.json` mark resistance markers as Tier I (e.g., KRAS G12V in CRC).

**Rationale:** Well-established resistance markers that change standard-of-care treatment decisions ARE clinically actionable at the highest tier, even without a targeted alternative therapy.

**Affected Entries:**
- KRAS G12V, G13D, Q61H in Colorectal Cancer
- NRAS Q61R in Colorectal Cancer (though this one may be Tier III - less established)

---

## Performance Optimizations

### 11. Evidence Item Limits

**Location:**
- `src/tumorboard/llm/service.py` - `max_items=10` for evidence summary
- `src/tumorboard/engine.py` - `max_results=15` for VICC fetch

**Rationale:** Balance between providing sufficient context and avoiding prompt bloat. More evidence = more tokens = slower/more expensive LLM calls.

**Trade-off:** May miss relevant evidence if it falls outside the top N items.

---

### 12. Low-Quality Minority Signal Filtering

**Location:** `src/tumorboard/models/evidence.py` - `filter_low_quality_minority_signals()`

**Current Approach:** Filter out low-quality minority signals from VICC evidence before showing to LLM.

```python
def filter_low_quality_minority_signals(self) -> tuple[list[VICCEvidence], list[VICCEvidence]]:
    """Filter out low-quality minority signals from VICC evidence.

    If we have Level A/B sensitivity evidence and only Level C/D resistance,
    the resistance is likely noise from case reports and should be filtered.
    """
    # If high-quality sensitivity (A/B) and low-quality resistance (C/D only, <=2 entries):
    #   → Drop the resistance entries
    # If high-quality resistance (A/B) and low-quality sensitivity (C/D only, <=2 entries):
    #   → Drop the sensitivity entries
    # Otherwise keep both
```

**Rationale:**
- Level C/D evidence is case reports and preclinical data
- A single Level C resistance entry shouldn't override Level A sensitivity
- Threshold of ≤2 entries prevents filtering real signals that have multiple sources

**Safety Valve:** If there are 3+ low-quality minority entries, they're kept since multiple sources might indicate a real signal.

---

### 13. Drug-Level Evidence Aggregation

**Location:** `src/tumorboard/models/evidence.py` - `aggregate_evidence_by_drug()` and `format_drug_aggregation_summary()`

**Current Approach:** Aggregate multiple evidence entries per drug into a single summary line.

**Before (5 entries):**
```
1. Erlotinib [SENSITIVITY] Level B - NSCLC
2. Erlotinib [SENSITIVITY] Level C - NSCLC
3. Erlotinib [SENSITIVITY] Level C - lung adenocarcinoma
4. Erlotinib [RESISTANCE] Level C - lung cancer
5. Gefitinib [SENSITIVITY] Level A - NSCLC
```

**After (2 aggregated lines):**
```
DRUG-LEVEL SUMMARY:
1. Erlotinib: 3 sens (B:1, C:2), 1 res (C:1) → SENSITIVE [Level B]
2. Gefitinib: 1 sens (A:1), 0 res → SENSITIVE [Level A]
```

**Net Signal Rules:**
- Sensitivity only → `SENSITIVE`
- Resistance only → `RESISTANT`
- 3:1 ratio favoring sensitivity → `SENSITIVE`
- 3:1 ratio favoring resistance → `RESISTANT`
- Otherwise → `MIXED`

**Rationale:**
- Reduces cognitive load on LLM from parsing many repetitive entries
- Makes the overall signal clearer at a glance
- Best evidence level (A > B > C > D) shown for drug prioritization

**Integration:** Called in `src/tumorboard/llm/service.py` and included between the evidence header and detailed evidence.

---

---

### 14. FDA Label Search Strategy - Full-Text Search Across All Fields

**Location:** `src/tumorboard/api/fda.py` - `fetch_drug_approvals()` method

**Previous Approach:** Search only `indications_and_usage` field:
```python
search_query = f'indications_and_usage:({gene} AND {variant})'
```

**Problem:** FDA drug labels often use generic language in the indications section (e.g., "non-resistant EGFR mutations") while specific variants like G719X, S768I, L861Q only appear in the `clinical_studies` section.

**Example - Gilotrif (afatinib):**
- `indications_and_usage`: "...tumors have non-resistant EGFR mutations..."
- `clinical_studies`: "...efficacy of GILOTRIF in patients with NSCLC harboring non-resistant EGFR mutations (S768I, L861Q, and G719X)..."

**Current Approach:** Use full-text search across all label fields:
```python
# Strategy 1: Full-text search for gene + variant across all fields
search_query = f'{gene} AND {variant}'
result = await self._query_drugsfda(search_query, limit=15)

# Strategy 2: If no results, fall back to gene-only search in indications
gene_search = f'indications_and_usage:{gene}'
```

**Rationale:**
- The openFDA API supports unqualified full-text search that searches across ALL fields
- Query `EGFR AND G719X` finds Gilotrif because G719X appears in `clinical_studies`
- Simple and effective - no need to enumerate specific fields

**Impact:** This change enables detection of FDA approvals for:
- Uncommon EGFR mutations (G719X, S768I, L861Q) → Gilotrif (afatinib)
- Other variants mentioned only in clinical trial sections of FDA labels

**Validation:** The query `https://api.fda.gov/drug/label.json?search=EGFR+AND+G719X` now returns 7 results including Gilotrif and Gefitinib/IRESSA.

---

### 15. CGI Biomarker Pattern Matching for Position-Based Wildcards

**Location:** `src/tumorboard/api/cgi.py` - `_variant_matches()` method

**Previous Approach:** Only handled end-of-pattern wildcards like `G719.`

**Problem:** CGI database uses position-based wildcard patterns for variant groups:
- `KRAS:.12.,.13.` - any mutation at position 12 or 13 (matches G12D, G13D, etc.)
- `KRAS:.` - any KRAS mutation
- `KRAS:.12.,.13.,.59.,.61.,.117.,.146.` - multiple position wildcards

**Current Approach:** Extended pattern matching to handle:

```python
# Position-based wildcard: ".13." matches any mutation at position 13
if part.startswith(".") and part.endswith(".") and len(part) > 2:
    position_str = part[1:-1]  # Extract "13" from ".13."
    if position_str.isdigit():
        # Match variants like G13D where position == 13
        variant_match = re.match(r'^([A-Z])(\d+)([A-Z])$', variant_upper)
        if variant_match and variant_match.group(2) == position_str:
            return True

# Wildcard for any mutation in gene: "." alone matches any variant
if part == ".":
    return True
```

**Impact:** Enables detection of:
- KRAS G13D, G12D as resistance markers for cetuximab/panitumumab in CRC
- Any position-based variant groupings in CGI biomarkers database

**Related Fix:** Added `coread` to `TUMOR_TYPE_MAPPINGS` in `constants.py` since CGI uses "COREAD" for colorectal cancer.

---

### 16. FDA-Approved Resistance Marker Emphasis in Evidence Summary

**Location:** `src/tumorboard/models/evidence.py` - `format_evidence_summary_header()` and `summary_compact()`

**Problem:** Resistance markers that exclude FDA-approved therapies were being presented the same as sensitivity markers, causing the LLM to underweight their clinical significance.

**Current Approach:**
1. Pre-compute FDA-approved resistance biomarkers from CGI
2. Add explicit guidance in evidence header:
```
FDA STATUS: This is an FDA-MANDATED RESISTANCE BIOMARKER - variant EXCLUDES use of: Cetuximab, Panitumumab
ACTIONABILITY: This is Tier II (or potentially Tier I) because it changes treatment decisions (do NOT use these drugs).
```
3. Separate resistance and sensitivity biomarkers in detailed evidence with clear headers

**Impact:** KRAS G13D in CRC now correctly classified as Tier II (resistance marker changing treatment decisions) instead of Tier III.

---

### 17. CIViC Assertions Integration (AMP/ASCO/CAP Tier Classifications)

**Location:** `src/tumorboard/api/civic.py` - New CIViC GraphQL client

**Purpose:** CIViC Assertions provide curated AMP/ASCO/CAP tier classifications with:
- Expert-curated tier assignments (Tier I/II/III/IV, Level A/B/C/D)
- FDA companion diagnostic status
- NCCN guideline references
- Assertion types: PREDICTIVE, PROGNOSTIC, DIAGNOSTIC, ONCOGENIC

**Why CIViC Assertions (not OncoKB):**
- OncoKB requires commercial licensing
- CIViC is open source and free for all use
- CIViC Assertions align with AMP/ASCO/CAP guidelines (similar to ESCAT)
- Provides NCCN guideline references that ESMO ESCAT would provide

**GraphQL Query:**
```graphql
query GetAssertions($molecularProfileName: String, $first: Int) {
    assertions(molecularProfileName: $molecularProfileName, first: $first) {
        nodes {
            id name ampLevel assertionType significance
            therapies { name }
            disease { name }
            molecularProfile { name }
            fdaCompanionTest
            nccnGuideline { name }
        }
    }
}
```

**AMP Level Mapping:**
- `TIER_I_LEVEL_A` → Tier I, Level A (FDA-approved, guideline-backed)
- `TIER_I_LEVEL_B` → Tier I, Level B (strong consensus)
- `TIER_II_LEVEL_C` → Tier II, Level C (clinical trials)
- `TIER_II_LEVEL_D` → Tier II, Level D (case studies)

**Integration:**
- Fetched in parallel with MyVariant, FDA, CGI, and VICC
- Added to Evidence model as `civic_assertions` field
- Displayed in evidence summary with TIER I/II breakdown
- NCCN guideline references shown in output

**Impact:** Provides authoritative tier classifications similar to ESMO ESCAT but using open-source data. Example for EGFR L858R:
```
CIViC AMP/ASCO/CAP TIER I ASSERTIONS (3):
  *** EXPERT-CURATED - STRONG CLINICAL SIGNIFICANCE ***
  • EGFR L858R: Erlotinib [SENSITIVITYRESPONSE] [FDA Companion Test] [NCCN: Non-Small Cell Lung Cancer]
      AMP Level: TIER_I_LEVEL_A, Disease: Lung Non-small Cell Carcinoma
```

---

## Open Issues

1. ~~**Mixed evidence weighting**~~ - ADDRESSED: Pre-processing now computes stats and dominant signal (Decision #1)
2. ~~**Pure resistance markers**~~ - ADDRESSED: Enhanced evidence summary emphasis for FDA-approved resistance markers (Decision #16)
3. ~~**Clinical trial integration**~~ - ADDRESSED: FDA search now includes clinical_studies section (Decision #14)
4. ~~**ESMO/ESCAT integration**~~ - ADDRESSED: CIViC Assertions provide equivalent AMP/ASCO/CAP tier classifications (Decision #17)
5. **Tier IV detection** - Currently 0% accuracy on benign/VUS variants
