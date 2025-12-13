"""Variant normalization utilities for standardizing variant representations.

This module provides tools to normalize variant notations across different formats:
- One-letter amino acid codes (V600E)
- Three-letter amino acid codes (Val600Glu)
- HGVS protein notation (p.V600E, p.Val600Glu)
- HGVS cDNA notation (c.1799T>A)
- Legacy notations (185delAG)

"""

import re
from typing import Dict, Optional

from tumorboard.constants import (
    ALLOWED_VARIANT_TYPES,
    AMINO_ACID_3TO1,
    AMINO_ACID_1TO3,
)


class VariantNormalizer:
    """Normalizes variant representations to standard formats."""

    # Reference centralized constants
    ALLOWED_VARIANT_TYPES = ALLOWED_VARIANT_TYPES
    AA_3TO1 = AMINO_ACID_3TO1
    AA_1TO3 = AMINO_ACID_1TO3

    # Variant type patterns
    MISSENSE_PATTERN = re.compile(r'^([A-Z*])(\d+)([A-Z*])$', re.IGNORECASE)
    MISSENSE_3LETTER_PATTERN = re.compile(r'^([A-Z]{3})(\d+)([A-Z]{3})$', re.IGNORECASE)
    HGVS_PROTEIN_PATTERN = re.compile(r'^p\.([A-Z]{1,3})(\d+)([A-Z*]{1,3})$', re.IGNORECASE)
    DELETION_PATTERN = re.compile(r'del', re.IGNORECASE)
    INSERTION_PATTERN = re.compile(r'ins', re.IGNORECASE)
    DUPLICATION_PATTERN = re.compile(r'dup', re.IGNORECASE)
    FRAMESHIFT_PATTERN = re.compile(r'fs', re.IGNORECASE)
    NONSENSE_PATTERN = re.compile(r'([A-Z*])(\d+)\*', re.IGNORECASE)

    @staticmethod
    def normalize_protein_change(variant: str) -> Dict[str, Optional[str]]:
        """Normalize a protein change to multiple standard formats.

        Args:
            variant: Protein change in any format (V600E, Val600Glu, p.V600E, etc.)

        Returns:
            Dictionary with normalized representations:
            - short_form: One-letter code (V600E)
            - hgvs_protein: HGVS protein notation (p.V600E)
            - long_form: Three-letter code (Val600Glu)
            - position: Position number (600)
            - ref_aa: Reference amino acid one-letter (V)
            - alt_aa: Alternate amino acid one-letter (E)
            - is_missense: Boolean indicating if this is a missense variant

        e.g.
        p.V600E - >
        {'alt_aa': 'E', 'hgvs_protein': 'p.V600E', 'is_missense': True, 'long_form': 'VAL600GLU', 'position': 600, 'ref_aa': 'V', 'short_form': 'V600E'}
        """
        variant = variant.strip()

        # Remove common prefixes
        if variant.lower().startswith('p.'):
            variant = variant[2:]

        result = {
            'short_form': None,
            'hgvs_protein': None,
            'long_form': None,
            'position': None,
            'ref_aa': None,
            'alt_aa': None,
            'is_missense': False
        }

        # Try one-letter missense format (V600E)
        match = VariantNormalizer.MISSENSE_PATTERN.match(variant)
        if match:
            ref, pos, alt = match.groups()
            ref = ref.upper()
            alt = alt.upper()
            result['short_form'] = f"{ref}{pos}{alt}"
            result['hgvs_protein'] = f"p.{ref}{pos}{alt}"
            result['position'] = int(pos)
            result['ref_aa'] = ref
            result['alt_aa'] = alt
            result['is_missense'] = alt != '*'
            if ref in VariantNormalizer.AA_1TO3 and alt in VariantNormalizer.AA_1TO3:
                result['long_form'] = f"{VariantNormalizer.AA_1TO3[ref]}{pos}{VariantNormalizer.AA_1TO3[alt]}"
            return result

        # Try three-letter missense format (Val600Glu)
        match = VariantNormalizer.MISSENSE_3LETTER_PATTERN.match(variant)
        if match:
            ref_3, pos, alt_3 = match.groups()
            ref_3 = ref_3.upper()
            alt_3 = alt_3.upper()

            if ref_3 in VariantNormalizer.AA_3TO1 and alt_3 in VariantNormalizer.AA_3TO1:
                ref = VariantNormalizer.AA_3TO1[ref_3]
                alt = VariantNormalizer.AA_3TO1[alt_3]
                result['short_form'] = f"{ref}{pos}{alt}"
                result['hgvs_protein'] = f"p.{ref}{pos}{alt}"
                result['long_form'] = f"{ref_3}{pos}{alt_3}"
                result['position'] = int(pos)
                result['ref_aa'] = ref
                result['alt_aa'] = alt
                result['is_missense'] = alt != '*'
                return result

        return result

    @staticmethod
    def classify_variant_type(variant: str) -> str:
        """Classify the type of variant.

        Args:
            variant: Variant string in any format

        Returns:
            Variant type: 'missense', 'nonsense', 'frameshift', 'deletion',
                         'insertion', 'duplication', 'fusion', 'amplification',
                         'splice', 'truncating', or 'unknown'
        """
        variant_lower = variant.lower()

        # Check for structural variants
        if any(kw in variant_lower for kw in ['fusion', 'fus', 'rearrangement']):
            return 'fusion'
        if any(kw in variant_lower for kw in ['amp', 'amplification', 'overexpression']):
            return 'amplification'
        if 'truncat' in variant_lower:
            return 'truncating'
        if any(kw in variant_lower for kw in ['splice', 'exon', 'skip']):
            return 'splice'

        # Check for indels
        if VariantNormalizer.FRAMESHIFT_PATTERN.search(variant):
            return 'frameshift'
        if VariantNormalizer.DELETION_PATTERN.search(variant):
            return 'deletion'
        if VariantNormalizer.INSERTION_PATTERN.search(variant):
            return 'insertion'
        if VariantNormalizer.DUPLICATION_PATTERN.search(variant):
            return 'duplication'

        # Check for nonsense
        if VariantNormalizer.NONSENSE_PATTERN.search(variant):
            return 'nonsense'

        # Check for missense
        normalized = VariantNormalizer.normalize_protein_change(variant)
        if normalized['is_missense']:
            return 'missense'

        return 'unknown'

    @classmethod
    def normalize_variant(cls, gene: str, variant: str) -> Dict[str, any]:
        """Full variant normalization pipeline.

        Args:
            gene: Gene symbol (e.g., 'BRAF')
            variant: Variant string in any format

        Returns:
            Dictionary with:
            - gene: Normalized gene symbol (uppercase)
            - variant_original: Original input variant
            - variant_normalized: Best normalized form
            - variant_type: Classified variant type
            - protein_change: Normalized protein change details (if applicable)
        """
        result = {
            'gene': gene.upper().strip(),
            'variant_original': variant,
            'variant_normalized': variant.strip(),
            'variant_type': cls.classify_variant_type(variant),
            'protein_change': None
        }

        # Attempt protein change normalization for point mutations
        protein_norm = cls.normalize_protein_change(variant)
        if protein_norm['short_form']:
            result['variant_normalized'] = protein_norm['short_form']
            result['protein_change'] = protein_norm

        return result


