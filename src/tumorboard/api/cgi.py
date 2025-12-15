"""Cancer Genome Interpreter (CGI) biomarkers client.

ARCHITECTURE:
    Gene + Variant → CGI Biomarkers TSV → FDA/NCCN approval status

Fetches FDA approval and guideline information from the Cancer Genome Interpreter
biomarkers database, which provides curated variant-drug associations with
explicit regulatory approval status.

Key Design:
- Downloads and caches the biomarkers TSV file
- Parses variant patterns to match specific mutations (e.g., G719S matches G719.)
- Returns structured CGIBiomarker objects with approval status
- Complements FDA label search which uses generic text (e.g., "non-resistant mutations")
"""

import csv
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from tumorboard.constants import TUMOR_TYPE_MAPPINGS


class CGIError(Exception):
    """Exception raised for CGI-related errors."""

    pass


class CGIBiomarker:
    """A biomarker entry from CGI database."""

    def __init__(
        self,
        gene: str,
        alteration: str,
        drug: str,
        drug_status: str,
        association: str,
        evidence_level: str,
        source: str,
        tumor_type: str,
        tumor_type_full: str,
    ):
        self.gene = gene
        self.alteration = alteration
        self.drug = drug
        self.drug_status = drug_status  # "Approved", "Clinical trial", etc.
        self.association = association  # "Responsive", "Resistant"
        self.evidence_level = evidence_level  # "FDA guidelines", "NCCN guidelines", etc.
        self.source = source
        self.tumor_type = tumor_type
        self.tumor_type_full = tumor_type_full

    def is_fda_approved(self) -> bool:
        """Check if this biomarker represents FDA-approved therapy."""
        return self.drug_status == "Approved" and (
            "FDA" in self.evidence_level.upper()
            or self.evidence_level.upper() in ["NCCN GUIDELINES", "NCCN/CGC GUIDELINES"]
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "gene": self.gene,
            "alteration": self.alteration,
            "drug": self.drug,
            "drug_status": self.drug_status,
            "association": self.association,
            "evidence_level": self.evidence_level,
            "source": self.source,
            "tumor_type": self.tumor_type,
            "tumor_type_full": self.tumor_type_full,
            "fda_approved": self.is_fda_approved(),
        }


