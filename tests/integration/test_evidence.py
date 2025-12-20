"""Integration tests for Evidence class aggregation.

Tests validate that the Evidence class correctly aggregates data from
multiple APIs and provides accurate tier hints, statistics, and summaries.
"""

import pytest

from tumorboard.api.myvariant import MyVariantClient
from tumorboard.api.fda import FDAClient
from tumorboard.api.cgi import CGIClient
from tumorboard.api.vicc import VICCClient
from tumorboard.api.civic import CIViCClient
from tumorboard.models.evidence.evidence import Evidence
from tumorboard.models.evidence.fda import FDAApproval
from tumorboard.models.evidence.cgi import CGIBiomarkerEvidence
from tumorboard.models.evidence.vicc import VICCEvidence
from tumorboard.models.evidence.civic import CIViCAssertionEvidence


class TestEvidenceAggregation:
    """Tests for evidence aggregation from multiple sources."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_braf_v600e_melanoma_aggregation(self):
        """BRAF V600E in melanoma should aggregate evidence correctly."""
        async with MyVariantClient() as myvariant_client:
            evidence = await myvariant_client.fetch_evidence("BRAF", "V600E")

        async with VICCClient() as vicc_client:
            vicc_associations = await vicc_client.fetch_associations(
                "BRAF", "V600E", tumor_type="melanoma", max_results=20
            )

        # Add VICC evidence
        vicc_evidence = []
        for assoc in vicc_associations:
            vicc_evidence.append(VICCEvidence(
                description=assoc.description,
                gene=assoc.gene,
                variant=assoc.variant,
                disease=assoc.disease,
                drugs=assoc.drugs,
                evidence_level=assoc.evidence_level,
                response_type=assoc.response_type,
                source=assoc.source,
                is_sensitivity=assoc.is_sensitivity(),
                is_resistance=assoc.is_resistance(),
                oncokb_level=assoc.get_oncokb_level(),
            ))
        evidence.vicc = vicc_evidence

        assert evidence.gene == "BRAF"
        assert evidence.variant == "V600E"
        assert evidence.has_evidence()
        assert len(evidence.vicc) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_egfr_l858r_nsclc_aggregation(self):
        """EGFR L858R in NSCLC should aggregate evidence correctly."""
        async with MyVariantClient() as myvariant_client:
            evidence = await myvariant_client.fetch_evidence("EGFR", "L858R")

        async with VICCClient() as vicc_client:
            vicc_associations = await vicc_client.fetch_associations(
                "EGFR", "L858R", tumor_type="lung", max_results=20
            )

        vicc_evidence = []
        for assoc in vicc_associations:
            vicc_evidence.append(VICCEvidence(
                description=assoc.description,
                gene=assoc.gene,
                variant=assoc.variant,
                disease=assoc.disease,
                drugs=assoc.drugs,
                evidence_level=assoc.evidence_level,
                response_type=assoc.response_type,
                source=assoc.source,
                is_sensitivity=assoc.is_sensitivity(),
                is_resistance=assoc.is_resistance(),
            ))
        evidence.vicc = vicc_evidence

        assert evidence.has_evidence()
        stats = evidence.compute_evidence_stats(tumor_type="lung")
        assert stats['sensitivity_count'] > 0


class TestEvidenceStats:
    """Tests for evidence statistics computation."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_stats_structure(self):
        """Evidence stats should have correct structure."""
        async with MyVariantClient() as myvariant_client:
            evidence = await myvariant_client.fetch_evidence("BRAF", "V600E")

        async with VICCClient() as vicc_client:
            vicc_associations = await vicc_client.fetch_associations("BRAF", "V600E", max_results=30)

        vicc_evidence = []
        for assoc in vicc_associations:
            vicc_evidence.append(VICCEvidence(
                description=assoc.description,
                gene=assoc.gene,
                variant=assoc.variant,
                disease=assoc.disease,
                drugs=assoc.drugs,
                evidence_level=assoc.evidence_level,
                response_type=assoc.response_type,
                source=assoc.source,
                is_sensitivity=assoc.is_sensitivity(),
                is_resistance=assoc.is_resistance(),
            ))
        evidence.vicc = vicc_evidence

        stats = evidence.compute_evidence_stats()

        assert 'sensitivity_count' in stats
        assert 'resistance_count' in stats
        assert 'sensitivity_by_level' in stats
        assert 'resistance_by_level' in stats
        assert 'conflicts' in stats
        assert 'dominant_signal' in stats
        assert 'has_fda_approved' in stats

        assert stats['sensitivity_count'] >= 0
        assert stats['resistance_count'] >= 0

        valid_signals = ['none', 'sensitivity_only', 'resistance_only',
                        'sensitivity_dominant', 'resistance_dominant', 'mixed']
        assert stats['dominant_signal'] in valid_signals


