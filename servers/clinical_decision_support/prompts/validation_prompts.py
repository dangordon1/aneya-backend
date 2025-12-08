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

TEXT TO VALIDATE:
{clinical_scenario}

VALID clinical consultations include:
- Patient symptoms and complaints (e.g., "Patient with fever and cough")
- Clinical presentations (e.g., "3-year-old with barking cough and stridor")
- Medical history and examination findings
- Requests for clinical decision support or treatment guidance
- Diagnostic scenarios

INVALID inputs include:
- Random statements unrelated to medicine (e.g., "I am feeling autistic", "What's the weather")
- General questions not about a specific patient case
- Non-medical topics
- Personal statements that aren't medical consultations
- Test inputs or nonsense text

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
