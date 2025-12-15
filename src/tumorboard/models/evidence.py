"""Evidence data models from external databases."""

from typing import Any

from pydantic import BaseModel, Field

from tumorboard.constants import TUMOR_TYPE_MAPPINGS
from tumorboard.models.annotations import VariantAnnotations


class CIViCEvidence(BaseModel):
    """Evidence from CIViC (Clinical Interpretations of Variants in Cancer)."""

    evidence_type: str | None = None
    evidence_level: str | None = None
    evidence_direction: str | None = None
    clinical_significance: str | None = None
    disease: str | None = None
    drugs: list[str] = Field(default_factory=list)
    description: str | None = None
    source: str | None = None
    rating: int | None = None


class ClinVarEvidence(BaseModel):
    """Evidence from ClinVar."""

    clinical_significance: str | None = None
    review_status: str | None = None
    conditions: list[str] = Field(default_factory=list)
    last_evaluated: str | None = None
    variation_id: str | None = None


class COSMICEvidence(BaseModel):
    """Evidence from COSMIC (Catalogue of Somatic Mutations in Cancer)."""

    mutation_id: str | None = None
    primary_site: str | None = None
    site_subtype: str | None = None
    primary_histology: str | None = None
    histology_subtype: str | None = None
    sample_count: int | None = None
    mutation_somatic_status: str | None = None


class FDAApproval(BaseModel):
    """FDA drug approval information."""

    drug_name: str | None = None
    brand_name: str | None = None
    generic_name: str | None = None
    indication: str | None = None
    approval_date: str | None = None
    marketing_status: str | None = None
    gene: str | None = None
    variant_in_indications: bool = False  # True if variant explicitly in indications_and_usage (strongest evidence)
    variant_in_clinical_studies: bool = False  # True if variant mentioned in clinical_studies section

    def parse_indication_for_tumor(self, tumor_type: str) -> dict:
        """Parse FDA indication text to extract line-of-therapy and approval type for a specific tumor.

        Returns dict with:
        - tumor_match: bool - whether indication mentions this tumor type
        - line_of_therapy: 'first-line' | 'later-line' | 'unspecified'
        - approval_type: 'full' | 'accelerated' | 'unspecified'
        - indication_excerpt: str - relevant excerpt from indication text
        """
        if not self.indication or not tumor_type:
            return {
                'tumor_match': False,
                'line_of_therapy': 'unspecified',
                'approval_type': 'unspecified',
                'indication_excerpt': ''
            }

        indication_lower = self.indication.lower()
        tumor_lower = tumor_type.lower()

        # Check for tumor type match (flexible matching)
        tumor_keywords = {
            'colorectal': ['colorectal', 'colon', 'rectal', 'crc', 'mcrc'],
            'melanoma': ['melanoma'],
            'lung': ['lung', 'nsclc', 'non-small cell'],
            'breast': ['breast'],
            'thyroid': ['thyroid', 'atc', 'anaplastic thyroid'],
        }

        tumor_match = False
        matched_section = ""

        # Find which tumor keywords to use
        tumor_keys = []
        for key, keywords in tumor_keywords.items():
            if any(kw in tumor_lower for kw in keywords):
                tumor_keys = keywords
                break
        if not tumor_keys:
            tumor_keys = [tumor_lower]

        # Find the relevant section of the indication
        # Need to capture the FULL tumor-specific section, not just first 500 chars
        for kw in tumor_keys:
            if kw in indication_lower:
                tumor_match = True
                # Extract a larger window to capture all indications for this tumor
                idx = indication_lower.find(kw)
                start = max(0, idx - 50)
                # Look for next major section (other tumor types) to find end
                # Use section headers that clearly indicate a new tumor type
                next_section_markers = [
                    'non-small cell lung cancer',
                    'nsclc)',  # Parenthetical NSCLC
                    'melanoma •',
                    'breast cancer',
                    'thyroid cancer',
                    'limitations of use',
                    '1.1 braf',  # Next numbered section
                    '1.2 braf',
                    '1.3 braf',
                    '1.4 ',
                ]
                end = len(self.indication)
                for next_sec in next_section_markers:
                    next_idx = indication_lower.find(next_sec, idx + len(kw) + 100)
                    if next_idx > idx and next_idx < end:
                        end = next_idx
                matched_section = self.indication[start:end]
                break

        if not tumor_match:
            return {
                'tumor_match': False,
                'line_of_therapy': 'unspecified',
                'approval_type': 'unspecified',
                'indication_excerpt': ''
            }

        # Determine line of therapy
        later_line_phrases = [
            'after prior therapy',
            'after progression',
            'following progression',
            'following recurrence',
            'second-line',
            'second line',
            'third-line',
            'third line',
            'previously treated',
            'refractory',
            'who have failed',
            'after failure',
            'following prior',
            'disease progression',
        ]

        first_line_phrases = [
            'first-line',
            'first line',
            'frontline',
            'initial treatment',
            'treatment-naive',
            'previously untreated',
        ]

        matched_lower = matched_section.lower()
        line_of_therapy = 'unspecified'

        for phrase in later_line_phrases:
            if phrase in matched_lower:
                line_of_therapy = 'later-line'
                break

        if line_of_therapy == 'unspecified':
            for phrase in first_line_phrases:
                if phrase in matched_lower:
                    line_of_therapy = 'first-line'
                    break

        # Determine approval type
        approval_type = 'full'
        accelerated_phrases = [
            'accelerated approval',
            'approved under accelerated',
            'contingent upon verification',
            'confirmatory trial',
        ]

        for phrase in accelerated_phrases:
            if phrase in matched_lower:
                approval_type = 'accelerated'
                break

        return {
            'tumor_match': True,
            'line_of_therapy': line_of_therapy,
            'approval_type': approval_type,
            'indication_excerpt': matched_section[:300]
        }


