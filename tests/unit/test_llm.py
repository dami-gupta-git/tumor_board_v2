"""Tests for LLM service."""

import json
import pytest
from unittest.mock import AsyncMock, patch

from tumorboard.llm.service import LLMService
from tumorboard.models.assessment import ActionabilityTier


class TestLLMService:
    """Tests for LLMService."""

    @pytest.mark.asyncio
    async def test_assess_variant(self, sample_evidence, mock_llm_response):
        """Test variant assessment."""
        service = LLMService()

        # Mock the acompletion call
        with patch("tumorboard.llm.service.acompletion", new_callable=AsyncMock) as mock_call:
            # Create mock response object
            mock_response = AsyncMock()
            mock_response.choices = [AsyncMock()]
            mock_response.choices[0].message.content = mock_llm_response
            mock_call.return_value = mock_response

            assessment = await service.assess_variant(
                gene="BRAF",
                variant="V600E",
                tumor_type="Melanoma",
                evidence=sample_evidence,
            )

            assert assessment.tier == ActionabilityTier.TIER_I
            assert assessment.gene == "BRAF"
            assert assessment.variant == "V600E"
            assert assessment.confidence_score == 0.95

    @pytest.mark.asyncio
    async def test_assess_variant_with_markdown(self, sample_evidence):
        """Test assessment with markdown-wrapped JSON."""
        service = LLMService()

        response_json = {
            "tier": "Tier I",
            "confidence_score": 0.95,
            "summary": "Test summary",
            "rationale": "Test rationale",
            "recommended_therapies": [],
        }

        markdown_response = f"```json\n{json.dumps(response_json)}\n```"

        with patch("tumorboard.llm.service.acompletion", new_callable=AsyncMock) as mock_call:
            mock_response = AsyncMock()
            mock_response.choices = [AsyncMock()]
            mock_response.choices[0].message.content = markdown_response
            mock_call.return_value = mock_response

            assessment = await service.assess_variant(
                gene="BRAF",
                variant="V600E",
                tumor_type="Melanoma",
                evidence=sample_evidence,
            )

            assert assessment.tier == ActionabilityTier.TIER_I
            assert assessment.confidence_score == 0.95

    @pytest.mark.asyncio
    async def test_llm_service_with_custom_temperature(self, sample_evidence):
        """Test LLM service with custom temperature parameter."""
        custom_temp = 0.5
        service = LLMService(model="gpt-4o-mini", temperature=custom_temp)

        assert service.temperature == custom_temp
        assert service.model == "gpt-4o-mini"

        response_json = {
            "tier": "Tier I",
            "confidence_score": 0.95,
            "summary": "Test summary",
            "rationale": "Test rationale",
            "recommended_therapies": [],
        }

        with patch("tumorboard.llm.service.acompletion", new_callable=AsyncMock) as mock_call:
            mock_response = AsyncMock()
            mock_response.choices = [AsyncMock()]
            mock_response.choices[0].message.content = json.dumps(response_json)
            mock_call.return_value = mock_response

            await service.assess_variant(
                gene="BRAF",
                variant="V600E",
                tumor_type="Melanoma",
                evidence=sample_evidence,
            )

            # Verify temperature was passed to acompletion
            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args[1]
            assert call_kwargs["temperature"] == custom_temp
            assert call_kwargs["model"] == "gpt-4o-mini"
