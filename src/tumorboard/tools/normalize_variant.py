#!/usr/bin/env python3
"""Command-line utility for variant normalization.

This tool normalizes variant notations across different formats:
- One-letter amino acid codes (V600E)
- Three-letter amino acid codes (Val600Glu)
- HGVS protein notation (p.V600E, p.Val600Glu)
- Structural variants (fusion, amplification)
- Indels (del, ins, dup, fs)

Usage:
    python -m tumorboard.tools.normalize_variant BRAF V600E
    python -m tumorboard.tools.normalize_variant BRAF Val600Glu
    python -m tumorboard.tools.normalize_variant BRAF p.V600E
    python -m tumorboard.tools.normalize_variant ALK fusion
    python -m tumorboard.tools.normalize_variant --batch variants.txt
    echo "BRAF,V600E" | python -m tumorboard.tools.normalize_variant --stdin

    # With genomic lookup (requires network)
    python -m tumorboard.tools.normalize_variant BRAF V600E --lookup

Output formats:
    --format json    JSON output (default)
    --format table   Human-readable table
    --format tsv     Tab-separated values
"""

import argparse
import asyncio
import json
import re
import sys
from typing import Any, TextIO

import httpx

from tumorboard.utils.variant_normalization import (
    VariantNormalizer,
    normalize_variant,
    to_hgvs_protein,
    get_protein_position,
    is_snp_or_small_indel,
)


# Gene to chromosome mapping for common cancer genes
GENE_CHROMOSOMES = {
    "BRAF": "7",
    "KRAS": "12",
    "NRAS": "1",
    "EGFR": "7",
    "TP53": "17",
    "PIK3CA": "3",
    "ALK": "2",
    "ROS1": "6",
    "RET": "10",
    "MET": "7",
    "ERBB2": "17",
    "HER2": "17",
    "BRCA1": "17",
    "BRCA2": "13",
    "APC": "5",
    "PTEN": "10",
    "KIT": "4",
    "PDGFRA": "4",
    "IDH1": "2",
    "IDH2": "15",
    "FGFR1": "8",
    "FGFR2": "10",
    "FGFR3": "4",
    "ATM": "11",
    "BRIP1": "17",
    "PALB2": "16",
    "CHEK2": "22",
    "CDH1": "16",
    "STK11": "19",
    "SMAD4": "18",
    "VHL": "3",
    "NF1": "17",
    "NF2": "22",
    "RB1": "13",
    "CDKN2A": "9",
    "MLH1": "3",
    "MSH2": "2",
    "MSH6": "2",
    "PMS2": "7",
    "ARID1A": "1",
    "NOTCH1": "9",
    "FBXW7": "4",
    "CTNNB1": "3",
    "AKT1": "14",
    "MTOR": "1",
    "ESR1": "6",
    "AR": "X",
    "JAK2": "9",
    "MPL": "1",
    "CALR": "19",
    "NPM1": "5",
    "FLT3": "13",
    "DNMT3A": "2",
    "TET2": "4",
    "ASXL1": "20",
    "SF3B1": "2",
    "U2AF1": "21",
    "SRSF2": "17",
    "RUNX1": "21",
    "CEBPA": "19",
    "WT1": "11",
    "GATA2": "3",
    "MYD88": "3",
    "BTK": "X",
    "BCL2": "18",
    "BCL6": "3",
    "MYC": "8",
    "CCND1": "11",
    "CDK4": "12",
    "CDK6": "7",
    "MDM2": "12",
    "TERT": "5",
}


