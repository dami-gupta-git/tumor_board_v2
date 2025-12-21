# tumorboard/prompts.py
"""
Prompts for variant actionability narrative generation.
The tier is determined by deterministic logic - the LLM only writes the explanation.
"""

NARRATIVE_SYSTEM_PROMPT = """You are an expert molecular tumor board pathologist. Your job is to write a clear, concise clinical explanation for a variant classification that has already been determined.

You do NOT decide the tier - that has been computed deterministically. Your role is to:
1. Explain WHY this tier was assigned based on the evidence provided
2. Summarize the key evidence supporting this classification
3. Note any therapeutic implications or clinical recommendations
4. Write in plain language suitable for a clinical report

Keep your response focused and professional. 2-4 sentences for the summary, 3-5 sentences for the rationale."""

NARRATIVE_USER_PROMPT = """Write a clinical explanation for the following variant classification:

Gene: {gene}
Variant: {variant}
Tumor Type: {tumor_type}
Assigned Tier: {tier}
Classification Reason: {tier_reason}

Evidence Summary:
{evidence_summary}

Respond with JSON:
{{
  "summary": "2-4 sentence clinical significance summary for the report",
  "rationale": "3-5 sentence explanation of why this tier was assigned, citing key evidence",
  "therapeutic_note": "Brief note on therapeutic implications (or null if none)",
  "key_evidence": ["evidence point 1", "evidence point 2", ...]
}}
"""


def create_narrative_prompt(
    gene: str,
    variant: str,
    tumor_type: str | None,
    tier: str,
    tier_reason: str,
    evidence_summary: str,
) -> list[dict]:
    """
    Create a prompt for the LLM to write a narrative explanation of a pre-computed tier.

    Args:
        gene: Gene symbol
        variant: Variant notation
        tumor_type: Patient's tumor type
        tier: The pre-computed tier (e.g., "Tier I-B", "Tier II-A")
        tier_reason: The reason from get_tier_hint() explaining why this tier
        evidence_summary: Formatted evidence for context

    Returns:
        Messages list for LLM API call
    """
    tumor_display = tumor_type if tumor_type else "Unspecified"

    user_content = NARRATIVE_USER_PROMPT.format(
        gene=gene,
        variant=variant,
        tumor_type=tumor_display,
        tier=tier,
        tier_reason=tier_reason,
        evidence_summary=evidence_summary.strip()[:3000],  # Limit context size
    )

    return [
        {"role": "system", "content": NARRATIVE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content}
    ]


# Keep the old prompt for backwards compatibility if needed
ACTIONABILITY_SYSTEM_PROMPT = NARRATIVE_SYSTEM_PROMPT
ACTIONABILITY_USER_PROMPT = NARRATIVE_USER_PROMPT

def create_assessment_prompt(
    gene: str,
    variant: str,
    tumor_type: str | None,
    evidence_summary: str
) -> list[dict]:
    """
    Legacy function - redirects to narrative prompt with placeholder tier.
    Use create_narrative_prompt() directly for new code.
    """
    # Extract tier from evidence summary if present
    tier = "Unknown"
    tier_reason = "See evidence summary"

    if "TIER I" in evidence_summary:
        tier = "Tier I"
    elif "TIER II" in evidence_summary:
        tier = "Tier II"
    elif "TIER III" in evidence_summary:
        tier = "Tier III"
    elif "TIER IV" in evidence_summary:
        tier = "Tier IV"

    return create_narrative_prompt(
        gene=gene,
        variant=variant,
        tumor_type=tumor_type,
        tier=tier,
        tier_reason=tier_reason,
        evidence_summary=evidence_summary,
    )
