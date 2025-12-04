# TumorBoard Features

Detailed feature documentation for TumorBoard v2.

## Core Capabilities

- **SNP/Small Indel Focus**: Specialized support for point mutations, small insertions, deletions, and frameshifts
- **Variant Type Validation**: Automatically validates and rejects unsupported variant types (fusions, amplifications, etc.)
- **Variant Normalization**: Automatically standardizes variant notations (Val600Glu → V600E, p.V600E → V600E) for better API matching
- **Evidence Aggregation**: Automatically fetches variant evidence from MyVariant.info API and FDA drug approval data
- **FDA Drug Approvals**: Fetches FDA-approved oncology drugs with companion diagnostics and biomarker-based indications
- **Database Identifiers**: Extracts COSMIC, dbSNP, ClinVar, NCBI Gene IDs, and HGVS notations
- **Functional Annotations**: SnpEff effects, PolyPhen2 predictions, CADD scores, gnomAD frequencies
- **LLM Assessment**: Uses LLMs to interpret evidence and assign actionability tiers
- **Evidence Prioritization**: Intelligent ranking of PREDICTIVE evidence with tumor-type-specific filtering
- **Validated Performance**: 73.33% overall accuracy on SNP/indel gold standard dataset
- **Validation Framework**: Built-in benchmarking against gold standard datasets with per-tier metrics
- **Multiple LLM Support**: Works with OpenAI, Anthropic, Google, Groq via litellm
- **Async Throughout**: Fast, concurrent processing for batch assessments
- **Rich CLI**: Command-line interface with progress indicators
- **Streamlit Interface**: Modern single-container web app with three-tab interface