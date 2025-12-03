"""Tests for API client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tumorboard.api.myvariant import MyVariantAPIError, MyVariantClient
from tumorboard.api.fda import FDAAPIError, FDAClient
from tumorboard.models.evidence import CIViCEvidence, ClinVarEvidence


class TestMyVariantClient:
    """Tests for MyVariantClient."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        async with MyVariantClient() as client:
            assert client._client is not None

        # Client should be closed after exit
        assert client._client is None

    @pytest.mark.asyncio
    async def test_fetch_evidence_no_results(self):
        """Test fetching evidence with no results."""
        client = MyVariantClient()

        with patch.object(client, "_query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {"hits": []}

            evidence = await client.fetch_evidence("UNKNOWN", "X123Y")

            assert evidence.gene == "UNKNOWN"
            assert evidence.variant == "X123Y"
            assert not evidence.has_evidence()

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_evidence_with_civic(self):
        """Test fetching evidence with CIViC data."""
        client = MyVariantClient()

        mock_response = {
            "hits": [
                {
                    "_id": "test123",
                    "civic": {
                        "evidence_items": [
                            {
                                "evidence_type": "Predictive",
                                "evidence_level": "A",
                                "clinical_significance": "Sensitivity/Response",
                                "disease": {"name": "Melanoma"},
                                "drugs": [{"name": "Vemurafenib"}],
                                "description": "Test description",
                            }
                        ]
                    },
                }
            ]
        }

        with patch.object(client, "_query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_response

            evidence = await client.fetch_evidence("BRAF", "V600E")

            assert evidence.has_evidence()
            assert len(evidence.civic) == 1
            assert evidence.civic[0].evidence_type == "Predictive"
            assert "Vemurafenib" in evidence.civic[0].drugs

        await client.close()

    @pytest.mark.asyncio
    async def test_parse_civic_evidence(self):
        """Test parsing CIViC evidence."""
        client = MyVariantClient()

        civic_data = {
            "evidence_items": [
                {
                    "evidence_type": "Predictive",
                    "evidence_level": "A",
                    "disease": {"name": "Melanoma"},
                    "drugs": [{"name": "Drug1"}, {"name": "Drug2"}],
                }
            ]
        }

        parsed = client._parse_civic_evidence(civic_data)

        assert len(parsed) == 1
        assert parsed[0].evidence_type == "Predictive"
        assert len(parsed[0].drugs) == 2

    @pytest.mark.asyncio
    async def test_parse_clinvar_evidence(self):
        """Test parsing ClinVar evidence."""
        client = MyVariantClient()

        clinvar_data = {
            "clinical_significance": "Pathogenic",
            "review_status": "reviewed by expert panel",
            "conditions": [{"name": "Cancer"}],
            "variation_id": "12345",
        }

        parsed = client._parse_clinvar_evidence(clinvar_data)

        assert len(parsed) == 1
        assert "Pathogenic" in parsed[0].clinical_significance
        assert "Cancer" in parsed[0].conditions

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Test API error handling."""
        client = MyVariantClient()

        with patch.object(client, "_query", new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = MyVariantAPIError("API error")

            with pytest.raises(MyVariantAPIError):
                await client.fetch_evidence("BRAF", "V600E")

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_evidence_with_identifiers(self):
        """Test fetching evidence with database identifiers."""
        client = MyVariantClient()

        mock_response = {
            "hits": [
                {
                    "_id": "chr7:g.140453136A>T",
                    "cosmic": {"cosmic_id": "COSM476"},
                    "dbsnp": {
                        "rsid": "rs113488022",
                        "gene": {"geneid": 673},
                    },
                    "clinvar": {"variant_id": "13961"},
                    "civic": {},
                }
            ]
        }

        with patch.object(client, "_query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_response

            evidence = await client.fetch_evidence("BRAF", "V600E")

            # Verify identifiers were extracted
            assert evidence.cosmic_id == "COSM476"
            assert evidence.ncbi_gene_id == "673"
            assert evidence.dbsnp_id == "rs113488022"
            assert evidence.clinvar_id == "13961"
            assert evidence.hgvs_genomic == "chr7:g.140453136A>T"

        await client.close()

    @pytest.mark.asyncio
    async def test_query_strategy_with_protein_notation(self):
        """Test that the client tries protein notation query first."""
        client = MyVariantClient()

        with patch.object(client, "_query", new_callable=AsyncMock) as mock_query:
            # First call returns results (protein notation query succeeds)
            mock_query.return_value = {
                "hits": [{"_id": "test", "civic": {}, "clinvar": {}, "cosmic": {}}]
            }

            await client.fetch_evidence("BRAF", "V600E")

            # Verify the first query used protein notation
            first_call_args = mock_query.call_args_list[0]
            # Should be called with "BRAF p.V600E"
            assert "p.V600E" in first_call_args[0][0] or "BRAF p.V600E" == first_call_args[0][0]

        await client.close()


class TestFDAClient:
    """Tests for FDAClient."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        async with FDAClient() as client:
            assert client._client is not None

        # Client should be closed after exit
        assert client._client is None

    @pytest.mark.asyncio
    async def test_fetch_drug_approvals_with_results(self):
        """Test fetching drug approvals with results."""
        client = FDAClient()

        mock_response = {
            "results": [
                {
                    "openfda": {
                        "brand_name": ["Tagrisso"],
                        "generic_name": ["osimertinib"],
                    },
                    "indications_and_usage": ["For the treatment of patients with EGFR T790M mutation-positive non-small cell lung cancer."],
                    "products": [
                        {
                            "approval_date": "20151113",
                            "marketing_status": "Prescription"
                        }
                    ]
                }
            ]
        }

        with patch.object(client, "_query_drugsfda", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_response

            approvals = await client.fetch_drug_approvals("EGFR", "T790M")

            assert len(approvals) > 0
            assert approvals[0]["openfda"]["brand_name"][0] == "Tagrisso"

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_drug_approvals_no_results(self):
        """Test fetching drug approvals with no results."""
        client = FDAClient()

        with patch.object(client, "_query_drugsfda", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {"results": []}

            approvals = await client.fetch_drug_approvals("UNKNOWN", "X123Y")

            assert len(approvals) == 0

        await client.close()

    @pytest.mark.asyncio
    async def test_known_gene_drugs_mapping(self):
        """Test known gene-drug mappings fallback."""
        client = FDAClient()

        # Test BRAF
        braf_drugs = client._get_known_gene_drugs("BRAF")
        assert "Tafinlar" in braf_drugs
        assert "Zelboraf" in braf_drugs

        # Test EGFR
        egfr_drugs = client._get_known_gene_drugs("EGFR")
        assert "Tagrisso" in egfr_drugs
        assert "Tarceva" in egfr_drugs

        # Test KRAS
        kras_drugs = client._get_known_gene_drugs("KRAS")
        assert "Lumakras" in kras_drugs

        # Test unknown gene
        unknown_drugs = client._get_known_gene_drugs("UNKNOWN")
        assert len(unknown_drugs) == 0

    def test_parse_approval_data(self):
        """Test parsing FDA approval data from drug label endpoint."""
        client = FDAClient()

        # Label endpoint format (no products field, has indications_and_usage)
        approval_record = {
            "openfda": {
                "brand_name": ["Zelboraf"],
                "generic_name": ["vemurafenib"],
            },
            "indications_and_usage": ["Treatment of patients with unresectable or metastatic melanoma with BRAF V600E mutation"]
        }

        parsed = client.parse_approval_data(approval_record, "BRAF")

        assert parsed is not None
        assert parsed["drug_name"] == "Zelboraf"
        assert parsed["brand_name"] == "Zelboraf"
        assert parsed["generic_name"] == "vemurafenib"
        assert "BRAF V600E" in parsed["indication"]
        assert parsed["marketing_status"] == "Prescription"  # Default for label endpoint
        assert parsed["gene"] == "BRAF"
        # approval_date not available in label endpoint
        assert parsed["approval_date"] is None

    def test_parse_approval_data_minimal(self):
        """Test parsing FDA approval data with minimal fields."""
        client = FDAClient()

        approval_record = {
            "openfda": {
                "brand_name": ["SomeDrug"],
            }
        }

        parsed = client.parse_approval_data(approval_record, "GENE")

        assert parsed is not None
        assert parsed["drug_name"] == "SomeDrug"
        assert parsed["gene"] == "GENE"

    def test_parse_approval_data_insufficient(self):
        """Test parsing FDA approval data with insufficient data."""
        client = FDAClient()

        approval_record = {
            "products": [{"approval_date": "20210101"}]
        }

        parsed = client.parse_approval_data(approval_record, "GENE")

        # Should return None if no drug name available
        assert parsed is None

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Test FDA API error handling."""
        client = FDAClient()

        with patch.object(client, "_query_drugsfda", new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = FDAAPIError("API error")

            # Should not raise exception, just return empty list
            approvals = await client.fetch_drug_approvals("BRAF", "V600E")
            assert approvals == []

        await client.close()

    @pytest.mark.asyncio
    async def test_fetch_drug_approvals_filters_by_gene(self):
        """Test that fetch_drug_approvals filters results by gene mention."""
        client = FDAClient()

        mock_response = {
            "results": [
                {
                    "openfda": {"brand_name": ["RelevantDrug"]},
                    "indications_and_usage": ["For BRAF V600E mutation"],
                },
                {
                    "openfda": {"brand_name": ["IrrelevantDrug"]},
                    "indications_and_usage": ["For some other condition"],
                }
            ]
        }

        with patch.object(client, "_query_drugsfda", new_callable=AsyncMock) as mock_query:
            # First call returns empty, second call returns broad results
            mock_query.side_effect = [{"results": []}, mock_response]

            approvals = await client.fetch_drug_approvals("BRAF", "V600E")

            # Should only include the drug that mentions BRAF
            assert len(approvals) >= 1
            # Check that at least one drug is relevant
            has_braf_mention = any(
                "BRAF" in str(approval.get("indications_and_usage", "")).upper()
                for approval in approvals
            )
            assert has_braf_mention

        await client.close()