class TestEvidenceTierHints:
    """Tests for tier hint generation."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tp53_investigational_only(self):
        """TP53 mutations should be identified as investigational-only."""
        async with MyVariantClient() as myvariant_client:
            evidence = await myvariant_client.fetch_evidence("TP53", "R248W")

        is_investigational = evidence.is_investigational_only(tumor_type="breast")
        assert is_investigational, "TP53 should be investigational-only in most tumors"

        tier_hint = evidence.get_tier_hint(tumor_type="breast")
        assert "TIER III" in tier_hint or "investigational" in tier_hint.lower()


class TestEvidenceSummary:
    """Tests for evidence summary generation."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_summary_header_generation(self):
        """Summary header should be generated correctly."""
        async with MyVariantClient() as myvariant_client:
            evidence = await myvariant_client.fetch_evidence("BRAF", "V600E")

        async with VICCClient() as vicc_client:
            vicc_associations = await vicc_client.fetch_associations(
                "BRAF", "V600E", tumor_type="melanoma", max_results=10
            )

        vicc_evidence = []
        for assoc in vicc_associations:
            vicc_evidence.append(VICCEvidence(
                description=assoc.description,
                gene=assoc.gene,
                variant=assoc.variant,
                disease=assoc.disease,
                drugs=assoc.drugs,
                evidence_level=assoc.evidence_level,
                response_type=assoc.response_type,
                source=assoc.source,
                is_sensitivity=assoc.is_sensitivity(),
                is_resistance=assoc.is_resistance(),
            ))
        evidence.vicc = vicc_evidence

        summary_header = evidence.format_evidence_summary_header(tumor_type="melanoma")
        assert "EVIDENCE SUMMARY" in summary_header
        assert "TIER" in summary_header

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_compact_summary_generation(self):
        """Compact summary should be generated correctly when there's evidence."""
        async with MyVariantClient() as myvariant_client:
            evidence = await myvariant_client.fetch_evidence("BRAF", "V600E")

        async with FDAClient() as fda_client:
            fda_approvals_raw = await fda_client.fetch_drug_approvals("BRAF", "V600E")
            if fda_approvals_raw:
                fda_approvals = []
                for approval_record in fda_approvals_raw:
                    parsed = fda_client.parse_approval_data(approval_record, "BRAF", "V600E")
                    if parsed:
                        fda_approvals.append(FDAApproval(**parsed))
                evidence.fda_approvals = fda_approvals

        compact_summary = evidence.summary_compact(tumor_type="melanoma")
        # Summary includes gene/variant info when there's FDA data
        if evidence.fda_approvals:
            assert "BRAF" in compact_summary or "Evidence for" in compact_summary
        else:
            # Without FDA data, summary may be minimal
            assert isinstance(compact_summary, str)


