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
            'gist': ['gist', 'gastrointestinal stromal tumor', 'gastrointestinal stromal'],
            'gastrointestinal stromal tumor': ['gist', 'gastrointestinal stromal tumor', 'gastrointestinal stromal'],
            'bladder': ['bladder', 'urothelial', 'transitional cell'],
            'bladder cancer': ['bladder', 'urothelial', 'transitional cell', 'urothelial carcinoma'],
            'urothelial': ['urothelial', 'bladder', 'transitional cell'],
            'cholangiocarcinoma': ['cholangiocarcinoma', 'bile duct', 'biliary'],
            # Myeloproliferative neoplasms - these are DEFINED by MPL/JAK2/CALR mutations
            # The FDA labels say "myelofibrosis" or "polycythemia vera" but patients present
            # with a diagnosis of "myeloproliferative neoplasm" containing these mutations
            'myeloproliferative neoplasm': ['myelofibrosis', 'polycythemia vera', 'myeloproliferative', 'mpn'],
            'myeloproliferative': ['myelofibrosis', 'polycythemia vera', 'myeloproliferative', 'mpn'],
            'mpn': ['myelofibrosis', 'polycythemia vera', 'myeloproliferative', 'mpn'],
            'myelofibrosis': ['myelofibrosis', 'myeloproliferative'],
            'polycythemia vera': ['polycythemia vera', 'myeloproliferative'],
        }

        tumor_match = False
        matched_section = ""

        # Priority 0: Detect TUMOR-AGNOSTIC MSI-H/dMMR approvals
        # These apply to ANY solid tumor (endometrial, pancreatic, ovarian, etc.)
        # FDA label says "MSI-H or dMMR solid tumors" or "MSI-H or dMMR Cancer"
        # The [FDA APPROVED FOR MSI-H...] prefix indicates this is a tumor-agnostic approval
        msi_h_tumor_agnostic_patterns = [
            'fda approved for msi-h',
            'fda approved for dmmr',
            'microsatellite instability-high',
            'mismatch repair deficient',
        ]
        is_msi_h_approval = any(p in indication_lower for p in msi_h_tumor_agnostic_patterns)

        # For MSI-H/dMMR approvals, check if approval is tumor-agnostic (applies to all solid tumors)
        # vs tumor-specific (e.g., "MSI-H colorectal cancer" only applies to CRC)
        if is_msi_h_approval:
            # Check if this is a tumor-agnostic approval (no specific tumor mentioned with MSI-H)
            # Look for phrases like "MSI-H solid tumors" or "MSI-H Cancer" without a specific site
            tumor_agnostic_phrases = [
                'msi-h or dmmr cancer',
                'msi-h cancer',
                'dmmr cancer',
                'msi-h solid tumor',
                'dmmr solid tumor',
                'msi-h or mismatch repair deficient cancer',
                'microsatellite instability-high or mismatch repair deficient cancer',
            ]
            is_tumor_agnostic = any(p in indication_lower for p in tumor_agnostic_phrases)

            if is_tumor_agnostic:
                # This is a tumor-agnostic approval - applies to ANY solid tumor
                # Including endometrial, pancreatic, ovarian, gastric, etc.
                # Extract the MSI-H section as the matched section
                for pattern in ['[fda approved for msi-h', '[fda approved for dmmr']:
                    if pattern in indication_lower:
                        idx = indication_lower.find(pattern)
                        bracket_end = self.indication.find(']', idx)
                        if bracket_end > 0:
                            matched_section = self.indication[idx:bracket_end + 1]
                            tumor_match = True
                            break

                if not tumor_match:
                    # Fallback: find MSI-H mention in indication
                    for pattern in msi_h_tumor_agnostic_patterns:
                        if pattern in indication_lower:
                            idx = indication_lower.find(pattern)
                            start = max(0, idx - 50)
                            end = min(len(self.indication), idx + 300)
                            matched_section = self.indication[start:end]
                            tumor_match = True
                            break

        # Priority 1: If indication has a variant-specific section at the start (from fda.py),
        # use that section for line-of-therapy detection. This handles cases like TAGRISSO
        # where T790M has its own later-line indication separate from L858R/exon19del first-line.
        if not tumor_match and self.indication.startswith('[FDA APPROVED FOR'):
            # Extract the variant-specific section
            bracket_end = self.indication.find(']')
            if bracket_end > 0:
                variant_section = self.indication[:bracket_end + 1]
                # Check if this variant section mentions the tumor type
                variant_section_lower = variant_section.lower()
                for key, keywords in tumor_keywords.items():
                    if any(kw in tumor_lower for kw in keywords):
                        if any(kw in variant_section_lower for kw in keywords):
                            tumor_match = True
                            matched_section = variant_section
                            break
                if not tumor_match and tumor_lower in variant_section_lower:
                    tumor_match = True
                    matched_section = variant_section

        # Priority 2: Standard tumor type matching in full indication
        if not tumor_match:
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
            'has progressed',  # "whose disease has progressed on or after"
            'progressed on or after',
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

