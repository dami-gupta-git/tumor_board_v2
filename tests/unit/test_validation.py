"""Tests for validation framework."""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from tumorboard.models.assessment import ActionabilityAssessment, ActionabilityTier
from tumorboard.models.validation import GoldStandardEntry
from tumorboard.validation.validator import Validator


class TestValidator:
    """Tests for Validator."""

    def test_load_gold_standard_list_format(self, tmp_path):
        """Test loading gold standard from list format."""
        from tumorboard.engine import AssessmentEngine

        gold_standard_data = [
            {
                "gene": "BRAF",
                "variant": "V600E",
                "tumor_type": "Melanoma",
                "expected_tier": "Tier I",
                "notes": "Test",
            }
        ]

        gold_standard_path = tmp_path / "gold_standard.json"
        with open(gold_standard_path, "w") as f:
            json.dump(gold_standard_data, f)

        engine = AssessmentEngine()
        validator = Validator(engine)

        entries = validator.load_gold_standard(gold_standard_path)

        assert len(entries) == 1
        assert entries[0].gene == "BRAF"
        assert entries[0].expected_tier == ActionabilityTier.TIER_I

    def test_load_gold_standard_dict_format(self, tmp_path):
        """Test loading gold standard from dict format."""
        from tumorboard.engine import AssessmentEngine

        gold_standard_data = {
            "entries": [
                {
                    "gene": "BRAF",
                    "variant": "V600E",
                    "tumor_type": "Melanoma",
                    "expected_tier": "Tier I",
                }
            ]
        }

        gold_standard_path = tmp_path / "gold_standard.json"
        with open(gold_standard_path, "w") as f:
            json.dump(gold_standard_data, f)

        engine = AssessmentEngine()
        validator = Validator(engine)

        entries = validator.load_gold_standard(gold_standard_path)

        assert len(entries) == 1
        assert entries[0].gene == "BRAF"

    def test_load_gold_standard_not_found(self):
        """Test loading non-existent gold standard file."""
        from tumorboard.engine import AssessmentEngine

        engine = AssessmentEngine()
        validator = Validator(engine)

        with pytest.raises(FileNotFoundError):
            validator.load_gold_standard("nonexistent.json")

    def test_load_gold_standard_invalid_json(self, tmp_path):
        """Test loading invalid JSON."""
        from tumorboard.engine import AssessmentEngine

        gold_standard_path = tmp_path / "invalid.json"
        with open(gold_standard_path, "w") as f:
            f.write("not valid json")

        engine = AssessmentEngine()
        validator = Validator(engine)

        with pytest.raises(ValueError):
            validator.load_gold_standard(gold_standard_path)

    @pytest.mark.asyncio
    async def test_validate_single_correct(self, sample_gold_standard_entry):
        """Test validating a single correct prediction."""
        from tumorboard.engine import AssessmentEngine

        engine = AssessmentEngine()
        validator = Validator(engine)

        # Mock the engine's assess_variant method
        mock_assessment = ActionabilityAssessment(
            gene="BRAF",
            variant="V600E",
            tumor_type="Melanoma",
            tier=ActionabilityTier.TIER_I,
            confidence_score=0.95,
            summary="Test",
            rationale="Test",
        )

        with patch.object(engine, "assess_variant", new_callable=AsyncMock) as mock_assess:
            mock_assess.return_value = mock_assessment

            result = await validator.validate_single(sample_gold_standard_entry)

            assert result.is_correct
            assert result.expected_tier == ActionabilityTier.TIER_I
            assert result.predicted_tier == ActionabilityTier.TIER_I
            assert result.tier_distance == 0

    @pytest.mark.asyncio
    async def test_validate_single_incorrect(self, sample_gold_standard_entry):
        """Test validating a single incorrect prediction."""
        from tumorboard.engine import AssessmentEngine

        engine = AssessmentEngine()
        validator = Validator(engine)

        # Mock incorrect prediction
        mock_assessment = ActionabilityAssessment(
            gene="BRAF",
            variant="V600E",
            tumor_type="Melanoma",
            tier=ActionabilityTier.TIER_II,  # Wrong tier
            confidence_score=0.7,
            summary="Test",
            rationale="Test",
        )

        with patch.object(engine, "assess_variant", new_callable=AsyncMock) as mock_assess:
            mock_assess.return_value = mock_assessment

            result = await validator.validate_single(sample_gold_standard_entry)

            assert not result.is_correct
            assert result.expected_tier == ActionabilityTier.TIER_I
            assert result.predicted_tier == ActionabilityTier.TIER_II
            assert result.tier_distance == 1

    @pytest.mark.asyncio
    async def test_validate_dataset(self):
        """Test validating a complete dataset."""
        from tumorboard.engine import AssessmentEngine

        engine = AssessmentEngine()
        validator = Validator(engine)

        gold_standard = [
            GoldStandardEntry(
                gene="BRAF",
                variant="V600E",
                tumor_type="Melanoma",
                expected_tier=ActionabilityTier.TIER_I,
            ),
            GoldStandardEntry(
                gene="KRAS",
                variant="G12C",
                tumor_type="Lung Cancer",
                expected_tier=ActionabilityTier.TIER_II,
            ),
        ]

        # Mock assessments - one correct, one incorrect
        mock_assessments = [
            ActionabilityAssessment(
                gene="BRAF",
                variant="V600E",
                tumor_type="Melanoma",
                tier=ActionabilityTier.TIER_I,  # Correct
                confidence_score=0.95,
                summary="Test",
                rationale="Test",
            ),
            ActionabilityAssessment(
                gene="KRAS",
                variant="G12C",
                tumor_type="Lung Cancer",
                tier=ActionabilityTier.TIER_III,  # Incorrect
                confidence_score=0.6,
                summary="Test",
                rationale="Test",
            ),
        ]

        with patch.object(engine, "assess_variant", new_callable=AsyncMock) as mock_assess:
            mock_assess.side_effect = mock_assessments

            metrics = await validator.validate_dataset(gold_standard, max_concurrent=2)

            assert metrics.total_cases == 2
            assert metrics.correct_predictions == 1
            assert metrics.accuracy == 0.5
            assert len(metrics.failure_analysis) == 1
