"""Validation and benchmarking models.

CONCEPTUAL OVERVIEW:
===================

This module implements a clinical validation framework for assessing LLM accuracy
in cancer variant actionability assessment. The design follows these key principles:

1. GOLD STANDARD APPROACH
   - Medical AI systems must be validated against expert-curated ground truth
   - Each gold standard entry represents a clinically verified variant-tumor pair
   - References link back to clinical guidelines (e.g., NCCN, FDA labels)

2. MULTI-LEVEL EVALUATION
   - Binary correctness: Did we get the exact tier right?
   - Tier distance: How far off were we? (Tier I vs II is better than I vs IV)
   - Confidence calibration: Are high-confidence predictions more accurate?
   - Per-tier metrics: Which tiers are hardest to classify?

3. CONFUSION MATRIX TRACKING
   - Track True Positives, False Positives, False Negatives per tier
   - Calculate precision (how many predicted Tier I are actually Tier I?)
   - Calculate recall (how many actual Tier I did we correctly identify?)
   - F1 score balances precision and recall

4. FAILURE ANALYSIS
   - Systematic tracking of errors helps identify systematic biases
   - Understanding where the LLM fails guides prompt engineering
   - Distance metric helps distinguish "close misses" from major errors

This validation framework is essential for clinical deployment - we can't use
AI for cancer treatment decisions without rigorous validation.
"""

from pydantic import BaseModel, Field

from tumorboard.models.assessment import ActionabilityAssessment, ActionabilityTier


class GoldStandardEntry(BaseModel):
    """Gold standard entry for validation.

    Represents expert-curated ground truth for a specific variant-tumor combination.
    These entries typically come from clinical guidelines, FDA labels, or consensus
    expert panels. The quality of validation depends entirely on the quality of
    these gold standard entries.
    """

    gene: str
    variant: str
    tumor_type: str
    expected_tier: ActionabilityTier  # The "correct answer" from clinical experts
    notes: str | None = None  # Context about why this tier was chosen
    references: list[str] = Field(default_factory=list)  # NCCN, FDA labels, etc.


class ValidationResult(BaseModel):
    """Result of validating a single assessment against gold standard.

    Captures the outcome of comparing an LLM prediction to expert ground truth.
    This granular result enables both aggregate statistics and individual error analysis.
    """

    gene: str
    variant: str
    tumor_type: str
    expected_tier: ActionabilityTier  # What experts say it should be
    predicted_tier: ActionabilityTier  # What the LLM predicted
    is_correct: bool  # Binary: exact match or not
    confidence_score: float  # LLM's confidence in its prediction (0-1)
    assessment: ActionabilityAssessment  # Full LLM output for error analysis

    @property
    def tier_distance(self) -> int:
        """Calculate distance between predicted and expected tier (0-3).

        CONCEPT: Not all errors are equal in clinical impact.

        - Distance 0: Perfect prediction
        - Distance 1: Adjacent tier (e.g., Tier I vs II) - clinically similar
        - Distance 2-3: Major misclassification - could impact treatment decisions

        For example, confusing Tier I (FDA-approved) with Tier IV (no evidence)
        would be a distance of 3 - a critical error that could lead to inappropriate
        therapy selection or missed treatment opportunities.
        """
        tier_order = {
            ActionabilityTier.TIER_I: 0,
            ActionabilityTier.TIER_II: 1,
            ActionabilityTier.TIER_III: 2,
            ActionabilityTier.TIER_IV: 3,
            ActionabilityTier.UNKNOWN: -1,
        }
        expected_idx = tier_order.get(self.expected_tier, -1)
        predicted_idx = tier_order.get(self.predicted_tier, -1)

        if expected_idx == -1 or predicted_idx == -1:
            return 999  # Unknown tier - flag as invalid
        return abs(expected_idx - predicted_idx)


class TierMetrics(BaseModel):
    """Metrics for a specific tier.

    CONCEPT: Per-tier metrics reveal systematic biases in the model.

    Examples of what these metrics can reveal:
    - Low Tier I recall: Model is too conservative, missing actionable variants
    - Low Tier IV precision: Model is over-calling significance
    - High Tier II/III confusion: Model struggles with borderline cases

    These insights drive iterative improvement of prompts and evidence retrieval.
    """

    tier: ActionabilityTier
    true_positives: int = 0   # Correctly predicted this tier
    false_positives: int = 0  # Incorrectly predicted this tier
    false_negatives: int = 0  # Missed cases that should be this tier
    precision: float = 0.0    # Of all predictions for this tier, how many were right?
    recall: float = 0.0       # Of all actual cases in this tier, how many did we find?
    f1_score: float = 0.0     # Harmonic mean balancing precision and recall

    def calculate(self) -> None:
        """Calculate precision, recall, and F1 score.

        PRECISION: "When we predict Tier I, how often are we correct?"
        - Critical for avoiding false hope about treatment options
        - High precision = trustworthy positive predictions

        RECALL: "Of all actual Tier I variants, how many do we identify?"
        - Critical for not missing actionable treatment opportunities
        - High recall = comprehensive detection

        F1 SCORE: Harmonic mean of precision and recall
        - Balances both metrics (better than arithmetic mean for this use case)
        - Used when you care equally about false positives and false negatives
        """
        if self.true_positives + self.false_positives > 0:
            self.precision = self.true_positives / (self.true_positives + self.false_positives)
        else:
            self.precision = 0.0

        if self.true_positives + self.false_negatives > 0:
            self.recall = self.true_positives / (self.true_positives + self.false_negatives)
        else:
            self.recall = 0.0

        if self.precision + self.recall > 0:
            self.f1_score = 2 * (self.precision * self.recall) / (self.precision + self.recall)
        else:
            self.f1_score = 0.0


