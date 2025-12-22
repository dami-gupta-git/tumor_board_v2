# Development Guide

This guide is for developers who want to contribute to TumorBoard or extend its functionality.

## Setup Development Environment

1. Clone the repository:
```bash
git clone <repository-url>
cd tumor_board_v2
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install in development mode with dev dependencies:
```bash
pip install -e ".[dev]"
```

4. Set up API keys for testing:
```bash
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"  # Optional
```

## Project Architecture

### Core Components

```
src/tumorboard/
├── api/                    # External API clients
│   ├── myvariant.py        # MyVariant.info client (CIViC, ClinVar, COSMIC)
│   ├── myvariant_models.py # API response models
│   ├── fda.py              # FDA openFDA API client
│   ├── cgi.py              # Cancer Genome Interpreter biomarkers
│   ├── vicc.py             # VICC MetaKB harmonized evidence
│   ├── civic.py            # CIViC GraphQL client (fallback)
│   ├── semantic_scholar.py # Literature search with TLDRs
│   ├── pubmed.py           # PubMed fallback
│   ├── clinicaltrials.py   # ClinicalTrials.gov client
│   └── oncokb.py           # OncoKB cancer gene list
├── llm/                    # LLM integration
│   ├── service.py          # LLM service (narrative + literature analysis)
│   └── prompts.py          # Narrative prompts (tier is deterministic)
├── models/                 # Pydantic data models
│   ├── variant.py          # Variant input/output models
│   ├── evidence.py         # Evidence + get_tier_hint() for deterministic tier
│   ├── assessment.py       # Assessment and tier models
│   ├── validation.py       # Validation metrics models
│   ├── annotations.py      # Shared annotation fields (HGVS, scores)
│   └── gene_context.py     # Oncogene classes, pathway-actionable TSGs
├── config/                 # Configuration files
│   └── variant_classes.yaml # Variant-class matching rules
├── validation/             # Validation framework
│   └── validator.py        # Gold standard validation logic
├── utils/                  # Utilities
│   ├── variant_normalization.py  # Variant format standardization
│   └── logging_config.py   # Logging setup
├── engine.py               # Core assessment engine
└── cli.py                  # CLI interface with Typer
```

### Data Flow

The system uses **deterministic tier classification** with LLM for narrative generation only:

```
1. User Input → VariantInput model
2. Evidence Gathering (parallel):
   → MyVariant API (CIViC, ClinVar, COSMIC)
   → FDA openFDA API
   → CGI Biomarkers
   → VICC MetaKB
   → Semantic Scholar / PubMed
   → ClinicalTrials.gov
3. Evidence Aggregation → Evidence model
4. Deterministic Tier → Evidence.get_tier_hint() (Python code, NOT LLM)
5. LLM Narrative → LiteLLM (explains the pre-computed tier)
6. Output → ActionabilityAssessment (tier + narrative)
```

### Key Design Patterns

- **Deterministic tiers**: `get_tier_hint()` computes tier in testable Python code
- **LLM for narrative only**: LLM writes clinical explanations, doesn't decide tiers
- **Async throughout**: All I/O operations are async for performance
- **Retry logic**: API calls use tenacity for automatic retries
- **Type safety**: Full type hints with Pydantic validation
- **Fallback chains**: CIViC GraphQL, ClinVar E-utilities when primary sources fail

## Key Files to Understand

### Tier Classification Logic

- **`models/evidence.py`** - `get_tier_hint()` method contains all tier decision logic
- **`models/gene_context.py`** - Oncogene mutation classes (BRAF I/II/III), pathway-actionable TSGs
- **`config/variant_classes.yaml`** - Variant-class matching rules (BRAF V600 specificity, EGFR exclusions)
- **`DECISIONS.md`** - Documents all tier classification decisions and rationale

### LLM Integration

- **`llm/service.py`** - Three main functions:
  - `assess_variant()` - Generates narrative for pre-computed tier
  - `score_paper_relevance()` - Scores papers for relevance (0-1)
  - `extract_variant_knowledge()` - Extracts structured knowledge from papers
- **`llm/prompts.py`** - Narrative-only prompts (LLM doesn't decide tier)

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=tumorboard --cov-report=html
open htmlcov/index.html
```

### Run specific test file
```bash
pytest tests/unit/test_evidence.py -v
```

### Run tests matching a pattern
```bash
pytest -k "test_tier" -v
```

### Run integration tests
```bash
pytest tests/integration/ -v
```

## Code Quality

### Linting with Ruff

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

### Type Checking with MyPy

```bash
mypy src/
```

### Pre-commit Checks

Before committing, run:
```bash
ruff format .
ruff check --fix .
mypy src/
pytest
```

## Adding New Features

### Adding a New Tier Rule

1. Identify where in the priority order the rule belongs (see `DECISIONS.md`)
2. Add the logic to `models/evidence.py` in `get_tier_hint()`
3. Add tests in `tests/unit/test_evidence.py`
4. Document the decision in `DECISIONS.md`
5. Run validation: `tumorboard validate benchmarks/gold_standard_snp.json`

Example:
```python
# In get_tier_hint()
def get_tier_hint(self, tumor_type: str | None = None) -> str:
    # ... existing checks ...

    # NEW RULE: Check for my new condition
    if self._check_my_new_condition(tumor_type):
        return "TIER II-B INDICATOR: My new condition explanation"

    # ... remaining checks ...
```

### Adding a New Database Source

1. Create a new client in `src/tumorboard/api/`:
```python
class NewDatabaseClient:
    async def fetch_data(self, gene: str, variant: str) -> list[NewEvidence]:
        # Implementation
        pass
```

