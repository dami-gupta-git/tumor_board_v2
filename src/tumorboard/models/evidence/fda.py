from pydantic import BaseModel, Field

class FDAApproval(BaseModel):
    """FDA drug approval information."""

    drug_name: str | None = None
    brand_name: str | None = None
    generic_name: str | None = None
    indication: str | None = None
    approval_date: str | None = None
    marketing_status: str | None = None
    gene: str | None = None
    variant_in_indications: bool = False
    variant_in_clinical_studies: bool = False

    def parse_indication_for_tumor(self, tumor_type: str) -> dict:
        """Parse FDA indication text to extract line-of-therapy and approval type for a specific tumor."""
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

        tumor_keys = []
        for key, keywords in tumor_keywords.items():
            if any(kw in tumor_lower for kw in keywords):
                tumor_keys = keywords
                break
        if not tumor_keys:
            tumor_keys = [tumor_lower]

        for kw in tumor_keys:
            if kw in indication_lower:
                tumor_match = True
                idx = indication_lower.find(kw)
                start = max(0, idx - 50)
                next_section_markers = [
                    'non-small cell lung cancer',
                    'nsclc)',
                    'melanoma •',
                    'breast cancer',
                    'thyroid cancer',
                    'limitations of use',
                    '1.1 braf',
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

