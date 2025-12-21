"""Evidence data models from external databases."""

from typing import Any
import logging

from pydantic import Field

from tumorboard.config.gene_classes import load_gene_classes
from tumorboard.config.variant_classes import load_variant_classes
from tumorboard.models.gene_context import (
    get_gene_context, get_therapeutic_implication, get_lof_assessment, GeneRole
)
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
        This includes gene-tumor pairs where:
        1. Targeted therapies have FAILED in clinical trials for this tumor type
        2. FDA approval exists in OTHER tumor types but has no evidence of efficacy here
        3. The biomarker is prognostic only in this tumor type

        Example: PTEN mutations in GBM are prognostic (poor outcome) but NOT actionable.
        mTOR/PI3K inhibitors have failed in GBM trials despite approvals elsewhere.
        """
        gene_lower = self.gene.lower()
        tumor_lower = (tumor_type or '').lower()

        # Known investigational-only combinations
        # These are gene-tumor pairs where:
        # - Targeted therapies have failed in clinical trials for this specific tumor
        # - FDA approval may exist for OTHER tumors but has NO efficacy here
        # - Biomarker is prognostic only (not therapeutically actionable)
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
            # PTEN in GBM: mTOR/PI3K inhibitors have FAILED in clinical trials
            # PTEN loss is prognostic (worse outcome) but NOT therapeutically actionable
            # Reference: PMID 26066373 (Phase II temsirolimus), PMID 25260750 (mTOR inhibitors in GBM)
            # Despite PTEN being targetable in breast cancer (capivasertib/TRUQAP),
            # this does NOT translate to GBM
            ('pten', 'glioblastoma'): True,
            ('pten', 'gbm'): True,
            ('pten', 'glioma'): True,
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

        # Check CIViC Level A/B with tumor matching
        # Per AMP/ASCO/CAP 2017:
        #   - Level A = FDA-approved or professional guidelines → Tier I-A
        #   - Level B = Well-powered clinical studies → Tier I-B
        for ev in self.civic:
            if (ev.evidence_level in ['A', 'B'] and
                ev.evidence_type == 'PREDICTIVE' and
                self._tumor_matches(tumor_type, ev.disease)):
                sig = (ev.clinical_significance or '').upper()
                if 'SENSITIVITY' in sig or 'RESPONSE' in sig:
                    desc = (ev.description or '').lower()
                    if self.variant.lower() in desc or self.gene.lower() in desc:
                        logger.debug(f"Tier I via CIViC Level {ev.evidence_level}")
                        return True

        # Check CIViC Assertions (curated AMP/ASCO/CAP classifications)
        for assertion in self.civic_assertions:
            if not self._tumor_matches(tumor_type, assertion.disease):
                continue

            # Per AMP/ASCO/CAP: Tier I includes variants in professional guidelines (NCCN/ASCO)
            # CIViC assertions with NCCN guideline references = Tier I
            if assertion.nccn_guideline and assertion.assertion_type == 'PREDICTIVE':
                sig = (assertion.significance or '').upper()
                if 'SENSITIVITY' in sig or 'RESPONSE' in sig:
                    logger.debug(f"Tier I via NCCN guideline: {assertion.nccn_guideline}")
                    return True

            # Explicit Tier I assertions
            if assertion.amp_tier == 'Tier I' and assertion.assertion_type == 'PREDICTIVE':
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

    def _get_nccn_guideline_for_tumor(self, tumor_type: str | None) -> str | None:
        """Get NCCN guideline name if variant is in NCCN guidelines for this tumor.

        Returns the guideline name (e.g., "Non-Small Cell Lung Cancer") or None.
        """
        if not tumor_type:
            return None

        for assertion in self.civic_assertions:
            if (assertion.nccn_guideline and
                assertion.assertion_type == 'PREDICTIVE' and
                self._tumor_matches(tumor_type, assertion.disease)):
                sig = (assertion.significance or '').upper()
                if 'SENSITIVITY' in sig or 'RESPONSE' in sig:
                    return assertion.nccn_guideline

        return None

    def _get_tier_i_sublevel(self, tumor_type: str | None) -> str:
        """Determine Tier I sub-level (A or B) per AMP/ASCO/CAP 2017.

        Tier I-A: FDA-approved OR professional guidelines
        Tier I-B: Well-powered clinical studies (Level B evidence)

        Returns "A", "B", or "A" as default.
        """
        # Check for FDA approval (Tier I-A)
        for approval in self.fda_approvals:
            parsed = approval.parse_indication_for_tumor(tumor_type or "")
            if parsed.get('tumor_match'):
                return "A"

        # Check for Level A evidence (Tier I-A)
        for ev in self.civic:
            if (ev.evidence_level == 'A' and
                ev.evidence_type == 'PREDICTIVE' and
                self._tumor_matches(tumor_type, ev.disease)):
                return "A"

        # Check for NCCN guidelines (Tier I-A)
        if self._get_nccn_guideline_for_tumor(tumor_type):
            return "A"

        # Check for CIViC Tier I assertions (usually Tier I-A)
        for assertion in self.civic_assertions:
            if (assertion.amp_tier == 'Tier I' and
                self._tumor_matches(tumor_type, assertion.disease)):
                return "A"

        # Check for CGI FDA-approved biomarkers (Tier I-A)
        for biomarker in self.cgi_biomarkers:
            if biomarker.fda_approved and self._tumor_matches(tumor_type, biomarker.tumor_type):
                return "A"

        # Check for Level B evidence (Tier I-B)
        for ev in self.civic:
            if (ev.evidence_level == 'B' and
                ev.evidence_type == 'PREDICTIVE' and
                self._tumor_matches(tumor_type, ev.disease)):
                return "B"

        # Default to A if we can't determine
        return "A"

    def _get_tier_ii_sublevel(self, tumor_type: str | None, context: str = "general") -> str:
        """Determine Tier II sub-level (A, B, C, or D) per AMP/ASCO/CAP 2017.

        Per guidelines/tier2.md and tier3.md:
        Tier II-A: FDA approved in DIFFERENT tumor type (off-label)
        Tier II-B: Well-powered studies (Phase 2/3) without guideline endorsement
        Tier II-C: Prognostic with established clinical value (Level A/B/C evidence)
        Tier II-D: Active clinical trials, OR resistance without approved alternatives

        NOTE: Case reports only (Level C) and preclinical only (Level D) are now
        Tier III per guidelines/tier3.md, NOT Tier II. Tier II requires at least
        well-powered studies (Level B) or active clinical trials.

        Args:
            tumor_type: Patient's tumor type
            context: Hint about why this is Tier II ("fda_different_tumor", "resistance",
                     "trials", "prognostic", "general")

        Returns: "A", "B", "C", or "D"
        """
        # Context-based classification (when caller knows why it's Tier II)
        if context == "fda_different_tumor":
            return "A"
        if context == "trials":
            # Check if trials are Phase 1 (II-D) vs Phase 2/3 (II-B)
            return "D"  # Default to D for clinical trials (investigational)
        if context == "resistance":
            # Per guidelines/tier2.md scenario 5: Resistance mutations WITHOUT approved alternatives
            # Example: EGFR C797S = "Tier II-D (explains resistance, trial eligibility, no approved therapy)"
            return "D"
        if context == "prognostic":
            # Prognostic without treatment implications = II-C
            return "C"

        # Analyze evidence to determine sub-level

        # Check for FDA approval in different tumor (II-A)
        for approval in self.fda_approvals:
            parsed = approval.parse_indication_for_tumor(tumor_type or "")
            if not parsed.get('tumor_match'):
                # Has FDA approval but NOT in this tumor
                return "A"

        # Check for CIViC Level A evidence in different tumor (II-A)
        has_level_a_elsewhere = False
        for ev in self.civic:
            if ev.evidence_level == 'A' and ev.evidence_type == 'PREDICTIVE':
                if not self._tumor_matches(tumor_type, ev.disease):
                    has_level_a_elsewhere = True
                    break
        if has_level_a_elsewhere:
            return "A"

        # Check for CGI FDA-approved in different tumor (II-A)
        for biomarker in self.cgi_biomarkers:
            if biomarker.fda_approved:
                if not self._tumor_matches(tumor_type, biomarker.tumor_type):
                    return "A"

        # Check for well-powered studies (Level B/C) without guidelines (II-B)
        has_level_b = any(
            ev.evidence_level == 'B' and ev.evidence_type == 'PREDICTIVE'
            for ev in self.civic
        )
        if has_level_b:
            return "B"

        # NOTE: Level C (case reports) and Level D (preclinical) without other context
        # should now be Tier III per guidelines/tier3.md, NOT Tier II.
        # This method should only be called when we've already determined it's Tier II.

        # Check for active clinical trials (II-D)
        has_trials, _ = self.has_active_clinical_trials(variant_specific_only=True)
        if has_trials:
            return "D"

        # Default to B (well-powered studies) since if we're calling this for Tier II,
        # we should have Level B evidence or FDA approval elsewhere
        return "B"

    def _get_tier_iii_sublevel(self, tumor_type: str | None, context: str = "general") -> str:
        """Determine Tier III sub-level (A, B, C, or D) per AMP/ASCO/CAP 2017.

        Per guidelines/tier3.md:
        Tier III-A: FDA/guideline support in other tumor types BUT NO evidence in patient's tumor
        Tier III-B: VUS in established cancer gene (functional impact unknown)
        Tier III-C: Preclinical data only OR case reports (n<5) - insufficient for clinical use
        Tier III-D: No evidence at all (truly unknown)

        Args:
            tumor_type: Patient's tumor type
            context: Hint about why this is Tier III ("actionable_elsewhere", "vus",
                     "case_reports", "preclinical", "prognostic_only", "no_evidence", "general")

        Returns: "A", "B", "C", or "D"
        """
        # Context-based classification (when caller knows why it's Tier III)
        if context == "actionable_elsewhere":
            # FDA/guideline support elsewhere but zero evidence in patient's tumor
            return "A"
        if context == "vus":
            # VUS in established cancer gene
            return "B"
        if context == "case_reports":
            # Case reports only (n<5)
            return "C"
        if context == "preclinical":
            # Preclinical data only (no human clinical evidence)
            return "C"
        if context == "prognostic_only":
            # Prognostic only with limited evidence
            return "C"
        if context == "no_evidence":
            # No evidence at all
            return "D"

        # Evidence-based fallback classification

        # Check for FDA approval or Level A evidence in OTHER tumor types (III-A)
        # This is biomarkers actionable elsewhere but with zero evidence in patient's tumor
        has_fda_or_level_a_elsewhere = False
        for approval in self.fda_approvals:
            parsed = approval.parse_indication_for_tumor(tumor_type or "")
            if not parsed.get('tumor_match'):
                has_fda_or_level_a_elsewhere = True
                break
        if not has_fda_or_level_a_elsewhere:
            for ev in self.civic:
                if ev.evidence_level == 'A' and ev.evidence_type == 'PREDICTIVE':
                    if not self._tumor_matches(tumor_type, ev.disease):
                        has_fda_or_level_a_elsewhere = True
                        break

        # But for III-A, there must be ZERO evidence in the patient's tumor
        has_any_evidence_in_tumor = False
        for ev in self.civic:
            if self._tumor_matches(tumor_type, ev.disease):
                has_any_evidence_in_tumor = True
                break
        for ev in self.vicc:
            if self._tumor_matches(tumor_type, ev.disease):
                has_any_evidence_in_tumor = True
                break

        if has_fda_or_level_a_elsewhere and not has_any_evidence_in_tumor:
            return "A"

        # Check for Level C (case reports) evidence → III-C
        has_level_c = any(
            ev.evidence_level == 'C' and ev.evidence_type == 'PREDICTIVE'
            for ev in self.civic
        )
        if has_level_c:
            return "C"

        # Check for Level D (preclinical) evidence → III-C
        has_level_d = any(
            ev.evidence_level == 'D' and ev.evidence_type == 'PREDICTIVE'
            for ev in self.civic
        )
        if has_level_d:
            return "C"

        # Check for prognostic/diagnostic with weak evidence → III-C
        has_weak_prognostic = any(
            ev.evidence_level in ['C', 'D'] and
            ev.evidence_type in ['PROGNOSTIC', 'DIAGNOSTIC']
            for ev in self.civic
        )
        if has_weak_prognostic:
            return "C"

        # If we have any evidence at all, default to C (limited evidence)
        if self.civic or self.vicc or self.cgi_biomarkers:
            return "C"

        # No evidence at all → III-D
        return "D"

    def is_resistance_marker_without_targeted_therapy(self, tumor_type: str | None = None) -> tuple[bool, list[str]]:
        """Detect resistance-only markers WITHOUT FDA-approved therapy FOR the variant.

        A TRUE resistance marker (Tier II) must:
        1. Cause resistance to a therapy that IS FDA-approved/standard for the tumor type
        2. Not just be "associated with worse outcomes" (that's prognostic, Tier III)

        Examples:
        - KRAS G12D in CRC → Tier II (excludes anti-EGFR which IS approved for CRC)
        - SMAD4 loss in pancreatic → Tier III (no targeted therapy requires wild-type SMAD4)

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

        # Literature-only resistance is NOT sufficient for Tier II
        # The drug must also be FDA-approved/standard for this tumor type
        # (Prognostic associations like "SMAD4 loss = worse survival" are Tier III, not II)
        # We'll collect lit_drugs but only include them if validated below
        literature_candidate_drugs = lit_drugs if lit_drugs else []
        if literature_candidate_drugs:
            logger.debug(f"Literature resistance candidates: {literature_candidate_drugs} (PMIDs: {lit_pmids})")

        # Check FDA labels for wild-type requirements (strongest evidence)
        if tumor_type:
            requires_wt, wt_drugs = self._check_fda_requires_wildtype(tumor_type)
            if requires_wt:
                drugs_excluded.extend(wt_drugs)

        # From CGI FDA-approved resistance markers
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

        # From VICC resistance evidence (Level A/B only for Tier II)
        if tumor_type:
            for ev in self.vicc:
                if ev.is_resistance and ev.evidence_level in ['A', 'B']:
                    if self._tumor_matches(tumor_type, ev.disease):
                        drugs_excluded.extend(ev.drugs)

        # From CIViC resistance evidence (Level A/B only for Tier II)
        if tumor_type:
            for ev in self.civic:
                if ev.evidence_type == 'PREDICTIVE' and ev.evidence_level in ['A', 'B']:
                    sig = (ev.clinical_significance or '').upper()
                    if 'RESISTANCE' in sig:
                        if self._tumor_matches(tumor_type, ev.disease):
                            drugs_excluded.extend(ev.drugs)

        # Only include literature drugs if they match a drug from curated sources
        # This prevents prognostic associations from being misclassified as resistance markers
        if literature_candidate_drugs and drugs_excluded:
            curated_drug_names = {d.lower() for d in drugs_excluded}
            for lit_drug in literature_candidate_drugs:
                if lit_drug.lower() in curated_drug_names:
                    # Literature confirms curated evidence - already included
                    pass
                # Don't add literature-only drugs without curated backing

        drugs_excluded = list(set(d for d in drugs_excluded if d))[:5]

        # Final check: only return True if we have drugs from curated sources
        # Literature-only "resistance" (like SMAD4 prognostic) doesn't count
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

    def is_clinvar_benign(self) -> bool:
        """Check if ClinVar classifies this variant as benign/likely benign.

        This is critical for gene-class approvals (e.g., BRCA-mutated) where
        the approval is for PATHOGENIC mutations only. Benign variants should
        NOT be matched against these approvals.

        Examples:
        - BRCA2 K3326* is a known benign polymorphism despite being a stop codon
        - MLH1 V716M is a common missense polymorphism classified as benign
        - These should NOT be eligible for targeted therapy
        """
        # Check the annotation field first (primary source from MyVariant)
        if self.clinvar_clinical_significance:
            sig = self.clinvar_clinical_significance.lower()
            # Check for benign classifications
            if 'benign' in sig and 'pathogenic' not in sig:
                # "Benign", "Likely benign", "Benign/Likely benign" all match
                # But "Conflicting interpretations of pathogenicity" or
                # "Uncertain significance" don't match
                return True

        # Also check the clinvar list entries as fallback
        for cv in self.clinvar:
            sig = (cv.clinical_significance or '').lower()
            if 'benign' in sig and 'pathogenic' not in sig:
                return True

        return False

    def is_vus_in_known_cancer_gene(self) -> bool:
        """Check if this variant is a VUS (Variant of Uncertain Significance) in a known cancer gene.

        Per AMP/ASCO/CAP 2017 Tier III-B definition:
        - The gene is a known cancer gene (established oncogene or tumor suppressor)
        - BUT the functional impact of THIS specific variant is unknown

        This uses OncoKB's curated cancer gene list to determine if the gene is a known
        cancer gene. The variant is considered a VUS if:
        1. Gene is in OncoKB cancer gene list (or fallback list)
        2. No curated evidence exists for this specific variant (no FDA, CIViC Level A/B, etc.)

        Returns:
            True if variant is a VUS in a known cancer gene (Tier III-B candidate)
        """
        # Lazy import to avoid circular dependency
        from tumorboard.api.oncokb import is_known_cancer_gene_sync, FALLBACK_CANCER_GENES

        gene_upper = self.gene.upper()

        # Check if gene is in OncoKB cancer gene list (cached from API) or fallback list
        is_cancer_gene = is_known_cancer_gene_sync(gene_upper)
        if not is_cancer_gene:
            # Fallback to hardcoded list if API cache not available
            is_cancer_gene = gene_upper in FALLBACK_CANCER_GENES

        if not is_cancer_gene:
            return False  # Gene is not a known cancer gene

        # Gene is a known cancer gene - check if variant has curated evidence
        # If variant has strong evidence (Level A/B), it's NOT a VUS
        has_strong_evidence = False

        # Check for Level A/B CIViC evidence for THIS variant
        for ev in self.civic:
            if ev.evidence_level in ['A', 'B']:
                has_strong_evidence = True
                break

        # Check for CIViC assertions
        if self.civic_assertions:
            has_strong_evidence = True

        # Check for CGI FDA-approved biomarkers
        if any(b.fda_approved for b in self.cgi_biomarkers):
            has_strong_evidence = True

        # Check for FDA approvals that match this variant
        if self.fda_approvals:
            has_strong_evidence = True

        # If no strong evidence, this is a VUS in a known cancer gene
        return not has_strong_evidence

    def get_gene_level_therapeutic_summary(self, tumor_type: str | None = None) -> dict:
        """Aggregate CIViC evidence to understand gene-level therapeutic implications.

        This method analyzes all PREDICTIVE CIViC evidence for this gene to determine:
        1. Which drugs show sensitivity across any variant in the gene
        2. Which drugs show resistance
        3. Conflicts (same drug sensitive in one context, resistant in another)
        4. Whether evidence exists for the patient's specific tumor type

        This enables gene-centric reasoning when variant-specific evidence is lacking.
        For DDR genes, loss-of-function mutations generally have similar therapeutic
        implications even if the specific variant isn't well-characterized.

        Args:
            tumor_type: Patient's tumor type for disease-specific matching

        Returns:
            Dict with keys:
            - sensitivities: List of {drug, level, diseases, count}
            - resistances: List of {drug, level, diseases, count}
            - has_conflicts: bool indicating if same drug has both signals
            - conflicts: List of conflicting drugs with context
            - best_evidence_level: Highest evidence level (A > B > C > D)
            - disease_match: Whether any evidence matches patient's tumor
            - disease_matched_drugs: Drugs with evidence in patient's tumor
        """
        sensitivities: dict[str, dict] = {}
        resistances: dict[str, dict] = {}

        level_priority = {'A': 0, 'B': 1, 'C': 2, 'D': 3}

        for ev in self.civic:
            if ev.evidence_type != "PREDICTIVE":
                continue

            sig = (ev.clinical_significance or "").upper()
            direction = (ev.evidence_direction or "").upper()
            level = ev.evidence_level or "D"

            # Determine if this is sensitivity or resistance
            is_sensitivity = (
                ("SENSITIVITY" in sig or "RESPONSE" in sig) and
                direction != "DOES_NOT_SUPPORT"
            )
            is_resistance = (
                "RESISTANCE" in sig or
                direction == "DOES_NOT_SUPPORT"
            )

            if not is_sensitivity and not is_resistance:
                continue

            for drug in (ev.drugs or []):
                drug_lower = drug.lower().strip()
                target_dict = sensitivities if is_sensitivity else resistances

                if drug_lower not in target_dict:
                    target_dict[drug_lower] = {
                        "drug": drug,
                        "best_level": level,
                        "diseases": set(),
                        "count": 0,
                        "tumor_match": False,
                    }

                entry = target_dict[drug_lower]
                entry["count"] += 1

                # Track best evidence level
                if level_priority.get(level, 99) < level_priority.get(entry["best_level"], 99):
                    entry["best_level"] = level

                # Track diseases
                if ev.disease:
                    entry["diseases"].add(ev.disease)
                    if tumor_type and self._tumor_matches(tumor_type, ev.disease):
                        entry["tumor_match"] = True

        # Find conflicts (same drug in both sensitivity and resistance)
        conflicts = []
        sensitivity_drugs = set(sensitivities.keys())
        resistance_drugs = set(resistances.keys())
        conflict_drugs = sensitivity_drugs & resistance_drugs

        for drug_lower in conflict_drugs:
            sens = sensitivities[drug_lower]
            res = resistances[drug_lower]
            conflicts.append({
                "drug": sens["drug"],
                "sensitivity_diseases": list(sens["diseases"])[:3],
                "resistance_diseases": list(res["diseases"])[:3],
                "sensitivity_level": sens["best_level"],
                "resistance_level": res["best_level"],
            })

        # Find best evidence level across all entries
        all_levels = (
            [s["best_level"] for s in sensitivities.values()] +
            [r["best_level"] for r in resistances.values()]
        )
        best_level = "D"
        for level in all_levels:
            if level_priority.get(level, 99) < level_priority.get(best_level, 99):
                best_level = level

        # Format output lists
        sens_list = [
            {
                "drug": s["drug"],
                "level": s["best_level"],
                "diseases": list(s["diseases"])[:5],
                "count": s["count"],
                "tumor_match": s["tumor_match"],
            }
            for s in sorted(
                sensitivities.values(),
                key=lambda x: (level_priority.get(x["best_level"], 99), -x["count"])
            )
        ]

        res_list = [
            {
                "drug": r["drug"],
                "level": r["best_level"],
                "diseases": list(r["diseases"])[:5],
                "count": r["count"],
                "tumor_match": r["tumor_match"],
            }
            for r in sorted(
                resistances.values(),
                key=lambda x: (level_priority.get(x["best_level"], 99), -x["count"])
            )
        ]

        # Check disease match and collect matched drugs
        has_disease_match = (
            any(s["tumor_match"] for s in sens_list) or
            any(r["tumor_match"] for r in res_list)
        )

        disease_matched_drugs = (
            [s["drug"] for s in sens_list if s["tumor_match"]] +
            [r["drug"] for r in res_list if r["tumor_match"]]
        )

        return {
            "sensitivities": sens_list,
            "resistances": res_list,
            "has_conflicts": bool(conflicts),
            "conflicts": conflicts,
            "best_evidence_level": best_level if all_levels else None,
            "disease_match": has_disease_match,
            "disease_matched_drugs": disease_matched_drugs,
        }

    def is_molecular_subtype_defining(self, tumor_type: str | None = None) -> tuple[bool, str | None]:
        """Check if this variant defines a molecular subtype with Level A clinical utility.

        Some variants DEFINE molecular subtypes that are the gold standard for clinical
        classification, even without FDA-approved targeted therapy. These are Tier I
        diagnostic/prognostic biomarkers per AMP/ASCO/CAP guidelines.

        Examples:
        - POLE P286R, V411L, S459F in endometrial cancer → defines "POLE-ultramutated" subtype
          (TCGA 2013, NCCN/ESMO guidelines) - excellent prognosis, may de-escalate treatment
        - MPL W515L/K in myeloproliferative neoplasm → defines MPN (already handled via FDA)
        - MMR mutations → define dMMR/MSI-H (already handled via tumor-agnostic approval)

        Returns:
            Tuple of (is_defining, subtype_description) if variant defines a molecular subtype.
        """
        gene_upper = self.gene.upper()
        variant_upper = self.variant.upper()
        tumor_lower = (tumor_type or '').lower()

        # POLE exonuclease domain hotspot mutations define POLE-ultramutated subtype
        # in endometrial cancer (TCGA 2013 landmark study, NCCN/ESMO guidelines)
        if gene_upper == 'POLE':
            # Hotspot mutations in the exonuclease domain (codons 268-471)
            # These mutations cause ultramutation phenotype with exceptional prognosis
            pole_hotspots = [
                'P286R', 'P286H', 'P286S',  # Most common hotspot (~50% of POLE-mutated EC)
                'V411L', 'V411M',            # Second most common hotspot
                'S459F',                      # Other recurrent hotspots
                'A456P',
                'F367S', 'F367C', 'F367V',
                'S297F', 'S297Y',
                'M444K',
                'L424V', 'L424I',
            ]

            if variant_upper in pole_hotspots:
                # Check if tumor type is endometrial/uterine
                endometrial_keywords = ['endometrial', 'endometrium', 'uterine', 'uterus']
                if any(kw in tumor_lower for kw in endometrial_keywords):
                    return True, (
                        "POLE-ultramutated molecular subtype (Tier I-B: guideline-supported). "
                        "Per TCGA 2013 and NCCN/ESMO guidelines, this mutation defines the "
                        "POLE-ultramutated subtype with excellent prognosis regardless of "
                        "histologic grade. May de-escalate adjuvant treatment."
                    )

                # POLE mutations also have prognostic value in colorectal cancer
                colorectal_keywords = ['colorectal', 'colon', 'rectal', 'crc']
                if any(kw in tumor_lower for kw in colorectal_keywords):
                    return True, (
                        "POLE-ultramutated subtype (Tier I-B: well-powered studies). "
                        "POLE exonuclease domain mutations are associated with hypermutation "
                        "phenotype and favorable prognosis in colorectal cancer."
                    )

        return False, None

    def get_tier_hint(self, tumor_type: str | None = None) -> str:
        """Generate explicit tier guidance based on evidence structure."""

        # PRIORITY 0: Check for BENIGN classification in ClinVar
        # Benign variants are Tier IV and should NOT be matched against
        # gene-class FDA approvals (e.g., BRCA2 K3326* is benign, not PARP eligible)
        if self.is_clinvar_benign():
            logger.info(f"Tier IV: {self.gene} {self.variant} is classified as benign/likely benign in ClinVar")
            return "TIER IV INDICATOR: ClinVar classifies this variant as Benign/Likely benign - NOT eligible for gene-class targeted therapy approvals"

        # PRIORITY 0.5: Check for molecular subtype-defining biomarkers (Level A diagnostic)
        # These variants DEFINE molecular subtypes that are the gold standard for classification
        # Examples: POLE P286R → POLE-ultramutated in endometrial cancer (TCGA 2013)
        is_subtype_defining, subtype_description = self.is_molecular_subtype_defining(tumor_type)
        if is_subtype_defining:
            # Molecular subtype-defining biomarkers are typically Tier I-B (guideline-supported, not FDA label)
            logger.info(f"Tier I-B: {self.gene} {self.variant} in {tumor_type} defines molecular subtype")
            return f"TIER I-B INDICATOR: {subtype_description}"

        # PRIORITY 1: Check for FDA approval or professional guidelines FOR variant in tumor
        # Per AMP/ASCO/CAP: Tier I = FDA-approved OR in professional guidelines (NCCN/ASCO)
        # OR well-powered clinical studies with expert consensus
        if self.has_fda_for_variant_in_tumor(tumor_type):
            # Determine Tier I sub-level (A vs B) per AMP/ASCO/CAP 2017
            sublevel = self._get_tier_i_sublevel(tumor_type)
            # Check if this is specifically via NCCN guideline (for better messaging)
            nccn_guideline = self._get_nccn_guideline_for_tumor(tumor_type)
            if nccn_guideline:
                logger.info(f"Tier I-{sublevel}: {self.gene} {self.variant} in {tumor_type} - NCCN guideline: {nccn_guideline}")
                return f"TIER I-{sublevel} INDICATOR: Included in NCCN guidelines ({nccn_guideline}) for this tumor type"
            logger.info(f"Tier I-{sublevel}: {self.gene} {self.variant} in {tumor_type} has FDA approval or guideline backing")
            return f"TIER I-{sublevel} INDICATOR: FDA-approved therapy or professional guideline FOR this variant in this tumor type"

        # PRIORITY 2: Check LLM-extracted literature knowledge
        # Only use literature if no FDA approval exists for this variant in tumor
        if self.literature_knowledge and self.literature_knowledge.confidence >= 0.7:
            lit = self.literature_knowledge
            tier_rec = lit.tier_recommendation

            # IMPORTANT: Literature-based resistance ALONE is NOT sufficient for Tier II
            # Literature can incorrectly classify prognostic markers (e.g., SMAD4 loss)
            # as "resistance" when they're really just associated with worse outcomes.
            # True Tier II resistance requires the drug to be FDA-approved/standard for the tumor.
            # We check this via is_resistance_marker_without_targeted_therapy() later.
            # So we skip literature resistance classification here and let the curated check handle it.

            # If literature says Tier I and has sensitivity evidence with high confidence
            # Literature-based Tier I is typically Tier I-B (well-powered studies without FDA approval)
            if tier_rec.tier == "I" and lit.has_therapeutic_options():
                sensitive_drugs = ", ".join(lit.get_sensitivity_drugs()[:2])
                logger.info(f"Tier I-B (literature): {self.gene} {self.variant} has therapeutic options: {sensitive_drugs}")
                return f"TIER I-B INDICATOR (LITERATURE): Therapeutic options: {sensitive_drugs}. {tier_rec.rationale}"

        # Check for active clinical trials - overrides investigational-only (Tier II-D)
        has_trials, trial_drugs = self.has_active_clinical_trials(variant_specific_only=True)
        if has_trials:
            drugs_str = ', '.join(trial_drugs[:3]) if trial_drugs else 'investigational agents'
            sublevel = self._get_tier_ii_sublevel(tumor_type, context="trials")
            logger.info(f"Tier II-{sublevel}: {self.gene} {self.variant} has variant-specific clinical trials ({drugs_str})")
            return f"TIER II-{sublevel} INDICATOR: Active clinical trials specifically enrolling {self.variant} patients ({drugs_str})"

        # Check investigational-only (but no active variant-specific trials)
        if self.is_investigational_only(tumor_type):
            sublevel = self._get_tier_iii_sublevel(tumor_type, context="general")
            logger.info(f"Tier III-{sublevel}: {self.gene} {self.variant} in {tumor_type} is investigational-only")
            return f"TIER III-{sublevel} INDICATOR: Known investigational-only (no approved therapy exists)"

        # Check for resistance-only marker (excludes therapy but no targeted alternative)
        # Per AMP/ASCO/CAP: Resistance markers that affect treatment selection are Tier II
        # (e.g., NRAS mutations exclude anti-EGFR therapy in CRC - this IS clinically actionable)
        # Also checks PubMed literature for resistance evidence
        # Per guidelines/tier2.md scenario 5: Resistance without alternatives = Tier II-D
        is_resistance_only, drugs = self.is_resistance_marker_without_targeted_therapy(tumor_type)
        if is_resistance_only:
            drugs_str = ', '.join(drugs) if drugs else 'standard therapies'
            sublevel = self._get_tier_ii_sublevel(tumor_type, context="resistance")
            # Check if evidence comes from literature
            has_lit_evidence, lit_drugs, lit_pmids = self.has_literature_resistance_evidence()
            if has_lit_evidence:
                pmid_str = ', '.join(lit_pmids[:3])
                logger.info(f"Tier II-{sublevel}: {self.gene} {self.variant} in {tumor_type} is resistance marker (literature: PMIDs {pmid_str})")
                return f"TIER II-{sublevel} INDICATOR: Resistance marker that EXCLUDES {drugs_str} - supported by peer-reviewed literature (PMIDs: {pmid_str})"
            else:
                logger.info(f"Tier II-{sublevel}: {self.gene} {self.variant} in {tumor_type} is resistance marker excluding {drugs_str}")
                return f"TIER II-{sublevel} INDICATOR: Resistance marker that EXCLUDES {drugs_str} (no FDA-approved therapy FOR this variant)"

        # Check for prognostic/diagnostic only
        # Per AMP/ASCO/CAP: Prognostic without treatment implications = Tier II-C if well-established
        # Tier III if unknown significance
        if self.is_prognostic_or_diagnostic_only():
            # Check for strong prognostic/diagnostic evidence (Level A/B/C)
            has_strong_prognostic = any(
                ev.evidence_level in ['A', 'B', 'C'] and
                ev.evidence_type in ['PROGNOSTIC', 'DIAGNOSTIC']
                for ev in self.civic
            )
            # Check if there's ANY prognostic/diagnostic evidence (even weak Level D)
            has_any_prognostic = any(
                ev.evidence_type in ['PROGNOSTIC', 'DIAGNOSTIC']
                for ev in self.civic
            )
            if has_strong_prognostic:
                sublevel = self._get_tier_ii_sublevel(tumor_type, context="prognostic")
                logger.info(f"Tier II-{sublevel}: {self.gene} {self.variant} has strong prognostic/diagnostic evidence")
                return f"TIER II-{sublevel} INDICATOR: Prognostic/diagnostic marker with established clinical significance - no therapeutic impact"
            elif has_any_prognostic:
                # Has weak prognostic evidence (Level D) → Tier III-C
                sublevel = self._get_tier_iii_sublevel(tumor_type, context="prognostic_only")
                logger.info(f"Tier III-{sublevel}: {self.gene} {self.variant} is prognostic/diagnostic only (weak evidence)")
                return f"TIER III-{sublevel} INDICATOR: Prognostic/diagnostic only - no therapeutic impact, limited evidence"
            # No actual prognostic evidence - fall through to VUS/no evidence check below

        # Check for FDA approval in different tumor type (Tier II-A)
        # Per AMP/ASCO/CAP: FDA approved in different tumor = Tier II-A
        # IMPORTANT: Must verify the variant actually matches the approval criteria
        # (e.g., EGFR R108K does NOT match "EGFR mutation" approval - extracellular domain)
        has_fda_elsewhere = False
        for approval in self.fda_approvals:
            indication_lower = (approval.indication or '').lower()
            # Check if variant matches approval criteria (not just gene mention)
            if self._variant_matches_approval_class(
                self.gene, self.variant, indication_lower, approval, tumor_type=None
            ):
                has_fda_elsewhere = True
                break
        if not has_fda_elsewhere:
            for biomarker in self.cgi_biomarkers:
                if biomarker.fda_approved:
                    alt = (biomarker.alteration or '').upper()
                    if self.variant.upper() in alt or 'MUT' in alt:
                        has_fda_elsewhere = True
                        break
        if not has_fda_elsewhere:
            for ev in self.civic:
                if ev.evidence_level == 'A' and ev.evidence_type == 'PREDICTIVE':
                    sig = (ev.clinical_significance or '').upper()
                    if 'SENSITIVITY' in sig or 'RESPONSE' in sig:
                        has_fda_elsewhere = True
                        break

        if has_fda_elsewhere:
            sublevel = self._get_tier_ii_sublevel(tumor_type, context="fda_different_tumor")
            logger.info(f"Tier II-{sublevel}: {self.gene} {self.variant} has FDA approval in different tumor type")
            return f"TIER II-{sublevel} INDICATOR: FDA-approved therapy exists in different tumor type (off-label potential)"

        # Gene-level therapeutic evidence from CIViC aggregation
        # This enables gene-centric reasoning when variant-specific evidence is lacking
        # For DDR genes and other gene classes, loss-of-function mutations generally
        # have similar therapeutic implications even if the specific variant isn't well-characterized
        gene_summary = self.get_gene_level_therapeutic_summary(tumor_type)

        # Check if we have gene-level therapeutic evidence
        if gene_summary["sensitivities"] or gene_summary["resistances"]:
            _gene_config = load_gene_classes()
            is_ddr = _gene_config.is_ddr_gene(self.gene)

            # Format disease context
            all_diseases = set()
            for s in gene_summary["sensitivities"][:3]:
                all_diseases.update(s["diseases"][:2])
            for r in gene_summary["resistances"][:3]:
                all_diseases.update(r["diseases"][:2])
            disease_str = ", ".join(list(all_diseases)[:3])
            if len(all_diseases) > 3:
                disease_str += "..."

            # Handle conflicts first (same drug shows both sensitivity and resistance)
            if gene_summary["has_conflicts"]:
                conflict_drugs = [c["drug"] for c in gene_summary["conflicts"][:2]]
                conflict_str = ", ".join(conflict_drugs)
                gene_type = "DDR gene" if is_ddr else "cancer gene"
                logger.info(f"Tier II-C: {self.gene} {self.variant} {gene_type} with CONFLICTING evidence for {conflict_str}")
                return f"TIER II-C INDICATOR: {self.gene} is a {gene_type} with conflicting therapeutic evidence for {conflict_str}. Sensitivity shown in some contexts, resistance/no-benefit in others. Evidence from: {disease_str}. Requires careful disease-specific evaluation."

            # Check for sensitivity evidence
            if gene_summary["sensitivities"]:
                best_sens = gene_summary["sensitivities"][0]  # Already sorted by level
                sens_level = best_sens["level"]
                sens_drugs = [s["drug"] for s in gene_summary["sensitivities"][:3]]
                drugs_str = ", ".join(sens_drugs)

                # Determine tier based on evidence quality and disease match
                if sens_level in ["A", "B"]:
                    # High-quality sensitivity evidence
                    if gene_summary["disease_match"]:
                        # Evidence matches patient's tumor type - stronger signal
                        gene_type = "DDR gene" if is_ddr else "cancer gene"
                        logger.info(f"Tier II-B: {self.gene} {self.variant} {gene_type} with Level {sens_level} sensitivity in matching tumor")
                        return f"TIER II-B INDICATOR: {self.gene} is a {gene_type} with Level {sens_level} therapeutic sensitivity ({drugs_str}) demonstrated in {tumor_type}. Gene-level evidence suggests potential actionability."
                    else:
                        # Evidence from other tumor types
                        gene_type = "DDR gene" if is_ddr else "cancer gene"
                        logger.info(f"Tier II-D: {self.gene} {self.variant} {gene_type} with Level {sens_level} sensitivity in other cancers")
                        return f"TIER II-D INDICATOR: {self.gene} is a {gene_type} with therapeutic sensitivity ({drugs_str}) demonstrated in other cancers ({disease_str}). Variant-specific functional impact unknown but gene-level evidence suggests potential actionability."
                else:
                    # Lower quality sensitivity evidence (Level C/D)
                    gene_type = "DDR gene" if is_ddr else "cancer gene"
                    logger.info(f"Tier II-D: {self.gene} {self.variant} {gene_type} with Level {sens_level} sensitivity evidence")
                    return f"TIER II-D INDICATOR: {self.gene} is a {gene_type}. Preclinical/early evidence suggests sensitivity to {drugs_str} in other cancers ({disease_str}). Limited clinical validation."

        # =================================================================
        # GENE-CENTRIC FALLBACK CHAIN
        # =================================================================
        # When variant-specific evidence is lacking, use gene context + functional predictions
        # This provides therapeutic guidance based on gene role even without CIViC evidence

        gene_context = get_gene_context(self.gene)

        if gene_context.is_cancer_gene:
            # Assess LOF status using variant notation and predictions
            is_lof, lof_confidence, lof_rationale = get_lof_assessment(
                self.variant,
                snpeff_effect=self.snpeff_effect,
                polyphen2_prediction=self.polyphen2_prediction,
                cadd_score=self.cadd_score,
                alphamissense_prediction=self.alphamissense_prediction,
            )

            # Get therapeutic implication based on gene role
            therapeutic_note = get_therapeutic_implication(gene_context, is_lof)

            # Handle DDR genes - special therapeutic implications
            if gene_context.role == GeneRole.DDR:
                if is_lof or not lof_rationale or lof_rationale == "no functional predictions available":
                    # LOF confirmed or unknown (give benefit of doubt for DDR genes)
                    logger.info(f"Tier II-D: {self.gene} {self.variant} DDR gene (LOF: {lof_confidence})")
                    return (
                        f"TIER II-D INDICATOR: {self.gene} is a DDR gene. "
                        f"Variant {self.variant} ({lof_rationale}, confidence: {lof_confidence}). "
                        f"{therapeutic_note or 'Consider platinum/PARP inhibitor sensitivity.'}"
                    )
                else:
                    # DDR gene but variant is predicted tolerated
                    logger.info(f"Tier III-B: {self.gene} {self.variant} DDR gene but predicted tolerated")
                    return (
                        f"TIER III-B INDICATOR: {self.gene} is a DDR gene, but {self.variant} is "
                        f"predicted TOLERATED ({lof_rationale}). May not cause loss of function. "
                        "Functional testing recommended if clinical suspicion is high."
                    )

            elif gene_context.role == GeneRole.ONCOGENE:
                # For oncogenes, we need variant-specific evidence (hotspots matter)
                # Gene-level reasoning doesn't apply the same way
                logger.info(f"Tier III-B: {self.gene} {self.variant} oncogene without variant-specific evidence")
                return (
                    f"TIER III-B INDICATOR: {self.gene} is an oncogene. "
                    f"Variant {self.variant} lacks specific evidence. "
                    "Oncogene therapeutic implications depend on specific activating mutations - "
                    "this variant's effect is unknown."
                )

            elif gene_context.role == GeneRole.TSG:
                if is_lof:
                    logger.info(f"Tier III-B: {self.gene} {self.variant} TSG with predicted LOF")
                    return (
                        f"TIER III-B INDICATOR: {self.gene} is a tumor suppressor. "
                        f"Variant {self.variant} is predicted loss-of-function ({lof_rationale}). "
                        f"{therapeutic_note or 'Generally not directly targetable but confirms pathogenic variant.'}"
                    )
                else:
                    logger.info(f"Tier III-C: {self.gene} {self.variant} TSG without LOF prediction")
                    return (
                        f"TIER III-C INDICATOR: {self.gene} is a tumor suppressor, but {self.variant} "
                        f"is not clearly loss-of-function ({lof_rationale}). Clinical significance uncertain."
                    )

        # Use functional predictions to inform VUS classification (for genes not in curated lists)
        # If we have PolyPhen-2, CADD, or AlphaMissense predictions, use them to refine the tier
        if self.polyphen2_prediction or self.cadd_score or self.alphamissense_prediction:
            is_predicted_damaging = (
                self.polyphen2_prediction in ["probably_damaging", "possibly_damaging", "D", "P"] or
                (self.cadd_score is not None and self.cadd_score >= 20) or  # CADD >= 20 is often used as damaging threshold
                self.alphamissense_prediction in ["likely_pathogenic", "ambiguous", "pathogenic"]
            )

            if is_predicted_damaging:
                # Build prediction summary
                pred_parts = []
                if self.polyphen2_prediction:
                    pred_parts.append(f"PolyPhen2: {self.polyphen2_prediction}")
                if self.cadd_score is not None:
                    pred_parts.append(f"CADD: {self.cadd_score:.1f}")
                if self.alphamissense_prediction:
                    pred_parts.append(f"AlphaMissense: {self.alphamissense_prediction}")
                pred_summary = ", ".join(pred_parts)

                # Predicted damaging VUS - still Tier III-B but with additional context
                logger.info(f"Tier III-B: {self.gene} {self.variant} is VUS but predicted damaging ({pred_summary})")
                return f"TIER III-B INDICATOR: VUS in {self.gene} with predicted functional impact ({pred_summary}). Consider functional testing."

        # Check for VUS in known cancer gene (Tier III-B)
        # Per decision tree: "Is the variant in a known cancer gene? → YES, but function unknown → TIER III-B (VUS)"
        if self.is_vus_in_known_cancer_gene():
            sublevel = self._get_tier_iii_sublevel(tumor_type, context="vus")
            logger.info(f"Tier III-{sublevel}: {self.gene} {self.variant} is VUS in known cancer gene")
            return f"TIER III-{sublevel} INDICATOR: VUS in established cancer gene ({self.gene}) - functional impact unknown"

        # Default fallback - no evidence at all (gene not in known cancer gene list)
        sublevel = self._get_tier_iii_sublevel(tumor_type, context="no_evidence")
        return f"TIER III-{sublevel} INDICATOR: Investigational/emerging evidence only"

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

        # Flag if CIViC evidence is from different cancer types
        if tumor_type and self.civic:
            civic_diseases = [ev.disease for ev in self.civic if ev.disease]
            tumor_lower = tumor_type.lower()

            # Check if any CIViC evidence matches the queried tumor
            matching_diseases = [
                d for d in civic_diseases
                if tumor_lower in d.lower() or d.lower() in tumor_lower
            ]

            if civic_diseases and not matching_diseases:
                unique_diseases = list(set(civic_diseases))[:5]
                lines.append("⚠️ DISEASE CONTEXT WARNING: No CIViC evidence specific to " + tumor_type + ".")
                lines.append("   All evidence is from: " + ", ".join(unique_diseases))
                lines.append("   Gene-level extrapolation may not apply to this tumor type.")
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
        # But suppress the tier recommendation when FDA approval already exists
        # (literature extraction doesn't know about FDA approvals and may contradict)
        has_fda_approval = self.has_fda_for_variant_in_tumor(tumor_type)

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

            # Only include literature tier recommendation if no FDA approval exists
            # This prevents the LLM from being confused by conflicting tier signals
            if not has_fda_approval:
                lines.append(f"Literature Tier Recommendation: {lit.tier_recommendation.tier}")
                if lit.tier_recommendation.rationale:
                    lines.append(f"  Rationale: {lit.tier_recommendation.rationale}")
            else:
                lines.append("(Literature tier recommendation suppressed - FDA approval takes precedence)")

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