2. Add a new evidence model in `src/tumorboard/models/evidence.py`:
```python
class NewDatabaseEvidence(BaseModel):
    field1: str
    field2: int
```

3. Update `Evidence` model to include new source:
```python
class Evidence(BaseModel):
    # ... existing fields
    new_database: list[NewDatabaseEvidence] = Field(default_factory=list)
```

4. Update `engine.py` to fetch from new source in parallel
5. Update `get_tier_hint()` if the new source affects tier decisions
6. Add tests in `tests/unit/test_api.py`

### Adding an Oncogene Mutation Class

Edit `src/tumorboard/models/gene_context.py`:

```python
ONCOGENE_MUTATION_CLASSES: dict[str, dict] = {
    # ... existing entries ...
    "NEW_GENE": {
        "class_i": {
            "name": "Class I",
            "variants": ["V600E", "V600K"],
            "mechanism": "Description of mechanism",
            "drugs": ["drug1", "drug2"],
            "fda_tumors": ["tumor1", "tumor2"],
            "note": "Clinical note for LLM",
        },
    },
}
```

### Adding a Pathway-Actionable TSG

Edit `src/tumorboard/models/gene_context.py`:

```python
PATHWAY_ACTIONABLE_TSGS: dict[str, dict] = {
    # ... existing entries ...
    "NEW_TSG": {
        "pathway": "Pathway Name",
        "mechanism": "LOF mechanism description",
        "drugs": ["drug1", "drug2"],
        "high_prevalence_tumors": ["tumor1", "tumor2"],
        "fda_context": "FDA approval context",
    },
}
```

### Modifying the LLM Prompt

Since tier is deterministic, prompt changes only affect narrative quality:

1. Edit `src/tumorboard/llm/prompts.py`
2. Update `NARRATIVE_SYSTEM_PROMPT` or `NARRATIVE_USER_PROMPT`
3. Test with: `tumorboard assess BRAF V600E --tumor Melanoma`
4. The tier won't change, but the narrative should improve

### Adding New CLI Commands

1. Add command in `src/tumorboard/cli.py`:
```python
@app.command()
def my_command(
    arg: str = typer.Argument(..., help="Description"),
) -> None:
    """Command description."""
    # Implementation
```

2. Test: `tumorboard my_command --help`

## Testing Strategy

### Unit Tests
- Test tier logic: `tests/unit/test_evidence.py`
- Test gene context: `tests/unit/test_gene_context.py`
- Test API parsing: `tests/unit/test_api.py`
- Test LLM service: `tests/unit/test_llm.py`

### Integration Tests
- Test end-to-end flow: `tests/integration/`
- Mock external APIs to avoid rate limits

### Fixtures
- Common test data in `tests/conftest.py`
- Use fixtures for reusable test objects

## Debugging

### Enable Verbose Logging
```bash
tumorboard assess BRAF V600E --tumor Melanoma --log
```

### Debug Tier Classification
Add prints in `get_tier_hint()` or use debugger:
```python
# In get_tier_hint()
print(f"DEBUG: Checking FDA approval for {tumor_type}")
print(f"DEBUG: CIViC evidence: {self.civic}")
```

### Test with Mock Data
```python
from unittest.mock import AsyncMock, patch

with patch.object(client, "fetch_evidence", new_callable=AsyncMock) as mock:
    mock.return_value = mock_evidence
    # Test code
```

## Adding to Gold Standard Dataset

1. Research the variant to determine correct tier (use AMP/ASCO/CAP 2017)
2. Find supporting references
3. Add entry to `benchmarks/gold_standard_snp.json`:
```json
{
  "gene": "GENE_NAME",
  "variant": "VARIANT",
  "tumor_type": "TUMOR_TYPE",
  "expected_tier": "Tier I",
  "notes": "Clinical rationale with evidence",
  "references": ["Reference 1", "Reference 2"]
}
```
4. Run validation: `tumorboard validate benchmarks/gold_standard_snp.json`

## Validation

Run validation to measure tier classification accuracy:

```bash
# Run against gold standard
tumorboard validate benchmarks/gold_standard_snp.json

# With specific model
tumorboard validate benchmarks/gold_standard_snp.json --model gpt-4o-mini
```

Current performance: **80%+ accuracy**, **~95% Tier I recall**

## Release Process

1. Update version in `src/tumorboard/__init__.py`
2. Update version in `pyproject.toml`
3. Run full test suite: `pytest`
4. Run validation: `tumorboard validate benchmarks/gold_standard_snp.json`
5. Update CHANGELOG.md
6. Create git tag: `git tag v0.2.0`
7. Push: `git push origin v0.2.0`

## Best Practices

1. **Deterministic first**: Put tier logic in `get_tier_hint()`, not LLM prompts
2. **Document decisions**: Update `DECISIONS.md` when adding tier rules
3. **Type everything**: Use type hints for all functions
4. **Test first**: Write tests before implementing features
5. **Async by default**: Use async/await for I/O operations
6. **Fail fast**: Validate inputs early with Pydantic

## Resources

- [DECISIONS.md](DECISIONS.md) - Tier classification decisions and rationale
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture documentation
- [FEATURES.md](FEATURES.md) - Feature documentation
- [AMP/ASCO/CAP 2017 Guidelines](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5707196/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [MyVariant.info API](https://docs.myvariant.info/)

## Getting Help

- Check existing issues on GitHub
- Read the test files for examples
- Review `DECISIONS.md` for tier logic rationale
- Review the code comments
