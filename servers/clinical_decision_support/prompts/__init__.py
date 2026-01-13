"""
Prompt templates for Clinical Decision Support.

This module contains all prompts used by the clinical decision support system,
organized by category.
"""

from .validation_prompts import (
    get_clinical_validation_prompt,
    get_search_term_extraction_prompt,
)

from .diagnosis_prompts import (
    get_diagnosis_analysis_prompt,
    get_pubmed_fallback_prompt,
    get_literature_fallback_prompt,
)

from .drug_prompts import (
    get_drug_validation_prompt,
    get_drug_info_generation_prompt,
    get_dosing_extraction_prompt,
    get_special_considerations_prompt,
    get_patient_tailored_drug_prompt,
)

from .analysis_prompts import (
    get_guideline_analysis_prompt,
    get_bnf_analysis_prompt,
)

__all__ = [
    # Validation
    'get_clinical_validation_prompt',
    'get_search_term_extraction_prompt',
    # Diagnosis
    'get_diagnosis_analysis_prompt',
    'get_pubmed_fallback_prompt',
    'get_literature_fallback_prompt',
    # Drug
    'get_drug_validation_prompt',
    'get_drug_info_generation_prompt',
    'get_dosing_extraction_prompt',
    'get_special_considerations_prompt',
    'get_patient_tailored_drug_prompt',
    # Analysis
    'get_guideline_analysis_prompt',
    'get_bnf_analysis_prompt',
]