class CGIClient:
    """Client for Cancer Genome Interpreter biomarkers database.

    CGI provides curated biomarker-drug associations with explicit
    FDA approval status, complementing the FDA label API which uses
    generic text descriptions.

    Data is downloaded once and cached locally.
    """

    BIOMARKERS_URL = "https://www.cancergenomeinterpreter.org/data/biomarkers/cgi_biomarkers_latest.tsv"
    CACHE_DIR = Path.home() / ".cache" / "tumorboard"
    CACHE_FILE = CACHE_DIR / "cgi_biomarkers.tsv"
    CACHE_MAX_AGE = timedelta(days=7)  # Re-download after 7 days

    def __init__(self, timeout: float = 30.0):
        """Initialize the CGI client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self._biomarkers: list[dict[str, str]] | None = None

    def _cache_is_valid(self) -> bool:
        """Check if the cached file exists and is recent enough."""
        if not self.CACHE_FILE.exists():
            return False
        mtime = datetime.fromtimestamp(self.CACHE_FILE.stat().st_mtime)
        return datetime.now() - mtime < self.CACHE_MAX_AGE

    def _download_biomarkers(self) -> None:
        """Download the biomarkers TSV file."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(self.BIOMARKERS_URL)
            response.raise_for_status()
            self.CACHE_FILE.write_text(response.text)

    def _load_biomarkers(self) -> list[dict[str, str]]:
        """Load and parse the biomarkers TSV file."""
        if not self._cache_is_valid():
            try:
                self._download_biomarkers()
            except Exception as e:
                if not self.CACHE_FILE.exists():
                    raise CGIError(f"Failed to download CGI biomarkers: {e}")
                # Use stale cache if download fails

        with open(self.CACHE_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            return list(reader)

    def _get_biomarkers(self) -> list[dict[str, str]]:
        """Get biomarkers, loading from cache if needed."""
        if self._biomarkers is None:
            self._biomarkers = self._load_biomarkers()
        return self._biomarkers

    def _variant_matches(self, cgi_alteration: str, gene: str, variant: str) -> bool:
        """Check if a CGI alteration pattern matches a specific variant.

        CGI uses patterns like:
        - "EGFR:G719." matches G719S, G719A, G719C, etc.
        - "EGFR:G719A,G719S,G719C" matches any of these specific variants
        - "EGFR:L858R" matches exactly L858R
        - "KRAS:.12.,.13." matches any mutation at position 12 or 13 (G12D, G13D, etc.)
        - "KRAS:." matches any KRAS mutation

        Args:
            cgi_alteration: CGI alteration string (e.g., "EGFR:G719.,L858R")
            gene: Gene symbol (e.g., "EGFR")
            variant: Variant notation (e.g., "G719S")

        Returns:
            True if the variant matches the CGI pattern
        """
        if not cgi_alteration:
            return False

        # Parse the CGI alteration string: "GENE:variant1,variant2,..."
        # Handle both formats: "EGFR:V600E" and just "V600E" after gene match
        gene_upper = gene.upper()
        variant_upper = variant.upper().replace("P.", "")  # Remove p. prefix if present

        # Split by comma to get individual variants
        parts = cgi_alteration.replace(f"{gene_upper}:", "").split(",")

        for part in parts:
            part = part.strip().upper()
            if not part:
                continue

            # Remove gene prefix if still present
            if ":" in part:
                part = part.split(":")[-1]

            # Exact match
            if part == variant_upper:
                return True

            # Wildcard for any mutation in gene: "." alone matches any variant
            if part == ".":
                return True

            # Pattern match: "G719." matches G719S, G719A, etc.
            # The dot represents a wildcard for any amino acid
            if part.endswith(".") and not part.startswith("."):
                # Extract base pattern (e.g., "G719" from "G719.")
                base_pattern = part[:-1]
                # Check if variant starts with base and has exactly one more character
                if variant_upper.startswith(base_pattern) and len(variant_upper) == len(
                    base_pattern
                ) + 1:
                    return True

            # Position-based wildcard: ".13." matches any mutation at position 13
            # Format: .{position}. where position is a number
            # This matches variants like G13D, G13C, G13V, etc.
            if part.startswith(".") and part.endswith(".") and len(part) > 2:
                position_str = part[1:-1]  # Extract position number (e.g., "13" from ".13.")
                if position_str.isdigit():
                    position = position_str
                    # Extract position from variant (e.g., "13" from "G13D")
                    # Variant format: {ref_aa}{position}{alt_aa} like G13D
                    variant_match = re.match(r'^([A-Z])(\d+)([A-Z])$', variant_upper)
                    if variant_match:
                        variant_position = variant_match.group(2)
                        if variant_position == position:
                            return True

        return False

    def _tumor_type_matches(self, cgi_tumor_type: str, tumor_type: str | None) -> bool:
        """Check if tumor types match.

        Args:
            cgi_tumor_type: CGI tumor type abbreviation (e.g., "NSCLC", "L")
            tumor_type: User-provided tumor type (e.g., "Non-Small Cell Lung Cancer")

        Returns:
            True if tumor types match
        """
        if not tumor_type:
            return True  # No filter, match all

        tumor_lower = tumor_type.lower()
        cgi_lower = cgi_tumor_type.lower() if cgi_tumor_type else ""

        # Check if any mapping matches using centralized constants
        for abbrev, full_names in TUMOR_TYPE_MAPPINGS.items():
            if cgi_lower == abbrev or cgi_lower in full_names:
                if any(name in tumor_lower for name in full_names):
                    return True

        # Direct substring match
        if cgi_lower and cgi_lower in tumor_lower:
            return True

        return False

    def fetch_biomarkers(
        self, gene: str, variant: str, tumor_type: str | None = None
    ) -> list[CGIBiomarker]:
        """Fetch CGI biomarkers for a gene/variant combination.

        Args:
            gene: Gene symbol (e.g., "EGFR")
            variant: Variant notation (e.g., "G719S")
            tumor_type: Optional tumor type to filter results

        Returns:
            List of matching CGIBiomarker objects
        """
        biomarkers = self._get_biomarkers()
        matches = []
        gene_upper = gene.upper()

        for row in biomarkers:
            # Check gene match
            if row.get("Gene", "").upper() != gene_upper:
                continue

            # Check variant match
            alteration = row.get("Alteration", "")
            if not self._variant_matches(alteration, gene, variant):
                continue

            # Check tumor type match if specified
            if tumor_type and not self._tumor_type_matches(
                row.get("Primary Tumor type", ""), tumor_type
            ):
                continue

            # Create biomarker object
            matches.append(
                CGIBiomarker(
                    gene=row.get("Gene", ""),
                    alteration=alteration,
                    drug=row.get("Drug", ""),
                    drug_status=row.get("Drug status", ""),
                    association=row.get("Association", ""),
                    evidence_level=row.get("Evidence level", ""),
                    source=row.get("Source", ""),
                    tumor_type=row.get("Primary Tumor type", ""),
                    tumor_type_full=row.get("Primary Tumor type full name", ""),
                )
            )

        return matches

    def fetch_fda_approved(
        self, gene: str, variant: str, tumor_type: str | None = None
    ) -> list[CGIBiomarker]:
        """Fetch only FDA-approved biomarkers for a gene/variant.

        This is a convenience method that filters for:
        - Drug status = "Approved"
        - Evidence level contains "FDA" or is "NCCN guidelines"
        - Association = "Responsive" (excludes resistance markers)

        Args:
            gene: Gene symbol (e.g., "EGFR")
            variant: Variant notation (e.g., "G719S")
            tumor_type: Optional tumor type to filter results

        Returns:
            List of FDA-approved CGIBiomarker objects
        """
        all_biomarkers = self.fetch_biomarkers(gene, variant, tumor_type)
        return [
            b
            for b in all_biomarkers
            if b.is_fda_approved() and b.association.upper() == "RESPONSIVE"
        ]