async def lookup_genomic_info(gene: str, variant: str) -> dict[str, Any]:
    """Look up genomic information from MyVariant.info API.

    Returns chromosome, genomic notation (g.), transcript info, and gene details.
    """
    result = {
        "chromosome": None,
        "hgvs_genomic": None,
        "gene_id": None,
        "gene_name": None,
        "transcript_id": None,
        "exon": None,
        "ref_allele": None,
        "alt_allele": None,
        "genomic_position": None,
    }

    # Add chromosome from local mapping first
    gene_upper = gene.upper()
    if gene_upper in GENE_CHROMOSOMES:
        result["chromosome"] = GENE_CHROMOSOMES[gene_upper]

    # Query MyVariant.info API
    protein_notation = f"p.{variant}" if not variant.lower().startswith("p.") else variant
    query = f"{gene} {protein_notation}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://myvariant.info/v1/query",
                params={"q": query, "size": 1}
            )
            response.raise_for_status()
            data = response.json()

            if data.get("hits"):
                hit = data["hits"][0]

                # Extract genomic notation from _id (e.g., "chr7:g.140453136A>T")
                variant_id = hit.get("_id", "")
                if variant_id:
                    result["hgvs_genomic"] = variant_id

                    # Parse chromosome and position from _id
                    match = re.match(r"chr(\w+):g\.(\d+)([ACGT])>([ACGT])", variant_id)
                    if match:
                        result["chromosome"] = match.group(1)
                        result["genomic_position"] = int(match.group(2))
                        result["ref_allele"] = match.group(3)
                        result["alt_allele"] = match.group(4)

                # Extract CADD gene info
                cadd = hit.get("cadd", {})
                if cadd:
                    gene_info = cadd.get("gene", {})
                    if gene_info:
                        result["gene_name"] = gene_info.get("genename")
                        result["gene_id"] = gene_info.get("gene_id")
                        result["transcript_id"] = gene_info.get("feature_id")
                    result["exon"] = cadd.get("exon")

                    # Fallback for chromosome
                    if not result["chromosome"]:
                        result["chromosome"] = str(cadd.get("chrom", ""))

                # Try dbSNP for gene info
                dbsnp = hit.get("dbsnp", {})
                if dbsnp and not result["gene_id"]:
                    dbsnp_gene = dbsnp.get("gene", {})
                    if dbsnp_gene:
                        result["gene_id"] = str(dbsnp_gene.get("geneid", ""))

    except Exception:
        # Silently fail - we'll return partial results from local mapping
        pass

    return result


def normalize_single(gene: str, variant: str, genomic_info: dict | None = None) -> dict:
    """Normalize a single variant and return comprehensive results."""
    result = normalize_variant(gene, variant)

    # Add additional useful fields
    result['hgvs_protein'] = to_hgvs_protein(variant)
    result['position'] = get_protein_position(variant)
    result['is_allowed_type'] = is_snp_or_small_indel(gene, variant)

    # Add chromosome from local mapping
    gene_upper = gene.upper()
    result['chromosome'] = GENE_CHROMOSOMES.get(gene_upper)

    # Add genomic info if provided (from API lookup)
    if genomic_info:
        result['chromosome'] = genomic_info.get('chromosome') or result.get('chromosome')
        result['hgvs_genomic'] = genomic_info.get('hgvs_genomic')
        result['gene_name'] = genomic_info.get('gene_name')
        result['gene_id'] = genomic_info.get('gene_id')
        result['transcript_id'] = genomic_info.get('transcript_id')
        result['exon'] = genomic_info.get('exon')
        result['genomic_position'] = genomic_info.get('genomic_position')
        result['ref_allele'] = genomic_info.get('ref_allele')
        result['alt_allele'] = genomic_info.get('alt_allele')

    # Add query formats for common APIs
    result['query_formats'] = {
        'myvariant': f"{result['gene']} p.{result['variant_normalized']}" if result['protein_change'] else f"{result['gene']} {result['variant_normalized']}",
        'vicc': f"{result['gene']} {result['variant_normalized']}",
        'civic': f"{result['gene']} {result['variant_normalized']}",
    }

    return result


async def normalize_single_with_lookup(gene: str, variant: str) -> dict:
    """Normalize a variant with genomic lookup from MyVariant.info."""
    genomic_info = await lookup_genomic_info(gene, variant)
    return normalize_single(gene, variant, genomic_info)


