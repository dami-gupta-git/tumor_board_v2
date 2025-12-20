"""Variant class configuration loader.

Loads variant class definitions from YAML configuration file to determine
which variants qualify for FDA approvals based on indication text patterns.
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


class VariantClassConfig:
    """Configuration for variant class matching against FDA approvals."""

    def __init__(self, config: dict[str, Any]):
        self._config = config
        self._global_exclusions = config.get("global_exclusions", [])

    def get_global_exclusions(self, gene: str) -> list[str]:
        """Get global exclusion patterns with gene substituted."""
        return [
            pattern.replace("{gene}", gene.lower())
            for pattern in self._global_exclusions
        ]

    def has_gene_config(self, gene: str) -> bool:
        """Check if a gene has specific configuration."""
        return gene.upper() in self._config

    def get_gene_config(self, gene: str) -> dict[str, Any] | None:
        """Get configuration for a specific gene."""
        return self._config.get(gene.upper())

    def is_default_approve(self, gene: str) -> bool:
        """Check if gene uses default approval (any mutation qualifies)."""
        gene_config = self.get_gene_config(gene)
        if not gene_config:
            return True  # Unknown genes default to approve
        return gene_config.get("default_approve", False)

    def requires_explicit_match(self, gene: str) -> bool:
        """Check if gene requires explicit pattern match (like BRAF V600)."""
        gene_config = self.get_gene_config(gene)
        if not gene_config:
            return False
        return gene_config.get("require_explicit", False)

    def get_variant_class(
        self, gene: str, variant: str, indication_text: str
    ) -> tuple[bool, str | None]:
        """Determine if a variant matches an FDA approval based on indication text.

        Args:
            gene: Gene symbol (e.g., "BRAF")
            variant: Variant notation (e.g., "V600E")
            indication_text: Lowercased FDA indication text

        Returns:
            Tuple of (matches, class_name) where matches is True if variant
            qualifies for the approval, and class_name is the matched class.
        """
        gene_upper = gene.upper()
        variant_upper = variant.upper()
        gene_lower = gene.lower()

        # Check global exclusions first
        for exclusion in self.get_global_exclusions(gene):
            if exclusion in indication_text:
                return False, None

        gene_config = self.get_gene_config(gene)

        # No config for this gene - default approve if gene mentioned
        if not gene_config:
            return True, "default"

        # Gene uses default approval (e.g., PIK3CA, ALK)
        if gene_config.get("default_approve", False):
            return True, "default"

        # Check each variant class
        classes = gene_config.get("classes", {})
        for class_name, class_config in classes.items():
            patterns = class_config.get("patterns", [])
            variants = class_config.get("variants", [])
            exclude_patterns = class_config.get("exclude_patterns", [])
            exclude_variants = class_config.get("exclude_variants", [])
            codon_range = class_config.get("codon_range")

            # Check if any pattern matches
            pattern_matched = any(p in indication_text for p in patterns)

            if not pattern_matched:
                continue

            # Check exclude patterns
            if any(ep in indication_text for ep in exclude_patterns):
                continue

            # Check if variant is excluded
            if variant_upper in exclude_variants:
                continue

            # Check if variant qualifies
            if "*" in variants:
                # Wildcard - any variant matches
                return True, class_name

            if variant_upper in variants:
                return True, class_name

            # Check codon range for indels/deletions
            if codon_range:
                pos_match = re.search(r"[A-Z](\d+)", variant_upper)
                if pos_match:
                    position = int(pos_match.group(1))
                    if codon_range[0] <= position <= codon_range[1]:
                        return True, class_name

        # Gene requires explicit match but none found
        if gene_config.get("require_explicit", False):
            return False, None

        # No class matched, but gene doesn't require explicit - approve by default
        return True, "default"

    def check_special_rules(
        self,
        gene: str,
        variant: str,
        indication_text: str,
        tumor_type: str | None = None,
    ) -> bool | None:
        """Check special rules for complex cases like KIT D816V.

        Returns:
            True if explicitly approved, False if explicitly excluded,
            None if no special rule applies.
        """
        gene_config = self.get_gene_config(gene)
        if not gene_config:
            return None

        classes = gene_config.get("classes", {})
        variant_upper = variant.upper()
        tumor_lower = (tumor_type or "").lower()

        for class_name, class_config in classes.items():
            variants = class_config.get("variants", [])
            special_rules = class_config.get("special_rules", [])

            if variant_upper not in variants and "*" not in variants:
                continue

            for rule in special_rules:
                tumor_exclusions = rule.get("tumor_exclusion", [])
                unless_explicit = rule.get("unless_explicit", False)

                # Check if tumor matches exclusion
                tumor_excluded = any(te in tumor_lower for te in tumor_exclusions)

                if tumor_excluded:
                    if unless_explicit:
                        # Only allow if variant explicitly mentioned
                        if variant.lower() in indication_text:
                            return True
                        return False
                    return False

        return None


@lru_cache(maxsize=1)
def load_variant_classes() -> VariantClassConfig:
    """Load variant class configuration from YAML file.

    Returns:
        VariantClassConfig instance with loaded configuration.
    """
    config_path = Path(__file__).parent / "variant_classes.yaml"

    if not config_path.exists():
        # Return empty config if file doesn't exist
        return VariantClassConfig({})

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return VariantClassConfig(config or {})
