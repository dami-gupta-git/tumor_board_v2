"""Tests for variant normalization utilities."""

import pytest
from tumorboard.utils.variant_normalization import (
    VariantNormalizer,
    normalize_variant,
    is_missense_variant,
    is_snp_or_small_indel,
    get_protein_position,
    to_hgvs_protein,
)


class TestVariantNormalizer:
    """Tests for VariantNormalizer class."""

    def test_one_letter_missense_normalization(self):
        """Test normalization of one-letter amino acid codes."""
        result = VariantNormalizer.normalize_protein_change("V600E")

        assert result['short_form'] == "V600E"
        assert result['hgvs_protein'] == "p.V600E"
        assert result['long_form'] == "VAL600GLU"
        assert result['position'] == 600
        assert result['ref_aa'] == "V"
        assert result['alt_aa'] == "E"
        assert result['is_missense'] is True

    def test_three_letter_missense_normalization(self):
        """Test normalization of three-letter amino acid codes."""
        result = VariantNormalizer.normalize_protein_change("Val600Glu")

        assert result['short_form'] == "V600E"
        assert result['hgvs_protein'] == "p.V600E"
        assert result['position'] == 600
        assert result['ref_aa'] == "V"
        assert result['alt_aa'] == "E"
        assert result['is_missense'] is True

    def test_hgvs_protein_normalization(self):
        """Test normalization of HGVS protein notation."""
        # p.V600E format
        result = VariantNormalizer.normalize_protein_change("p.V600E")
        assert result['short_form'] == "V600E"
        assert result['hgvs_protein'] == "p.V600E"
        assert result['is_missense'] is True

        # p.Val600Glu format
        result = VariantNormalizer.normalize_protein_change("p.Val600Glu")
        assert result['short_form'] == "V600E"
        assert result['hgvs_protein'] == "p.V600E"
        assert result['is_missense'] is True

    def test_nonsense_variant(self):
        """Test nonsense (stop codon) variant normalization."""
        result = VariantNormalizer.normalize_protein_change("R248*")

        assert result['short_form'] == "R248*"
        assert result['hgvs_protein'] == "p.R248*"
        assert result['position'] == 248
        assert result['ref_aa'] == "R"
        assert result['alt_aa'] == "*"
        assert result['is_missense'] is False

    def test_case_insensitivity(self):
        """Test that normalization is case-insensitive."""
        result1 = VariantNormalizer.normalize_protein_change("v600e")
        result2 = VariantNormalizer.normalize_protein_change("V600E")

        assert result1['short_form'] == result2['short_form']
        assert result1['hgvs_protein'] == result2['hgvs_protein']

    def test_classify_missense_variant(self):
        """Test classification of missense variants."""
        assert VariantNormalizer.classify_variant_type("V600E") == "missense"
        assert VariantNormalizer.classify_variant_type("L858R") == "missense"
        assert VariantNormalizer.classify_variant_type("p.G12C") == "missense"

    def test_classify_nonsense_variant(self):
        """Test classification of nonsense variants."""
        assert VariantNormalizer.classify_variant_type("R248*") == "nonsense"
        assert VariantNormalizer.classify_variant_type("Q61*") == "nonsense"

    def test_classify_fusion_variant(self):
        """Test classification of fusion variants."""
        assert VariantNormalizer.classify_variant_type("fusion") == "fusion"
        assert VariantNormalizer.classify_variant_type("ALK fusion") == "fusion"
        assert VariantNormalizer.classify_variant_type("EML4-ALK fus") == "fusion"
        assert VariantNormalizer.classify_variant_type("rearrangement") == "fusion"

    def test_classify_amplification_variant(self):
        """Test classification of amplification variants."""
        assert VariantNormalizer.classify_variant_type("amplification") == "amplification"
        assert VariantNormalizer.classify_variant_type("amp") == "amplification"
        assert VariantNormalizer.classify_variant_type("overexpression") == "amplification"

    def test_classify_deletion_variant(self):
        """Test classification of deletion variants."""
        assert VariantNormalizer.classify_variant_type("exon 19 deletion") == "splice"
        assert VariantNormalizer.classify_variant_type("185delAG") == "deletion"
        assert VariantNormalizer.classify_variant_type("6174delT") == "deletion"

    def test_classify_frameshift_variant(self):
        """Test classification of frameshift variants."""
        assert VariantNormalizer.classify_variant_type("L747fs") == "frameshift"
        assert VariantNormalizer.classify_variant_type("Q61fs*5") == "frameshift"

    def test_classify_splice_variant(self):
        """Test classification of splice variants."""
        assert VariantNormalizer.classify_variant_type("exon 14 skipping") == "splice"
        assert VariantNormalizer.classify_variant_type("splice site") == "splice"

    def test_classify_truncating_variant(self):
        """Test classification of truncating variants."""
        assert VariantNormalizer.classify_variant_type("truncating mutation") == "truncating"
        assert VariantNormalizer.classify_variant_type("truncation") == "truncating"

    def test_normalize_variant_full_pipeline(self):
        """Test full variant normalization pipeline."""
        # Missense variant
        result = VariantNormalizer.normalize_variant("BRAF", "Val600Glu")
        assert result['gene'] == "BRAF"
        assert result['variant_original'] == "Val600Glu"
        assert result['variant_normalized'] == "V600E"
        assert result['variant_type'] == "missense"
        assert result['protein_change'] is not None
        assert result['protein_change']['position'] == 600

        # Fusion variant
        result = VariantNormalizer.normalize_variant("ALK", "fusion")
        assert result['gene'] == "ALK"
        assert result['variant_normalized'] == "fusion"
        assert result['variant_type'] == "fusion"
        assert result['protein_change'] is None

    def test_normalize_variant_preserves_gene_case(self):
        """Test that gene symbols are uppercased."""
        result = VariantNormalizer.normalize_variant("braf", "V600E")
        assert result['gene'] == "BRAF"

    def test_edge_cases(self):
        """Test edge cases and unusual inputs."""
        # Empty-ish variant
        result = VariantNormalizer.normalize_protein_change("")
        assert result['short_form'] is None
        assert result['is_missense'] is False

        # Unknown variant type
        result = VariantNormalizer.classify_variant_type("something_weird")
        assert result == "unknown"


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_normalize_variant_function(self):
        """Test normalize_variant convenience function."""
        result = normalize_variant("BRAF", "Val600Glu")
        assert result['gene'] == "BRAF"
        assert result['variant_normalized'] == "V600E"
        assert result['variant_type'] == "missense"

    def test_is_missense_variant_function(self):
        """Test is_missense_variant convenience function."""
        assert is_missense_variant("BRAF", "V600E") is True
        assert is_missense_variant("EGFR", "L858R") is True
        assert is_missense_variant("ALK", "fusion") is False
        assert is_missense_variant("ERBB2", "amplification") is False
        assert is_missense_variant("TP53", "R248*") is False  # Nonsense, not missense

    def test_is_snp_or_small_indel_function(self):
        """Test is_snp_or_small_indel convenience function."""
        # Allowed types
        assert is_snp_or_small_indel("BRAF", "V600E") is True  # Missense
        assert is_snp_or_small_indel("TP53", "R248*") is True  # Nonsense
        assert is_snp_or_small_indel("BRCA1", "185delAG") is True  # Deletion
        assert is_snp_or_small_indel("EGFR", "L747fs") is True  # Frameshift
        assert is_snp_or_small_indel("EGFR", "L747_P753delinsS") is True  # Insertion

        # Not allowed types
        assert is_snp_or_small_indel("ALK", "fusion") is False
        assert is_snp_or_small_indel("ERBB2", "amplification") is False
        assert is_snp_or_small_indel("MET", "exon 14 skipping") is False
        assert is_snp_or_small_indel("RET", "rearrangement") is False

    def test_allowed_variant_types_constant(self):
        """Test that ALLOWED_VARIANT_TYPES contains the expected types."""
        expected_types = {'missense', 'nonsense', 'insertion', 'deletion', 'frameshift'}
        assert VariantNormalizer.ALLOWED_VARIANT_TYPES == expected_types

    def test_get_protein_position_function(self):
        """Test get_protein_position convenience function."""
        assert get_protein_position("V600E") == 600
        assert get_protein_position("Val600Glu") == 600
        assert get_protein_position("p.V600E") == 600
        assert get_protein_position("p.Val600Glu") == 600
        assert get_protein_position("L858R") == 858
        assert get_protein_position("fusion") is None
        assert get_protein_position("amplification") is None

    def test_to_hgvs_protein_function(self):
        """Test to_hgvs_protein convenience function."""
        assert to_hgvs_protein("V600E") == "p.V600E"
        assert to_hgvs_protein("Val600Glu") == "p.V600E"
        assert to_hgvs_protein("p.V600E") == "p.V600E"
        assert to_hgvs_protein("L858R") == "p.L858R"
        assert to_hgvs_protein("fusion") is None
        assert to_hgvs_protein("amplification") is None