class CGIBiomarkerEvidence(BaseModel):
    """Evidence from Cancer Genome Interpreter biomarkers database.

    CGI provides curated biomarker-drug associations with explicit
    FDA/NCCN approval status, complementing FDA label searches.
    """

    gene: str | None = None
    alteration: str | None = None
    drug: str | None = None
    drug_status: str | None = None  # "Approved", "Clinical trial", etc.
    association: str | None = None  # "Responsive", "Resistant"
    evidence_level: str | None = None  # "FDA guidelines", "NCCN guidelines", etc.
    source: str | None = None
    tumor_type: str | None = None
    fda_approved: bool = False


class VICCEvidence(BaseModel):
    """Evidence from VICC MetaKB (harmonized multi-KB interpretations).

    VICC aggregates and harmonizes clinical interpretations from:
    - CIViC, CGI, JAX-CKB, OncoKB, PMKB, MolecularMatch

    Evidence levels: A (validated), B (clinical), C (case study), D (preclinical)
    Response types: Responsive/Sensitivity, Resistant, or OncoKB levels (1A, 1B, etc.)
    """

    description: str | None = None
    gene: str | None = None
    variant: str | None = None
    disease: str | None = None
    drugs: list[str] = Field(default_factory=list)
    evidence_level: str | None = None  # A, B, C, D
    response_type: str | None = None  # Responsive, Resistant, Sensitivity, 1A, etc.
    source: str | None = None  # civic, cgi, jax, oncokb, pmkb
    publication_url: str | list[str] | None = None  # Can be single URL or list
    oncogenic: str | None = None
    is_sensitivity: bool = False
    is_resistance: bool = False
    oncokb_level: str | None = None  # 1A, 1B, 2A, 2B, 3A, 3B, 4, R1, R2


class CIViCAssertionEvidence(BaseModel):
    """Evidence from CIViC Assertions (curated AMP/ASCO/CAP classifications).

    CIViC Assertions provide expert-curated clinical interpretations with:
    - AMP/ASCO/CAP tier assignments (Tier I/II/III/IV, Level A/B/C/D)
    - FDA companion diagnostic status
    - NCCN guideline references

    This complements VICC/CGI by providing authoritative tier classifications
    that align with professional guidelines (similar to ESCAT but open source).
    """

    assertion_id: int | None = None
    name: str | None = None  # e.g., "AID5"
    amp_level: str | None = None  # e.g., "TIER_I_LEVEL_A"
    amp_tier: str | None = None  # e.g., "Tier I"
    amp_level_letter: str | None = None  # e.g., "A"
    assertion_type: str | None = None  # PREDICTIVE, PROGNOSTIC, DIAGNOSTIC, ONCOGENIC
    significance: str | None = None  # SENSITIVITYRESPONSE, RESISTANCE, etc.
    status: str | None = None  # ACCEPTED, SUBMITTED
    molecular_profile: str | None = None  # e.g., "EGFR L858R"
    disease: str | None = None
    therapies: list[str] = Field(default_factory=list)
    fda_companion_test: bool | None = None
    nccn_guideline: str | None = None
    description: str | None = None
    is_sensitivity: bool = False
    is_resistance: bool = False


