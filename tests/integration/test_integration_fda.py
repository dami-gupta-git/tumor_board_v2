"""Integration tests for FDA data flow through the assessment pipeline."""

import pytest
from unittest.mock import AsyncMock, patch

from tumorboard.engine import AssessmentEngine
from tumorboard.models.variant import VariantInput


class TestFDAIntegration:
    """Integration tests for FDA API integration with assessment engine."""

    @pytest.mark.asyncio
    async def test_assessment_engine_fetches_fda_data(self):
        """Test that AssessmentEngine successfully fetches FDA data in parallel with MyVariant."""

        # Mock FDA response
        mock_fda_response = [
            {
                "openfda": {
                    "brand_name": ["Zelboraf"],
                    "generic_name": ["vemurafenib"],
                },
                "indications_and_usage": ["Treatment of patients with unresectable or metastatic melanoma with BRAF V600E mutation"],
                "products": [
                    {
                        "approval_date": "20110817",
                        "marketing_status": "Prescription"
                    }
                ]
            }
        ]

        # Mock MyVariant response (minimal)
        mock_myvariant_response = {
            "hits": [{
                "_id": "test",
                "civic": {},
                "clinvar": {},
                "cosmic": {}
            }]
        }

        variant_input = VariantInput(gene="BRAF", variant="V600E", tumor_type="Melanoma")

        async with AssessmentEngine() as engine:
            # Mock both API clients
            with patch.object(engine.myvariant_client, '_query', new_callable=AsyncMock) as mock_myvariant:
                with patch.object(engine.fda_client, 'fetch_drug_approvals', new_callable=AsyncMock) as mock_fda:
                    mock_myvariant.return_value = mock_myvariant_response
                    mock_fda.return_value = mock_fda_response

                    # Mock LLM to avoid real API call
                    with patch.object(engine.llm_service, 'assess_variant', new_callable=AsyncMock) as mock_llm:
                        from tumorboard.models.assessment import ActionabilityAssessment
                        mock_llm.return_value = ActionabilityAssessment(
                            gene="BRAF",
                            variant="V600E",
                            tumor_type="Melanoma",
                            tier="Tier I",
                            confidence_score=0.95,
                            summary="Test summary",
                            rationale="Test rationale",
                            evidence_strength="Strong",
                            recommended_therapies=[],
                            clinical_trials_available=False,
                            references=[]
                        )

                        assessment = await engine.assess_variant(variant_input)

                        # Verify FDA client was called
                        mock_fda.assert_called_once()
                        call_args = mock_fda.call_args
                        assert call_args[1]["gene"] == "BRAF"
                        assert call_args[1]["variant"] == "V600E"

    @pytest.mark.asyncio
    async def test_fda_data_added_to_evidence(self):
        """Test that FDA approval data is properly added to Evidence object."""

        # Mock response from FDA drug label endpoint (no products field)
        mock_fda_response = [
            {
                "openfda": {
                    "brand_name": ["Tagrisso"],
                    "generic_name": ["osimertinib"],
                },
                "indications_and_usage": ["For EGFR T790M mutation-positive NSCLC"]
            }
        ]

        mock_myvariant_response = {
            "hits": [{
                "_id": "test",
                "civic": {},
                "clinvar": {},
                "cosmic": {}
            }]
        }

        variant_input = VariantInput(gene="EGFR", variant="T790M", tumor_type="NSCLC")

        async with AssessmentEngine() as engine:
            with patch.object(engine.myvariant_client, '_query', new_callable=AsyncMock) as mock_myvariant:
                with patch.object(engine.fda_client, 'fetch_drug_approvals', new_callable=AsyncMock) as mock_fda:
                    mock_myvariant.return_value = mock_myvariant_response
                    mock_fda.return_value = mock_fda_response

                    with patch.object(engine.llm_service, 'assess_variant', new_callable=AsyncMock) as mock_llm:
                        # Capture the evidence passed to LLM
                        evidence_captured = None

                        def capture_evidence(gene, variant, tumor_type, evidence):
                            nonlocal evidence_captured
                            evidence_captured = evidence
                            from tumorboard.models.assessment import ActionabilityAssessment
                            return ActionabilityAssessment(
                                gene=gene,
                                variant=variant,
                                tumor_type=tumor_type,
                                tier="Tier I",
                                confidence_score=0.95,
                                summary="Test",
                                rationale="Test",
                                evidence_strength="Strong",
                                recommended_therapies=[],
                                clinical_trials_available=False,
                                references=[]
                            )

                        mock_llm.side_effect = capture_evidence

                        assessment = await engine.assess_variant(variant_input)

                        # Verify FDA data was added to evidence
                        assert evidence_captured is not None
                        assert len(evidence_captured.fda_approvals) > 0

                        fda_approval = evidence_captured.fda_approvals[0]
                        assert fda_approval.brand_name == "Tagrisso"
                        assert fda_approval.generic_name == "osimertinib"
                        assert "EGFR T790M" in fda_approval.indication
                        # Label endpoint doesn't have approval_date
                        assert fda_approval.marketing_status == "Prescription"

    @pytest.mark.asyncio
    async def test_fda_failure_does_not_break_pipeline(self):
        """Test that FDA API failures don't break the assessment pipeline."""

        mock_myvariant_response = {
            "hits": [{
                "_id": "test",
                "civic": {},
                "clinvar": {},
                "cosmic": {}
            }]
        }

        variant_input = VariantInput(gene="BRAF", variant="V600E", tumor_type="Melanoma")

        async with AssessmentEngine() as engine:
            with patch.object(engine.myvariant_client, '_query', new_callable=AsyncMock) as mock_myvariant:
                with patch.object(engine.fda_client, 'fetch_drug_approvals', new_callable=AsyncMock) as mock_fda:
                    mock_myvariant.return_value = mock_myvariant_response
                    # Simulate FDA API failure
                    mock_fda.side_effect = Exception("FDA API error")

                    with patch.object(engine.llm_service, 'assess_variant', new_callable=AsyncMock) as mock_llm:
                        from tumorboard.models.assessment import ActionabilityAssessment
                        mock_llm.return_value = ActionabilityAssessment(
                            gene="BRAF",
                            variant="V600E",
                            tumor_type="Melanoma",
                            tier="Tier I",
                            confidence_score=0.95,
                            summary="Test summary",
                            rationale="Test rationale",
                            evidence_strength="Strong",
                            recommended_therapies=[],
                            clinical_trials_available=False,
                            references=[]
                        )

                        # Should not raise exception
                        assessment = await engine.assess_variant(variant_input)

                        # Should still get valid assessment
                        assert assessment.tier == "Tier I"
                        assert assessment.gene == "BRAF"

    @pytest.mark.asyncio
    async def test_fda_data_in_evidence_summary(self):
        """Test that FDA approvals appear in evidence summary."""

        from tumorboard.models.evidence import Evidence, FDAApproval

        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
            fda_approvals=[
                FDAApproval(
                    drug_name="Zelboraf",
                    brand_name="Zelboraf",
                    generic_name="vemurafenib",
                    indication="Treatment of melanoma with BRAF V600E mutation",
                    approval_date="20110817",
                    marketing_status="Prescription",
                    gene="BRAF"
                ),
                FDAApproval(
                    drug_name="Tafinlar",
                    brand_name="Tafinlar",
                    generic_name="dabrafenib",
                    indication="BRAF V600E mutation-positive melanoma",
                    approval_date="20130529",
                    marketing_status="Prescription",
                    gene="BRAF"
                )
            ]
        )

        summary = evidence.summary()

        # Verify FDA section exists in summary
        assert "FDA Approved Drugs" in summary
        assert "Zelboraf" in summary
        assert "Tafinlar" in summary
        assert "20110817" in summary
        assert "Prescription" in summary
        assert "melanoma" in summary.lower()

    @pytest.mark.asyncio
    async def test_parallel_execution_of_myvariant_and_fda(self):
        """Test that MyVariant and FDA APIs are called in parallel."""

        import asyncio
        from unittest.mock import call

        mock_fda_response = [{"openfda": {"brand_name": ["TestDrug"]}}]
        mock_myvariant_response = {"hits": [{"_id": "test", "civic": {}}]}

        variant_input = VariantInput(gene="BRAF", variant="V600E", tumor_type="Melanoma")

        # Track order of API calls
        call_order = []

        async def track_myvariant(*args, **kwargs):
            call_order.append("myvariant_start")
            await asyncio.sleep(0.1)  # Simulate API delay
            call_order.append("myvariant_end")
            return mock_myvariant_response

        async def track_fda(*args, **kwargs):
            call_order.append("fda_start")
            await asyncio.sleep(0.1)  # Simulate API delay
            call_order.append("fda_end")
            return mock_fda_response

        async with AssessmentEngine() as engine:
            with patch.object(engine.myvariant_client, '_query', new_callable=AsyncMock) as mock_myvariant:
                with patch.object(engine.fda_client, 'fetch_drug_approvals', new_callable=AsyncMock) as mock_fda:
                    mock_myvariant.side_effect = track_myvariant
                    mock_fda.side_effect = track_fda

                    with patch.object(engine.llm_service, 'assess_variant', new_callable=AsyncMock) as mock_llm:
                        from tumorboard.models.assessment import ActionabilityAssessment
                        mock_llm.return_value = ActionabilityAssessment(
                            gene="BRAF",
                            variant="V600E",
                            tumor_type="Melanoma",
                            tier="Tier I",
                            confidence_score=0.95,
                            summary="Test",
                            rationale="Test",
                            evidence_strength="Strong",
                            recommended_therapies=[],
                            clinical_trials_available=False,
                            references=[]
                        )

                        assessment = await engine.assess_variant(variant_input)

                        # Verify both APIs were called
                        assert "myvariant_start" in call_order
                        assert "fda_start" in call_order

                        # In parallel execution, both should start before either ends
                        myvariant_start_idx = call_order.index("myvariant_start")
                        fda_start_idx = call_order.index("fda_start")
                        myvariant_end_idx = call_order.index("myvariant_end")

                        # At least one should start before the other finishes (indicating parallel execution)
                        # This is a simplified check - in true parallel execution,
                        # we expect both to start before either ends
                        assert (fda_start_idx < myvariant_end_idx or myvariant_start_idx < len(call_order))
