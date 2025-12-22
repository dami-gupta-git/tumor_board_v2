# TumorBoard Gold Standard Dataset

This directory contains a benchmark dataset for testing how well TumorBoard classifies cancer variants into AMP/ASCO/CAP tiers.

## Dataset

### `gold_standard_snps.json`

**Purpose**: Comprehensive SNP/indel validation dataset  
**Size**: 76 variants across 25 tumor types  
**Scope**: SNVs and small indels only (no fusions, amplifications, or structural variants)  
**Version**: 1.0  

**Tier Distribution**:
| Tier | Count | Description |
|------|-------|-------------|
| Tier I | 47 | FDA-approved therapies |
| Tier II | 19 | Resistance markers, off-label use, clinical trials |
| Tier III | 7 | Prognostic/diagnostic only |
| Tier IV | 3 | No clinical utility |

**Key Features**:
- Includes 2024 FDA approvals (KRAS G12C in CRC, vorasidenib for glioma)
- Multi-context variants (same variant assessed in different tumor types)
- Resistance markers with clinical utility (EGFR C797S, RAS mutations in CRC)
- Hematologic malignancies (FLT3, ABL1, IDH1/2)
- Rare tumor types (uveal melanoma, basal cell carcinoma)

## Validation Results

| Metric | Value |
|--------|-------|
| **Overall Accuracy** | 89.47% |
| **Average Confidence** | 81.12% |
| **Correct Predictions** | 68/76 |

### Per-Tier Metrics

| Tier | Precision | Recall | F1 Score | TP | FP | FN |
|------|-----------|--------|----------|----|----|-----|
| **Tier I** | 97.78% | 93.62% | 95.65% | 44 | 1 | 3 |
| **Tier II** | 79.17% | 100.00% | 88.37% | 19 | 5 | 0 |
| **Tier III** | 71.43% | 71.43% | 71.43% | 5 | 2 | 2 |
| **Tier IV** | 0.00% | 0.00% | 0.00% | 0 | 0 | 3 |

### Failure Analysis (8 errors)

1. **ERBB2 L755S in Breast Cancer**: Expected Tier III, Predicted Tier I (Distance: 2)
2. **KIT D816V in GIST**: Expected Tier I, Predicted Tier II (Distance: 1)
3. **SMO W535L in Basal Cell Carcinoma**: Expected Tier I, Predicted Tier II (Distance: 1)
4. **NRAS Q61R in Colorectal Cancer**: Expected Tier I, Predicted Tier II (Distance: 1)
5. **TP53 R175H in Breast Cancer**: Expected Tier IV, Predicted Tier II (Distance: 2)
6. **TP53 R248W in Colorectal Cancer**: Expected Tier IV, Predicted Tier III (Distance: 1)
7. **TP53 R273H in Ovarian Cancer**: Expected Tier IV, Predicted Tier III (Distance: 1)
8. **CTNNB1 S45F in HCC**: Expected Tier III, Predicted Tier II (Distance: 1)

### Key Observations

1. **High Tier I Performance**: 97.78% precision and 93.62% recall for Tier I variants.

2. **Resistance Marker Classification**: RAS mutations in CRC are classified as Tier II (resistance markers) rather than Tier I. The system emphasizes that these mutations exclude therapies rather than indicate approved therapies.

3. **TP53 Classification**: Tier IV variants are consistently over-tiered to Tier II/III due to active clinical trials enrolling TP53-mutant patients and prognostic significance detection.

4. **KIT D816V in GIST**: Classified as Tier II despite avapritinib approval. The system detects imatinib resistance but may not fully capture the D816V-specific approval context.

## Tumor Type Coverage

The dataset covers 25 tumor types:

- Acute Myeloid Leukemia
- Anaplastic Thyroid Cancer
- Basal Cell Carcinoma
- Bladder Cancer
- Breast Cancer
- Cholangiocarcinoma
- Chronic Myeloid Leukemia
- Colorectal Cancer
- Endometrial Cancer
- Gastrointestinal Stromal Tumor
- Glioma
- Head and Neck SCC
- Hepatocellular Carcinoma
- Lung Adenocarcinoma
- Lung Cancer
- Mastocytosis
- Medullary Thyroid Cancer
- Melanoma
- Non-Small Cell Lung Cancer
- Ovarian Cancer
- Pancreatic Cancer
- Systemic Mastocytosis
- Urothelial Carcinoma
- Uveal Melanoma

## Usage

### Running Validation

```bash
tumorboard validate benchmarks/gold_standard_snps.json
```

### Expected Output

```
================================================================================
VALIDATION REPORT
================================================================================

Total Cases: 76
Correct Predictions: 68
Overall Accuracy: 89.47%
Average Confidence: 81.12%

--------------------------------------------------------------------------------
PER-TIER METRICS
--------------------------------------------------------------------------------

Tier I:
  Precision: 97.78%
  Recall: 93.62%
  F1 Score: 95.65%
  TP: 44, FP: 1, FN: 3
...
```

## Dataset Curation Methodology
Tier assignments follow AMP/ASCO/CAP clinical guidelines, and have been checked against multiple sources.

**Scope**: SNVs and small indels only. Fusions, amplifications, and structural variants are excluded.

## License

This dataset is curated for academic and research purposes. Clinical decision-making should always involve expert review and not rely solely on computational predictions.

---

*Last Updated: 2024-12*