class Evidence(VariantAnnotations):
    """Aggregated evidence from multiple sources."""

    variant_id: str
    gene: str
    variant: str

    # Evidence from databases
    civic: list[CIViCEvidence] = Field(default_factory=list)
    clinvar: list[ClinVarEvidence] = Field(default_factory=list)
    cosmic: list[COSMICEvidence] = Field(default_factory=list)
    fda_approvals: list[FDAApproval] = Field(default_factory=list)
    cgi_biomarkers: list[CGIBiomarkerEvidence] = Field(default_factory=list)
    vicc: list[VICCEvidence] = Field(default_factory=list)
    civic_assertions: list[CIViCAssertionEvidence] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)

    def has_evidence(self) -> bool:
        """Check if any evidence was found."""
        return bool(self.civic or self.clinvar or self.cosmic or self.fda_approvals or self.cgi_biomarkers or self.vicc or self.civic_assertions)

    @staticmethod
    def _tumor_matches(tumor_type: str | None, disease: str | None) -> bool:
        """Check if tumor type matches disease using flexible matching.

        Args:
            tumor_type: User-provided tumor type (e.g., 'CRC', 'NSCLC')
            disease: Disease from evidence database (e.g., 'Colorectal Cancer')

        Returns:
            True if they match
        """
        if not tumor_type or not disease:
            return False

        tumor_lower = tumor_type.lower().strip()
        disease_lower = disease.lower().strip()

        # Direct substring match
        if tumor_lower in disease_lower or disease_lower in tumor_lower:
            return True

        # Check tumor type mappings
        for abbrev, full_names in TUMOR_TYPE_MAPPINGS.items():
            # If user's tumor_type matches an abbreviation or full name
            if tumor_lower == abbrev or any(tumor_lower in name for name in full_names):
                # Check if disease matches any of the full names
                if any(name in disease_lower for name in full_names):
                    return True

        return False

    def compute_evidence_stats(self, tumor_type: str | None = None) -> dict:
        """Compute summary statistics and detect conflicts in the evidence.

        Returns a dict with:
        - sensitivity_count: total sensitivity entries
        - resistance_count: total resistance entries
        - sensitivity_by_level: dict of level -> count
        - resistance_by_level: dict of level -> count
        - conflicts: list of {drug, sensitivity_context, resistance_context}
        - dominant_signal: 'sensitivity', 'resistance', 'mixed', or 'none'
        - has_fda_approved: bool
        """
        stats = {
            'sensitivity_count': 0,
            'resistance_count': 0,
            'sensitivity_by_level': {},
            'resistance_by_level': {},
            'conflicts': [],
            'dominant_signal': 'none',
            'has_fda_approved': bool(self.fda_approvals) or any(b.fda_approved for b in self.cgi_biomarkers),
        }

        # Track drugs with their signals for conflict detection
        drug_signals: dict[str, dict] = {}  # drug -> {'sensitivity': [...], 'resistance': [...]}

        def add_drug_signal(drug: str, signal_type: str, level: str | None, disease: str | None):
            drug_lower = drug.lower().strip()
            if drug_lower not in drug_signals:
                drug_signals[drug_lower] = {'sensitivity': [], 'resistance': [], 'drug_name': drug}
            drug_signals[drug_lower][signal_type].append({'level': level, 'disease': disease})

        # Process VICC evidence
        for ev in self.vicc:
            level = ev.evidence_level or 'Unknown'
            if ev.is_sensitivity:
                stats['sensitivity_count'] += 1
                stats['sensitivity_by_level'][level] = stats['sensitivity_by_level'].get(level, 0) + 1
                for drug in ev.drugs:
                    add_drug_signal(drug, 'sensitivity', level, ev.disease)
            elif ev.is_resistance:
                stats['resistance_count'] += 1
                stats['resistance_by_level'][level] = stats['resistance_by_level'].get(level, 0) + 1
                for drug in ev.drugs:
                    add_drug_signal(drug, 'resistance', level, ev.disease)

        # Process CIViC evidence
        for ev in self.civic:
            if ev.evidence_type != "PREDICTIVE":
                continue
            level = ev.evidence_level or 'Unknown'
            sig = (ev.clinical_significance or '').upper()
            if 'RESISTANCE' in sig:
                stats['resistance_count'] += 1
                stats['resistance_by_level'][level] = stats['resistance_by_level'].get(level, 0) + 1
                for drug in ev.drugs:
                    add_drug_signal(drug, 'resistance', level, ev.disease)
            elif 'SENSITIVITY' in sig or 'RESPONSE' in sig:
                stats['sensitivity_count'] += 1
                stats['sensitivity_by_level'][level] = stats['sensitivity_by_level'].get(level, 0) + 1
                for drug in ev.drugs:
                    add_drug_signal(drug, 'sensitivity', level, ev.disease)

        # Detect conflicts (same drug with both sensitivity and resistance)
        for drug_lower, signals in drug_signals.items():
            if signals['sensitivity'] and signals['resistance']:
                # Summarize contexts
                sens_diseases = list(set(s['disease'][:50] if s['disease'] else 'unspecified' for s in signals['sensitivity'][:3]))
                res_diseases = list(set(s['disease'][:50] if s['disease'] else 'unspecified' for s in signals['resistance'][:3]))
                stats['conflicts'].append({
                    'drug': signals['drug_name'],
                    'sensitivity_context': ', '.join(sens_diseases),
                    'resistance_context': ', '.join(res_diseases),
                    'sensitivity_count': len(signals['sensitivity']),
                    'resistance_count': len(signals['resistance']),
                })

        # Determine dominant signal
        total = stats['sensitivity_count'] + stats['resistance_count']
        if total == 0:
            stats['dominant_signal'] = 'none'
        elif stats['sensitivity_count'] == 0:
            stats['dominant_signal'] = 'resistance_only'
        elif stats['resistance_count'] == 0:
            stats['dominant_signal'] = 'sensitivity_only'
        elif stats['sensitivity_count'] >= total * 0.8:
            stats['dominant_signal'] = 'sensitivity_dominant'
        elif stats['resistance_count'] >= total * 0.8:
            stats['dominant_signal'] = 'resistance_dominant'
        else:
            stats['dominant_signal'] = 'mixed'

        return stats

    def format_evidence_summary_header(self, tumor_type: str | None = None) -> str:
        """Generate a pre-processed summary header with stats and conflicts.

        This appears BEFORE the detailed evidence to guide LLM interpretation.
        """
        stats = self.compute_evidence_stats(tumor_type)
        lines = []

        lines.append("=" * 60)
        lines.append("EVIDENCE SUMMARY (Pre-processed)")
        lines.append("=" * 60)

        # Overall stats
        total = stats['sensitivity_count'] + stats['resistance_count']
        if total > 0:
            sens_pct = (stats['sensitivity_count'] / total) * 100
            res_pct = (stats['resistance_count'] / total) * 100

            # Format by-level breakdown
            sens_levels = ', '.join(f"{k}:{v}" for k, v in sorted(stats['sensitivity_by_level'].items()))
            res_levels = ', '.join(f"{k}:{v}" for k, v in sorted(stats['resistance_by_level'].items()))

            lines.append(f"Sensitivity entries: {stats['sensitivity_count']} ({sens_pct:.0f}%) - Levels: {sens_levels or 'none'}")
            lines.append(f"Resistance entries: {stats['resistance_count']} ({res_pct:.0f}%) - Levels: {res_levels or 'none'}")

            # Dominant signal interpretation
            signal_interpretations = {
                'sensitivity_only': "INTERPRETATION: All evidence shows sensitivity. No resistance signals.",
                'resistance_only': "INTERPRETATION: All evidence shows resistance. This is a RESISTANCE MARKER.",
                'sensitivity_dominant': f"INTERPRETATION: Sensitivity evidence strongly predominates ({sens_pct:.0f}%). Minor resistance signals likely context-specific.",
                'resistance_dominant': f"INTERPRETATION: Resistance evidence strongly predominates ({res_pct:.0f}%). Minor sensitivity signals likely context-specific.",
                'mixed': "INTERPRETATION: Mixed signals - carefully evaluate tumor type and drug contexts below.",
            }
            if stats['dominant_signal'] in signal_interpretations:
                lines.append(signal_interpretations[stats['dominant_signal']])
        else:
            lines.append("No sensitivity/resistance evidence found in databases.")

        # FDA status - check for resistance markers specifically
        fda_resistance_markers = [b for b in self.cgi_biomarkers
                                   if b.fda_approved and b.association and 'RESIST' in b.association.upper()]
        if fda_resistance_markers:
            drugs = list(set(b.drug for b in fda_resistance_markers if b.drug))[:3]
            lines.append(f"FDA STATUS: This is an FDA-MANDATED RESISTANCE BIOMARKER - variant EXCLUDES use of: {', '.join(drugs)}")
            lines.append("ACTIONABILITY: This is Tier II (or potentially Tier I) because it changes treatment decisions (do NOT use these drugs).")
        elif stats['has_fda_approved']:
            lines.append("FDA STATUS: Has FDA-approved therapy associated with this gene.")

        # Check for later-line/accelerated approvals - important for tier classification
        if tumor_type and self.fda_approvals:
            later_line_approvals = []
            first_line_approvals = []
            for approval in self.fda_approvals:
                parsed = approval.parse_indication_for_tumor(tumor_type)
                if parsed['tumor_match']:
                    drug = approval.brand_name or approval.generic_name or approval.drug_name
                    if parsed['line_of_therapy'] == 'later-line':
                        accel_note = " (ACCELERATED)" if parsed['approval_type'] == 'accelerated' else ""
                        later_line_approvals.append(f"{drug}{accel_note}")
                    elif parsed['line_of_therapy'] == 'first-line':
                        first_line_approvals.append(drug)

            if later_line_approvals and not first_line_approvals:
                lines.append("")
                lines.append("FDA APPROVAL CONTEXT:")
                lines.append(f"  LATER-LINE ONLY: {', '.join(later_line_approvals)}")
                lines.append("  → No first-line FDA approval for this variant+tumor. This typically indicates TIER II, not Tier I.")
                lines.append("  → Tier I requires first-line therapy OR the biomarker being THE standard approach at that line.")
            elif first_line_approvals:
                lines.append("")
                lines.append(f"FDA FIRST-LINE APPROVAL: {', '.join(first_line_approvals)} → Strong Tier I signal")

        # Conflicts
        if stats['conflicts']:
            lines.append("")
            lines.append("CONFLICTS DETECTED:")
            for conflict in stats['conflicts'][:5]:  # Limit to 5 conflicts
                lines.append(f"  - {conflict['drug']}: "
                           f"SENSITIVITY in {conflict['sensitivity_context']} ({conflict['sensitivity_count']} entries) "
                           f"vs RESISTANCE in {conflict['resistance_context']} ({conflict['resistance_count']} entries)")

        lines.append("=" * 60)
        lines.append("")

        return "\n".join(lines)

    def filter_low_quality_minority_signals(self) -> tuple[list["VICCEvidence"], list["VICCEvidence"]]:
        """Filter out low-quality minority signals from VICC evidence.

        If we have Level A/B sensitivity evidence and only Level C/D resistance,
        the resistance is likely noise from case reports and should be filtered.
        Similarly, if we have Level A/B resistance and only Level C/D sensitivity.

        Returns:
            Tuple of (filtered_sensitivity, filtered_resistance) VICC entries
        """
        sensitivity = [e for e in self.vicc if e.is_sensitivity]
        resistance = [e for e in self.vicc if e.is_resistance]

        # Check evidence quality levels
        high_quality_levels = {'A', 'B'}
        low_quality_levels = {'C', 'D'}

        sens_levels = {e.evidence_level for e in sensitivity if e.evidence_level}
        res_levels = {e.evidence_level for e in resistance if e.evidence_level}

        sens_has_high = bool(sens_levels & high_quality_levels)
        sens_only_low = sens_levels and sens_levels <= low_quality_levels
        res_has_high = bool(res_levels & high_quality_levels)
        res_only_low = res_levels and res_levels <= low_quality_levels

        # Filter out low-quality minority signals
        if sens_has_high and res_only_low and len(resistance) <= 2:
            # Strong sensitivity, weak resistance - drop resistance
            return sensitivity, []
        elif res_has_high and sens_only_low and len(sensitivity) <= 2:
            # Strong resistance, weak sensitivity - drop sensitivity
            return [], resistance

        return sensitivity, resistance

    def aggregate_evidence_by_drug(self, tumor_type: str | None = None) -> list[dict]:
        """Aggregate evidence entries by drug for cleaner LLM presentation.

        Instead of showing 5 separate Erlotinib entries, show:
        "Erlotinib: 4 sensitivity (A:1, B:2, C:1), 1 resistance (C:1) → net: SENSITIVE"

        Returns:
            List of drug aggregation dicts with keys:
            - drug: drug name
            - sensitivity_count, resistance_count
            - sensitivity_levels, resistance_levels (dict of level -> count)
            - diseases: list of unique diseases
            - net_signal: 'SENSITIVE', 'RESISTANT', or 'MIXED'
            - best_level: highest evidence level (A > B > C > D)
        """
        drug_data: dict[str, dict] = {}

        def add_entry(drug: str, is_sens: bool, level: str | None, disease: str | None):
            drug_key = drug.lower().strip()
            if drug_key not in drug_data:
                drug_data[drug_key] = {
                    'drug': drug,
                    'sensitivity_count': 0,
                    'resistance_count': 0,
                    'sensitivity_levels': {},
                    'resistance_levels': {},
                    'diseases': set(),
                    'best_level': 'D',
                }
            entry = drug_data[drug_key]
            if is_sens:
                entry['sensitivity_count'] += 1
                lvl = level or 'Unknown'
                entry['sensitivity_levels'][lvl] = entry['sensitivity_levels'].get(lvl, 0) + 1
            else:
                entry['resistance_count'] += 1
                lvl = level or 'Unknown'
                entry['resistance_levels'][lvl] = entry['resistance_levels'].get(lvl, 0) + 1
            if disease:
                entry['diseases'].add(disease[:50])  # Truncate long disease names
            # Update best level
            level_priority = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
            if level and level_priority.get(level, 99) < level_priority.get(entry['best_level'], 99):
                entry['best_level'] = level

        # Process VICC evidence
        for ev in self.vicc:
            for drug in ev.drugs:
                add_entry(drug, ev.is_sensitivity, ev.evidence_level, ev.disease)

        # Process CIViC evidence
        for ev in self.civic:
            if ev.evidence_type != "PREDICTIVE":
                continue
            sig = (ev.clinical_significance or '').upper()
            is_sens = 'SENSITIVITY' in sig or 'RESPONSE' in sig
            is_res = 'RESISTANCE' in sig
            if not is_sens and not is_res:
                continue
            for drug in ev.drugs:
                add_entry(drug, is_sens, ev.evidence_level, ev.disease)

        # Calculate net signal for each drug
        results = []
        for drug_key, data in drug_data.items():
            sens = data['sensitivity_count']
            res = data['resistance_count']
            if sens > 0 and res == 0:
                net_signal = 'SENSITIVE'
            elif res > 0 and sens == 0:
                net_signal = 'RESISTANT'
            elif sens >= res * 3:  # 3:1 ratio = clearly sensitive
                net_signal = 'SENSITIVE'
            elif res >= sens * 3:  # 3:1 ratio = clearly resistant
                net_signal = 'RESISTANT'
            else:
                net_signal = 'MIXED'

            data['net_signal'] = net_signal
            data['diseases'] = list(data['diseases'])[:5]  # Convert to list, limit to 5
            results.append(data)

        # Sort by best evidence level, then by total entries
        level_priority = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        results.sort(key=lambda x: (level_priority.get(x['best_level'], 99), -(x['sensitivity_count'] + x['resistance_count'])))

        return results

    def format_drug_aggregation_summary(self, tumor_type: str | None = None) -> str:
        """Format drug-level aggregation for LLM prompt.

        Returns a concise summary like:
        DRUG-LEVEL SUMMARY:
        1. Vemurafenib: 5 sens (A:2, B:3), 0 res → SENSITIVE [Level A]
        2. Erlotinib: 3 sens (B:2, C:1), 2 res (C:2) → MIXED [Level B]
        """
        aggregated = self.aggregate_evidence_by_drug(tumor_type)
        if not aggregated:
            return ""

        lines = ["", "DRUG-LEVEL SUMMARY (aggregated from all sources):"]

        for idx, drug in enumerate(aggregated[:10], 1):  # Top 10 drugs
            sens_str = f"{drug['sensitivity_count']} sens"
            if drug['sensitivity_levels']:
                levels = ', '.join(f"{k}:{v}" for k, v in sorted(drug['sensitivity_levels'].items()))
                sens_str += f" ({levels})"

            res_str = f"{drug['resistance_count']} res"
            if drug['resistance_levels']:
                levels = ', '.join(f"{k}:{v}" for k, v in sorted(drug['resistance_levels'].items()))
                res_str += f" ({levels})"

            lines.append(f"  {idx}. {drug['drug']}: {sens_str}, {res_str} → {drug['net_signal']} [Level {drug['best_level']}]")

        lines.append("")
        return "\n".join(lines)

    def summary_compact(self, tumor_type: str | None = None) -> str:
        """Generate a compact summary - FDA approvals and CGI only (no verbose VICC/CIViC).

        Used when drug aggregation summary is provided separately.
        This reduces prompt size by ~50-70% while keeping tier-critical info.
        """
        lines = [f"Evidence for {self.gene} {self.variant}:\n"]

        if self.fda_approvals:
            lines.append(f"FDA Approved Drugs ({len(self.fda_approvals)}):")
            for approval in self.fda_approvals[:5]:
                drug = approval.brand_name or approval.generic_name or approval.drug_name

                # Check if variant is explicitly mentioned in clinical studies (strong Tier I signal)
                variant_explicit = approval.variant_in_clinical_studies

                # Parse indication for tumor-specific metadata
                if tumor_type:
                    parsed = approval.parse_indication_for_tumor(tumor_type)
                    if parsed['tumor_match'] or variant_explicit:
                        # Show structured metadata for this tumor type
                        line_info = parsed['line_of_therapy'].upper() if parsed['tumor_match'] else "UNSPECIFIED"
                        approval_info = parsed['approval_type'].upper() if parsed['tumor_match'] else "UNSPECIFIED"

                        # Emphasize if variant is explicitly in FDA label clinical studies
                        variant_note = ""
                        if variant_explicit:
                            variant_note = " *** VARIANT EXPLICITLY IN FDA LABEL ***"

                        lines.append(f"  • {drug} [FOR {tumor_type.upper()}]{variant_note}:")
                        lines.append(f"      Line of therapy: {line_info}")
                        lines.append(f"      Approval type: {approval_info}")

                        # Show the clinical studies excerpt if variant is mentioned there
                        indication = approval.indication or ""
                        if "[Clinical studies mention" in indication:
                            # Extract and show the clinical studies note
                            cs_start = indication.find("[Clinical studies mention")
                            cs_excerpt = indication[cs_start:cs_start+400]
                            lines.append(f"      {cs_excerpt}...")
                        else:
                            lines.append(f"      Excerpt: {parsed['indication_excerpt'][:200]}...")
                    else:
                        # Drug approved but not for this tumor type
                        indication = (approval.indication or "")[:300]
                        lines.append(f"  • {drug} [OTHER INDICATIONS]: {indication}...")
                else:
                    # No tumor type specified, show raw indication
                    indication = (approval.indication or "")[:800]
                    lines.append(f"  • {drug}: {indication}...")
            lines.append("")

        if self.cgi_biomarkers:
            approved = [b for b in self.cgi_biomarkers if b.fda_approved]
            if approved:
                # Separate resistance and sensitivity markers - resistance markers are HIGHLY actionable
                resistance_approved = [b for b in approved if b.association and 'RESIST' in b.association.upper()]
                sensitivity_approved = [b for b in approved if b.association and 'RESIST' not in b.association.upper()]

                if resistance_approved:
                    lines.append(f"CGI FDA-APPROVED RESISTANCE MARKERS ({len(resistance_approved)}):")
                    lines.append("  *** THESE VARIANTS EXCLUDE USE OF FDA-APPROVED THERAPIES ***")
                    for b in resistance_approved[:5]:
                        lines.append(f"  • {b.drug} [{b.association.upper()}] in {b.tumor_type or 'solid tumors'} - Evidence: {b.evidence_level}")
                    lines.append("  → This variant causes RESISTANCE to the above drug(s), making it Tier I/II actionable as a NEGATIVE biomarker.")
                    lines.append("")

                if sensitivity_approved:
                    lines.append(f"CGI FDA-Approved Sensitivity Biomarkers ({len(sensitivity_approved)}):")
                    for b in sensitivity_approved[:5]:
                        lines.append(f"  • {b.drug} [{b.association}] in {b.tumor_type or 'solid tumors'} - Evidence: {b.evidence_level}")
                    lines.append("")

        # CIViC Assertions - curated AMP/ASCO/CAP tier classifications
        # IMPORTANT: Separate PREDICTIVE (therapy-related) from PROGNOSTIC (outcome-related)
        if self.civic_assertions:
            # Separate by assertion type - PREDICTIVE matters for therapy actionability
            predictive_tier_i = [a for a in self.civic_assertions
                                  if a.amp_tier == "Tier I" and a.assertion_type == "PREDICTIVE"]
            predictive_tier_ii = [a for a in self.civic_assertions
                                   if a.amp_tier == "Tier II" and a.assertion_type == "PREDICTIVE"]
            prognostic = [a for a in self.civic_assertions if a.assertion_type == "PROGNOSTIC"]

            # PREDICTIVE Tier I = therapy actionability (most relevant for tier classification)
            if predictive_tier_i:
                lines.append(f"CIViC PREDICTIVE TIER I ASSERTIONS ({len(predictive_tier_i)}):")
                lines.append("  *** EXPERT-CURATED - THERAPY ACTIONABLE ***")
                for a in predictive_tier_i[:5]:
                    therapies = ", ".join(a.therapies) if a.therapies else "N/A"
                    fda_note = " [FDA Companion Test]" if a.fda_companion_test else ""
                    nccn_note = f" [NCCN: {a.nccn_guideline}]" if a.nccn_guideline else ""
                    lines.append(f"  • {a.molecular_profile}: {therapies} [{a.significance}]{fda_note}{nccn_note}")
                    lines.append(f"      AMP Level: {a.amp_level}, Disease: {a.disease}")
                lines.append("")

            if predictive_tier_ii:
                lines.append(f"CIViC Predictive Tier II Assertions ({len(predictive_tier_ii)}):")
                for a in predictive_tier_ii[:3]:
                    therapies = ", ".join(a.therapies) if a.therapies else "N/A"
                    lines.append(f"  • {a.molecular_profile}: {therapies} [{a.significance}]")
                lines.append("")

            # PROGNOSTIC assertions - important but do NOT determine therapy tier
            if prognostic:
                lines.append(f"CIViC PROGNOSTIC Assertions ({len(prognostic)}):")
                lines.append("  *** PROGNOSTIC ONLY - indicates outcome, NOT therapy actionability ***")
                for a in prognostic[:3]:
                    lines.append(f"  • {a.molecular_profile}: {a.significance} in {a.disease}")
                    if a.amp_tier:
                        lines.append(f"      (Prognostic {a.amp_tier} - does NOT imply Tier I/II for therapy)")
                lines.append("")

        if self.clinvar:
            sig = self.clinvar[0].clinical_significance if self.clinvar else None
            if sig:
                lines.append(f"ClinVar: {sig}")
                lines.append("")

        return "\n".join(lines) if len(lines) > 1 else ""

    def summary(self, tumor_type: str | None = None, max_items: int = 15) -> str:
        """Generate a text summary of all evidence.

        Args:
            tumor_type: Optional tumor type to filter and prioritize evidence
            max_items: Maximum number of evidence items to include (default: 15)

        Returns:
            Formatted evidence summary
        """
        lines = [f"Evidence for {self.gene} {self.variant}:\n"]

        if self.civic:
            # Helper function to sort by evidence level (A > B > C > D > E > None)
            def evidence_level_key(ev):
                level_priority = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4}
                return level_priority.get(ev.evidence_level, 99)

            # Filter and prioritize CIViC evidence
            civic_evidence = list(self.civic)

            # Priority 1: Tumor-specific SENSITIVITY evidence (most actionable for treatment)
            tumor_sensitivity = []
            if tumor_type:
                tumor_sensitivity = [e for e in civic_evidence
                                     if self._tumor_matches(tumor_type, e.disease)
                                     and e.evidence_type == "PREDICTIVE"
                                     and e.clinical_significance
                                     and "RESISTANCE" not in e.clinical_significance.upper()]
                tumor_sensitivity = sorted(tumor_sensitivity, key=evidence_level_key)

            # Priority 2: Tumor-specific RESISTANCE evidence (important for avoiding drugs)
            tumor_resistance = []
            if tumor_type:
                tumor_resistance = [e for e in civic_evidence
                                    if self._tumor_matches(tumor_type, e.disease)
                                    and e.evidence_type == "PREDICTIVE"
                                    and e.clinical_significance
                                    and "RESISTANCE" in e.clinical_significance.upper()
                                    and e not in tumor_sensitivity]
                tumor_resistance = sorted(tumor_resistance, key=evidence_level_key)

            # Priority 3: Other PREDICTIVE with drugs and SENSITIVITY
            other_sensitivity = [e for e in civic_evidence
                                 if e.evidence_type == "PREDICTIVE" and e.drugs
                                 and e.clinical_significance
                                 and "RESISTANCE" not in e.clinical_significance.upper()
                                 and e not in tumor_sensitivity
                                 and e not in tumor_resistance]
            other_sensitivity = sorted(other_sensitivity, key=evidence_level_key)

            # Priority 4: Other RESISTANCE evidence
            other_resistance = [e for e in civic_evidence
                                if e.evidence_type == "PREDICTIVE"
                                and e.clinical_significance
                                and "RESISTANCE" in e.clinical_significance.upper()
                                and e not in tumor_sensitivity
                                and e not in tumor_resistance
                                and e not in other_sensitivity]
            other_resistance = sorted(other_resistance, key=evidence_level_key)

            # Priority 5: Remaining evidence
            remaining = [e for e in civic_evidence
                         if e not in tumor_sensitivity
                         and e not in tumor_resistance
                         and e not in other_sensitivity
                         and e not in other_resistance]
            remaining = sorted(remaining, key=evidence_level_key)

            # Combine in priority order
            # CRITICAL: Interleave sensitivity and resistance to ensure both are represented
            # Take top entries from each category proportionally
            max_per_category = max(max_items // 3, 3)  # At least 3 per major category

            prioritized = []
            # Add tumor-specific entries (interleaved)
            for i in range(max(len(tumor_sensitivity), len(tumor_resistance))):
                if i < len(tumor_sensitivity):
                    prioritized.append(tumor_sensitivity[i])
                if i < len(tumor_resistance):
                    prioritized.append(tumor_resistance[i])

            # Then add other sensitivity
            prioritized.extend(other_sensitivity[:max_per_category])
            # Then other resistance
            prioritized.extend(other_resistance[:max_per_category])
            # Then remaining
            prioritized.extend(remaining[:max_per_category])

            lines.append(f"CIViC Evidence ({len(self.civic)} entries, showing top {min(len(prioritized), max_items)}):")
            for idx, ev in enumerate(prioritized[:max_items], 1):
                lines.append(f"  {idx}. Type: {ev.evidence_type or 'Unknown'} | Level: {ev.evidence_level or 'N/A'}")
                if ev.disease:
                    lines.append(f"     Disease: {ev.disease}")
                if ev.drugs:
                    lines.append(f"     Drugs: {', '.join(ev.drugs)}")
                if ev.clinical_significance:
                    lines.append(f"     Significance: {ev.clinical_significance}")
                if ev.description:
                    # Include more of the description
                    desc = ev.description[:300] if len(ev.description) > 300 else ev.description
                    lines.append(f"     Description: {desc}...")
            lines.append("")

        if self.clinvar:
            lines.append(f"ClinVar Evidence ({len(self.clinvar)} entries):")
            for idx, ev in enumerate(self.clinvar[:5], 1):
                lines.append(f"  {idx}. Significance: {ev.clinical_significance or 'Unknown'}")
                if ev.conditions:
                    lines.append(f"     Conditions: {', '.join(ev.conditions)}")
                if ev.review_status:
                    lines.append(f"     Review Status: {ev.review_status}")
            lines.append("")

        if self.cosmic:
            lines.append(f"COSMIC Evidence ({len(self.cosmic)} entries):")
            for idx, ev in enumerate(self.cosmic[:5], 1):
                lines.append(f"  {idx}. Primary Site: {ev.primary_site or 'Unknown'}")
                if ev.primary_histology:
                    lines.append(f"     Histology: {ev.primary_histology}")
                if ev.sample_count:
                    lines.append(f"     Sample Count: {ev.sample_count}")
            lines.append("")

        if self.fda_approvals:
            lines.append(f"FDA Approved Drugs ({len(self.fda_approvals)} entries):")
            for idx, approval in enumerate(self.fda_approvals[:10], 1):
                drug_display = approval.brand_name or approval.generic_name or approval.drug_name
                lines.append(f"  {idx}. Drug: {drug_display}")
                if approval.approval_date:
                    lines.append(f"     Approval Date: {approval.approval_date}")
                if approval.marketing_status:
                    lines.append(f"     Status: {approval.marketing_status}")
                if approval.indication:
                    # Show full indication text - critical for multi-indication drugs like Tafinlar
                    # which has ATC approval listed after melanoma/NSCLC indications
                    indication = approval.indication[:1500] if len(approval.indication) > 1500 else approval.indication
                    lines.append(f"     Indication: {indication}...")
            lines.append("")

        if self.cgi_biomarkers:
            # CGI biomarkers provide explicit FDA/NCCN approval status
            # Prioritize FDA-approved entries
            approved = [b for b in self.cgi_biomarkers if b.fda_approved]
            other = [b for b in self.cgi_biomarkers if not b.fda_approved]
            prioritized = approved + other

            lines.append(f"CGI Biomarkers ({len(self.cgi_biomarkers)} entries):")
            for idx, biomarker in enumerate(prioritized[:10], 1):
                status_marker = "[FDA APPROVED]" if biomarker.fda_approved else ""
                lines.append(f"  {idx}. Drug: {biomarker.drug} {status_marker}")
                lines.append(f"     Status: {biomarker.drug_status} | Evidence: {biomarker.evidence_level}")
                lines.append(f"     Association: {biomarker.association}")
                if biomarker.tumor_type:
                    lines.append(f"     Tumor Type: {biomarker.tumor_type}")
                if biomarker.source:
                    lines.append(f"     Source: {biomarker.source[:200]}...")
            lines.append("")

        if self.vicc:
            # VICC MetaKB provides harmonized evidence from multiple KBs
            # Prioritize by evidence level (A > B > C > D) and OncoKB levels
            def vicc_priority(ev):
                level_priority = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
                oncokb_priority = {'1A': 0, '1B': 1, '2A': 2, '2B': 3, '3A': 4, '3B': 5, '4': 6, 'R1': 7, 'R2': 8}
                base = level_priority.get(ev.evidence_level, 99)
                oncokb = oncokb_priority.get(ev.oncokb_level, 99) if ev.oncokb_level else 99
                return (base, oncokb)

            # Separate sensitivity and resistance
            sensitivity = [e for e in self.vicc if e.is_sensitivity]
            resistance = [e for e in self.vicc if e.is_resistance]
            other_vicc = [e for e in self.vicc if not e.is_sensitivity and not e.is_resistance]

            sensitivity = sorted(sensitivity, key=vicc_priority)
            resistance = sorted(resistance, key=vicc_priority)
            other_vicc = sorted(other_vicc, key=vicc_priority)

            # Interleave sensitivity and resistance
            vicc_prioritized = []
            for i in range(max(len(sensitivity), len(resistance))):
                if i < len(sensitivity):
                    vicc_prioritized.append(sensitivity[i])
                if i < len(resistance):
                    vicc_prioritized.append(resistance[i])
            vicc_prioritized.extend(other_vicc)

            lines.append(f"VICC MetaKB Evidence ({len(self.vicc)} entries, harmonized from CIViC/CGI/JAX/OncoKB/PMKB):")
            for idx, ev in enumerate(vicc_prioritized[:15], 1):
                level_str = f"Level {ev.evidence_level}" if ev.evidence_level else "N/A"
                oncokb_str = f" [OncoKB {ev.oncokb_level}]" if ev.oncokb_level else ""
                response_str = ""
                if ev.is_sensitivity:
                    response_str = " [SENSITIVITY]"
                elif ev.is_resistance:
                    response_str = " [RESISTANCE]"

                lines.append(f"  {idx}. {level_str}{oncokb_str}{response_str} (via {ev.source})")
                if ev.disease:
                    lines.append(f"     Disease: {ev.disease[:100]}...")
                if ev.drugs:
                    lines.append(f"     Drugs: {', '.join(ev.drugs[:5])}")
                if ev.description:
                    desc = ev.description[:250] if len(ev.description) > 250 else ev.description
                    lines.append(f"     Description: {desc}...")
            lines.append("")

        return "\n".join(lines) if len(lines) > 1 else "No evidence found."
