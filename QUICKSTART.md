# TumorBoard Quick Start Guide

This guide will get you up and running with TumorBoard in 5 minutes.

## Choose Your Interface

TumorBoard is available as:
- **🐳 Docker**: One-command deployment (easiest!)
- **🌐 Web Application**: Modern Angular UI with Flask REST API
- **💻 Command-Line Interface**: Python CLI tool for batch processing

## 🐳 Docker Quick Start (Recommended for POC)

### Prerequisites
- Docker
- OpenAI API key

### 3-Command Setup

```bash
# 1. Set API key
echo "OPENAI_API_KEY=your-key-here" > .env

# 2. Start container
docker compose up

# 3. Open in browser (wait ~30s for build)
open http://localhost:4200
```

Done! See [DOCKER_SIMPLE.md](DOCKER_SIMPLE.md) for simple guide or [DOCKER.md](DOCKER.md) for advanced setup.

---

## Web Application Quick Start (Manual)

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- OpenAI API key

### 5-Minute Setup

1. **Setup Python environment**:
```bash
cd tumor_board_v0
python -m venv venv
source venv/bin/activate
pip install -e .
pip install -r backend/requirements.txt
```

2. **Configure API key**:
```bash
cp .env.example .env
# Edit .env and add: OPENAI_API_KEY=your-key-here
```

3. **Start both servers** (easiest method):
```bash
chmod +x start-dev.sh
./start-dev.sh
```

4. **Open in browser**: http://localhost:4200

That's it! See [README_WEBAPP.md](README_WEBAPP.md) for detailed web app documentation.

---

## CLI Quick Start

### Prerequisites

- Python 3.11 or higher
- An OpenAI API key (or Anthropic/other LLM provider)

## Installation

1. Clone and navigate to the directory:
```bash
cd tumor_board
```

2. Create a virtual environment with Python 3.11:
```bash
python3.11 -m venv venv
source venv/bin/activate
```

3. Install the package:
```bash
pip install -e ".[dev]"
```

4. Create a `.env` file in the project root with your API key:
```bash
echo "OPENAI_API_KEY=sk-..." > .env
```

The `.env` file is automatically loaded when you run `tumorboard` commands!

## Your First Assessment

Assess the BRAF V600E mutation in melanoma:

```bash
tumorboard assess BRAF V600E --tumor "Melanoma"
```

You should see output like:
```
================================================================================
VARIANT ACTIONABILITY ASSESSMENT REPORT
================================================================================

Variant: BRAF V600E
Tumor Type: Melanoma

Tier: Tier I
Confidence: 95.0%
Evidence Strength: Strong

--------------------------------------------------------------------------------
SUMMARY
--------------------------------------------------------------------------------
BRAF V600E is a well-established actionable mutation in melanoma...

--------------------------------------------------------------------------------
RECOMMENDED THERAPIES (2)
--------------------------------------------------------------------------------

1. Vemurafenib
   Evidence Level: FDA-approved
   Approval Status: Approved
   Clinical Context: First-line therapy

2. Dabrafenib + Trametinib
   Evidence Level: FDA-approved
   Approval Status: Approved
   Clinical Context: First-line therapy
...
```

## Batch Processing

1. Create a file `my_variants.json`:
```json
[
  {
    "gene": "BRAF",
    "variant": "V600E",
    "tumor_type": "Melanoma"
  },
  {
    "gene": "EGFR",
    "variant": "L858R",
    "tumor_type": "Lung Adenocarcinoma"
  },
  {
    "gene": "KRAS",
    "variant": "G12C",
    "tumor_type": "Non-Small Cell Lung Cancer"
  }
]
```

2. Run batch assessment:
```bash
tumorboard batch my_variants.json --output my_results.json
```

3. View results:
```bash
cat my_results.json
```

## Validate Against Gold Standard

Run validation to see how well the model performs:

```bash
tumorboard validate benchmarks/gold_standard.json
```

This will output metrics like:
```
================================================================================
VALIDATION REPORT
================================================================================

Total Cases: 15
Correct Predictions: 13
Overall Accuracy: 86.67%
Average Confidence: 87.50%

--------------------------------------------------------------------------------
PER-TIER METRICS
--------------------------------------------------------------------------------

Tier I:
  Precision: 90.00%
  Recall: 90.00%
  F1 Score: 90.00%
...
```

## Try Different Models

Use Claude instead of GPT:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
tumorboard assess BRAF V600E --tumor "Melanoma" --model claude-3-sonnet-20240229
```

Or GPT-4 for potentially better accuracy:

```bash
tumorboard assess BRAF V600E --tumor "Melanoma" --model gpt-4o
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore the [gold_standard.json](benchmarks/gold_standard.json) to understand the benchmark dataset
- Try the [sample_batch.json](benchmarks/sample_batch.json) for more examples
- Run the test suite: `pytest`
- Experiment with different prompts by modifying [src/tumorboard/llm/prompts.py](src/tumorboard/llm/prompts.py)

## Common Issues

**Issue**: `ModuleNotFoundError: No module named 'tumorboard'`
**Solution**: Make sure you installed with `pip install -e .` from the project root

**Issue**: `litellm.exceptions.AuthenticationError`
**Solution**: Check that your API key is set correctly: `echo $OPENAI_API_KEY`

**Issue**: `MyVariantAPIError`
**Solution**: This is usually a network issue or the variant isn't in the database. Check your internet connection.

## Getting Help

- Check the [README.md](README.md) for full documentation
- Look at test files in `tests/` for usage examples
- Open an issue on GitHub if you find bugs