# Convenience functions for common operations

def normalize_variant(gene: str, variant: str) -> Dict[str, any]:
    """Normalize a variant to standard representation.

    Args:
        gene: Gene symbol
        variant: Variant string

    Returns:
        Dictionary with normalized variant information

    Examples:
        >>> normalize_variant('BRAF', 'Val600Glu')
        {'gene': 'BRAF', 'variant_normalized': 'V600E', 'variant_type': 'missense', ...}

        >>> normalize_variant('ALK', 'fusion')
        {'gene': 'ALK', 'variant_normalized': 'fusion', 'variant_type': 'fusion', ...}
    """
    return VariantNormalizer.normalize_variant(gene, variant)


def is_missense_variant(gene: str, variant: str) -> bool:
    """Check if a variant is a missense mutation.

    Args:
        gene: Gene symbol
        variant: Variant string

    Returns:
        True if the variant is a missense mutation, False otherwise

    Examples:
        >>> is_missense_variant('BRAF', 'V600E')
        True

        >>> is_missense_variant('ALK', 'fusion')
        False
    """
    norm = VariantNormalizer.normalize_variant(gene, variant)
    return norm['variant_type'] == 'missense'


def get_protein_position(variant: str) -> Optional[int]:
    """Extract the protein position from a variant string.

    Args:
        variant: Variant string (V600E, Val600Glu, p.V600E, etc.)

    Returns:
        Position number if found, None otherwise

    Examples:
        >>> get_protein_position('V600E')
        600

        >>> get_protein_position('p.Val600Glu')
        600

        >>> get_protein_position('fusion')
        None
    """
    protein_norm = VariantNormalizer.normalize_protein_change(variant)
    return protein_norm.get('position')


def to_hgvs_protein(variant: str) -> Optional[str]:
    """Convert a variant to HGVS protein notation.

    Args:
        variant: Variant string in any format

    Returns:
        HGVS protein notation (p.V600E) if applicable, None otherwise

    Examples:
        >>> to_hgvs_protein('V600E')
        'p.V600E'

        >>> to_hgvs_protein('Val600Glu')
        'p.V600E'

        >>> to_hgvs_protein('fusion')
        None
    """
    protein_norm = VariantNormalizer.normalize_protein_change(variant)
    return protein_norm.get('hgvs_protein')


def is_snp_or_small_indel(gene: str, variant: str) -> bool:
    """Check if a variant is a SNP or small indel (allowed variant type).

    Args:
        gene: Gene symbol
        variant: Variant string

    Returns:
        True if the variant is a SNP or small indel, False otherwise

    Examples:
        >>> is_snp_or_small_indel('BRAF', 'V600E')
        True

        >>> is_snp_or_small_indel('EGFR', 'L747_P753delinsS')
        True

        >>> is_snp_or_small_indel('ALK', 'fusion')
        False

        >>> is_snp_or_small_indel('ERBB2', 'amplification')
        False
    """
    norm = VariantNormalizer.normalize_variant(gene, variant)
    return norm['variant_type'] in VariantNormalizer.ALLOWED_VARIANT_TYPES