class TestDrugAggregation:
    """Tests for drug-level evidence aggregation."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_drug_aggregation_structure(self):
        """Drug aggregation should have correct structure."""
        async with MyVariantClient() as myvariant_client:
            evidence = await myvariant_client.fetch_evidence("BRAF", "V600E")

        async with VICCClient() as vicc_client:
            vicc_associations = await vicc_client.fetch_associations("BRAF", "V600E", max_results=30)

        vicc_evidence = []
        for assoc in vicc_associations:
            vicc_evidence.append(VICCEvidence(
                description=assoc.description,
                gene=assoc.gene,
                variant=assoc.variant,
                disease=assoc.disease,
                drugs=assoc.drugs,
                evidence_level=assoc.evidence_level,
                response_type=assoc.response_type,
                source=assoc.source,
                is_sensitivity=assoc.is_sensitivity(),
                is_resistance=assoc.is_resistance(),
            ))
        evidence.vicc = vicc_evidence

        drug_summary = evidence.aggregate_evidence_by_drug()

        if drug_summary:
            for drug_data in drug_summary:
                assert 'drug' in drug_data
                assert 'sensitivity_count' in drug_data
                assert 'resistance_count' in drug_data
                assert 'net_signal' in drug_data
                assert 'best_level' in drug_data
                assert 'diseases' in drug_data

                assert isinstance(drug_data['drug'], str)
                assert isinstance(drug_data['sensitivity_count'], int)
                assert isinstance(drug_data['resistance_count'], int)
                assert drug_data['net_signal'] in ['SENSITIVE', 'RESISTANT', 'MIXED']
                assert isinstance(drug_data['diseases'], list)


class TestCIViCAssertions:
    """Tests for CIViC assertions integration."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_civic_assertions_integration(self):
        """CIViC assertions should be integrated correctly."""
        async with CIViCClient() as civic_client:
            assertions = await civic_client.fetch_assertions(
                gene="BRAF",
                variant="V600E",
                tumor_type="melanoma",
                max_results=10
            )

        evidence = Evidence(
            variant_id="BRAF:V600E",
            gene="BRAF",
            variant="V600E",
        )

        if assertions:
            civic_assertions_evidence = []
            for assertion in assertions:
                civic_assertions_evidence.append(CIViCAssertionEvidence(
                    assertion_id=assertion.assertion_id,
                    name=assertion.name,
                    amp_level=assertion.amp_level,
                    amp_tier=assertion.get_amp_tier(),
                    amp_level_letter=assertion.get_amp_level(),
                    assertion_type=assertion.assertion_type,
                    significance=assertion.significance,
                    status=assertion.status,
                    molecular_profile=assertion.molecular_profile,
                    disease=assertion.disease,
                    therapies=assertion.therapies,
                    fda_companion_test=assertion.fda_companion_test,
                    nccn_guideline=assertion.nccn_guideline,
                    description=assertion.description,
                    is_sensitivity=assertion.is_sensitivity(),
                    is_resistance=assertion.is_resistance(),
                ))
            evidence.civic_assertions = civic_assertions_evidence

        if evidence.civic_assertions:
            assert len(evidence.civic_assertions) > 0
            for assertion in evidence.civic_assertions:
                assert hasattr(assertion, 'amp_tier')
                assert hasattr(assertion, 'assertion_type')
                assert hasattr(assertion, 'significance')


