# Development Guide

This guide is for developers who want to contribute to TumorBoard or extend its functionality.

## Setup Development Environment

1. Clone the repository:
```bash
git clone <repository-url>
cd tumor_board
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
├── api/              # External API clients
│   └── myvariant.py  # MyVariant.info client with retry logic
├── llm/              # LLM integration
│   ├── service.py    # LLM service using litellm
│   └── prompts.py    # System and assessment prompts
├── models/           # Pydantic data models
│   ├── variant.py    # Variant input/output models
│   ├── evidence.py   # Evidence from databases
│   ├── assessment.py # Assessment and tier models
│   └── validation.py # Validation metrics models
├── validation/       # Validation framework
│   └── validator.py  # Gold standard validation logic
├── engine.py         # Core assessment engine
└── cli.py            # CLI interface with Typer
```

### Data Flow

1. **User Input** → `VariantInput` model
2. **Evidence Gathering** → MyVariant API → `Evidence` model
3. **LLM Assessment** → LiteLLM → `ActionabilityAssessment` model
4. **Output** → JSON or formatted report

### Key Design Patterns

- **Async throughout**: All I/O operations are async for performance
- **Retry logic**: API calls use tenacity for automatic retries
- **Type safety**: Full type hints with Pydantic validation
- **Error handling**: Custom exceptions with meaningful messages
- **Separation of concerns**: Each module has a single responsibility

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
pytest tests/test_models.py -v
```

### Run tests matching a pattern
```bash
pytest -k "test_civic" -v
```

### Run async tests only
```bash
pytest tests/test_api.py tests/test_llm.py
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

### Adding a New Database Source

1. Create a new parser in `src/tumorboard/api/`:
```python
class NewDatabaseClient:
    async def fetch_data(self, gene: str, variant: str) -> dict:
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

4. Update `engine.py` to fetch from new source

5. Add tests in `tests/test_api.py`

### Modifying the LLM Prompt

1. Edit `src/tumorboard/llm/prompts.py`
2. Update `ACTIONABILITY_SYSTEM_PROMPT` or `ACTIONABILITY_ASSESSMENT_PROMPT`
3. Test with: `tumorboard assess BRAF V600E --tumor Melanoma`
4. Run validation to measure impact: `tumorboard validate benchmarks/gold_standard.json`

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
- Test individual models: `tests/test_models.py`
- Test API parsing: `tests/test_api.py`
- Test LLM service: `tests/test_llm.py`

### Integration Tests
- Test end-to-end flow: `tests/test_validation.py`
- Mock external APIs to avoid rate limits

### Fixtures
- Common test data in `tests/conftest.py`
- Use fixtures for reusable test objects

## Debugging

### Enable Verbose Logging
```bash
tumorboard assess BRAF V600E --tumor Melanoma --verbose
```

### Use Python Debugger
```python
# Add breakpoint in code
import pdb; pdb.set_trace()
```

### Test with Mock Data
```python
from unittest.mock import AsyncMock, patch

with patch.object(client, "fetch_evidence", new_callable=AsyncMock) as mock:
    mock.return_value = mock_evidence
    # Test code
```

## Performance Optimization

### Profiling
```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()
# Code to profile
profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

### Concurrency Tuning
- Adjust `max_concurrent` parameter in batch operations
- Monitor API rate limits
- Consider caching evidence data

## Adding to Gold Standard Dataset

1. Research the variant to determine correct tier
2. Find supporting references
3. Add entry to `benchmarks/gold_standard.json`:
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
4. Run validation: `tumorboard validate benchmarks/gold_standard.json`

## Release Process

1. Update version in `src/tumorboard/__init__.py`
2. Update version in `pyproject.toml`
3. Run full test suite: `pytest`
4. Run validation: `tumorboard validate benchmarks/gold_standard.json`
5. Update CHANGELOG.md
6. Create git tag: `git tag v0.2.0`
7. Push: `git push origin v0.2.0`

## Common Development Tasks

### Add a new test
```python
# In tests/test_*.py
import pytest

@pytest.mark.asyncio
async def test_my_feature(sample_fixture):
    """Test description."""
    # Arrange
    expected = "result"

    # Act
    result = await my_function()

    # Assert
    assert result == expected
```

### Update dependencies
```bash
# Edit pyproject.toml
# Then reinstall
pip install -e ".[dev]"
```

### Generate test coverage report
```bash
pytest --cov=tumorboard --cov-report=term-missing
```

## Best Practices

1. **Type everything**: Use type hints for all functions
2. **Document thoroughly**: Add docstrings to all public functions
3. **Test first**: Write tests before implementing features
4. **Keep it simple**: Avoid unnecessary complexity
5. **Async by default**: Use async/await for I/O operations
6. **Fail fast**: Validate inputs early with Pydantic
7. **Log appropriately**: Use logging for debugging, not print()
8. **Handle errors**: Use custom exceptions with clear messages

## Troubleshooting

### Tests failing with API errors
- Check API keys are set
- Check internet connection
- Consider mocking external APIs

### MyPy type errors
- Add type hints
- Use `# type: ignore` sparingly
- Check imports are correct

### Import errors
- Reinstall: `pip install -e .`
- Check Python path: `echo $PYTHONPATH`

## Resources

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Typer Documentation](https://typer.tiangolo.com/)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [MyVariant.info API](https://docs.myvariant.info/)
- [AMP/ASCO/CAP Guidelines](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5707196/)

## Getting Help

- Check existing issues on GitHub
- Read the test files for examples
- Ask questions in GitHub Discussions
- Review the code comments
