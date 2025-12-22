# Contributing to TumorBoard

## Quick Start

```bash
# Install for development
pip install -e ".[dev]"

# Run tests
pytest --cov=tumorboard

# Code quality
ruff format . && ruff check . && mypy src/
```

## Workflow

1. Fork repo → Create feature branch
2. Make changes → Add tests
3. Run: `ruff format . && ruff check . && mypy src/ && pytest`
4. Commit → Push → Submit PR

## Adding Gold Standard Entries

Edit `benchmarks/gold_standard.json`:

```json
{
  "gene": "GENE",
  "variant": "VARIANT",
  "tumor_type": "TUMOR_TYPE",
  "expected_tier": "Tier I|II|III|IV",
  "notes": "Clinical rationale",
  "references": ["PMID:12345"]
}
```

Use well-documented variants with clear evidence and references.

## Guidelines

- Write tests for new features (>80% coverage)
- Use type hints and docstrings
- Keep PRs focused on single changes
- Update docs as needed

Questions? Open an issue.