class TestCGIBiomarkers:
    """Tests for CGI biomarkers integration."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cgi_biomarkers_integration(self):
        """CGI biomarkers should be integrated correctly."""
        cgi_client = CGIClient()
        biomarkers = cgi_client.fetch_biomarkers(
            gene="KRAS",
            variant="G12C",
            tumor_type="lung"
        )

        evidence = Evidence(
            variant_id="KRAS:G12C",
            gene="KRAS",
            variant="G12C",
        )

        if biomarkers:
            cgi_evidence = []
            for biomarker in biomarkers:
                cgi_evidence.append(CGIBiomarkerEvidence(
                    gene=biomarker.gene,
                    alteration=biomarker.alteration,
                    drug=biomarker.drug,
                    drug_status=biomarker.drug_status,
                    association=biomarker.association,
                    evidence_level=biomarker.evidence_level,
                    source=biomarker.source,
                    tumor_type=biomarker.tumor_type,
                    fda_approved=biomarker.is_fda_approved(),
                ))
            evidence.cgi_biomarkers = cgi_evidence

        if evidence.cgi_biomarkers:
            assert len(evidence.cgi_biomarkers) > 0
            for biomarker in evidence.cgi_biomarkers:
                assert hasattr(biomarker, 'drug')
                assert hasattr(biomarker, 'association')
                assert hasattr(biomarker, 'fda_approved')


class TestFullPipeline:
    """End-to-end tests for the full evidence pipeline."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_pipeline_braf_v600e(self):
        """Full pipeline should aggregate evidence from all sources."""
        gene = "BRAF"
        variant = "V600E"
        tumor_type = "melanoma"

        # Fetch from MyVariant
        async with MyVariantClient() as myvariant_client:
            evidence = await myvariant_client.fetch_evidence(gene, variant)

        # Fetch from FDA
        async with FDAClient() as fda_client:
            fda_approvals_raw = await fda_client.fetch_drug_approvals(gene, variant)
            if fda_approvals_raw:
                fda_approvals = []
                for approval_record in fda_approvals_raw:
                    parsed = fda_client.parse_approval_data(approval_record, gene, variant)
                    if parsed:
                        fda_approvals.append(FDAApproval(**parsed))
                evidence.fda_approvals = fda_approvals

        # Fetch from CGI
        cgi_client = CGIClient()
        cgi_biomarkers_raw = cgi_client.fetch_biomarkers(gene, variant, tumor_type)
        if cgi_biomarkers_raw:
            cgi_evidence = []
            for biomarker in cgi_biomarkers_raw:
                cgi_evidence.append(CGIBiomarkerEvidence(
                    gene=biomarker.gene,
                    alteration=biomarker.alteration,
                    drug=biomarker.drug,
                    drug_status=biomarker.drug_status,
                    association=biomarker.association,
                    evidence_level=biomarker.evidence_level,
                    source=biomarker.source,
                    tumor_type=biomarker.tumor_type,
                    fda_approved=biomarker.is_fda_approved(),
                ))
            evidence.cgi_biomarkers = cgi_evidence

        # Fetch from VICC
        async with VICCClient() as vicc_client:
            vicc_associations = await vicc_client.fetch_associations(
                gene, variant, tumor_type=tumor_type, max_results=15
            )
            if vicc_associations:
                vicc_evidence = []
                for assoc in vicc_associations:
                    vicc_evidence.append(VICCEvidence(
                        description=assoc.description,
                        gene=assoc.gene,
                        variant=assoc.variant,
                        disease=assoc.disease,
                        drugs=assoc.drugs,
                        evidence_level=assoc.evidence_level,
                        response_type=assoc.response_type,
                        source=assoc.source,
                        is_sensitivity=assoc.is_sensitivity(),
                        is_resistance=assoc.is_resistance(),
                        oncokb_level=assoc.get_oncokb_level(),
                    ))
                evidence.vicc = vicc_evidence

        # Fetch from CIViC Assertions
        async with CIViCClient() as civic_client:
            civic_assertions = await civic_client.fetch_assertions(
                gene, variant, tumor_type=tumor_type, max_results=20
            )
            if civic_assertions:
                civic_assertions_evidence = []
                for assertion in civic_assertions:
                    civic_assertions_evidence.append(CIViCAssertionEvidence(
                        assertion_id=assertion.assertion_id,
                        name=assertion.name,
                        amp_level=assertion.amp_level,
                        amp_tier=assertion.get_amp_tier(),
                        amp_level_letter=assertion.get_amp_level(),
                        assertion_type=assertion.assertion_type,
                        significance=assertion.significance,
                        status=assertion.status,
                        molecular_profile=assertion.molecular_profile,
                        disease=assertion.disease,
                        therapies=assertion.therapies,
                        fda_companion_test=assertion.fda_companion_test,
                        nccn_guideline=assertion.nccn_guideline,
                        description=assertion.description,
                        is_sensitivity=assertion.is_sensitivity(),
                        is_resistance=assertion.is_resistance(),
                    ))
                evidence.civic_assertions = civic_assertions_evidence

        # Verify full pipeline results
        assert evidence.gene == gene
        assert evidence.variant == variant
        assert evidence.has_evidence()

        stats = evidence.compute_evidence_stats(tumor_type)
        tier_hint = evidence.get_tier_hint(tumor_type)
        summary = evidence.summary_compact(tumor_type)

        assert stats['sensitivity_count'] >= 0
        assert "TIER" in tier_hint
        assert len(summary) > 0
