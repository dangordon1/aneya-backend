"""
Prompt templates for drug-related AI interactions.

This module contains prompt functions used by the Clinical Decision Support client
for drug validation, information generation, dosing extraction, and special considerations.
"""


def get_drug_validation_prompt(drug_name: str) -> str:
    """
    Generate a prompt for validating whether a drug name is a real medication.

    This prompt instructs the AI to determine if the provided drug name corresponds
    to a real medication (brand or generic), considering common misspellings and
    returning structured validation results.

    Args:
        drug_name: The drug name to validate (brand or generic name)

    Returns:
        A formatted prompt string for drug validation

    Example:
        >>> prompt = get_drug_validation_prompt("Paracetamol")
        >>> # Use with Claude API to validate the drug name
    """
    return f"""You are a clinical pharmacist validating medication names.

TASK: Determine if "{drug_name}" is a real medication (brand or generic name).

Consider:
- Generic names (e.g., Paracetamol, Amoxicillin)
- Brand names (e.g., Tylenol, Augmentin)
- Common misspellings of real drugs
- Non-existent or fabricated drug names

CRITICAL: Respond with ONLY a JSON object:
{{
  "is_real": true/false,
  "reasoning": "Brief explanation (1-2 sentences)",
  "generic_name": "Generic name if real, empty string if not"
}}

Examples:
- "Paracetamol" → {{"is_real": true, "reasoning": "Common analgesic/antipyretic", "generic_name": "Paracetamol"}}
- "Amoxicillin" → {{"is_real": true, "reasoning": "Beta-lactam antibiotic", "generic_name": "Amoxicillin"}}
- "Xyzzylox" → {{"is_real": false, "reasoning": "Not a recognized medication", "generic_name": ""}}
"""


def get_drug_info_generation_prompt(drug_name: str, generic_name: str = None) -> str:
    """
    Generate a prompt for creating comprehensive drug information in BNF style.

    This prompt instructs the AI to generate detailed prescribing information
    following the British National Formulary (BNF) format, including indications,
    dosage, contraindications, side effects, and special populations.

    Args:
        drug_name: The drug name (original query)
        generic_name: Generic name if known (from validation), defaults to None

    Returns:
        A formatted prompt string for drug information generation

    Example:
        >>> prompt = get_drug_info_generation_prompt("Tylenol", "Paracetamol")
        >>> # Use with Claude API to generate comprehensive drug info
    """
    name_to_use = generic_name or drug_name

    return f"""You are a clinical pharmacist providing comprehensive drug information for "{name_to_use}".

TASK: Generate detailed prescribing information in the style of the British National Formulary (BNF).

Provide information in the following structured format. For each field, write 2-4 concise sentences with SPECIFIC details (doses, frequencies, durations, specific contraindications).

CRITICAL INSTRUCTIONS:
1. Use ONLY your medical knowledge from training data
2. Provide SPECIFIC dosing (e.g., "500mg orally three times daily")
3. List SPECIFIC contraindications and interactions
4. If information for a field is unknown or uncertain, write "Information not available"
5. Focus on adult dosing (include pediatric only if significantly different)
6. Respond with ONLY a JSON object (no other text)

JSON Format:
{{
  "drug_name": "{name_to_use}",
  "indications": "Primary therapeutic uses and approved indications (2-3 sentences with specific conditions)",
  "dosage": "Specific adult dosing with route, frequency, and duration for main indications (e.g., 'Oral: 500mg three times daily for 7 days for respiratory infections')",
  "contraindications": "Absolute contraindications (specific conditions, not general warnings)",
  "cautions": "Situations requiring dose adjustment or careful monitoring (specific populations or conditions)",
  "side_effects": "Common and serious adverse effects with approximate frequencies if known (e.g., 'Common: nausea (10-15%), headache (5%)')",
  "interactions": "Major drug interactions with specific mechanisms and clinical significance",
  "pregnancy": "Safety in pregnancy with FDA/BNF category if applicable and specific trimester concerns",
  "breast_feeding": "Safety during lactation with concentration in breast milk if known",
  "renal_impairment": "Specific dose adjustments for renal impairment (e.g., 'CrCl <30: reduce dose by 50%')",
  "hepatic_impairment": "Specific dose adjustments for hepatic impairment with Child-Pugh staging if relevant",
  "prescribing_info": "Additional prescribing notes: monitoring requirements, administration tips, storage"
}}

Example for Paracetamol:
{{
  "drug_name": "Paracetamol",
  "indications": "Mild to moderate pain relief and fever reduction. Used for headache, musculoskeletal pain, dysmenorrhea, and post-operative pain.",
  "dosage": "Oral: Adults 500-1000mg every 4-6 hours (maximum 4g daily). Children 10-15mg/kg every 4-6 hours. Intravenous: 1g every 6 hours for severe pain.",
  "contraindications": "Severe hepatic impairment. Hypersensitivity to paracetamol.",
  "cautions": "Chronic alcohol use, hepatic impairment, malnutrition, dehydration. Risk of hepatotoxicity with overdose (>4g/day in adults).",
  "side_effects": "Rare: rash, blood disorders. Serious: hepatotoxicity with overdose (dose-dependent, potentially fatal).",
  "interactions": "Warfarin (prolonged use may enhance anticoagulant effect). Carbamazepine, phenytoin (increased metabolism, reduced efficacy).",
  "pregnancy": "Safe in pregnancy at therapeutic doses. Category A - no evidence of harm.",
  "breast_feeding": "Safe during breastfeeding. Small amounts in breast milk, not harmful.",
  "renal_impairment": "CrCl 10-50: increase dosing interval to every 6 hours. CrCl <10: increase interval to every 8 hours.",
  "hepatic_impairment": "Use with caution. Reduce dose in severe impairment. Avoid in acute liver failure.",
  "prescribing_info": "Monitor liver function in chronic use. Patients should be warned about overdose risk with combined paracetamol products."
}}

Now generate information for: {name_to_use}
"""