class ValidationMetrics(BaseModel):
    """Overall validation metrics.

    CONCEPT: Aggregates individual validation results into actionable insights.

    This class builds a complete picture of model performance:
    1. Overall accuracy: Simple benchmark for comparison
    2. Confidence calibration: Are confident predictions more accurate?
    3. Per-tier performance: Where does the model excel or struggle?
    4. Failure patterns: Systematic errors to address

    The validation process mirrors clinical validation of diagnostic tests,
    where we need to understand both overall accuracy and error patterns
    before deploying in practice.
    """

    total_cases: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.0  # Overall accuracy across all tiers
    average_confidence: float = 0.0  # Used to assess calibration
    tier_metrics: dict[str, TierMetrics] = Field(default_factory=dict)
    failure_analysis: list[dict[str, str]] = Field(default_factory=list)

    def add_result(self, result: ValidationResult) -> None:
        """Add a validation result and update metrics.

        This method incrementally builds the confusion matrix for multi-class
        classification. Each result updates:
        - Overall counts (total, correct)
        - Per-tier TP/FP/FN counts
        - Failure tracking for error analysis
        """
        self.total_cases += 1

        if result.is_correct:
            self.correct_predictions += 1

        # Update tier-specific metrics
        expected_key = result.expected_tier.value
        predicted_key = result.predicted_tier.value

        # Initialize tier metrics if needed
        for tier in [result.expected_tier, result.predicted_tier]:
            if tier.value not in self.tier_metrics:
                self.tier_metrics[tier.value] = TierMetrics(tier=tier)

        # Update confusion matrix counts
        # CONCEPT: Multi-class confusion matrix tracking
        # - If correct: increment TP for that tier
        # - If wrong: increment FN for expected tier, FP for predicted tier
        if result.is_correct:
            self.tier_metrics[expected_key].true_positives += 1
        else:
            self.tier_metrics[expected_key].false_negatives += 1
            self.tier_metrics[predicted_key].false_positives += 1

            # Add to failure analysis for later review
            self.failure_analysis.append(
                {
                    "variant": f"{result.gene} {result.variant}",
                    "tumor_type": result.tumor_type,
                    "expected": result.expected_tier.value,
                    "predicted": result.predicted_tier.value,
                    "tier_distance": str(result.tier_distance),
                    "confidence": f"{result.confidence_score:.2%}",
                    "summary": result.assessment.summary[:200] + "..."
                    if len(result.assessment.summary) > 200
                    else result.assessment.summary,
                }
            )

    def calculate(self, results: list[ValidationResult]) -> None:
        """Calculate overall metrics from results."""
        if not results:
            return

        # Add all results
        for result in results:
            self.add_result(result)

        # Calculate overall metrics
        if self.total_cases > 0:
            self.accuracy = self.correct_predictions / self.total_cases

        total_confidence = sum(r.confidence_score for r in results)
        self.average_confidence = total_confidence / len(results) if results else 0.0

        # Calculate per-tier metrics
        for metrics in self.tier_metrics.values():
            metrics.calculate()

    def to_report(self) -> str:
        """Generate a formatted validation report.

        CONCEPT: Human-readable validation summary for stakeholders.

        This report format is designed for clinical review meetings where
        oncologists and bioinformaticians assess whether the system is
        ready for clinical use. It highlights:
        - Overall performance metrics
        - Per-tier strengths and weaknesses
        - Specific failure cases for expert review

        The format mimics clinical trial reporting conventions.
        """
        lines = [
            "=" * 80,
            "VALIDATION REPORT",
            "=" * 80,
            f"\nTotal Cases: {self.total_cases}",
            f"Correct Predictions: {self.correct_predictions}",
            f"Overall Accuracy: {self.accuracy:.2%}",
            f"Average Confidence: {self.average_confidence:.2%}",
            f"\n{'-' * 80}",
            "PER-TIER METRICS",
            f"{'-' * 80}",
        ]

        # Sort tiers in order
        tier_order = [
            ActionabilityTier.TIER_I,
            ActionabilityTier.TIER_II,
            ActionabilityTier.TIER_III,
            ActionabilityTier.TIER_IV,
        ]

        for tier in tier_order:
            if tier.value in self.tier_metrics:
                metrics = self.tier_metrics[tier.value]
                lines.append(f"\n{tier.value}:")
                lines.append(f"  Precision: {metrics.precision:.2%}")
                lines.append(f"  Recall: {metrics.recall:.2%}")
                lines.append(f"  F1 Score: {metrics.f1_score:.2%}")
                lines.append(
                    f"  TP: {metrics.true_positives}, "
                    f"FP: {metrics.false_positives}, "
                    f"FN: {metrics.false_negatives}"
                )

        if self.failure_analysis:
            lines.append(f"\n{'-' * 80}")
            lines.append(f"FAILURE ANALYSIS ({len(self.failure_analysis)} errors)")
            lines.append(f"{'-' * 80}")
            for idx, failure in enumerate(self.failure_analysis[:10], 1):  # Show top 10
                lines.append(f"\n{idx}. {failure['variant']} in {failure['tumor_type']}")
                lines.append(
                    f"   Expected: {failure['expected']} | "
                    f"Predicted: {failure['predicted']} | "
                    f"Distance: {failure['tier_distance']}"
                )
                lines.append(f"   Confidence: {failure['confidence']}")
                lines.append(f"   Summary: {failure['summary']}")

            if len(self.failure_analysis) > 10:
                lines.append(f"\n... and {len(self.failure_analysis) - 10} more errors")

        lines.append(f"\n{'=' * 80}")
        return "\n".join(lines)
