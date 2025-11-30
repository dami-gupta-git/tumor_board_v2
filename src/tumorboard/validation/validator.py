"""Validator for benchmarking LLM assessments against gold standard.

ARCHITECTURE:
    Gold Standard (JSON) → Validator → LLM Assessments → ValidationMetrics

Runs assessments against expert datasets and computes accuracy/precision/recall/F1.

Key Design:
- Semaphore for concurrency control
- Flexible input: list or dict-wrapped JSON
- Per-tier confusion matrix + overall statistics
"""

import json
import logging
from pathlib import Path
from typing import Any

from tumorboard.engine import AssessmentEngine
from tumorboard.models.validation import GoldStandardEntry, ValidationMetrics, ValidationResult
from tumorboard.models.variant import VariantInput

logger = logging.getLogger(__name__)


class Validator:
    """Validator for benchmarking assessments against gold standard dataset."""

    def __init__(self, engine: AssessmentEngine) -> None:
        """Initialize the validator.

        Args:
            engine: Assessment engine to use for validation
        """
        self.engine = engine

    def load_gold_standard(self, path: str | Path) -> list[GoldStandardEntry]:
        """Load gold standard dataset from JSON file.

        Args:
            path: Path to gold standard JSON file

        Returns:
            List of gold standard entries

        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If JSON is invalid
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Gold standard file not found: {path}")

        logger.info(f"Loading gold standard from {path}")

        try:
            with open(path, "r") as f:
                data = json.load(f)

            # Handle both list and dict with "entries" key
            if isinstance(data, dict) and "entries" in data:
                entries_data = data["entries"]
            elif isinstance(data, list):
                entries_data = data
            else:
                raise ValueError("Invalid gold standard format")

            entries = [GoldStandardEntry(**entry) for entry in entries_data]
            logger.info(f"Loaded {len(entries)} gold standard entries")

            return entries

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in gold standard file: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to load gold standard: {str(e)}")

    async def validate_single(self, entry: GoldStandardEntry) -> ValidationResult:
        """Validate a single gold standard entry.

        Args:
            entry: Gold standard entry to validate

        Returns:
            Validation result with comparison
        """
        # Create variant input
        variant_input = VariantInput(
            gene=entry.gene,
            variant=entry.variant,
            tumor_type=entry.tumor_type,
        )

        # Assess the variant
        assessment = await self.engine.assess_variant(variant_input)

        # Compare with expected
        is_correct = assessment.tier == entry.expected_tier

        return ValidationResult(
            gene=entry.gene,
            variant=entry.variant,
            tumor_type=entry.tumor_type,
            expected_tier=entry.expected_tier,
            predicted_tier=assessment.tier,
            is_correct=is_correct,
            confidence_score=assessment.confidence_score,
            assessment=assessment,
        )

    async def validate_dataset(
        self,
        gold_standard: list[GoldStandardEntry],
        max_concurrent: int = 3,
    ) -> ValidationMetrics:
        """Validate all entries in gold standard dataset.

        Args:
            gold_standard: List of gold standard entries
            max_concurrent: Maximum concurrent validations

        Returns:
            Overall validation metrics
        """
        import asyncio

        logger.info(f"Starting validation of {len(gold_standard)} entries")

        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)

        async def validate_with_semaphore(entry: GoldStandardEntry) -> ValidationResult:
            async with semaphore:
                return await self.validate_single(entry)

        # Execute all validations with concurrency limit
        tasks = [validate_with_semaphore(entry) for entry in gold_standard]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and collect valid results
        validation_results = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Validation failed for entry {idx}: {str(result)}")
            else:
                validation_results.append(result)

        # Calculate metrics
        metrics = ValidationMetrics()
        metrics.calculate(validation_results)

        logger.info(
            f"Validation complete: {metrics.correct_predictions}/{metrics.total_cases} "
            f"correct ({metrics.accuracy:.1%})"
        )

        return metrics

    async def validate_from_file(
        self,
        gold_standard_path: str | Path,
        max_concurrent: int = 3,
    ) -> ValidationMetrics:
        """Load gold standard from file and validate.

        Args:
            gold_standard_path: Path to gold standard JSON file
            max_concurrent: Maximum concurrent validations

        Returns:
            Overall validation metrics
        """
        gold_standard = self.load_gold_standard(gold_standard_path)
        return await self.validate_dataset(gold_standard, max_concurrent=max_concurrent)

    def save_results(
        self,
        metrics: ValidationMetrics,
        results: list[ValidationResult],
        output_path: str | Path,
    ) -> None:
        """Save validation results to JSON file.

        Args:
            metrics: Validation metrics
            results: List of validation results
            output_path: Path to save results
        """
        output_path = Path(output_path)

        output_data = {
            "metrics": metrics.model_dump(),
            "results": [result.model_dump() for result in results],
        }

        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"Saved validation results to {output_path}")
