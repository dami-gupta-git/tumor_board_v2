# Variant Annotations

TumorBoard automatically extracts comprehensive variant annotations from MyVariant.info and FDA drug approval data.

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

- **Drug Names**: FDA-approved brand and generic drug names
- **Indications**: Specific cancer indications and biomarker requirements
- **Approval Dates**: When drugs were approved by FDA
- **Marketing Status**: Current prescription status

## Where Annotations Appear

All annotations are included in:
- Console output (via the assessment report)
- JSON output files (when using `--output` flag)
- Batch processing results

**Note**: Annotation availability depends on database coverage. Not all variants have complete annotation in all databases.
