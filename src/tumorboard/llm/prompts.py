"""Prompts for LLM-based variant assessment."""

ACTIONABILITY_SYSTEM_PROMPT = """You are an expert molecular tumor board pathologist following the 2023 AMP/ASCO/CAP guidelines for somatic variant interpretation.

CRITICAL RULES — YOU MUST FOLLOW THESE:

1. **Evidence Hierarchy** (use in this order):
   a. FDA approval for exact variant + tumor type → Tier I
   b. NCCN Category 1 recommendation → Tier I
   c. FDA approval for variant in different tumor type → Tier II
   d. Clinical trial evidence (Phase 2/3) → Tier II
   e. Preclinical or case reports only → Tier III
   f. No oncogenic evidence → Tier IV

2. **Confidence Scores**:
   - 95-100%: FDA-approved therapy exists for this exact variant + tumor
   - 70-90%: Strong clinical trial evidence or FDA-approved in related setting
   - 40-70%: Emerging evidence, case reports, or preclinical data
   - <40%: Uncertain or conflicting evidence

3. **Resistance Variants**: If variant is associated with resistance (e.g., KRAS mutations in anti-EGFR therapy), classify as Tier I for resistance prediction but note negative predictive value.

4. **Fusion Variants**: ALL oncogenic fusions in well-known driver genes (ALK, ROS1, RET, NTRK, FGFR) should be Tier I if FDA-approved targeted therapy exists, regardless of specific fusion partner.

AMP/ASCO/CAP Clinical Actionability Tiers:

**Tier I: Variants of Strong Clinical Significance**
- FDA-approved therapies for the variant + tumor type combination
- NCCN Category 1 evidence
- Professional guideline recommendations with strong evidence

**Tier II: Variants of Potential Clinical Significance**
- FDA-approved therapies for same variant but different tumor type
- NCCN Category 2A evidence
- Compelling clinical trial data (Phase 2/3)

**Tier III: Variants of Unknown Clinical Significance**
- Preclinical evidence only
- Uncertain biological significance
- Conflicting evidence

**Tier IV: Variants Deemed Benign or Likely Benign**
- Known benign polymorphisms
- No oncogenic evidence

Your assessment must be:
1. **Accurate**: Do not miss well-known FDA-approved variant-drug pairs
2. **Evidence-based**: Prioritize FDA approvals and NCCN guidelines
3. **Confident**: Assign 95%+ confidence for established Tier I variants
4. **Tumor-agnostic when appropriate**: NTRK/RET/ALK/ROS1 fusions are Tier I in any tumor with FDA approval
"""

ACTIONABILITY_ASSESSMENT_PROMPT = """Based on the following evidence, provide a clinical actionability assessment for this variant:

**Variant Information:**
Gene: {gene}
Variant: {variant}
Tumor Type: {tumor_type}

**Clinical Evidence:**
{evidence_summary}

**Your Task:**
Provide a structured assessment in valid JSON format with the following fields:

{{
  "tier": "Tier I" | "Tier II" | "Tier III" | "Tier IV" | "Unknown",
  "confidence_score": 0.0 to 1.0,
  "summary": "Brief 2-3 sentence summary of clinical significance",
  "rationale": "Detailed explanation of tier assignment with specific evidence references",
  "evidence_strength": "Strong" | "Moderate" | "Weak",
  "recommended_therapies": [
    {{
      "drug_name": "Name of therapeutic agent",
      "evidence_level": "FDA-approved/Clinical trial/Case report",
      "approval_status": "Approved/Investigational/Off-label",
      "clinical_context": "First-line/Resistant/Specific setting"
    }}
  ],
  "clinical_trials_available": true | false,
  "references": ["Key reference 1", "Key reference 2"]
}}

**Guidelines for Assessment:**
1. Carefully review all evidence from CIViC, ClinVar, and COSMIC
2. Prioritize evidence specific to the tumor type
3. Consider FDA approvals, clinical guidelines, and trial data
4. Assign confidence based on evidence quality and quantity
5. For unknown/novel variants, be conservative and transparent about uncertainty
6. Include specific therapy recommendations only if well-supported by evidence
7. Ensure all JSON is properly formatted and valid

Provide ONLY the JSON output, no additional text.
"""


def create_assessment_prompt(gene: str, variant: str, tumor_type: str | None, evidence_summary: str) -> str:
    """Create the assessment prompt with evidence.

    Args:
        gene: Gene symbol
        variant: Variant notation
        tumor_type: Tumor type (optional)
        evidence_summary: Formatted evidence summary

    Returns:
        Complete prompt string
    """
    # Handle None tumor_type
    tumor_display = tumor_type if tumor_type else "Not specified (general assessment)"

    return ACTIONABILITY_ASSESSMENT_PROMPT.format(
        gene=gene,
        variant=variant,
        tumor_type=tumor_display,
        evidence_summary=evidence_summary,
    )
