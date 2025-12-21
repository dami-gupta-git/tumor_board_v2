"""Gene class configuration loader.

Loads gene class definitions from YAML configuration file to determine
gene-level therapeutic implications when variant-specific evidence is lacking.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


class GeneClassConfig:
    """Configuration for gene class properties and tier rules."""

    def __init__(self, config: dict[str, Any]):
        self._config = config
        self._gene_to_class: dict[str, str] = {}

        # Build reverse mapping: gene -> class name
        for class_name, class_config in config.items():
            if isinstance(class_config, dict) and 'genes' in class_config:
                for gene in class_config['genes']:
                    self._gene_to_class[gene.upper()] = class_name

    def get_gene_class(self, gene: str) -> str | None:
        """Get the class name for a gene (e.g., 'ddr', 'mmr', 'splicing')."""
        return self._gene_to_class.get(gene.upper())

    def is_ddr_gene(self, gene: str) -> bool:
        """Check if a gene is a DNA Damage Repair gene."""
        return self.get_gene_class(gene) == 'ddr'

    def is_mmr_gene(self, gene: str) -> bool:
        """Check if a gene is a Mismatch Repair gene."""
        return self.get_gene_class(gene) == 'mmr'

    def is_splicing_gene(self, gene: str) -> bool:
        """Check if a gene is a splicing factor gene."""
        return self.get_gene_class(gene) == 'splicing'

    def get_genes_in_class(self, class_name: str) -> list[str]:
        """Get all genes in a specific class."""
        class_config = self._config.get(class_name, {})
        return class_config.get('genes', [])

    def get_therapeutic_drugs(self, gene: str) -> list[str]:
        """Get therapeutic drugs/classes for a gene's class."""
        class_name = self.get_gene_class(gene)
        if not class_name:
            return []

        class_config = self._config.get(class_name, {})
        implications = class_config.get('therapeutic_implications', {})
        return implications.get('drugs', [])

    def get_tier_for_evidence_pattern(
        self, gene: str, pattern: str
    ) -> str | None:
        """Get the tier recommendation based on evidence pattern.

        Args:
            gene: Gene symbol
            pattern: One of 'conflicting_evidence', 'sensitivity_only', 'preclinical_only'

        Returns:
            Tier string (e.g., 'II-C', 'II-D') or None if not configured
        """
        class_name = self.get_gene_class(gene)
        if not class_name:
            return None

        class_config = self._config.get(class_name, {})
        tier_rules = class_config.get('tier_rules', {})
        return tier_rules.get(pattern)

    def get_class_description(self, gene: str) -> str | None:
        """Get the description for a gene's class."""
        class_name = self.get_gene_class(gene)
        if not class_name:
            return None

        class_config = self._config.get(class_name, {})
        return class_config.get('description')

    def get_therapeutic_mechanism(self, gene: str) -> str | None:
        """Get the therapeutic mechanism explanation for a gene's class."""
        class_name = self.get_gene_class(gene)
        if not class_name:
            return None

        class_config = self._config.get(class_name, {})
        implications = class_config.get('therapeutic_implications', {})
        return implications.get('mechanism')


@lru_cache(maxsize=1)
def load_gene_classes() -> GeneClassConfig:
    """Load gene class configuration from YAML file.

    Returns:
        GeneClassConfig instance with loaded configuration.
    """
    config_path = Path(__file__).parent / "gene_classes.yaml"

    if not config_path.exists():
        # Return empty config if file doesn't exist
        return GeneClassConfig({})

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return GeneClassConfig(config or {})