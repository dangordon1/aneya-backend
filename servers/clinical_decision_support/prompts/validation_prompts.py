"""
Validation prompts for Clinical Decision Support.

Contains prompts for validating clinical input and extracting search terms.
"""


def get_clinical_validation_prompt(clinical_scenario: str) -> str:
    """
    Generate a prompt to validate if input is a genuine clinical consultation.

    Args:
        clinical_scenario: The text to validate

    Returns:
        Formatted prompt string for validation
    """
    return f"""You are a medical consultation validator. Your job is to determine if the following text represents a genuine clinical consultation or medical scenario.

IMPORTANT: Be LENIENT with transcribed conversations that may have:
- Grammar errors or poor sentence structure
- Repetitions or fragmented dialogue
- Unclear phrasing or translation issues
- Conversational filler words or incomplete sentences

As long as the text contains ANY genuine medical content (symptoms, conditions, patient details, medical history), mark it as VALID.

TEXT TO VALIDATE:
{clinical_scenario}

VALID clinical consultations include:
- Patient symptoms and complaints (e.g., "Patient with fever and cough")
- Clinical presentations (e.g., "3-year-old with barking cough and stridor")
- Medical history and examination findings
- Requests for clinical decision support or treatment guidance
- Diagnostic scenarios
- Transcribed conversations with medical terminology, even if poorly structured
- Discussions mentioning conditions, medications, symptoms, or patient details

INVALID inputs (only reject clearly non-medical content):
- Completely unrelated to medicine (e.g., "What's the weather", "Hello world")
- No medical context whatsoever
- Pure test inputs with no clinical information (e.g., "test test test")
- Marketing or spam content

If there is ANY legitimate medical content, symptoms, conditions, or patient information present, mark it as VALID even if the text is poorly formatted or fragmented.

Respond with ONLY a JSON object:
{{
  "is_valid": true/false,
  "reason": "brief explanation of why this is or isn't a clinical consultation"
}}

Do not include any other text besides the JSON object."""


def get_search_term_extraction_prompt(clinical_scenario: str) -> str:
    """
    Generate a prompt to extract key medical conditions for guideline search.

    Args:
        clinical_scenario: The clinical consultation text

    Returns:
        Formatted prompt string for search term extraction
    """
    return f"""Extract the PRIMARY medical condition or symptom from this clinical consultation for searching medical guidelines.

Consultation: "{clinical_scenario}"

Return ONLY 1-3 words describing the core medical condition (e.g., "throat infection", "pneumonia", "asthma exacerbation").
Do NOT include:
- Medication names
- Dosages
- Instructions like "prescribe" or "treat"
- Patient details

Examples:
- "prescribe amoxicillin 500mg for bacterial throat infection" → "throat infection"
- "3-year-old with croup and stridor" → "croup"
- "patient with pneumonia needs antibiotics" → "pneumonia"

Medical condition:"""
