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

### LLM-Powered Literature Search
Automated PubMed searches with LLM-based evidence synthesis for real-time literature review:
- Query formulation based on variant context
- Relevance ranking of retrieved abstracts
- Automated evidence extraction and summarization
- Citation tracking and reference generation

### ESMFold Integration
Protein structure predictions and visualization:
- 3D structure predictions for variant proteins
- Visualization of variant location in protein structure
- Structural impact assessment

### Clinical Trials Matching
Integration with ClinicalTrials.gov API to identify relevant ongoing trials:
- Real-time trial search based on variant and tumor type
- Eligibility criteria matching
- Geographic filtering
- Phase and status filtering

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

## RAG (Retrieval-Augmented Generation)

Enhance evidence gathering with semantic search over domain-specific knowledge.

### Literature Retrieval
Vector-indexed PubMed abstracts for rare variants with limited database coverage:
- Embedding-based similarity search
- Temporal weighting for recent publications
- Citation network analysis
- Full-text retrieval for high-relevance papers

### Clinical Trial Matching
Semantic search over ClinicalTrials.gov to surface relevant ongoing trials:
- Natural language eligibility matching
- Biomarker-based trial identification
- Location-aware recommendations

### Guideline Integration
Retrieve relevant NCCN/ESMO guideline sections dynamically based on variant context:
- Automatic guideline section identification
- Version tracking and updates
- Conflict detection between guidelines

### Similar Variant Lookup
Find structurally similar variants with known actionability for novel mutations:
- Protein domain-aware similarity
- Functional impact prediction transfer
- Actionability inference from similar variants

### Proposed Stack
- **Vector Database**: ChromaDB (local) or Pinecone (cloud)
- **Embeddings**: sentence-transformers (BioBERT, PubMedBERT)
- **Integration Point**: Before LLM assessment, augmenting evidence summary

## Agentic AI Architecture

Two-phase multi-agent system mimicking real tumor board dynamics. 

Semantic embeddings and a knowledge graph that store and retrieve the full history of agent debates for improved 
reasoning and transparency

### Collaborative Phase
Specialized agents gather evidence in parallel into a shared pool:

| Agent | Role | Data Sources |
|-------|------|--------------|
| Literature Agent | PubMed search, abstract summarization | PubMed, PMC |
| Trials Agent | Clinical trial identification | ClinicalTrials.gov |
| Pathways Agent | Pathway analysis, drug targets | KEGG, Reactome |
| Guidelines Agent | Guideline retrieval | NCCN, ESMO, ASCO |
| Similar Variants Agent | Find analogous variants | CIViC, ClinVar |

### Adversarial Phase
Debate-based tiering for robust decisions:

1. **Advocate**: Argues for highest reasonable actionability tier
   - Highlights strong evidence
   - Identifies potential therapeutic options
   - Emphasizes clinical relevance

2. **Skeptic**: Challenges weak evidence and potential overclassification
   - Questions evidence quality
   - Identifies conflicting data
   - Highlights limitations and caveats

3. **Arbiter**: Synthesizes debate and assigns final tier
   - Weighs arguments from both sides
   - Applies AMP/ASCO/CAP guidelines strictly
   - Provides final tier with confidence and rationale

### Knowledge Graph Memory & Learning   
All reasoning is embedded and stored as evolving edges in a knowledge graph so future queries can ‘remember’ past debates and why decisions changed.
Over time, this supports a continuously refined, case‑based decision engine that can reuse successful reasoning patterns and highlight when new cases deviate from prior experience, while remaining subject to explicit validation and human oversight.

### Benefits
- Reduces LLM overconfidence through adversarial challenge
- Provides transparent reasoning traces
- Mimics real multidisciplinary tumor board dynamics
- Enables configurable meta-rules for when to dig deeper

### Configuration Options
- Toggle between fast single-LLM mode and full multi-agent mode
- Configurable debate depth (rounds of argument)
- Adjustable confidence thresholds for escalation
- Custom agent prompts for institutional preferences

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
