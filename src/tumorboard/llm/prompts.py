# tumorboard/prompts.py
"""
Prompts for variant actionability narrative generation.
The tier is determined by deterministic logic - the LLM only writes the explanation.
"""

NARRATIVE_SYSTEM_PROMPT = """You are an expert molecular tumor board pathologist writing a concise clinical summary for a variant that has already been classified.

You do NOT decide the tier - that has been computed deterministically. Write a single cohesive narrative that:
1. States the clinical significance of this variant
2. Notes any therapeutic implications (approved therapies, contraindications, or trials)
3. Is suitable for a clinical report

Keep it focused: 3-5 sentences total. Prioritize actionable information."""

NARRATIVE_USER_PROMPT = """Write a clinical summary for this variant classification:

Gene: {gene}
Variant: {variant}
Tumor Type: {tumor_type}
Assigned Tier: {tier}
Classification Reason: {tier_reason}
{resistance_note_section}
Evidence Summary:
{evidence_summary}

Respond with JSON:
{{
  "narrative": "3-5 sentence clinical summary covering significance and therapeutic implications"
}}
"""


def create_narrative_prompt(
    gene: str,
    variant: str,
    tumor_type: str | None,
    tier: str,
    tier_reason: str,
    evidence_summary: str,
    resistance_note: str | None = None,
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
        resistance_note: Optional note about resistance/sensitivity (e.g., for BRAF Class II mutations)

    Returns:
        Messages list for LLM API call
    """
    tumor_display = tumor_type if tumor_type else "Unspecified"

    # Format resistance note section if provided
    resistance_note_section = ""
    if resistance_note:
        resistance_note_section = f"\nIMPORTANT - Resistance/Sensitivity Note: {resistance_note}\n"

    user_content = NARRATIVE_USER_PROMPT.format(
        gene=gene,
        variant=variant,
        tumor_type=tumor_display,
        tier=tier,
        tier_reason=tier_reason,
        resistance_note_section=resistance_note_section,
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
