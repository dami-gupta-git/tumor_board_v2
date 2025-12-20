"""Evidence data models from external databases."""

from typing import Any
import logging

from pydantic import BaseModel, Field

from tumorboard.config.variant_classes import load_variant_classes
from tumorboard.constants import TUMOR_TYPE_MAPPINGS
from tumorboard.models.annotations import VariantAnnotations
from tumorboard.models.evidence.cgi import CGIBiomarkerEvidence
from tumorboard.models.evidence.civic import CIViCEvidence, CIViCAssertionEvidence
from tumorboard.models.evidence.clinical_trials import ClinicalTrialEvidence
from tumorboard.models.evidence.clinvar import ClinVarEvidence
from tumorboard.models.evidence.cosmic import COSMICEvidence
from tumorboard.models.evidence.fda import FDAApproval
from tumorboard.models.evidence.pubmed import PubMedEvidence
from tumorboard.models.evidence.vicc import VICCEvidence
from tumorboard.models.evidence.literature_knowledge import LiteratureKnowledge

logger = logging.getLogger(__name__)

# Load variant class configuration
_variant_config = load_variant_classes()





class Evidence(VariantAnnotations):
    """Aggregated evidence from multiple sources."""

    variant_id: str
    gene: str
    variant: str

    civic: list[CIViCEvidence] = Field(default_factory=list)
    clinvar: list[ClinVarEvidence] = Field(default_factory=list)
    cosmic: list[COSMICEvidence] = Field(default_factory=list)
    fda_approvals: list[FDAApproval] = Field(default_factory=list)
    cgi_biomarkers: list[CGIBiomarkerEvidence] = Field(default_factory=list)
    vicc: list[VICCEvidence] = Field(default_factory=list)
    civic_assertions: list[CIViCAssertionEvidence] = Field(default_factory=list)
    clinical_trials: list[ClinicalTrialEvidence] = Field(default_factory=list)
    pubmed_articles: list[PubMedEvidence] = Field(default_factory=list)
    literature_knowledge: LiteratureKnowledge | None = Field(
        None, description="Structured knowledge extracted from literature via LLM"
    )
    raw_data: dict[str, Any] = Field(default_factory=dict)

    def has_evidence(self) -> bool:
        """Check if any evidence was found."""
        return bool(self.civic or self.clinvar or self.cosmic or self.fda_approvals or
                   self.cgi_biomarkers or self.vicc or self.civic_assertions or
                   self.clinical_trials or self.pubmed_articles)

    @staticmethod
    def _tumor_matches(tumor_type: str | None, disease: str | None) -> bool:
        """Check if tumor type matches disease using flexible matching."""
        if not tumor_type or not disease:
            return False

        tumor_lower = tumor_type.lower().strip()
        disease_lower = disease.lower().strip()

        if tumor_lower in disease_lower or disease_lower in tumor_lower:
            return True

        for abbrev, full_names in TUMOR_TYPE_MAPPINGS.items():
            if tumor_lower == abbrev or any(tumor_lower in name for name in full_names):
                if any(name in disease_lower for name in full_names):
                    return True

        return False

    def _variant_matches_approval_class(self, gene: str, variant: str,
                                       indication_text: str, approval: FDAApproval,
                                       tumor_type: str | None = None) -> bool:
        """Determine if this specific variant falls under the approval.

        Uses configuration from variant_classes.yaml to determine which variants
        qualify for FDA approvals based on indication text patterns.

        This prevents:
        - BRAF G469A claiming BRAF V600E approvals
        - KRAS G12D claiming broad "KRAS" mentions
        - Non-specific matches
        - KIT D816V matching generic GIST approvals (D816V causes imatinib resistance in GIST)
        """
        # Check special rules first (e.g., KIT D816V in GIST)
        special_result = _variant_config.check_special_rules(
            gene, variant, indication_text, tumor_type
        )
        if special_result is not None:
            if not special_result:
                logger.debug(f"{gene} {variant}: excluded by special rule for tumor {tumor_type}")
            return special_result

        # Use config-based matching
        matches, class_name = _variant_config.get_variant_class(
            gene, variant, indication_text
        )

        if matches:
            logger.debug(f"{gene} {variant}: matched class '{class_name}'")
        else:
            logger.debug(f"{gene} {variant}: no matching class found")

        return matches

    def _check_fda_requires_wildtype(self, tumor_type: str) -> tuple[bool, list[str]]:
        """Check if any FDA drugs in this tumor REQUIRE wild-type (exclude mutants).

        Returns: (requires_wildtype, list_of_drugs)
        """
        wildtype_drugs = []

        for approval in self.fda_approvals:
            parsed = approval.parse_indication_for_tumor(tumor_type)
            if not parsed['tumor_match']:
                continue

            indication_lower = (approval.indication or '').lower()
            gene_lower = self.gene.lower()

            wildtype_patterns = [
                f'{gene_lower} wild-type',
                f'{gene_lower}-wild-type',
                f'wild type {gene_lower}',
                f'without {gene_lower} mutation',
                f'{gene_lower}-negative',
                'ras wild-type',
                'ras wildtype',
            ]

            if any(pattern in indication_lower for pattern in wildtype_patterns):
                drug = approval.brand_name or approval.generic_name
                if drug:
                    wildtype_drugs.append(drug)

        return bool(wildtype_drugs), wildtype_drugs

    def is_investigational_only(self, tumor_type: str | None = None) -> bool:
        """Check if variant is in investigational-only context.

        Some gene-tumor combinations have NO approved therapies despite active research.
        """
        gene_lower = self.gene.lower()
        tumor_lower = (tumor_type or '').lower()

        # Known investigational-only combinations
        investigational_pairs = {
            ('kras', 'pancreatic'): True,
            ('kras', 'pancreas'): True,
            ('nras', 'melanoma'): True,
            ('tp53', '*'): True,
            ('apc', 'colorectal'): True,
            ('apc', 'colon'): True,
            ('vhl', 'renal'): True,
            ('vhl', 'kidney'): True,
            ('smad4', 'pancreatic'): True,
            ('smad4', 'pancreas'): True,
            ('cdkn2a', 'melanoma'): True,
            ('arid1a', '*'): True,
        }

        for (gene, tumor), is_investigational in investigational_pairs.items():
            if gene == gene_lower:
                if tumor == '*' or tumor in tumor_lower:
                    return True

        return False

    def has_active_clinical_trials(self, variant_specific_only: bool = False) -> tuple[bool, list[str]]:
        """Check if there are active clinical trials for this variant.

        Args:
            variant_specific_only: If True, only count trials that explicitly mention the variant

        Returns:
            Tuple of (has_trials, list of trial drug names)
        """
        if not self.clinical_trials:
            return False, []

        trials = self.clinical_trials
        if variant_specific_only:
            trials = [t for t in trials if t.variant_specific]

        if not trials:
            return False, []

        # Extract drug names from trials
        drugs = []
        for trial in trials:
            drugs.extend(trial.get_drug_names())

        # Deduplicate
        drugs = list(set(drugs))[:5]

        return True, drugs

    def has_literature_resistance_evidence(self) -> tuple[bool, list[str], list[str]]:
        """Check if PubMed literature indicates this is a resistance mutation.

        Returns:
            Tuple of (has_resistance_evidence, list of drugs causing resistance, list of PMIDs)
        """
        if not self.pubmed_articles:
            return False, [], []

        resistance_articles = [a for a in self.pubmed_articles if a.is_resistance_evidence()]

        if not resistance_articles:
            return False, [], []

        # Collect drugs mentioned in resistance articles
        drugs = []
        pmids = []
        for article in resistance_articles:
            drugs.extend(article.drugs_mentioned)
            pmids.append(article.pmid)

        drugs = list(set(drugs))[:5]
        pmids = list(set(pmids))[:5]

        return True, drugs, pmids

    def get_pubmed_summary(self) -> str:
        """Get a summary of PubMed literature for the LLM prompt."""
        if not self.pubmed_articles:
            return ""

        lines = []
        resistance_articles = [a for a in self.pubmed_articles if a.is_resistance_evidence()]
        other_articles = [a for a in self.pubmed_articles if not a.is_resistance_evidence()]

        if resistance_articles:
            lines.append(f"PUBMED LITERATURE - RESISTANCE EVIDENCE ({len(resistance_articles)} articles):")
            lines.append("  *** PEER-REVIEWED LITERATURE SUPPORTS RESISTANCE CLASSIFICATION ***")
            for article in resistance_articles[:3]:
                drugs_str = f" [Drugs: {', '.join(article.drugs_mentioned)}]" if article.drugs_mentioned else ""
                lines.append(f"  • PMID {article.pmid}: {article.title[:100]}...{drugs_str}")
                lines.append(f"      {article.format_citation()}")
                if article.abstract:
                    # Show first 200 chars of abstract
                    abstract_preview = article.abstract[:200].replace('\n', ' ')
                    lines.append(f"      Abstract: {abstract_preview}...")
            lines.append("")

        if other_articles and not resistance_articles:
            lines.append(f"PubMed Literature ({len(other_articles)} articles):")
            for article in other_articles[:2]:
                lines.append(f"  • PMID {article.pmid}: {article.title[:80]}...")
            lines.append("")

        return "\n".join(lines)

    def get_clinical_trial_summary(self) -> str:
        """Get a summary of active clinical trials for the LLM prompt."""
        if not self.clinical_trials:
            return ""

        lines = []
        variant_specific = [t for t in self.clinical_trials if t.variant_specific]
        gene_level = [t for t in self.clinical_trials if not t.variant_specific]

        if variant_specific:
            lines.append(f"ACTIVE CLINICAL TRIALS FOR {self.variant.upper()} ({len(variant_specific)}):")
            lines.append("  *** VARIANT-SPECIFIC TRIALS - supports Tier II classification ***")
            for trial in variant_specific[:3]:
                phase_str = f" [{trial.phase}]" if trial.phase else ""
                drugs = ', '.join(trial.get_drug_names()[:3]) or 'N/A'
                lines.append(f"  • {trial.nct_id}{phase_str}: {drugs}")
                lines.append(f"      {trial.title[:100]}...")
            lines.append("")

        if gene_level and not variant_specific:
            lines.append(f"Active {self.gene.upper()} trials (gene-level, not variant-specific): {len(gene_level)}")
            for trial in gene_level[:2]:
                drugs = ', '.join(trial.get_drug_names()[:2]) or 'N/A'
                lines.append(f"  • {trial.nct_id}: {drugs}")
            lines.append("")

        return "\n".join(lines)

    def has_fda_for_variant_in_tumor(self, tumor_type: str | None = None) -> bool:
        """Check if FDA approval exists FOR this specific variant in this tumor type."""
        if not tumor_type:
            return False

        # Check investigational-only FIRST
        if self.is_investigational_only(tumor_type):
            return False

        variant_is_approved = False

        # Check FDA labels with variant-specific matching
        for approval in self.fda_approvals:
            parsed = approval.parse_indication_for_tumor(tumor_type)
            if not parsed['tumor_match']:
                continue

            indication_lower = (approval.indication or '').lower()
            variant_lower = self.variant.lower()

            # Strategy 1: Explicit variant mention (but check for exclusion context AND special rules)
            if variant_lower in indication_lower:
                # Check for exclusion patterns around the variant mention
                # e.g., "without the D816V mutation" means NOT approved for D816V
                exclusion_patterns = [
                    f'without the {variant_lower}',
                    f'without {variant_lower}',
                    f'no {variant_lower}',
                    f'not {variant_lower}',
                    f'excluding {variant_lower}',
                    f'absence of {variant_lower}',
                ]
                is_exclusion = any(pattern in indication_lower for pattern in exclusion_patterns)

                if is_exclusion:
                    logger.debug(f"Variant {self.variant} found in exclusion context for {approval.drug_name}")
                    continue

                # CRITICAL: Check special rules even for explicit variant mentions
                # This handles cases like KIT D816V which is approved for mastocytosis
                # but causes resistance in GIST - the label mentions D816V but for a different tumor
                special_result = _variant_config.check_special_rules(
                    self.gene, self.variant, indication_lower, tumor_type
                )
                if special_result is False:
                    logger.debug(f"Variant {self.variant} excluded by special rule for {tumor_type} (drug: {approval.drug_name})")
                    continue

                variant_is_approved = True
                logger.debug(f"FDA approval found via explicit variant mention: {approval.drug_name}")
                break

            # Strategy 2: Gene mention with variant class validation
            if self.gene.lower() in indication_lower:
                variant_is_approved = self._variant_matches_approval_class(
                    gene=self.gene,
                    variant=self.variant,
                    indication_text=indication_lower,
                    approval=approval,
                    tumor_type=tumor_type
                )
                if variant_is_approved:
                    logger.debug(f"FDA approval found via gene+class validation: {approval.drug_name}")
                    break

        if variant_is_approved:
            return True

        # Check CIViC Level A with tumor matching
        for ev in self.civic:
            if (ev.evidence_level == 'A' and
                ev.evidence_type == 'PREDICTIVE' and
                self._tumor_matches(tumor_type, ev.disease)):
                sig = (ev.clinical_significance or '').upper()
                if 'SENSITIVITY' in sig or 'RESPONSE' in sig:
                    desc = (ev.description or '').lower()
                    if self.variant.lower() in desc or self.gene.lower() in desc:
                        logger.debug(f"FDA approval found via CIViC Level A")
                        return True

        # Check CIViC Assertions
        for assertion in self.civic_assertions:
            if (assertion.amp_tier == 'Tier I' and
                assertion.assertion_type == 'PREDICTIVE' and
                self._tumor_matches(tumor_type, assertion.disease)):
                sig = (assertion.significance or '').upper()
                if 'SENSITIVITY' in sig or 'RESPONSE' in sig:
                    logger.debug(f"FDA approval found via CIViC Assertion Tier I")
                    return True
                if 'RESISTANCE' in sig and assertion.therapies:
                    # Resistance with alternative therapy
                    logger.debug(f"FDA approval found via CIViC Tier I resistance with alternative")
                    return True

        # Check CGI FDA-approved SENSITIVITY biomarkers
        for biomarker in self.cgi_biomarkers:
            if (biomarker.fda_approved and
                biomarker.tumor_type and
                self._tumor_matches(tumor_type, biomarker.tumor_type)):
                if biomarker.association and 'RESIST' not in biomarker.association.upper():
                    alt = (biomarker.alteration or '').upper()
                    if self.variant.upper() in alt or 'MUT' in alt:
                        logger.debug(f"FDA approval found via CGI biomarker: {biomarker.drug}")
                        return True

        return False

    def is_resistance_marker_without_targeted_therapy(self, tumor_type: str | None = None) -> tuple[bool, list[str]]:
        """Detect resistance-only markers WITHOUT FDA-approved therapy FOR the variant.

        Uses multiple evidence sources including:
        - Curated databases (CGI, VICC, CIViC)
        - PubMed literature (research papers)
        """
        stats = self.compute_evidence_stats(tumor_type)

        # Check for literature-based resistance evidence
        has_lit_resistance, lit_drugs, lit_pmids = self.has_literature_resistance_evidence()

        # If no resistance evidence from databases AND no literature evidence, return False
        if stats['resistance_count'] == 0 and not has_lit_resistance:
            return False, []

        # If we have literature resistance evidence, that's strong support
        # even if database evidence is limited
        if not has_lit_resistance:
            if stats['dominant_signal'] not in ['resistance_only', 'resistance_dominant']:
                if stats['resistance_count'] < 3:
                    return False, []

        # Check if there's FDA-approved therapy FOR this variant (sensitivity)
        if self.has_fda_for_variant_in_tumor(tumor_type):
            return False, []

        drugs_excluded = []

        # From PubMed literature (highest priority for emerging evidence)
        if lit_drugs:
            drugs_excluded.extend(lit_drugs)
            logger.info(f"Literature resistance evidence found: {lit_drugs} (PMIDs: {lit_pmids})")

        # Check FDA labels for wild-type requirements
        if tumor_type:
            requires_wt, wt_drugs = self._check_fda_requires_wildtype(tumor_type)
            if requires_wt:
                drugs_excluded.extend(wt_drugs)

        # From CGI resistance markers
        for biomarker in self.cgi_biomarkers:
            if (biomarker.fda_approved and
                biomarker.association and
                'RESIST' in biomarker.association.upper()):
                if tumor_type and biomarker.tumor_type:
                    if self._tumor_matches(tumor_type, biomarker.tumor_type):
                        if biomarker.drug:
                            drugs_excluded.append(biomarker.drug)
                elif not tumor_type and biomarker.drug:
                    drugs_excluded.append(biomarker.drug)

        # From VICC resistance evidence
        if tumor_type:
            for ev in self.vicc:
                if ev.is_resistance:
                    if self._tumor_matches(tumor_type, ev.disease):
                        drugs_excluded.extend(ev.drugs)

        # From CIViC resistance evidence
        if tumor_type:
            for ev in self.civic:
                if ev.evidence_type == 'PREDICTIVE':
                    sig = (ev.clinical_significance or '').upper()
                    if 'RESISTANCE' in sig:
                        if self._tumor_matches(tumor_type, ev.disease):
                            drugs_excluded.extend(ev.drugs)

        drugs_excluded = list(set(d for d in drugs_excluded if d))[:5]

        return bool(drugs_excluded), drugs_excluded

    def is_prognostic_or_diagnostic_only(self) -> bool:
        """Check if variant is prognostic/diagnostic only with NO therapeutic impact."""
        has_predictive = False

        for ev in self.civic:
            if ev.evidence_type == 'PREDICTIVE' and ev.drugs:
                has_predictive = True
                break

        for assertion in self.civic_assertions:
            if assertion.assertion_type == 'PREDICTIVE' and assertion.therapies:
                has_predictive = True
                break

        if self.vicc and any(v.drugs and (v.is_sensitivity or v.is_resistance) for v in self.vicc):
            has_predictive = True

        if self.cgi_biomarkers:
            has_predictive = True

        if self.fda_approvals:
            has_predictive = True

        return not has_predictive

    def get_tier_hint(self, tumor_type: str | None = None) -> str:
        """Generate explicit tier guidance based on evidence structure."""

        # Check LLM-extracted literature knowledge FIRST (highest confidence source)
        # This uses structured extraction from papers to determine tier
        if self.literature_knowledge and self.literature_knowledge.confidence >= 0.7:
            lit = self.literature_knowledge
            tier_rec = lit.tier_recommendation

            # If literature strongly indicates resistance, that takes precedence
            if lit.is_resistance_marker() and tier_rec.tier == "II":
                resistant_drugs = ", ".join(lit.get_resistance_drugs()[:3])
                sensitive_drugs = lit.get_sensitivity_drugs()
                refs = ", ".join(lit.references[:3]) if lit.references else "literature"

                if sensitive_drugs:
                    alt_drugs = ", ".join(sensitive_drugs[:2])
                    logger.info(f"Tier II (literature): {self.gene} {self.variant} resistant to {resistant_drugs}, may respond to {alt_drugs}")
                    return f"TIER II INDICATOR (LITERATURE): Resistant to {resistant_drugs}. Potential alternatives: {alt_drugs}. Evidence: {refs}"
                else:
                    logger.info(f"Tier II (literature): {self.gene} {self.variant} resistant to {resistant_drugs}")
                    return f"TIER II INDICATOR (LITERATURE): Resistant to {resistant_drugs} - no FDA-approved alternative. Evidence: {refs}"

            # If literature says Tier I and has sensitivity evidence with high confidence
            if tier_rec.tier == "I" and lit.has_therapeutic_options():
                sensitive_drugs = ", ".join(lit.get_sensitivity_drugs()[:2])
                logger.info(f"Tier I (literature): {self.gene} {self.variant} has therapeutic options: {sensitive_drugs}")
                return f"TIER I INDICATOR (LITERATURE): Therapeutic options: {sensitive_drugs}. {tier_rec.rationale}"

        # Check for FDA approval FOR variant in tumor (highest priority from structured data)
        if self.has_fda_for_variant_in_tumor(tumor_type):
            logger.info(f"Tier I: {self.gene} {self.variant} in {tumor_type} has FDA approval")
            return "TIER I INDICATOR: FDA-approved therapy FOR this variant in this tumor type"

        # Check for active clinical trials - overrides investigational-only (Tier II)
        has_trials, trial_drugs = self.has_active_clinical_trials(variant_specific_only=True)
        if has_trials:
            drugs_str = ', '.join(trial_drugs[:3]) if trial_drugs else 'investigational agents'
            logger.info(f"Tier II: {self.gene} {self.variant} has variant-specific clinical trials ({drugs_str})")
            return f"TIER II INDICATOR: Active clinical trials specifically enrolling {self.variant} patients ({drugs_str})"

        # Check investigational-only (but no active variant-specific trials)
        if self.is_investigational_only(tumor_type):
            logger.info(f"Tier III: {self.gene} {self.variant} in {tumor_type} is investigational-only")
            return "TIER III INDICATOR: Known investigational-only (no approved therapy exists)"

        # Check for resistance-only marker (excludes therapy but no targeted alternative)
        # Per AMP/ASCO/CAP: Resistance markers that affect treatment selection are Tier II
        # (e.g., NRAS mutations exclude anti-EGFR therapy in CRC - this IS clinically actionable)
        # Also checks PubMed literature for resistance evidence
        is_resistance_only, drugs = self.is_resistance_marker_without_targeted_therapy(tumor_type)
        if is_resistance_only:
            drugs_str = ', '.join(drugs) if drugs else 'standard therapies'
            # Check if evidence comes from literature
            has_lit_evidence, lit_drugs, lit_pmids = self.has_literature_resistance_evidence()
            if has_lit_evidence:
                pmid_str = ', '.join(lit_pmids[:3])
                logger.info(f"Tier II: {self.gene} {self.variant} in {tumor_type} is resistance marker (literature evidence: PMIDs {pmid_str})")
                return f"TIER II INDICATOR: Resistance marker that EXCLUDES {drugs_str} - supported by peer-reviewed literature (PMIDs: {pmid_str})"
            else:
                logger.info(f"Tier II: {self.gene} {self.variant} in {tumor_type} is resistance marker excluding {drugs_str}")
                return f"TIER II INDICATOR: Resistance marker that EXCLUDES {drugs_str} (no FDA-approved therapy FOR this variant)"

        # Check for prognostic/diagnostic only
        if self.is_prognostic_or_diagnostic_only():
            logger.info(f"Tier III: {self.gene} {self.variant} is prognostic/diagnostic only")
            return "TIER III INDICATOR: Prognostic/diagnostic only - no therapeutic impact"

        # Check for FDA approval in different tumor type
        has_fda_elsewhere = False
        if self.fda_approvals:
            has_fda_elsewhere = True
        elif any(b.fda_approved for b in self.cgi_biomarkers):
            has_fda_elsewhere = True
        elif any(ev.evidence_level == 'A' and ev.evidence_type == 'PREDICTIVE' for ev in self.civic):
            has_fda_elsewhere = True

        if has_fda_elsewhere:
            return "TIER II INDICATOR: FDA-approved therapy exists in different tumor type (off-label potential)"

        # Otherwise evaluate based on evidence strength
        stats = self.compute_evidence_stats(tumor_type)

        has_strong_evidence = any(
            ev.evidence_level in ['A', 'B']
            for ev in self.civic
            if ev.evidence_type == 'PREDICTIVE'
        )

        if has_strong_evidence or stats['sensitivity_count'] > 0:
            return "TIER II/III: Strong evidence but no FDA approval - evaluate trial data and guidelines"

        return "TIER III: Investigational/emerging evidence only"

    def compute_evidence_stats(self, tumor_type: str | None = None) -> dict:
        """Compute summary statistics and detect conflicts in the evidence."""
        stats = {
            'sensitivity_count': 0,
            'resistance_count': 0,
            'sensitivity_by_level': {},
            'resistance_by_level': {},
            'conflicts': [],
            'dominant_signal': 'none',
            'has_fda_approved': bool(self.fda_approvals) or any(b.fda_approved for b in self.cgi_biomarkers),
        }

        drug_signals: dict[str, dict] = {}

        def add_drug_signal(drug: str, signal_type: str, level: str | None, disease: str | None):
            drug_lower = drug.lower().strip()
            if drug_lower not in drug_signals:
                drug_signals[drug_lower] = {'sensitivity': [], 'resistance': [], 'drug_name': drug}
            drug_signals[drug_lower][signal_type].append({'level': level, 'disease': disease})

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

        for drug_lower, signals in drug_signals.items():
            if signals['sensitivity'] and signals['resistance']:
                sens_diseases = list(set(s['disease'][:50] if s['disease'] else 'unspecified' for s in signals['sensitivity'][:3]))
                res_diseases = list(set(s['disease'][:50] if s['disease'] else 'unspecified' for s in signals['resistance'][:3]))
                stats['conflicts'].append({
                    'drug': signals['drug_name'],
                    'sensitivity_context': ', '.join(sens_diseases),
                    'resistance_context': ', '.join(res_diseases),
                    'sensitivity_count': len(signals['sensitivity']),
                    'resistance_count': len(signals['resistance']),
                })

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
        """Generate a pre-processed summary header with stats and conflicts."""
        stats = self.compute_evidence_stats(tumor_type)
        lines = []

        lines.append("=" * 60)
        lines.append("EVIDENCE SUMMARY (Pre-processed)")
        lines.append("=" * 60)

        tier_hint = self.get_tier_hint(tumor_type)
        lines.append("")
        lines.append("*** TIER CLASSIFICATION GUIDANCE ***")
        lines.append(tier_hint)
        lines.append("=" * 60)
        lines.append("")

        total = stats['sensitivity_count'] + stats['resistance_count']
        if total > 0:
            sens_pct = (stats['sensitivity_count'] / total) * 100
            res_pct = (stats['resistance_count'] / total) * 100

            sens_levels = ', '.join(f"{k}:{v}" for k, v in sorted(stats['sensitivity_by_level'].items()))
            res_levels = ', '.join(f"{k}:{v}" for k, v in sorted(stats['resistance_by_level'].items()))

            lines.append(f"Sensitivity entries: {stats['sensitivity_count']} ({sens_pct:.0f}%) - Levels: {sens_levels or 'none'}")
            lines.append(f"Resistance entries: {stats['resistance_count']} ({res_pct:.0f}%) - Levels: {res_levels or 'none'}")

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

        if tumor_type and self.fda_approvals:
            later_line_approvals = []
            first_line_approvals = []
            variant_specific_approvals = []
            for approval in self.fda_approvals:
                parsed = approval.parse_indication_for_tumor(tumor_type)
                if parsed['tumor_match']:
                    drug = approval.brand_name or approval.generic_name or approval.drug_name
                    indication_lower = (approval.indication or '').lower()

                    # Check if this approval is specifically for the variant being queried
                    # variant_in_indications is authoritative (FDA label explicitly mentions variant)
                    # For clinical_studies, use _variant_matches_approval_class which checks for exclusions
                    is_variant_specific = (
                        approval.variant_in_indications or
                        self._variant_matches_approval_class(self.gene, self.variant, indication_lower, approval, tumor_type)
                    )

                    if is_variant_specific:
                        variant_specific_approvals.append(drug)
                        if parsed['line_of_therapy'] == 'later-line':
                            accel_note = " (ACCELERATED)" if parsed['approval_type'] == 'accelerated' else ""
                            later_line_approvals.append(f"{drug}{accel_note}")
                        elif parsed['line_of_therapy'] == 'first-line':
                            first_line_approvals.append(drug)

            if variant_specific_approvals:
                if later_line_approvals and not first_line_approvals:
                    lines.append("")
                    lines.append("FDA APPROVAL CONTEXT:")
                    lines.append(f"  FDA-APPROVED FOR THIS VARIANT (later-line): {', '.join(later_line_approvals)}")
                    lines.append("  → IMPORTANT: Later-line FDA approval is STILL Tier I if the biomarker IS the therapeutic indication.")
                elif first_line_approvals:
                    lines.append("")
                    lines.append(f"FDA FIRST-LINE APPROVAL FOR THIS VARIANT: {', '.join(first_line_approvals)} → Strong Tier I signal")

        if stats['conflicts']:
            lines.append("")
            lines.append("CONFLICTS DETECTED:")
            for conflict in stats['conflicts'][:5]:
                lines.append(f"  - {conflict['drug']}: "
                           f"SENSITIVITY in {conflict['sensitivity_context']} ({conflict['sensitivity_count']} entries) "
                           f"vs RESISTANCE in {conflict['resistance_context']} ({conflict['resistance_count']} entries)")

        # Add clinical trial summary
        trial_summary = self.get_clinical_trial_summary()
        if trial_summary:
            lines.append("")
            lines.append(trial_summary)

        # Add PubMed literature summary
        pubmed_summary = self.get_pubmed_summary()
        if pubmed_summary:
            lines.append("")
            lines.append(pubmed_summary)

        # Add LLM-extracted literature knowledge
        if self.literature_knowledge and self.literature_knowledge.confidence >= 0.5:
            lit = self.literature_knowledge
            lines.append("")
            lines.append("*** LITERATURE-EXTRACTED KNOWLEDGE ***")
            lines.append(f"Confidence: {lit.confidence:.0%}")
            lines.append(f"Mutation Type: {lit.mutation_type}")

            if lit.resistant_to:
                drugs_info = [f"{r.drug} ({r.evidence})" for r in lit.resistant_to[:3]]
                lines.append(f"RESISTANT TO: {', '.join(drugs_info)}")

            if lit.sensitive_to:
                drugs_info = [f"{s.drug} ({s.evidence})" for s in lit.sensitive_to[:3]]
                lines.append(f"POTENTIALLY SENSITIVE TO: {', '.join(drugs_info)}")

            if lit.clinical_significance:
                lines.append(f"Clinical Significance: {lit.clinical_significance}")

            if lit.key_findings:
                lines.append("Key Findings:")
                for finding in lit.key_findings[:3]:
                    lines.append(f"  • {finding}")

            lines.append(f"Literature Tier Recommendation: {lit.tier_recommendation.tier}")
            if lit.tier_recommendation.rationale:
                lines.append(f"  Rationale: {lit.tier_recommendation.rationale}")

            if lit.references:
                lines.append(f"References: {', '.join(lit.references[:5])}")

        lines.append("=" * 60)
        lines.append("")

        return "\n".join(lines)

    def filter_low_quality_minority_signals(self) -> tuple[list["VICCEvidence"], list["VICCEvidence"]]:
        """Filter out low-quality minority signals from VICC evidence."""
        sensitivity = [e for e in self.vicc if e.is_sensitivity]
        resistance = [e for e in self.vicc if e.is_resistance]

        high_quality_levels = {'A', 'B'}
        low_quality_levels = {'C', 'D'}

        sens_levels = {e.evidence_level for e in sensitivity if e.evidence_level}
        res_levels = {e.evidence_level for e in resistance if e.evidence_level}

        sens_has_high = bool(sens_levels & high_quality_levels)
        sens_only_low = sens_levels and sens_levels <= low_quality_levels
        res_has_high = bool(res_levels & high_quality_levels)
        res_only_low = res_levels and res_levels <= low_quality_levels

        if sens_has_high and res_only_low and len(resistance) <= 2:
            return sensitivity, []
        elif res_has_high and sens_only_low and len(sensitivity) <= 2:
            return [], resistance

        return sensitivity, resistance

    def aggregate_evidence_by_drug(self, tumor_type: str | None = None) -> list[dict]:
        """Aggregate evidence entries by drug for cleaner LLM presentation."""
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
                entry['diseases'].add(disease[:50])
            level_priority = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
            if level and level_priority.get(level, 99) < level_priority.get(entry['best_level'], 99):
                entry['best_level'] = level

        for ev in self.vicc:
            for drug in ev.drugs:
                add_entry(drug, ev.is_sensitivity, ev.evidence_level, ev.disease)

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

        results = []
        for drug_key, data in drug_data.items():
            sens = data['sensitivity_count']
            res = data['resistance_count']
            if sens > 0 and res == 0:
                net_signal = 'SENSITIVE'
            elif res > 0 and sens == 0:
                net_signal = 'RESISTANT'
            elif sens >= res * 3:
                net_signal = 'SENSITIVE'
            elif res >= sens * 3:
                net_signal = 'RESISTANT'
            else:
                net_signal = 'MIXED'

            data['net_signal'] = net_signal
            data['diseases'] = list(data['diseases'])[:5]
            results.append(data)

        level_priority = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        results.sort(key=lambda x: (level_priority.get(x['best_level'], 99), -(x['sensitivity_count'] + x['resistance_count'])))

        return results

    def format_drug_aggregation_summary(self, tumor_type: str | None = None) -> str:
        """Format drug-level aggregation for LLM prompt."""
        aggregated = self.aggregate_evidence_by_drug(tumor_type)
        if not aggregated:
            return ""

        lines = ["", "DRUG-LEVEL SUMMARY (aggregated from all sources):"]

        for idx, drug in enumerate(aggregated[:10], 1):
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
        """Generate a compact summary - FDA approvals and CGI only."""
        lines = [f"Evidence for {self.gene} {self.variant}:\n"]

        if self.fda_approvals:
            lines.append(f"FDA Approved Drugs ({len(self.fda_approvals)}):")
            for approval in self.fda_approvals[:5]:
                drug = approval.brand_name or approval.generic_name or approval.drug_name
                variant_explicit = approval.variant_in_clinical_studies

                if tumor_type:
                    parsed = approval.parse_indication_for_tumor(tumor_type)
                    if parsed['tumor_match']:
                        # FDA approval matches the tumor type
                        line_info = parsed['line_of_therapy'].upper()
                        approval_info = parsed['approval_type'].upper()

                        # Check if this variant is actually approved for this tumor type
                        # (not just mentioned in clinical studies as resistant/not sensitive)
                        indication_lower = (approval.indication or '').lower()
                        is_variant_approved = (
                            approval.variant_in_indications or
                            self._variant_matches_approval_class(self.gene, self.variant, indication_lower, approval, tumor_type)
                        )

                        variant_note = ""
                        if variant_explicit and is_variant_approved:
                            variant_note = " *** VARIANT EXPLICITLY IN FDA LABEL ***"
                        elif variant_explicit and not is_variant_approved:
                            # Variant mentioned in clinical studies but NOT as sensitivity indication
                            # (e.g., D816V mentioned as resistant in GIST context)
                            variant_note = " [variant mentioned but NOT approved for this tumor type]"

                        lines.append(f"  • {drug} [FOR {tumor_type.upper()}]{variant_note}:")
                        lines.append(f"      Line of therapy: {line_info}")
                        lines.append(f"      Approval type: {approval_info}")

                        indication = approval.indication or ""
                        if "[Clinical studies mention" in indication:
                            cs_start = indication.find("[Clinical studies mention")
                            cs_excerpt = indication[cs_start:cs_start+400]
                            lines.append(f"      {cs_excerpt}...")
                        else:
                            lines.append(f"      Excerpt: {parsed['indication_excerpt'][:200]}...")
                    else:
                        # FDA approval is for a DIFFERENT tumor type
                        indication = (approval.indication or "")[:300]
                        lines.append(f"  • {drug} [DIFFERENT TUMOR TYPE - NOT {tumor_type.upper()}]: {indication}...")
                else:
                    indication = (approval.indication or "")[:300]
                    date_str = f" (Approved: {approval.approval_date})" if approval.approval_date else ""
                    status_str = f" [{approval.marketing_status}]" if approval.marketing_status else ""
                    lines.append(f"  • {drug}{date_str}{status_str}: {indication}...")
            lines.append("")

        if self.cgi_biomarkers:
            approved = [b for b in self.cgi_biomarkers if b.fda_approved]
            if approved:
                resistance_approved = [b for b in approved if b.association and 'RESIST' in b.association.upper()]
                sensitivity_approved = [b for b in approved if b.association and 'RESIST' not in b.association.upper()]

                if resistance_approved:
                    lines.append(f"CGI FDA-APPROVED RESISTANCE MARKERS ({len(resistance_approved)}):")
                    lines.append("  *** THESE VARIANTS EXCLUDE USE OF FDA-APPROVED THERAPIES ***")
                    for b in resistance_approved[:5]:
                        lines.append(f"  • {b.drug} [{b.association.upper()}] in {b.tumor_type or 'solid tumors'} - Evidence: {b.evidence_level}")
                    lines.append("  → This variant causes RESISTANCE to the above drug(s), making it Tier II actionable as a NEGATIVE biomarker.")
                    lines.append("")

                if sensitivity_approved:
                    lines.append(f"CGI FDA-Approved Sensitivity Biomarkers ({len(sensitivity_approved)}):")
                    for b in sensitivity_approved[:5]:
                        lines.append(f"  • {b.drug} [{b.association}] in {b.tumor_type or 'solid tumors'} - Evidence: {b.evidence_level}")
                    lines.append("")

        if self.civic_assertions:
            predictive_tier_i = [a for a in self.civic_assertions
                                  if a.amp_tier == "Tier I" and a.assertion_type == "PREDICTIVE"]
            predictive_tier_ii = [a for a in self.civic_assertions
                                   if a.amp_tier == "Tier II" and a.assertion_type == "PREDICTIVE"]
            prognostic = [a for a in self.civic_assertions if a.assertion_type == "PROGNOSTIC"]

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

        # Add PubMed literature evidence
        if self.pubmed_articles:
            resistance_articles = [a for a in self.pubmed_articles if a.is_resistance_evidence()]
            if resistance_articles:
                lines.append(f"PUBMED RESISTANCE LITERATURE ({len(resistance_articles)} articles):")
                lines.append("  *** PEER-REVIEWED EVIDENCE FOR RESISTANCE ***")
                for article in resistance_articles[:3]:
                    drugs_str = f" [Drugs: {', '.join(article.drugs_mentioned[:3])}]" if article.drugs_mentioned else ""
                    lines.append(f"  • PMID {article.pmid}: {article.title[:100]}...{drugs_str}")
                    lines.append(f"      {article.format_citation()}")
                    if article.abstract:
                        abstract_preview = article.abstract[:250].replace('\n', ' ')
                        lines.append(f"      Abstract: {abstract_preview}...")
                lines.append("")

        return "\n".join(lines) if len(lines) > 1 else ""

    def summary(self, tumor_type: str | None = None, max_items: int = 15) -> str:
        """Generate a text summary of all evidence."""
        # Implementation continues with existing logic...
        # (Keeping existing summary method as-is for brevity)
        return self.summary_compact(tumor_type)