# Variant Annotations

TumorBoard automatically extracts comprehensive variant annotations from MyVariant.info, FDA drug approval data, Cancer Genome Interpreter (CGI) biomarkers, and VICC MetaKB.

## Database Identifiers

- **COSMIC ID**: Catalogue of Somatic Mutations in Cancer identifier (e.g., COSM476)
- **NCBI Gene ID**: Entrez Gene identifier (e.g., 673 for BRAF)
- **dbSNP ID**: Reference SNP identifier (e.g., rs113488022)
- **ClinVar ID**: ClinVar variation identifier (e.g., 13961)
- **ClinVar Clinical Significance**: Pathogenicity classification (e.g., Pathogenic, Benign)
- **ClinVar Accession**: ClinVar record accession (e.g., RCV000013961)

## HGVS Notations

- **Genomic**: Chromosome-level notation (e.g., chr7:g.140453136A>T)
- **Protein**: Amino acid change notation (when available)
- **Transcript**: cDNA-level notation (when available)

## Functional Annotations

- **SnpEff Effect**: Predicted variant effect (e.g., missense_variant, stop_gained)
- **PolyPhen2**: Pathogenicity prediction (D=Damaging, P=Possibly damaging, B=Benign)
- **CADD Score**: Combined Annotation Dependent Depletion score (higher = more deleterious)
- **gnomAD AF**: Population allele frequency from gnomAD exomes (helps assess rarity)
- **AlphaMissense Score**: Google DeepMind's pathogenicity score (0-1, higher = more pathogenic)
- **AlphaMissense Prediction**: Classification (P=Pathogenic, B=Benign, A=Ambiguous)

## Transcript Information

- **Transcript ID**: Reference transcript identifier (e.g., NM_004333.4)
- **Consequence**: Effect on transcript (e.g., missense_variant, frameshift_variant)

## FDA Drug Approvals

The FDA client searches the openFDA `/drug/label.json` endpoint using full-text search across all label fields:

- **Drug Names**: FDA-approved brand and generic drug names
- **Indications**: Specific cancer indications and biomarker requirements
- **Clinical Studies**: Trial data with specific variant mentions (e.g., G719X, S768I, L861Q)
- **Marketing Status**: Current prescription status

**Search Strategy**: The system searches `{gene} AND {variant}` across all label fields, which finds variant mentions in the `clinical_studies` section even when the `indications_and_usage` section uses generic language (e.g., "non-resistant EGFR mutations" instead of listing specific variants).

## CGI Biomarkers

Cancer Genome Interpreter (CGI) biomarkers provide curated variant-drug associations with explicit approval status:

- **Drug**: Drug name or combination
- **Drug Status**: Approval status (Approved, Clinical trial, etc.)
- **Evidence Level**: Source of evidence (FDA guidelines, NCCN guidelines, Late trials, etc.)
- **Association**: Drug response (Responsive, Resistant)
- **Tumor Type**: Cancer type for which the association is valid
- **FDA Approved**: Boolean indicating FDA/NCCN approval for Tier I classification

CGI biomarkers are particularly useful for variants where FDA labels use generic language (e.g., "uncommon EGFR mutations" rather than listing specific variants like G719S).

## VICC MetaKB

The VICC (Variant Interpretation for Cancer Consortium) Meta-Knowledgebase provides harmonized clinical interpretations from multiple cancer variant databases:

- **Source Databases**: CIViC, CGI, JAX-CKB, OncoKB, PMKB, MolecularMatch
- **Evidence Level**: A (validated), B (clinical), C (case study), D (preclinical)
- **Response Type**: Sensitivity/Responsive, Resistant, or OncoKB-style levels (1A, 1B, 2A, 2B, 3A, 3B, 4, R1, R2)
- **Disease**: Cancer type for the association
- **Drugs**: Associated therapeutic agents
- **Oncogenic**: Oncogenicity classification when available
- **Publication**: Supporting publication URLs

VICC MetaKB is particularly valuable for:
- Cross-referencing evidence across multiple knowledgebases
- Identifying consensus interpretations from different sources
- Finding sensitivity vs. resistance associations for drug-variant pairs
- Accessing OncoKB-style evidence levels (1A = FDA-approved, 2A = standard care, etc.)

## CIViC Assertions (AMP/ASCO/CAP Tier Classifications)

CIViC Assertions provide expert-curated clinical interpretations with official AMP/ASCO/CAP tier assignments:

- **AMP Level**: Official tier classification (TIER_I_LEVEL_A, TIER_I_LEVEL_B, TIER_II_LEVEL_C, TIER_II_LEVEL_D)
- **Assertion Type**: PREDICTIVE (therapy response), PROGNOSTIC, DIAGNOSTIC, ONCOGENIC
- **Significance**: SENSITIVITYRESPONSE, RESISTANCE, ONCOGENIC, etc.
- **Therapies**: Associated drugs with clinical significance
- **FDA Companion Test**: Boolean indicating FDA companion diagnostic status
- **NCCN Guideline**: Reference to specific NCCN guideline (e.g., "Non-Small Cell Lung Cancer")
- **Disease**: Cancer type for the assertion
- **Status**: ACCEPTED or SUBMITTED

CIViC Assertions are particularly valuable for:
- Authoritative AMP/ASCO/CAP tier assignments (equivalent to ESMO ESCAT)
- NCCN guideline references for regulatory context
- FDA companion diagnostic status
- Expert-curated clinical significance assessments
- Open source (no licensing required, unlike OncoKB)

## Where Annotations Appear

All annotations are included in:
- Console output (via the assessment report)
- JSON output files (when using `--output` flag)
- Batch processing results

**Note**: Annotation availability depends on database coverage. Not all variants have complete annotation in all databases.
