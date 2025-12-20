"""Live integration tests for FDA API.

These tests make REAL API calls to the FDA openFDA endpoint.
Run with: pytest tests/integration/test_fda_live.py -v -s

Use the -s flag to see print output for debugging.
"""

import pytest
from tumorboard.api.fda import FDAClient


class TestFDALiveAPI:
    """Live FDA API integration tests.

    These tests hit the real FDA API to verify our search and parsing logic works
    with actual data. They may be slow and should be run sparingly.
    """

    @pytest.fixture
    def fda_client(self):
        """Create an FDA client for testing."""
        return FDAClient()

    # =========================================================================
    # BRCA1/BRCA2 Gene-Class Approval Tests (PARP Inhibitors)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_brca1_finds_parp_inhibitors(self, fda_client):
        """Test that BRCA1 search finds PARP inhibitors (Lynparza, Talzenna, Rubraca)."""
        approvals = await fda_client.fetch_drug_approvals("BRCA1", "C61G")

        # Should find at least Lynparza, Talzenna, and/or Rubraca
        brand_names = []
        for a in approvals:
            brand = a.get("openfda", {}).get("brand_name", [None])[0]
            if brand:
                brand_names.append(brand.lower())

        print(f"\nFound {len(approvals)} approvals for BRCA1:")
        for name in brand_names:
            print(f"  - {name}")

        # At least one PARP inhibitor should be found
        parp_inhibitors = {"lynparza", "talzenna", "rubraca", "zejula"}
        found_parp = any(name in parp_inhibitors for name in brand_names)

        assert found_parp, f"Expected PARP inhibitor, got: {brand_names}"

    @pytest.mark.asyncio
    async def test_brca1_gene_class_approval_detected(self, fda_client):
        """Test that BRCA-mutated class approvals are detected for any BRCA1 variant."""
        approvals = await fda_client.fetch_drug_approvals("BRCA1", "C61G")

        # Parse and check for variant_in_indications (gene-class approval)
        parp_with_approval = []
        for a in approvals:
            parsed = fda_client.parse_approval_data(a, "BRCA1", "C61G")
            if parsed and parsed.get("variant_in_indications"):
                brand = parsed.get("brand_name", "Unknown")
                parp_with_approval.append(brand)

        print(f"\nDrugs with variant_in_indications=True for BRCA1:")
        for name in parp_with_approval:
            print(f"  - {name}")

        # At least one PARP inhibitor should have variant_in_indications=True
        assert len(parp_with_approval) > 0, "No drugs detected with gene-class approval for BRCA1"

    @pytest.mark.asyncio
    async def test_brca2_finds_parp_inhibitors(self, fda_client):
        """Test that BRCA2 also finds PARP inhibitors."""
        approvals = await fda_client.fetch_drug_approvals("BRCA2", "K3326X")

        brand_names = []
        for a in approvals:
            brand = a.get("openfda", {}).get("brand_name", [None])[0]
            if brand:
                brand_names.append(brand.lower())

        print(f"\nFound {len(approvals)} approvals for BRCA2:")
        for name in brand_names:
            print(f"  - {name}")

        parp_inhibitors = {"lynparza", "talzenna", "rubraca", "zejula"}
        found_parp = any(name in parp_inhibitors for name in brand_names)

        assert found_parp, f"Expected PARP inhibitor for BRCA2, got: {brand_names}"

    # =========================================================================
    # Specific Variant Approval Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_braf_v600e_finds_vemurafenib(self, fda_client):
        """Test that BRAF V600E finds vemurafenib/Zelboraf."""
        approvals = await fda_client.fetch_drug_approvals("BRAF", "V600E")

        brand_names = []
        for a in approvals:
            brand = a.get("openfda", {}).get("brand_name", [None])[0]
            if brand:
                brand_names.append(brand.lower())

        print(f"\nFound {len(approvals)} approvals for BRAF V600E:")
        for name in brand_names:
            print(f"  - {name}")

        # Should find BRAF inhibitors
        braf_drugs = {"zelboraf", "tafinlar", "braftovi", "mektovi"}
        found_braf = any(name in braf_drugs for name in brand_names)

        assert found_braf, f"Expected BRAF inhibitor, got: {brand_names}"

    @pytest.mark.asyncio
    async def test_braf_v600e_variant_in_indications(self, fda_client):
        """Test that BRAF V600E is detected in indications text."""
        approvals = await fda_client.fetch_drug_approvals("BRAF", "V600E")

        drugs_with_variant = []
        for a in approvals:
            parsed = fda_client.parse_approval_data(a, "BRAF", "V600E")
            if parsed and parsed.get("variant_in_indications"):
                drugs_with_variant.append(parsed.get("brand_name", "Unknown"))

        print(f"\nDrugs with V600E in indications:")
        for name in drugs_with_variant:
            print(f"  - {name}")

        assert len(drugs_with_variant) > 0, "V600E should be in at least one drug's indication"

    @pytest.mark.asyncio
    async def test_egfr_t790m_finds_osimertinib(self, fda_client):
        """Test that EGFR T790M finds osimertinib/Tagrisso."""
        approvals = await fda_client.fetch_drug_approvals("EGFR", "T790M")

        brand_names = []
        for a in approvals:
            brand = a.get("openfda", {}).get("brand_name", [None])[0]
            if brand:
                brand_names.append(brand.lower())

        print(f"\nFound {len(approvals)} approvals for EGFR T790M:")
        for name in brand_names:
            print(f"  - {name}")

        assert "tagrisso" in brand_names, f"Expected Tagrisso, got: {brand_names}"

    @pytest.mark.asyncio
    async def test_kit_gist_finds_imatinib(self, fda_client):
        """Test that KIT variants find imatinib/Gleevec for GIST."""
        approvals = await fda_client.fetch_drug_approvals("KIT", "V560D")

        brand_names = []
        for a in approvals:
            brand = a.get("openfda", {}).get("brand_name", [None])[0]
            if brand:
                brand_names.append(brand.lower())

        print(f"\nFound {len(approvals)} approvals for KIT:")
        for name in brand_names:
            print(f"  - {name}")

        # Should find TKIs approved for GIST
        gist_drugs = {"gleevec", "sutent", "stivarga", "ayvakit", "qinlock"}
        found_gist = any(name in gist_drugs for name in brand_names)

        assert found_gist, f"Expected GIST TKI, got: {brand_names}"

    @pytest.mark.asyncio
    async def test_fgfr2_finds_pemigatinib(self, fda_client):
        """Test that FGFR2 finds pemigatinib/Pemazyre for cholangiocarcinoma."""
        approvals = await fda_client.fetch_drug_approvals("FGFR2", "N549K")

        brand_names = []
        for a in approvals:
            brand = a.get("openfda", {}).get("brand_name", [None])[0]
            if brand:
                brand_names.append(brand.lower())

        print(f"\nFound {len(approvals)} approvals for FGFR2:")
        for name in brand_names:
            print(f"  - {name}")

        # Should find FGFR inhibitors
        fgfr_drugs = {"pemazyre", "truseltiq", "lytgobi"}
        found_fgfr = any(name in fgfr_drugs for name in brand_names)

        assert found_fgfr, f"Expected FGFR inhibitor, got: {brand_names}"

    # =========================================================================
    # Edge Cases and Negative Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_unknown_gene_returns_empty(self, fda_client):
        """Test that unknown genes return empty results gracefully."""
        approvals = await fda_client.fetch_drug_approvals("FAKEGENE123", "X999Y")

        print(f"\nFound {len(approvals)} approvals for fake gene")

        assert isinstance(approvals, list)
        assert len(approvals) == 0

    @pytest.mark.asyncio
    async def test_tumor_suppressor_no_targeted_therapy(self, fda_client):
        """Test that tumor suppressors like TP53 don't falsely return targeted therapies."""
        approvals = await fda_client.fetch_drug_approvals("TP53", "R175H")

        # TP53 has no FDA-approved targeted therapies
        # Any results should not have variant_in_indications=True for R175H
        drugs_with_variant = []
        for a in approvals:
            parsed = fda_client.parse_approval_data(a, "TP53", "R175H")
            if parsed and parsed.get("variant_in_indications"):
                drugs_with_variant.append(parsed.get("brand_name", "Unknown"))

        print(f"\nDrugs claiming TP53 R175H approval: {drugs_with_variant}")

        # TP53 R175H should NOT have variant_in_indications=True
        # (there are no drugs approved FOR TP53 mutations)
        assert len(drugs_with_variant) == 0, f"TP53 shouldn't have targeted therapy, got: {drugs_with_variant}"

    # =========================================================================
    # Parsing Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_lynparza_breast_cancer_indication(self, fda_client):
        """Test that Lynparza's breast cancer indication is correctly parsed."""
        approvals = await fda_client.fetch_drug_approvals("BRCA1", "C61G")

        lynparza_parsed = None
        for a in approvals:
            parsed = fda_client.parse_approval_data(a, "BRCA1", "C61G")
            if parsed and parsed.get("brand_name", "").lower() == "lynparza":
                lynparza_parsed = parsed
                break

        assert lynparza_parsed is not None, "Lynparza should be found for BRCA1"

        print(f"\nLynparza parsed data:")
        print(f"  brand_name: {lynparza_parsed.get('brand_name')}")
        print(f"  generic_name: {lynparza_parsed.get('generic_name')}")
        print(f"  variant_in_indications: {lynparza_parsed.get('variant_in_indications')}")
        print(f"  indication preview: {lynparza_parsed.get('indication', '')[:200]}...")

        # Lynparza is approved for BRCA-mutated breast cancer
        assert lynparza_parsed.get("variant_in_indications") is True
        assert "breast" in lynparza_parsed.get("indication", "").lower()

    @pytest.mark.asyncio
    async def test_parse_excludes_negative_mentions(self, fda_client):
        """Test that drugs with 'no data for BRCA' are not flagged as approved."""
        # Raloxifene mentions BRCA but says "no data available" for BRCA mutations
        approvals = await fda_client.fetch_drug_approvals("BRCA1", "C61G")

        raloxifene_parsed = None
        for a in approvals:
            brand = a.get("openfda", {}).get("brand_name", [None])[0]
            if brand and "raloxifene" in brand.lower():
                raloxifene_parsed = fda_client.parse_approval_data(a, "BRCA1", "C61G")
                break

        if raloxifene_parsed:
            print(f"\nRaloxifene parsed:")
            print(f"  variant_in_indications: {raloxifene_parsed.get('variant_in_indications')}")

            # Raloxifene should NOT have variant_in_indications=True
            # because it says "no data available regarding BRCA"
            assert raloxifene_parsed.get("variant_in_indications") is False, \
                "Raloxifene mentions BRCA but isn't approved FOR BRCA mutations"


    # =========================================================================
    # Myeloproliferative Neoplasm Disease-Based Approvals (MPL/JAK2/CALR)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_mpl_finds_jakafi(self, fda_client):
        """Test that MPL variants find Jakafi (ruxolitinib) for myelofibrosis."""
        approvals = await fda_client.fetch_drug_approvals("MPL", "W515L")

        brand_names = []
        for a in approvals:
            brand = a.get("openfda", {}).get("brand_name", [None])[0]
            if brand:
                brand_names.append(brand.lower())

        print(f"\nFound {len(approvals)} approvals for MPL W515L:")
        for name in brand_names:
            print(f"  - {name}")

        # Should find JAK inhibitors approved for myelofibrosis/PV
        mpn_drugs = {"jakafi", "inrebic", "vonjo", "ojjaara", "besremi"}
        found_mpn = any(name in mpn_drugs for name in brand_names)

        assert found_mpn, f"Expected MPN drug (Jakafi/Inrebic/etc), got: {brand_names}"

    @pytest.mark.asyncio
    async def test_mpl_disease_based_approval_detected(self, fda_client):
        """Test that MPL W515L is detected as approved via disease-based matching."""
        approvals = await fda_client.fetch_drug_approvals("MPL", "W515L")

        # Parse and check for variant_in_indications (disease-based approval)
        drugs_with_approval = []
        for a in approvals:
            parsed = fda_client.parse_approval_data(a, "MPL", "W515L")
            if parsed and parsed.get("variant_in_indications"):
                brand = parsed.get("brand_name", "Unknown")
                drugs_with_approval.append(brand)

        print(f"\nDrugs with variant_in_indications=True for MPL W515L:")
        for name in drugs_with_approval:
            print(f"  - {name}")

        # MPL mutations are diagnostic for myelofibrosis/PV
        # Jakafi/Inrebic should have variant_in_indications=True via disease-based detection
        assert len(drugs_with_approval) > 0, "No drugs detected with disease-based approval for MPL"
        assert any("jakafi" in d.lower() for d in drugs_with_approval), \
            f"Jakafi should have variant_in_indications=True, got: {drugs_with_approval}"

    @pytest.mark.asyncio
    async def test_jak2_finds_jakafi(self, fda_client):
        """Test that JAK2 V617F finds Jakafi and other MPN drugs."""
        approvals = await fda_client.fetch_drug_approvals("JAK2", "V617F")

        brand_names = []
        for a in approvals:
            brand = a.get("openfda", {}).get("brand_name", [None])[0]
            if brand:
                brand_names.append(brand.lower())

        print(f"\nFound {len(approvals)} approvals for JAK2 V617F:")
        for name in brand_names:
            print(f"  - {name}")

        mpn_drugs = {"jakafi", "inrebic", "vonjo", "ojjaara", "besremi"}
        found_mpn = any(name in mpn_drugs for name in brand_names)

        assert found_mpn, f"Expected MPN drug for JAK2, got: {brand_names}"

    @pytest.mark.asyncio
    async def test_calr_finds_jakafi(self, fda_client):
        """Test that CALR mutations find Jakafi and other MPN drugs."""
        approvals = await fda_client.fetch_drug_approvals("CALR", "L367fs")

        brand_names = []
        for a in approvals:
            brand = a.get("openfda", {}).get("brand_name", [None])[0]
            if brand:
                brand_names.append(brand.lower())

        print(f"\nFound {len(approvals)} approvals for CALR L367fs:")
        for name in brand_names:
            print(f"  - {name}")

        mpn_drugs = {"jakafi", "inrebic", "vonjo", "ojjaara", "besremi"}
        found_mpn = any(name in mpn_drugs for name in brand_names)

        assert found_mpn, f"Expected MPN drug for CALR, got: {brand_names}"


    # =========================================================================
    # MSI-H/dMMR Biomarker Approvals (MLH1, MSH2, MSH6, PMS2)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_mlh1_finds_pembrolizumab(self, fda_client):
        """Test that MLH1 mutations find pembrolizumab (KEYTRUDA) for MSI-H/dMMR tumors."""
        approvals = await fda_client.fetch_drug_approvals("MLH1", "V716M")

        brand_names = []
        for a in approvals:
            brand = a.get("openfda", {}).get("brand_name", [None])[0]
            if brand:
                brand_names.append(brand.lower())

        print(f"\nFound {len(approvals)} approvals for MLH1 V716M:")
        for name in brand_names:
            print(f"  - {name}")

        # Should find checkpoint inhibitors approved for MSI-H/dMMR
        msi_drugs = {"keytruda", "opdivo", "jemperli"}
        found_msi = any(name in msi_drugs for name in brand_names)

        assert found_msi, f"Expected MSI-H drug (Keytruda/Opdivo/etc), got: {brand_names}"

    @pytest.mark.asyncio
    async def test_mlh1_msi_approval_detected(self, fda_client):
        """Test that MLH1 V716M is detected as approved via MSI-H/dMMR biomarker matching."""
        approvals = await fda_client.fetch_drug_approvals("MLH1", "V716M")

        # Parse and check for variant_in_indications (MSI-H/dMMR approval)
        drugs_with_approval = []
        for a in approvals:
            parsed = fda_client.parse_approval_data(a, "MLH1", "V716M")
            if parsed and parsed.get("variant_in_indications"):
                brand = parsed.get("brand_name", "Unknown")
                indication = parsed.get("indication", "")[:200]
                drugs_with_approval.append((brand, indication))

        print(f"\nDrugs with variant_in_indications=True for MLH1 V716M:")
        for name, ind in drugs_with_approval:
            print(f"  - {name}")
            print(f"    Indication: {ind}...")

        # MLH1 mutations cause dMMR/MSI-H
        # Keytruda should have variant_in_indications=True via MSI-H/dMMR detection
        assert len(drugs_with_approval) > 0, "No drugs detected with MSI-H/dMMR approval for MLH1"
        assert any("keytruda" in d[0].lower() for d in drugs_with_approval), \
            f"Keytruda should have variant_in_indications=True, got: {[d[0] for d in drugs_with_approval]}"

    @pytest.mark.asyncio
    async def test_msh2_finds_pembrolizumab(self, fda_client):
        """Test that MSH2 mutations find pembrolizumab for MSI-H/dMMR tumors."""
        approvals = await fda_client.fetch_drug_approvals("MSH2", "A636P")

        brand_names = []
        for a in approvals:
            brand = a.get("openfda", {}).get("brand_name", [None])[0]
            if brand:
                brand_names.append(brand.lower())

        print(f"\nFound {len(approvals)} approvals for MSH2:")
        for name in brand_names:
            print(f"  - {name}")

        msi_drugs = {"keytruda", "opdivo", "jemperli"}
        found_msi = any(name in msi_drugs for name in brand_names)

        assert found_msi, f"Expected MSI-H drug for MSH2, got: {brand_names}"

    @pytest.mark.asyncio
    async def test_pms2_finds_pembrolizumab(self, fda_client):
        """Test that PMS2 mutations find pembrolizumab for MSI-H/dMMR tumors."""
        approvals = await fda_client.fetch_drug_approvals("PMS2", "R20*")

        brand_names = []
        for a in approvals:
            brand = a.get("openfda", {}).get("brand_name", [None])[0]
            if brand:
                brand_names.append(brand.lower())

        print(f"\nFound {len(approvals)} approvals for PMS2:")
        for name in brand_names:
            print(f"  - {name}")

        msi_drugs = {"keytruda", "opdivo", "jemperli"}
        found_msi = any(name in msi_drugs for name in brand_names)

        assert found_msi, f"Expected MSI-H drug for PMS2, got: {brand_names}"


class TestFDAClientDirectQueries:
    """Test the FDA client's direct query functionality."""

    @pytest.fixture
    def fda_client(self):
        return FDAClient()

    @pytest.mark.asyncio
    async def test_query_drugsfda_by_brand_name(self, fda_client):
        """Test direct query to FDA API by brand name."""
        result = await fda_client._query_drugsfda("openfda.brand_name:LYNPARZA", limit=5)

        assert "results" in result
        assert len(result["results"]) > 0

        first_result = result["results"][0]
        brand_names = first_result.get("openfda", {}).get("brand_name", [])

        print(f"\nDirect query for Lynparza:")
        print(f"  Brand names: {brand_names}")

        assert any("lynparza" in name.lower() for name in brand_names)

    @pytest.mark.asyncio
    async def test_query_drugsfda_by_indication(self, fda_client):
        """Test direct query to FDA API by indication text."""
        result = await fda_client._query_drugsfda("indications_and_usage:EGFR", limit=10)

        assert "results" in result
        print(f"\nDirect query for EGFR in indications found {len(result.get('results', []))} results")

        # Should find multiple EGFR-targeted therapies
        assert len(result.get("results", [])) > 0
