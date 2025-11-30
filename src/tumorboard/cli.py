"""Command-line interface for TumorBoard.

ARCHITECTURE:
    CLI Commands → AssessmentEngine/Validator → JSON Output

Three workflows: assess (single), batch (concurrent), validate (benchmarking)

Key Design:
- Typer framework for auto-help and type validation
- asyncio.run() bridges sync CLI → async engine
- Flexible I/O: stdout or JSON file output
"""

import asyncio
import json
import warnings
from pathlib import Path
from typing import Optional
import typer
from dotenv import load_dotenv
from tumorboard.engine import AssessmentEngine
from tumorboard.models.variant import VariantInput
from tumorboard.validation.validator import Validator

# Suppress litellm's async cleanup warnings (harmless internal warnings)
warnings.filterwarnings("ignore", message=".*async_success_handler.*")
warnings.filterwarnings("ignore", message=".*coroutine.*was never awaited.*")

load_dotenv()

app = typer.Typer(
    name="tumorboard",
    help="LLM-powered cancer variant actionability assessment",
    add_completion=False,
)


@app.command()
def assess(
    gene: str = typer.Argument(..., help="Gene symbol (e.g., BRAF)"),
    variant: str = typer.Argument(..., help="Variant notation (e.g., V600E)"),
    tumor: Optional[str] = typer.Option(None, "--tumor", "-t", help="Tumor type"),
    model: str = typer.Option("gpt-4o-mini", "--model", "-m", help="LLM model"),
    temperature: float = typer.Option(0.1, "--temperature", help="LLM temperature (0.0-1.0)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
) -> None:
    """Assess clinical actionability of a single variant."""

    async def run_assessment() -> None:
        variant_input = VariantInput(gene=gene, variant=variant, tumor_type=tumor)

        if tumor:
            print(f"\nAssessing {gene} {variant} in {tumor}...")
        else:
            print(f"\nAssessing {gene} {variant}...")

        async with AssessmentEngine(llm_model=model, llm_temperature=temperature) as engine:
            assessment = await engine.assess_variant(variant_input)

            print(assessment.to_report())

            if output:
                output_data = assessment.model_dump(mode="json")
                with open(output, "w") as f:
                    json.dump(output_data, f, indent=2)
                print(f"Saved to {output}")

    asyncio.run(run_assessment())


@app.command()
def batch(
    input_file: Path = typer.Argument(..., help="Input JSON file with variants"),
    output: Path = typer.Option("results.json", "--output", "-o", help="Output file"),
    model: str = typer.Option("gpt-4o-mini", "--model", "-m", help="LLM model"),
    temperature: float = typer.Option(0.1, "--temperature", help="LLM temperature (0.0-1.0)"),
) -> None:
    """Batch process multiple variants."""

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        raise typer.Exit(1)

    async def run_batch() -> None:
        with open(input_file, "r") as f:
            data = json.load(f)

        variants = [VariantInput(**item) for item in data]
        print(f"\nLoaded {len(variants)} variants from {input_file}")

        async with AssessmentEngine(llm_model=model, llm_temperature=temperature) as engine:
            print(f"Assessing {len(variants)} variants...")
            assessments = await engine.batch_assess(variants)

            output_data = [assessment.model_dump(mode="json") for assessment in assessments]
            with open(output, "w") as f:
                json.dump(output_data, f, indent=2)

            print(f"\nSuccessfully assessed {len(assessments)}/{len(variants)} variants")
            print(f"Results saved to {output}")

            # Simple tier counts
            tier_counts = {}
            for assessment in assessments:
                tier = assessment.tier.value
                tier_counts[tier] = tier_counts.get(tier, 0) + 1

            print("\nTier Distribution:")
            for tier, count in sorted(tier_counts.items()):
                print(f"  {tier}: {count}")

    asyncio.run(run_batch())


@app.command()
def validate(
    gold_standard: Path = typer.Argument(..., help="Gold standard JSON file"),
    model: str = typer.Option("gpt-4o-mini", "--model", "-m", help="LLM model"),
    temperature: float = typer.Option(0.1, "--temperature", help="LLM temperature (0.0-1.0)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
    max_concurrent: int = typer.Option(3, "--max-concurrent", "-c", help="Max concurrent"),
) -> None:
    """Validate LLM assessments against gold standard."""

    if not gold_standard.exists():
        print(f"Error: Gold standard file not found: {gold_standard}")
        raise typer.Exit(1)

    async def run_validation() -> None:
        async with AssessmentEngine(llm_model=model, llm_temperature=temperature) as engine:
            validator = Validator(engine)

            entries = validator.load_gold_standard(gold_standard)
            print(f"\nLoaded {len(entries)} gold standard entries")

            print("Running validation...")
            metrics = await validator.validate_dataset(entries, max_concurrent=max_concurrent)

            print(metrics.to_report())

            if output:
                output_data = metrics.model_dump(mode="json")
                with open(output, "w") as f:
                    json.dump(output_data, f, indent=2)
                print(f"\nDetailed results saved to {output}")

    asyncio.run(run_validation())


@app.command()
def version() -> None:
    """Show version information."""
    from tumorboard import __version__
    print(f"TumorBoard version {__version__}")


if __name__ == "__main__":
    app()
