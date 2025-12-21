"""OncoKB API client for cancer gene list.

OncoKB is a precision oncology knowledge base that contains information about
the effects and treatment implications of specific cancer gene alterations.

This module fetches the curated cancer gene list from OncoKB's public API.
The list is used to determine if a variant is in a known cancer gene (Tier III-B).

Source: https://www.oncokb.org/cancerGenes
API: https://www.oncokb.org/api/v1/utils/cancerGeneList
"""

import logging
import aiohttp
from functools import lru_cache
from typing import Set

logger = logging.getLogger(__name__)

ONCOKB_CANCER_GENE_LIST_URL = "https://www.oncokb.org/api/v1/utils/cancerGeneList"

# Cache for the cancer gene set (module-level to persist across calls)
_cancer_gene_cache: Set[str] | None = None


async def fetch_cancer_gene_list() -> Set[str]:
    """Fetch the list of known cancer genes from OncoKB API.

    Returns:
        Set of gene symbols (Hugo symbols) that are known cancer genes.
        Returns empty set if API call fails.
    """
    global _cancer_gene_cache

    # Return cached result if available
    if _cancer_gene_cache is not None:
        return _cancer_gene_cache

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                ONCOKB_CANCER_GENE_LIST_URL,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    logger.warning(f"OncoKB API returned status {response.status}")
                    return set()

                data = await response.json()

                # Extract hugoSymbol from each gene entry
                genes = set()
                for gene_entry in data:
                    if isinstance(gene_entry, dict) and 'hugoSymbol' in gene_entry:
                        genes.add(gene_entry['hugoSymbol'].upper())

                logger.info(f"Fetched {len(genes)} cancer genes from OncoKB")
                _cancer_gene_cache = genes
                return genes

    except aiohttp.ClientError as e:
        logger.warning(f"Failed to fetch OncoKB cancer gene list: {e}")
        return set()
    except Exception as e:
        logger.error(f"Unexpected error fetching OncoKB cancer gene list: {e}")
        return set()


def is_known_cancer_gene_sync(gene: str) -> bool:
    """Synchronous check if a gene is in the OncoKB cancer gene list.

    Uses cached data if available. For async contexts, use fetch_cancer_gene_list().

    Args:
        gene: Gene symbol (e.g., 'EGFR', 'BRAF')

    Returns:
        True if gene is in the OncoKB cancer gene list, False otherwise.
        Returns False if cache is not populated (need to call fetch_cancer_gene_list first).
    """
    if _cancer_gene_cache is None:
        # Cache not populated - return False (conservative)
        # In practice, the engine should populate the cache during initialization
        return False

    return gene.upper() in _cancer_gene_cache


def get_cached_cancer_genes() -> Set[str]:
    """Get the cached cancer gene set.

    Returns:
        Set of gene symbols, or empty set if cache not populated.
    """
    return _cancer_gene_cache or set()


# Fallback list if API is unavailable
# Source: OncoKB curated genes (top tier cancer genes)
FALLBACK_CANCER_GENES: Set[str] = {
    # Most commonly mutated cancer genes from OncoKB
    'ABL1', 'AKT1', 'ALK', 'APC', 'AR', 'ARID1A', 'ASXL1', 'ATM', 'ATRX',
    'BAP1', 'BCL2', 'BRAF', 'BRCA1', 'BRCA2', 'CDH1', 'CDKN2A', 'CREBBP',
    'CTNNB1', 'DNMT3A', 'EGFR', 'EP300', 'ERBB2', 'EZH2', 'FBXW7', 'FGFR1',
    'FGFR2', 'FGFR3', 'FLT3', 'GATA3', 'GNA11', 'GNAQ', 'GNAS', 'HNF1A',
    'HRAS', 'IDH1', 'IDH2', 'JAK1', 'JAK2', 'JAK3', 'KDM5C', 'KDM6A',
    'KIT', 'KMT2A', 'KMT2C', 'KMT2D', 'KRAS', 'MAP2K1', 'MAP3K1', 'MED12',
    'MEN1', 'MET', 'MLH1', 'MPL', 'MSH2', 'MSH6', 'MTOR', 'MYC', 'MYCN',
    'MYD88', 'NF1', 'NF2', 'NFE2L2', 'NOTCH1', 'NOTCH2', 'NPM1', 'NRAS',
    'NTRK1', 'NTRK2', 'NTRK3', 'PALB2', 'PAX5', 'PBRM1', 'PDGFRA', 'PIK3CA',
    'PIK3R1', 'PMS2', 'POLE', 'POLD1', 'PTCH1', 'PTEN', 'PTPN11', 'RAD51C',
    'RAD51D', 'RB1', 'RET', 'RNF43', 'ROS1', 'RUNX1', 'SETD2', 'SF3B1',
    'SMAD2', 'SMAD4', 'SMARCA4', 'SMARCB1', 'SMO', 'SOCS1', 'SPOP', 'STAG2',
    'STK11', 'TET2', 'TNFAIP3', 'TP53', 'TSC1', 'TSC2', 'U2AF1', 'VHL',
    'WT1', 'CHEK2', 'ATR', 'BRIP1', 'CDK4', 'CDK6', 'CDK12', 'CCND1',
    'CCND2', 'CCND3', 'CCNE1', 'ERBB3', 'ERBB4', 'ESR1', 'FGFR4', 'KEAP1',
    'MDM2', 'MDM4', 'MUTYH', 'SDHA', 'SDHB', 'SDHC', 'SDHD', 'TGFBR2',
}