def format_json(results: list[dict], pretty: bool = True) -> str:
    """Format results as JSON."""
    if len(results) == 1:
        return json.dumps(results[0], indent=2 if pretty else None)
    return json.dumps(results, indent=2 if pretty else None)


def format_table(results: list[dict]) -> str:
    """Format results as a human-readable table."""
    lines = []

    for result in results:
        lines.append("=" * 60)
        lines.append(f"Gene:             {result['gene']}")
        lines.append(f"Original:         {result['variant_original']}")
        lines.append(f"Normalized:       {result['variant_normalized']}")
        lines.append(f"Type:             {result['variant_type']}")
        lines.append(f"Chromosome:       {result.get('chromosome', 'N/A')}")
        lines.append(f"HGVS Protein:     {result.get('hgvs_protein', 'N/A')}")
        lines.append(f"HGVS Genomic:     {result.get('hgvs_genomic', 'N/A')}")
        lines.append(f"Position:         {result.get('position', 'N/A')}")
        lines.append(f"Allowed Type:     {result.get('is_allowed_type', 'N/A')}")

        # Genomic details (if lookup was performed)
        if result.get('gene_name') or result.get('gene_id'):
            lines.append("-" * 40)
            lines.append("Genomic Details:")
            if result.get('gene_name'):
                lines.append(f"  Gene Name:      {result['gene_name']}")
            if result.get('gene_id'):
                lines.append(f"  Gene ID:        {result['gene_id']}")
            if result.get('transcript_id'):
                lines.append(f"  Transcript:     {result['transcript_id']}")
            if result.get('exon'):
                lines.append(f"  Exon:           {result['exon']}")
            if result.get('genomic_position'):
                lines.append(f"  Genomic Pos:    {result['genomic_position']}")
            if result.get('ref_allele') and result.get('alt_allele'):
                lines.append(f"  Alleles:        {result['ref_allele']}>{result['alt_allele']}")

        if result.get('protein_change'):
            pc = result['protein_change']
            lines.append("-" * 40)
            lines.append("Protein Change:")
            lines.append(f"  Ref AA:         {pc.get('ref_aa', 'N/A')}")
            lines.append(f"  Alt AA:         {pc.get('alt_aa', 'N/A')}")
            lines.append(f"  Long Form:      {pc.get('long_form', 'N/A')}")

        if result.get('query_formats'):
            qf = result['query_formats']
            lines.append("-" * 40)
            lines.append("Query Formats:")
            lines.append(f"  MyVariant:      {qf.get('myvariant', 'N/A')}")
            lines.append(f"  VICC:           {qf.get('vicc', 'N/A')}")
            lines.append(f"  CIViC:          {qf.get('civic', 'N/A')}")

    lines.append("=" * 60)
    return "\n".join(lines)


def format_tsv(results: list[dict]) -> str:
    """Format results as TSV."""
    headers = [
        "gene", "chromosome", "variant_original", "variant_normalized", "variant_type",
        "hgvs_protein", "hgvs_genomic", "position", "genomic_position",
        "is_allowed_type", "ref_aa", "alt_aa", "gene_name", "gene_id", "transcript_id", "exon"
    ]

    lines = ["\t".join(headers)]

    for result in results:
        pc = result.get('protein_change') or {}
        row = [
            result['gene'],
            result.get('chromosome') or '',
            result['variant_original'],
            result['variant_normalized'],
            result['variant_type'],
            result.get('hgvs_protein') or '',
            result.get('hgvs_genomic') or '',
            str(result.get('position') or ''),
            str(result.get('genomic_position') or ''),
            str(result.get('is_allowed_type', '')),
            pc.get('ref_aa') or '',
            pc.get('alt_aa') or '',
            result.get('gene_name') or '',
            result.get('gene_id') or '',
            result.get('transcript_id') or '',
            result.get('exon') or '',
        ]
        lines.append("\t".join(row))

    return "\n".join(lines)