def get_dosing_extraction_prompt(medication_name: str, condition: str, dosage_text: str) -> str:
    """
    Generate a prompt for extracting specific adult dosing information from BNF text.

    This prompt is used to parse comprehensive BNF dosage information and extract
    the specific dosing regimen relevant to a particular condition.

    Args:
        medication_name: The name of the medication
        condition: The medical condition being treated
        dosage_text: The BNF dosage text to extract from (will be truncated to 2000 chars)

    Returns:
        A formatted prompt string for dosing extraction

    Example:
        >>> prompt = get_dosing_extraction_prompt("Amoxicillin", "pneumonia", bnf_dosage_text)
        >>> # Use with Claude API to extract specific dosing
    """
    return f"""Extract the ADULT dosing for {medication_name} for treating {condition}.

BNF Dosage Information (first 2000 characters):
{dosage_text[:2000]}

Return ONLY a JSON object with these fields:
{{
  "dose": "concise adult dose (e.g., 500mg three times daily)",
  "route": "oral/intravenous/intramuscular",
  "duration": "treatment duration (e.g., 5-7 days)"
}}

Focus on: {condition}. Be concise. If not found, use most common adult dose."""


def get_special_considerations_prompt(drug_name: str, renal_text: str, hepatic_text: str, pregnancy_text: str) -> str:
    """
    Generate a prompt for extracting concise special considerations from BNF text.

    This prompt is used to summarize BNF information about special populations
    including renal impairment, hepatic impairment, and pregnancy considerations.

    Args:
        drug_name: The name of the drug
        renal_text: BNF text about renal impairment
        hepatic_text: BNF text about hepatic impairment
        pregnancy_text: BNF text about pregnancy

    Returns:
        A formatted prompt string for special considerations extraction

    Example:
        >>> prompt = get_special_considerations_prompt("Metformin", renal_info, hepatic_info, preg_info)
        >>> # Use with Claude API to extract special considerations
    """
    return f"""Extract CONCISE special considerations for {drug_name}.

BNF Information:
Renal Impairment: {renal_text[:800] if renal_text else ''}
Hepatic Impairment: {hepatic_text[:800] if hepatic_text else ''}
Pregnancy: {pregnancy_text[:800] if pregnancy_text else ''}

Return ONLY a JSON object with BRIEF (1-2 sentence) summaries:
{{
  "renal_impairment": "brief summary or 'No specific adjustments mentioned'",
  "hepatic_impairment": "brief summary or 'No specific adjustments mentioned'",
  "pregnancy": "brief summary or 'No specific concerns mentioned'"
}}

Be extremely concise. Focus on key dose adjustments and safety warnings only."""


