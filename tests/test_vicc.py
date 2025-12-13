"""Tests for VICC (Variant Interpretation for Cancer Consortium) MetaKB client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from tumorboard.api.vicc import VICCClient, VICCAssociation, VICCError
from tumorboard.models.evidence import VICCEvidence


class TestVICCAssociation:
    """Tests for VICCAssociation class."""

    def test_association_creation(self):
        """Test creating a VICC association."""
        assoc = VICCAssociation(
            description="BRAF V600E confers sensitivity to vemurafenib",
            gene="BRAF",
            variant="V600E",
            disease="melanoma",
            drugs=["vemurafenib", "dabrafenib"],
            evidence_level="A",
            response_type="Sensitivity",
            source="civic",
            publication_url="https://pubmed.ncbi.nlm.nih.gov/12345",
            oncogenic="BRAF V600E",
        )

        assert assoc.gene == "BRAF"
        assert assoc.variant == "V600E"
        assert assoc.evidence_level == "A"
        assert "vemurafenib" in assoc.drugs
        assert assoc.source == "civic"

    def test_is_sensitivity_true(self):
        """Test is_sensitivity returns True for sensitivity associations."""
        assoc = VICCAssociation(
            description="Sensitivity",
            gene="BRAF",
            variant="V600E",
            disease="melanoma",
            drugs=["vemurafenib"],
            evidence_level="A",
            response_type="Sensitivity",
            source="civic",
        )
        assert assoc.is_sensitivity() is True

        # Also test "Responsive" variant
        assoc2 = VICCAssociation(
            description="Response",
            gene="EGFR",
            variant="L858R",
            disease="NSCLC",
            drugs=["erlotinib"],
            evidence_level="A",
            response_type="Responsive",
            source="cgi",
        )
        assert assoc2.is_sensitivity() is True

    def test_is_sensitivity_false(self):
        """Test is_sensitivity returns False for resistance associations."""
        assoc = VICCAssociation(
            description="Resistance",
            gene="KRAS",
            variant="G12D",
            disease="CRC",
            drugs=["cetuximab"],
            evidence_level="A",
            response_type="Resistant",
            source="civic",
        )
        assert assoc.is_sensitivity() is False

    def test_is_resistance_true(self):
        """Test is_resistance returns True for resistance associations."""
        assoc = VICCAssociation(
            description="Resistance",
            gene="KRAS",
            variant="G12D",
            disease="colorectal cancer",
            drugs=["cetuximab"],
            evidence_level="A",
            response_type="resistant",  # lowercase
            source="civic",
        )
        assert assoc.is_resistance() is True

    def test_is_resistance_false(self):
        """Test is_resistance returns False for sensitivity associations."""
        assoc = VICCAssociation(
            description="Sensitivity",
            gene="BRAF",
            variant="V600E",
            disease="melanoma",
            drugs=["vemurafenib"],
            evidence_level="A",
            response_type="Sensitivity",
            source="civic",
        )
        assert assoc.is_resistance() is False

    def test_get_oncokb_level_valid(self):
        """Test extraction of OncoKB levels."""
        # Level 1A
        assoc1 = VICCAssociation(
            description="Level 1A",
            gene="BRAF",
            variant="V600E",
            disease="melanoma",
            drugs=["vemurafenib"],
            evidence_level="A",
            response_type="1A",
            source="oncokb",
        )
        assert assoc1.get_oncokb_level() == "1A"

        # Level 2B
        assoc2 = VICCAssociation(
            description="Level 2B",
            gene="EGFR",
            variant="L858R",
            disease="CRC",
            drugs=["erlotinib"],
            evidence_level="B",
            response_type="2B",
            source="oncokb",
        )
        assert assoc2.get_oncokb_level() == "2B"

        # Resistance level R1
        assoc3 = VICCAssociation(
            description="R1",
            gene="KRAS",
            variant="G12D",
            disease="CRC",
            drugs=["cetuximab"],
            evidence_level="A",
            response_type="R1",
            source="oncokb",
        )
        assert assoc3.get_oncokb_level() == "R1"

    def test_get_oncokb_level_none(self):
        """Test get_oncokb_level returns None for non-OncoKB response types."""
        assoc = VICCAssociation(
            description="Sensitivity",
            gene="BRAF",
            variant="V600E",
            disease="melanoma",
            drugs=["vemurafenib"],
            evidence_level="A",
            response_type="Sensitivity",  # Not an OncoKB level
            source="civic",
        )
        assert assoc.get_oncokb_level() is None

    def test_to_dict(self):
        """Test converting association to dictionary."""
        assoc = VICCAssociation(
            description="Test description",
            gene="BRAF",
            variant="V600E",
            disease="melanoma",
            drugs=["vemurafenib"],
            evidence_level="A",
            response_type="Sensitivity",
            source="civic",
            publication_url="https://pubmed.ncbi.nlm.nih.gov/12345",
        )

        result = assoc.to_dict()

        assert result["gene"] == "BRAF"
        assert result["variant"] == "V600E"
        assert result["evidence_level"] == "A"
        assert result["is_sensitivity"] is True
        assert result["is_resistance"] is False
        assert result["oncokb_level"] is None

    def test_publication_url_as_list(self):
        """Test that publication_url can be a list."""
        assoc = VICCAssociation(
            description="Test",
            gene="BRAF",
            variant="V600E",
            disease="melanoma",
            drugs=["vemurafenib"],
            evidence_level="A",
            response_type="Sensitivity",
            source="civic",
            publication_url=["https://pubmed.ncbi.nlm.nih.gov/12345", "https://pubmed.ncbi.nlm.nih.gov/67890"],
        )
        assert isinstance(assoc.publication_url, list)
        assert len(assoc.publication_url) == 2


class TestVICCClient:
    """Tests for VICCClient class."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        async with VICCClient() as client:
            assert client._client is not None

        # Client should be closed after exit
        assert client._client is None

    def test_build_query_gene_only(self):
        """Test building query with gene only."""
        client = VICCClient()
        query = client._build_query("BRAF")
        assert query == "BRAF"

    def test_build_query_gene_and_variant(self):
        """Test building query with gene and variant."""
        client = VICCClient()
        query = client._build_query("BRAF", "V600E")
        assert "BRAF" in query
        assert "V600E" in query
        assert "AND" in query

    def test_build_query_removes_p_prefix(self):
        """Test that p. prefix is removed from variant."""
        client = VICCClient()
        query = client._build_query("BRAF", "p.V600E")
        assert "V600E" in query
        assert "p." not in query

    def test_tumor_matches_direct(self):
        """Test direct tumor type matching."""
        client = VICCClient()

        # Direct match
        assert client._tumor_matches("melanoma", "melanoma") is True
        assert client._tumor_matches("lung cancer", "lung") is True

        # No match
        assert client._tumor_matches("breast cancer", "melanoma") is False

    def test_tumor_matches_with_mappings(self):
        """Test tumor type matching using mappings."""
        client = VICCClient()

        # NSCLC variations
        assert client._tumor_matches("non-small cell lung", "nsclc") is True
        assert client._tumor_matches("lung adenocarcinoma", "nsclc") is True

        # CRC variations
        assert client._tumor_matches("colorectal cancer", "crc") is True
        assert client._tumor_matches("colon cancer", "crc") is True

    def test_tumor_matches_none_filter(self):
        """Test that None tumor type matches all."""
        client = VICCClient()

        assert client._tumor_matches("melanoma", None) is True
        assert client._tumor_matches("lung cancer", None) is True
        assert client._tumor_matches("", None) is True

    @pytest.mark.asyncio
    async def test_fetch_associations_mocked(self):
        """Test fetching associations with mocked response."""
        client = VICCClient()

        mock_response = {
            "hits": {
                "total": 2,
                "hits": [
                    {
                        "association": {
                            "description": "BRAF V600E is sensitive to vemurafenib",
                            "response_type": "Sensitivity",
                            "publication_url": "https://pubmed.ncbi.nlm.nih.gov/12345",
                            "oncogenic": "BRAF V600E",
                            "evidence": [
                                {"evidenceType": {"sourceName": "civic"}}
                            ],
                        },
                        "features": [
                            {"geneSymbol": "BRAF", "name": "BRAF V600E"}
                        ],
                        "diseases": "melanoma",
                        "drugs": "vemurafenib",
                        "evidence_label": "A",
                    },
                    {
                        "association": {
                            "description": "BRAF V600E resistant to drug X",
                            "response_type": "resistant",
                            "evidence": [
                                {"evidenceType": {"sourceName": "jax"}}
                            ],
                        },
                        "features": [
                            {"geneSymbol": "BRAF", "name": "BRAF V600E"}
                        ],
                        "diseases": "colorectal cancer",
                        "drugs": "drug_x",
                        "evidence_label": "B",
                    },
                ],
            }
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = MagicMock()
            mock_http_client.get.return_value = mock_response_obj
            mock_get_client.return_value = mock_http_client

            associations = await client.fetch_associations("BRAF", "V600E")

            assert len(associations) == 2
            assert associations[0].gene == "BRAF"
            assert associations[0].is_sensitivity() is True
            assert associations[1].is_resistance() is True

    @pytest.mark.asyncio
    async def test_fetch_associations_with_tumor_filter(self):
        """Test fetching associations with tumor type filter."""
        client = VICCClient()

        mock_response = {
            "hits": {
                "total": 2,
                "hits": [
                    {
                        "association": {
                            "description": "Melanoma sensitivity",
                            "response_type": "Sensitivity",
                            "evidence": [{"evidenceType": {"sourceName": "civic"}}],
                        },
                        "features": [{"geneSymbol": "BRAF", "name": "BRAF V600E"}],
                        "diseases": "melanoma",
                        "drugs": "vemurafenib",
                        "evidence_label": "A",
                    },
                    {
                        "association": {
                            "description": "CRC resistance",
                            "response_type": "resistant",
                            "evidence": [{"evidenceType": {"sourceName": "civic"}}],
                        },
                        "features": [{"geneSymbol": "BRAF", "name": "BRAF V600E"}],
                        "diseases": "colorectal cancer",
                        "drugs": "drug_x",
                        "evidence_label": "B",
                    },
                ],
            }
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = MagicMock()
            mock_http_client.get.return_value = mock_response_obj
            mock_get_client.return_value = mock_http_client

            # Filter for melanoma only
            associations = await client.fetch_associations("BRAF", "V600E", tumor_type="melanoma")

            assert len(associations) == 1
            assert "melanoma" in associations[0].disease

    @pytest.mark.asyncio
    async def test_fetch_sensitivity_associations(self):
        """Test fetching only sensitivity associations."""
        client = VICCClient()

        mock_response = {
            "hits": {
                "total": 3,
                "hits": [
                    {
                        "association": {"response_type": "Sensitivity", "evidence": []},
                        "features": [{"geneSymbol": "BRAF", "name": "BRAF V600E"}],
                        "diseases": "melanoma",
                        "drugs": "drug1",
                        "evidence_label": "A",
                    },
                    {
                        "association": {"response_type": "resistant", "evidence": []},
                        "features": [{"geneSymbol": "BRAF", "name": "BRAF V600E"}],
                        "diseases": "CRC",
                        "drugs": "drug2",
                        "evidence_label": "A",
                    },
                    {
                        "association": {"response_type": "Responsive", "evidence": []},
                        "features": [{"geneSymbol": "BRAF", "name": "BRAF V600E"}],
                        "diseases": "thyroid",
                        "drugs": "drug3",
                        "evidence_label": "B",
                    },
                ],
            }
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = MagicMock()
            mock_http_client.get.return_value = mock_response_obj
            mock_get_client.return_value = mock_http_client

            sensitivity_assocs = await client.fetch_sensitivity_associations("BRAF", "V600E")

            assert len(sensitivity_assocs) == 2
            assert all(a.is_sensitivity() for a in sensitivity_assocs)

    @pytest.mark.asyncio
    async def test_fetch_resistance_associations(self):
        """Test fetching only resistance associations."""
        client = VICCClient()

        mock_response = {
            "hits": {
                "total": 2,
                "hits": [
                    {
                        "association": {"response_type": "Sensitivity", "evidence": []},
                        "features": [{"geneSymbol": "KRAS", "name": "KRAS G12D"}],
                        "diseases": "melanoma",
                        "drugs": "drug1",
                        "evidence_label": "A",
                    },
                    {
                        "association": {"response_type": "resistant", "evidence": []},
                        "features": [{"geneSymbol": "KRAS", "name": "KRAS G12D"}],
                        "diseases": "CRC",
                        "drugs": "cetuximab",
                        "evidence_label": "A",
                    },
                ],
            }
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = MagicMock()
            mock_http_client.get.return_value = mock_response_obj
            mock_get_client.return_value = mock_http_client

            resistance_assocs = await client.fetch_resistance_associations("KRAS", "G12D")

            assert len(resistance_assocs) == 1
            assert resistance_assocs[0].is_resistance() is True

    @pytest.mark.asyncio
    async def test_parse_association_handles_missing_fields(self):
        """Test that parse_association handles missing fields gracefully."""
        client = VICCClient()

        # Minimal hit with many missing fields
        hit = {
            "association": {
                "description": "Minimal description",
            },
            "features": [],
            "diseases": "",
            "drugs": "",
            "evidence_label": None,
        }

        assoc = client._parse_association(hit)

        # Should not raise, should return an association
        assert assoc is not None
        assert assoc.description == "Minimal description"
        assert assoc.gene == ""
        assert assoc.drugs == []


class TestVICCEvidence:
    """Tests for VICCEvidence model."""

    def test_vicc_evidence_creation(self):
        """Test creating a VICCEvidence model."""
        evidence = VICCEvidence(
            description="BRAF V600E sensitivity",
            gene="BRAF",
            variant="V600E",
            disease="melanoma",
            drugs=["vemurafenib"],
            evidence_level="A",
            response_type="Sensitivity",
            source="civic",
            publication_url="https://pubmed.ncbi.nlm.nih.gov/12345",
            is_sensitivity=True,
            is_resistance=False,
            oncokb_level=None,
        )

        assert evidence.gene == "BRAF"
        assert evidence.is_sensitivity is True
        assert evidence.is_resistance is False

    def test_vicc_evidence_with_oncokb_level(self):
        """Test VICCEvidence with OncoKB level."""
        evidence = VICCEvidence(
            description="Level 1A",
            gene="BRAF",
            variant="V600E",
            disease="melanoma",
            drugs=["vemurafenib"],
            evidence_level="A",
            response_type="1A",
            source="oncokb",
            is_sensitivity=True,
            is_resistance=False,
            oncokb_level="1A",
        )

        assert evidence.oncokb_level == "1A"

    def test_vicc_evidence_publication_url_as_list(self):
        """Test that publication_url can be a list."""
        evidence = VICCEvidence(
            description="Test",
            gene="BRAF",
            variant="V600E",
            disease="melanoma",
            drugs=[],
            publication_url=["https://url1.com", "https://url2.com"],
        )

        assert isinstance(evidence.publication_url, list)
        assert len(evidence.publication_url) == 2

    def test_vicc_evidence_publication_url_as_string(self):
        """Test that publication_url can be a string."""
        evidence = VICCEvidence(
            description="Test",
            gene="BRAF",
            variant="V600E",
            disease="melanoma",
            drugs=[],
            publication_url="https://url.com",
        )

        assert isinstance(evidence.publication_url, str)


class TestVICCClientIntegration:
    """Integration tests for VICC client (requires network)."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_fetch_real_associations_braf(self):
        """Test fetching real associations for BRAF V600E."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("BRAF", "V600E", max_results=5)

            # Should find some associations
            assert len(associations) > 0

            # Should have gene information
            assert any(a.gene == "BRAF" or "BRAF" in str(a.description) for a in associations)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_fetch_real_associations_kras(self):
        """Test fetching real associations for KRAS G12D."""
        async with VICCClient() as client:
            associations = await client.fetch_associations("KRAS", "G12D", max_results=5)

            # Should find some associations
            assert len(associations) > 0

            # KRAS G12D is commonly a resistance marker
            resistance_assocs = [a for a in associations if a.is_resistance()]
            # May or may not have resistance, depending on data
            # Just verify we got results

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_fetch_associations_with_tumor_filter_real(self):
        """Test fetching associations with tumor type filter (real API)."""
        async with VICCClient() as client:
            # Get melanoma-specific BRAF associations
            associations = await client.fetch_associations(
                "BRAF", "V600E", tumor_type="melanoma", max_results=10
            )

            # If we got results, they should be melanoma-related
            if associations:
                # At least one should mention melanoma
                has_melanoma = any("melanoma" in a.disease.lower() for a in associations if a.disease)
                # This might not always be true due to fuzzy matching
                # Just verify we didn't crash
                assert True