class TestRealWorldVariants:
    """Tests with real-world variant examples from the gold standard."""

    def test_braf_v600e_variants(self):
        """Test different representations of BRAF V600E."""
        variants = ["V600E", "Val600Glu", "p.V600E", "p.Val600Glu"]

        for variant in variants:
            result = normalize_variant("BRAF", variant)
            assert result['variant_normalized'] == "V600E"
            assert result['variant_type'] == "missense"

    def test_egfr_variants(self):
        """Test EGFR variant normalizations."""
        # L858R missense
        result = normalize_variant("EGFR", "L858R")
        assert result['variant_normalized'] == "L858R"
        assert result['variant_type'] == "missense"

        # Exon 19 deletion (splice)
        result = normalize_variant("EGFR", "exon 19 deletion")
        assert result['variant_type'] == "splice"

        # T790M resistance mutation
        result = normalize_variant("EGFR", "T790M")
        assert result['variant_normalized'] == "T790M"
        assert result['variant_type'] == "missense"

    def test_kras_variants(self):
        """Test KRAS variant normalizations."""
        # G12C
        result = normalize_variant("KRAS", "G12C")
        assert result['variant_normalized'] == "G12C"
        assert result['variant_type'] == "missense"
        assert get_protein_position("G12C") == 12

        # G12D
        result = normalize_variant("KRAS", "G12D")
        assert result['variant_normalized'] == "G12D"
        assert result['variant_type'] == "missense"

        # G12V
        result = normalize_variant("KRAS", "G12V")
        assert result['variant_normalized'] == "G12V"
        assert result['variant_type'] == "missense"

    def test_fusion_variants(self):
        """Test fusion variant normalizations."""
        genes_with_fusions = ["ALK", "ROS1", "RET", "NTRK1", "NTRK3", "FGFR2", "FGFR3"]

        for gene in genes_with_fusions:
            result = normalize_variant(gene, "fusion")
            assert result['variant_type'] == "fusion"
            assert is_missense_variant(gene, "fusion") is False

    def test_amplification_variants(self):
        """Test amplification variant normalizations."""
        # ERBB2 amplification
        result = normalize_variant("ERBB2", "amplification")
        assert result['variant_type'] == "amplification"

        # MET amplification
        result = normalize_variant("MET", "amplification")
        assert result['variant_type'] == "amplification"

    def test_pik3ca_variants(self):
        """Test PIK3CA hotspot mutations."""
        # H1047R
        result = normalize_variant("PIK3CA", "H1047R")
        assert result['variant_normalized'] == "H1047R"
        assert result['variant_type'] == "missense"

        # E545K
        result = normalize_variant("PIK3CA", "E545K")
        assert result['variant_normalized'] == "E545K"
        assert result['variant_type'] == "missense"

    def test_brca_variants(self):
        """Test BRCA variant notations."""
        # Legacy notation
        result = normalize_variant("BRCA1", "185delAG")
        assert result['variant_type'] == "deletion"

        # Another legacy notation
        result = normalize_variant("BRCA2", "6174delT")
        assert result['variant_type'] == "deletion"

        # Truncating mutation
        result = normalize_variant("BRCA1", "truncating mutation")
        assert result['variant_type'] == "truncating"

    def test_idh_variants(self):
        """Test IDH variant normalizations."""
        # IDH1 R132H
        result = normalize_variant("IDH1", "R132H")
        assert result['variant_normalized'] == "R132H"
        assert result['variant_type'] == "missense"
        assert get_protein_position("R132H") == 132

        # IDH2 R140Q
        result = normalize_variant("IDH2", "R140Q")
        assert result['variant_normalized'] == "R140Q"
        assert result['variant_type'] == "missense"

    def test_kit_variants(self):
        """Test KIT variant normalizations."""
        # D816V
        result = normalize_variant("KIT", "D816V")
        assert result['variant_normalized'] == "D816V"
        assert result['variant_type'] == "missense"

        # Exon 11 mutation
        result = normalize_variant("KIT", "exon 11 mutation")
        assert result['variant_type'] == "splice"

    def test_met_variants(self):
        """Test MET variant normalizations."""
        # Exon 14 skipping
        result = normalize_variant("MET", "exon 14 skipping")
        assert result['variant_type'] == "splice"

        # Amplification
        result = normalize_variant("MET", "amplification")
        assert result['variant_type'] == "amplification"

    def test_tp53_variants(self):
        """Test TP53 variant normalizations."""
        # R175H
        result = normalize_variant("TP53", "R175H")
        assert result['variant_normalized'] == "R175H"
        assert result['variant_type'] == "missense"

        # R248W
        result = normalize_variant("TP53", "R248W")
        assert result['variant_normalized'] == "R248W"
        assert result['variant_type'] == "missense"

    def test_nras_variants(self):
        """Test NRAS variant normalizations."""
        # Q61K
        result = normalize_variant("NRAS", "Q61K")
        assert result['variant_normalized'] == "Q61K"
        assert result['variant_type'] == "missense"

        # Q61R
        result = normalize_variant("NRAS", "Q61R")
        assert result['variant_normalized'] == "Q61R"
        assert result['variant_type'] == "missense"


