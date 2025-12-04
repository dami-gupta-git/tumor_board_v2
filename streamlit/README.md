# TumorBoard Streamlit Application

Clean, single-container Streamlit implementation of TumorBoard variant actionability assessment.

## Quick Start

1. **Set up environment variables:**
```bash
cd streamlit
cp .env.example .env
# Edit .env with your API keys
```

2. **Start the application:**
```bash
docker compose up --build
```

3. **Open in browser:**
```
http://localhost:8501
```

## Features

### 🔬 Single Variant Assessment
- Input gene, variant, and tumor type (The tumor type should exactly match values from the OncoTree ontology or CIViC database)
- Select LLM model (OpenAI, Anthropic, Google, Groq)
- Get comprehensive assessment with:
  - AMP/ASCO/CAP tier classification
  - Confidence score
  - Evidence strength
  - Recommended therapies
  - Database identifiers (COSMIC, ClinVar, dbSNP)
  - HGVS notations
  - Functional annotations

### 📊 Batch Upload
- Upload CSV with variant data
- Process multiple variants concurrently
- Download results as CSV or JSON
- Real-time progress tracking

### ✅ Validation
- Run against gold standard dataset
- Get accuracy metrics
- Per-tier precision/recall/F1 scores
- Failure analysis

## CSV Format for Batch Upload

```csv
gene,variant,tumor_type
BRAF,V600E,Melanoma
EGFR,L858R,Lung Adenocarcinoma
KRAS,G12D,Colorectal Cancer
```

- Required columns: `gene`, `variant`
- Optional column: `tumor_type`

## Development

To run locally without Docker:

```bash
# Install the tumorboard package
cd ..
pip install -e .

# Install streamlit dependencies
cd streamlit
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

## Environment Variables

- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `GOOGLE_API_KEY`: Google API key
- `GROQ_API_KEY`: Groq API key

## Volume Mounts

- `../benchmarks:/app/benchmarks`: Gold standard datasets for validation
- `../data:/app/data`: Additional data files

## Notes

- App runs on port 8501
- All scientific functionality from the original tumorboard package is preserved
- Backend uses async/await for efficient concurrent processing
- LiteLLM provides unified interface to multiple LLM providers