def parse_batch_line(line: str) -> tuple[str, str] | None:
    """Parse a line from batch input (gene,variant or gene\tvariant)."""
    line = line.strip()
    if not line or line.startswith('#'):
        return None

    # Try comma separator
    if ',' in line:
        parts = line.split(',', 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()

    # Try tab separator
    if '\t' in line:
        parts = line.split('\t', 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()

    # Try space separator (for "BRAF V600E" format)
    parts = line.split(None, 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()

    return None


def process_batch(input_file: TextIO, lookup: bool = False) -> list[dict]:
    """Process batch input from a file or stdin."""
    results = []

    for line_num, line in enumerate(input_file, 1):
        parsed = parse_batch_line(line)
        if parsed:
            gene, variant = parsed
            try:
                if lookup:
                    result = asyncio.run(normalize_single_with_lookup(gene, variant))
                else:
                    result = normalize_single(gene, variant)
                result['line_number'] = line_num
                results.append(result)
            except Exception as e:
                results.append({
                    'line_number': line_num,
                    'gene': gene,
                    'variant_original': variant,
                    'error': str(e)
                })

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Normalize variant notations to standard formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s BRAF V600E              # Normalize single variant
  %(prog)s BRAF Val600Glu          # Three-letter to one-letter
  %(prog)s BRAF p.V600E            # HGVS protein notation
  %(prog)s ALK fusion              # Structural variant
  %(prog)s --batch variants.txt    # Process batch file
  %(prog)s --format table EGFR L858R  # Table output
  %(prog)s --lookup BRAF V600E     # With genomic lookup (requires network)

Batch file format (one variant per line):
  BRAF,V600E
  EGFR,L858R
  ALK,fusion
  # Comments start with #
"""
    )

    parser.add_argument(
        'gene',
        nargs='?',
        help='Gene symbol (e.g., BRAF, EGFR)'
    )
    parser.add_argument(
        'variant',
        nargs='?',
        help='Variant notation (e.g., V600E, Val600Glu, p.V600E, fusion)'
    )
    parser.add_argument(
        '--batch', '-b',
        type=argparse.FileType('r'),
        help='Batch input file (one gene,variant per line)'
    )
    parser.add_argument(
        '--stdin', '-i',
        action='store_true',
        help='Read from stdin (batch mode)'
    )
    parser.add_argument(
        '--lookup', '-l',
        action='store_true',
        help='Look up genomic info from MyVariant.info (requires network)'
    )
    parser.add_argument(
        '--format', '-f',
        choices=['json', 'table', 'tsv'],
        default='json',
        help='Output format (default: json)'
    )
    parser.add_argument(
        '--compact', '-c',
        action='store_true',
        help='Compact JSON output (no indentation)'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Only output the normalized variant (no metadata)'
    )

    args = parser.parse_args()

    # Determine input mode
    if args.batch:
        results = process_batch(args.batch, lookup=args.lookup)
    elif args.stdin:
        results = process_batch(sys.stdin, lookup=args.lookup)
    elif args.gene and args.variant:
        if args.lookup:
            results = [asyncio.run(normalize_single_with_lookup(args.gene, args.variant))]
        else:
            results = [normalize_single(args.gene, args.variant)]
    else:
        parser.print_help()
        sys.exit(1)

    # Handle quiet mode
    if args.quiet:
        for result in results:
            if 'error' in result:
                print(f"ERROR: {result.get('gene', '?')} {result.get('variant_original', '?')}: {result['error']}", file=sys.stderr)
            else:
                chrom = result.get('chromosome', '')
                genomic = result.get('hgvs_genomic', '')
                print(f"{result['gene']}\t{result['variant_normalized']}\t{chrom}\t{genomic}")
        return

    # Format output
    if args.format == 'json':
        print(format_json(results, pretty=not args.compact))
    elif args.format == 'table':
        print(format_table(results))
    elif args.format == 'tsv':
        print(format_tsv(results))


if __name__ == '__main__':
    main()
