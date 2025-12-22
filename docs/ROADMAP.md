# TumorBoard Roadmap

Detailed roadmap for upcoming TumorBoard features and enhancements.

## Enhanced Evidence Sources

### AlphaMissense Integration ✅ COMPLETED
Pathogenicity predictions for missense variants using Google DeepMind's AlphaMissense scores:
- Pre-computed pathogenicity scores (0-1) for all possible missense variants
- Classification into Pathogenic, Benign, or Ambiguous
- Integrated with existing evidence for more informed tiering
- Available via MyVariant.info dbNSFP annotations

### SpliceAI Annotations
Splice variant impact predictions to better assess variants affecting RNA splicing:
- Delta scores for acceptor/donor gain/loss
- Distance to splice site predictions
- Visualization of splicing impact

### Semantic Scholar Literature Search ✅ COMPLETED
Research literature search with built-in citation metrics and AI summaries (replaced PubMed):
- Resistance-focused literature search using Semantic Scholar API
- Built-in citation counts and influential citation counts
- TLDR (AI-generated concise summaries) included in search results
- Open access PDF detection and direct links
- Automatic resistance/sensitivity signal classification
- Drug mention extraction from abstracts and TLDR
- Impact score calculation for evidence prioritization
- Example: EGFR C797S correctly classified as Tier II resistance marker via Semantic Scholar evidence

### Exon-Level Literature Search
Enhance literature search to find papers about mutation classes, not just specific variants:
- When searching for V560D, also search for "KIT exon 11" papers
- Map variants to their exon/domain using variant_classes.yaml configuration
- Find foundational papers like Heinrich 2003 (PMID 14645423) that establish exon-class response patterns
- Currently missed: Papers discussing "exon 11 mutations" won't be found when searching for "V560D"
- Note: Semantic Scholar may not index older foundational papers (e.g., PMID 14645423 not found)

### LLM-Powered Literature Synthesis (Future)
Enhanced literature analysis with LLM-based evidence synthesis:
- Relevance ranking of retrieved abstracts
- Automated evidence extraction and summarization
- Citation tracking and reference generation
- Semantic search over indexed literature

### ESMFold Integration
Protein structure predictions and visualization:
- 3D structure predictions for variant proteins
- Visualization of variant location in protein structure
- Structural impact assessment

### Clinical Trials Matching ✅ COMPLETED
Integration with ClinicalTrials.gov API v2 for active trial identification:
- Real-time trial search based on variant and tumor type
- Variant-specific trial detection (explicit mention in eligibility or study arms)
- Gene-level trial search as fallback
- Phase filtering (Phase 1-4)
- Recruiting/active status filtering
- Geographic and sponsor information
- Tier II classification support for variants with active trials

### gnomAD Integration
Filter out population noise:
- Population allele frequency lookups
- Ancestry-specific frequencies
- Automatic flagging of common polymorphisms
- Integration with variant filtering pipeline

### TCGA Data
Real somatic mutation frequency and cancer-type prevalence:
- Mutation frequency across 11,000+ tumors
- Cancer-type-specific prevalence data
- Driver vs passenger mutation context
- Co-occurrence patterns with other mutations

## Patient-Level Genomic Analysis

Transform from single-variant lookups to full patient-level precision oncology workflows.

### VCF File Upload & Processing
Direct import of patient VCF (Variant Call Format) files:
- Standard VCF 4.x support
- Multi-sample VCF handling
- Variant normalization and deduplication
- Quality filtering (QUAL, DP, AF thresholds)

### Whole-Exome/Genome Support
Process entire patient genomic profiles:
- Efficient batch processing of thousands of variants
- Parallel evidence fetching
- Incremental result streaming
- Memory-efficient processing for large files

### Variant Prioritization Engine
Automatic ranking of variants by clinical actionability:
- Tier-based prioritization (Tier I > II > III > IV)
- Pathogenicity score integration
- Germline vs somatic classification
- Actionability scoring algorithm

### Patient Report Generation
Comprehensive clinical reports:
- Executive summary of actionable findings
- Detailed variant-by-variant analysis
- Therapy recommendations with evidence levels
- Clinical trial eligibility summary
- Germline findings (with appropriate consent)
- PDF/HTML export options

### Cohort Analysis
Compare variant profiles across multiple patients:
- Mutation landscape visualization
- Treatment response correlations
- Biomarker discovery
- Outcome tracking integration

## Implementation Timeline

Features are prioritized based on clinical impact and implementation complexity. Check the GitHub issues for current status and contributions welcome.
