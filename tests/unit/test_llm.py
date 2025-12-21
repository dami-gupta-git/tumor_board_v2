"""Tests for LLM service."""

import json
import pytest
from unittest.mock import AsyncMock, patch

from tumorboard.llm.service import LLMService, extract_tier_from_hint
from tumorboard.models.assessment import ActionabilityTier


class TestExtractTierFromHint:
    """Tests for tier extraction from hint strings."""

    def test_tier_i_a(self):
        tier, sublevel = extract_tier_from_hint("TIER I-A INDICATOR: FDA-approved therapy")
        assert tier == "Tier I"
        assert sublevel == "A"

    def test_tier_ii_b(self):
        tier, sublevel = extract_tier_from_hint("TIER II-B INDICATOR: Well-powered studies")
        assert tier == "Tier II"
        assert sublevel == "B"

    def test_tier_iii_c(self):
        tier, sublevel = extract_tier_from_hint("TIER III-C INDICATOR: Case reports only")
        assert tier == "Tier III"
        assert sublevel == "C"

    def test_tier_iv(self):
        tier, sublevel = extract_tier_from_hint("TIER IV INDICATOR: Benign variant")
        assert tier == "Tier IV"
        assert sublevel == ""

    def test_no_match_defaults_to_tier_iii(self):
        tier, sublevel = extract_tier_from_hint("Unknown classification")
        assert tier == "Tier III"
        assert sublevel == ""


class TestLLMService:
    """Tests for LLMService."""

    @pytest.mark.asyncio
    async def test_assess_variant(self, sample_evidence, mock_llm_response):
        """Test variant assessment with deterministic tier."""
        service = LLMService()

        # Mock the acompletion call
        with patch("tumorboard.llm.service.acompletion", new_callable=AsyncMock) as mock_call:
            # Create mock response object - LLM returns single narrative field
            narrative_response = json.dumps({
                "narrative": "BRAF V600E is a well-characterized oncogenic mutation with FDA-approved targeted therapies including vemurafenib and dabrafenib."
            })
            mock_response = AsyncMock()
            mock_response.choices = [AsyncMock()]
            mock_response.choices[0].message.content = narrative_response
            mock_call.return_value = mock_response

            assessment = await service.assess_variant(
                gene="BRAF",
                variant="V600E",
                tumor_type="Melanoma",
                evidence=sample_evidence,
            )

            # Tier is now determined by get_tier_hint(), not LLM
            assert assessment.gene == "BRAF"
            assert assessment.variant == "V600E"
            # Confidence is determined by tier, not LLM response
            assert 0.0 <= assessment.confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_assess_variant_with_markdown(self, sample_evidence):
        """Test assessment with markdown-wrapped JSON."""
        service = LLMService()

        response_json = {
            "narrative": "Test narrative for the variant."
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

            # Tier determined by evidence, not LLM
            assert assessment.gene == "BRAF"
            assert assessment.summary == "Test narrative for the variant."

    @pytest.mark.asyncio
    async def test_llm_service_with_custom_temperature(self, sample_evidence):
        """Test LLM service with custom temperature parameter."""
        custom_temp = 0.5
        service = LLMService(model="gpt-4o-mini", temperature=custom_temp)

        assert service.temperature == custom_temp
        assert service.model == "gpt-4o-mini"

        response_json = {
            "narrative": "Test narrative for the variant."
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

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self, sample_evidence):
        """Test that LLM failure still returns valid assessment."""
        service = LLMService()

        with patch("tumorboard.llm.service.acompletion", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("LLM API error")

            assessment = await service.assess_variant(
                gene="BRAF",
                variant="V600E",
                tumor_type="Melanoma",
                evidence=sample_evidence,
            )

            # Should still get a valid assessment with tier from get_tier_hint
            assert assessment.gene == "BRAF"
            assert assessment.variant == "V600E"
            assert "LLM narrative generation failed" in assessment.rationale
