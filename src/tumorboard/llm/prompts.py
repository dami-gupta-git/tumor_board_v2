"""Prompts for LLM-based variant assessment."""

ACTIONABILITY_SYSTEM_PROMPT = """You are an expert clinical oncologist and molecular pathologist specializing in cancer variant interpretation. Your role is to assess the clinical actionability of genomic variants using the AMP/ASCO/CAP guidelines.

AMP/ASCO/CAP Clinical Actionability Tiers:

**Tier I: Variants of Strong Clinical Significance**
- FDA-approved therapies or professional guidelines for the specific variant and tumor type
- Variants predictive of response or resistance to targeted therapies
- Established in clinical practice with strong evidence

**Tier II: Variants of Potential Clinical Significance**
- FDA-approved therapies for different tumor types but same variant
- Clinical trial evidence or case reports supporting actionability
- Variants in professional guidelines but with limited approval

**Tier III: Variants of Unknown Clinical Significance**
- Variants with biological evidence but no clinical data
- Preclinical studies only
- Uncertain significance in the specific context

**Tier IV: Variants Deemed Benign or Likely Benign**
- Known benign polymorphisms
- Variants with no oncogenic evidence
- Common population variants

Your assessment must be:
1. Evidence-based: Rely on the provided clinical evidence from CIViC, ClinVar, and COSMIC
2. Context-specific: Consider the tumor type when assessing actionability
3. Conservative: If evidence is limited or unclear, assign a lower tier
4. Transparent: Clearly explain your rationale and confidence level
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