class TestAminoAcidConversions:
    """Tests for amino acid conversion dictionaries."""

    def test_three_to_one_conversion(self):
        """Test three-letter to one-letter amino acid conversion."""
        assert VariantNormalizer.AA_3TO1['VAL'] == 'V'
        assert VariantNormalizer.AA_3TO1['GLU'] == 'E'
        assert VariantNormalizer.AA_3TO1['LEU'] == 'L'
        assert VariantNormalizer.AA_3TO1['ARG'] == 'R'
        assert VariantNormalizer.AA_3TO1['TER'] == '*'
        assert VariantNormalizer.AA_3TO1['STOP'] == '*'

    def test_one_to_three_conversion(self):
        """Test one-letter to three-letter amino acid conversion."""
        assert VariantNormalizer.AA_1TO3['V'] == 'VAL'
        assert VariantNormalizer.AA_1TO3['E'] == 'GLU'
        assert VariantNormalizer.AA_1TO3['L'] == 'LEU'
        assert VariantNormalizer.AA_1TO3['R'] == 'ARG'
        # Note: * maps to STOP in the reverse dictionary (first occurrence wins)
        assert VariantNormalizer.AA_1TO3['*'] in ['TER', 'STOP']

    def test_all_standard_amino_acids(self):
        """Test that all 20 standard amino acids are represented."""
        standard_aa = ['A', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'K', 'L',
                       'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'V', 'W', 'Y']

        for aa in standard_aa:
            assert aa in VariantNormalizer.AA_1TO3
            three_letter = VariantNormalizer.AA_1TO3[aa]
            assert three_letter in VariantNormalizer.AA_3TO1
            assert VariantNormalizer.AA_3TO1[three_letter] == aa