def get_patient_tailored_drug_prompt(
    drug_name: str,
    bnf_data: dict,
    patient_context: dict
) -> str:
    """
    Generate a prompt for tailoring drug prescribing information to a specific patient.

    This prompt takes raw BNF drug data and patient context to generate personalized
    prescribing guidance that considers the patient's age, comorbidities, current
    medications, allergies, and clinical presentation.

    Args:
        drug_name: The name of the drug
        bnf_data: Raw BNF data including indications, dosage, contraindications, etc.
        patient_context: Dictionary containing:
            - clinical_scenario: The full clinical presentation
            - patient_age: Patient's age (if known)
            - allergies: Known allergies
            - diagnosis: The diagnosis this drug is being prescribed for

    Returns:
        A formatted prompt string for patient-tailored drug guidance

    Example:
        >>> prompt = get_patient_tailored_drug_prompt(
        ...     "Amoxicillin",
        ...     bnf_data,
        ...     {"clinical_scenario": "...", "patient_age": "45", "allergies": "None"}
        ... )
    """
    # Extract patient context
    clinical_scenario = patient_context.get('clinical_scenario', '')
    patient_age = patient_context.get('patient_age', 'Not specified')
    allergies = patient_context.get('allergies', 'None known')
    diagnosis = patient_context.get('diagnosis', 'Not specified')

    # Format BNF data for the prompt
    bnf_sections = []
    for key, value in bnf_data.items():
        if value and key not in ['url', 'source']:
            bnf_sections.append(f"{key.upper()}: {value}")
    bnf_text = "\n".join(bnf_sections)

    return f"""You are a clinical pharmacist providing personalized prescribing guidance.

PATIENT CONTEXT:
- Clinical Presentation: {clinical_scenario[:1500]}
- Age: {patient_age}
- Known Allergies: {allergies}
- Diagnosis: {diagnosis}

DRUG: {drug_name}

BNF PRESCRIBING INFORMATION:
{bnf_text[:3000]}

TASK: Generate PERSONALIZED prescribing guidance for this specific patient.

Consider:
1. PATIENT-SPECIFIC DOSING: Adjust dose based on age, weight indicators, renal/hepatic function mentioned
2. DRUG INTERACTIONS: Check for interactions with any medications mentioned in the clinical scenario
3. CONTRAINDICATIONS: Flag any contraindications based on patient's comorbidities
4. WARNINGS: Highlight relevant cautions for this patient's specific conditions
5. MONITORING: Suggest monitoring parameters relevant to this patient

CRITICAL INSTRUCTIONS:
1. Be SPECIFIC to THIS patient - do not give generic advice
2. Highlight any safety concerns prominently
3. If information is insufficient for personalization, note what additional information would be needed
4. Focus on practical, actionable guidance
5. Respond with ONLY a JSON object

JSON Format:
{{
  "drug_name": "{drug_name}",
  "recommended_dose": "Specific dose for THIS patient with reasoning",
  "route": "Route of administration",
  "frequency": "Dosing frequency",
  "duration": "Recommended treatment duration",
  "patient_specific_warnings": ["List of warnings specific to this patient's conditions/medications"],
  "contraindication_check": {{
    "safe_to_prescribe": true/false,
    "concerns": ["Any concerns based on patient's conditions"],
    "absolute_contraindications": ["Any absolute contraindications found"]
  }},
  "drug_interactions": ["List of potential interactions with patient's current medications"],
  "monitoring_required": ["Specific monitoring parameters for this patient"],
  "special_instructions": "Any special administration instructions for this patient",
  "clinical_pearls": "Brief clinical insight specific to this patient's presentation"
}}

Example for a diabetic patient on metformin receiving Amoxicillin:
{{
  "drug_name": "Amoxicillin",
  "recommended_dose": "500mg three times daily - standard dose appropriate as no renal impairment indicated",
  "route": "Oral",
  "frequency": "Every 8 hours",
  "duration": "5-7 days for community-acquired pneumonia",
  "patient_specific_warnings": ["Monitor blood glucose - antibiotics can affect glycemic control in diabetic patients"],
  "contraindication_check": {{
    "safe_to_prescribe": true,
    "concerns": ["No penicillin allergy documented - confirm before prescribing"],
    "absolute_contraindications": []
  }},
  "drug_interactions": ["No significant interaction with metformin"],
  "monitoring_required": ["Clinical response at 48-72 hours", "Blood glucose monitoring"],
  "special_instructions": "Take with or without food. Complete full course.",
  "clinical_pearls": "First-line for mild CAP in patient with controlled diabetes. Consider macrolide if atypical pathogens suspected."
}}

Now generate personalized guidance for {drug_name} for this patient:"""
