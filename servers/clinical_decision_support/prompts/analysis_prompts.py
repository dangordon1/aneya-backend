"""
Analysis prompt functions for clinical decision support.

This module contains prompt engineering functions that construct detailed prompts
for analyzing clinical guidelines and BNF treatment summaries using Claude.
"""

from typing import List, Optional


def get_guideline_analysis_prompt(
    clinical_scenario: str,
    patient_info: Optional[dict],
    guideline_contents: List[dict],
    cks_contents: List[dict],
    location_info: Optional[dict]
) -> str:
    """
    Generate a prompt for analyzing clinical guidelines to extract diagnoses and treatments.

    This prompt instructs Claude to analyze NICE guidelines, FOGSI guidelines, and CKS
    (Clinical Knowledge Summaries) to identify potential diagnoses and treatment options
    based on a clinical scenario.

    Args:
        clinical_scenario: Patient case description
        patient_info: Patient information dictionary with keys:
            - success: Whether patient info was successfully retrieved
            - age: Patient age
            - gender: Patient gender
            - weight_kg: Patient weight in kg
            - current_medications: List of current medications
            - existing_conditions: List of existing conditions
            - allergies: List of allergies
        guideline_contents: List of guideline dictionaries. Each can be either:
            - NICE guideline with keys: reference, title, url, published_date, overview, sections
            - FOGSI guideline with keys: title, url, category, overview, content, sections
        cks_contents: List of CKS guideline dictionaries with keys:
            - title: CKS title
            - url: CKS URL
            - summary: Summary text
            - management: Management guidance
            - prescribing: Prescribing information
        location_info: User location dictionary with keys:
            - country: Country name
            - country_code: ISO country code (e.g., 'GB' for UK)

    Returns:
        Formatted prompt string for Claude API
    """
    # Build location context
    location_context = ""
    if location_info:
        location_context = f"""
User Location:
- Country: {location_info.get('country')} ({location_info.get('country_code')})
- Healthcare System: {'NHS (UK)' if location_info.get('country_code') == 'GB' else 'International'}
"""

    # Build patient context
    patient_context = ""
    if patient_info and patient_info.get('success'):
        patient_context = f"""
Patient Information:
- Age: {patient_info.get('age')}
- Gender: {patient_info.get('gender')}
- Weight: {patient_info.get('weight_kg')}kg
- Current medications: {', '.join(patient_info.get('current_medications', [])) or 'None'}
- Existing conditions: {', '.join(patient_info.get('existing_conditions', [])) or 'None'}
- Allergies: {', '.join(patient_info.get('allergies', [])) or 'None'}
"""

    # Build guidelines context - combine both NICE guidelines and CKS
    guidelines_context = ""
    guideline_num = 1

    # Add guidelines (NICE or FOGSI)
    for guideline in guideline_contents:
        # Check if this is a NICE guideline (has 'reference') or FOGSI guideline
        if 'reference' in guideline:
            # NICE guideline
            guidelines_context += f"""
--- Guideline {guideline_num}: {guideline['reference']} - {guideline['title']} ---
URL: {guideline['url']}
Published: {guideline['published_date']}
Overview: {guideline['overview'][:1000]}

Sections:
"""
            for section in guideline['sections'][:5]:  # Limit to first 5 sections
                # sections are strings (section titles), not dictionaries
                guidelines_context += f"  • {section}\n"
        else:
            # FOGSI guideline
            guidelines_context += f"""
--- Guideline {guideline_num}: {guideline['title']} ---
URL: {guideline['url']}
Category: {guideline.get('category', 'General')}
Overview: {guideline['overview'][:1000]}

Content Summary:
{guideline.get('content', '')[:2000]}

Sections:
"""
            for section in guideline['sections'][:5]:  # Limit to first 5 sections
                if isinstance(section, dict):
                    guidelines_context += f"  • {section.get('heading', 'Section')}\n"
                else:
                    guidelines_context += f"  • {section}\n"

        guidelines_context += "\n"
        guideline_num += 1

    # Add CKS guidelines
    for cks in cks_contents:
        guidelines_context += f"""
--- Guideline {guideline_num}: CKS - {cks['title']} ---
URL: {cks['url']}
Summary: {cks['summary']}

Management: {cks['management'][:1000]}

Prescribing: {cks['prescribing'][:1000]}

"""
        guideline_num += 1

    # Create the prompt for Claude
    prompt = f"""You are a clinical decision support AI assistant analyzing medical guidelines for a patient case.

Clinical Scenario:
{clinical_scenario}

{location_context}{patient_context}

Available NICE Guidelines and Clinical Knowledge Summaries:
{guidelines_context}

Based on the clinical scenario and the available guidelines above, identify possible diagnoses and treatment options.

CRITICAL: You MUST respond with valid JSON only. Even if information is limited, return valid JSON format with empty arrays if needed.

Return your analysis in the following JSON format:
{{
  "diagnoses": [
    {{
      "diagnosis": "Diagnosis name (e.g., Community-Acquired Pneumonia)",
      "source": "NICE guideline reference or CKS",
      "guideline_url": "URL from above - MUST match the specific guideline that supports THIS diagnosis",
      "summary": "Brief clinical summary based on scenario and patient info",
      "confidence": "high|medium|low",
      "treatments": [
        {{
          "treatment_name": "Treatment approach (e.g., Antibiotic Therapy, Oxygen Therapy)",
          "treatment_type": "pharmacological|procedural|supportive",
          "description": "Brief description",
          "medication_names": ["medication1", "medication2"],
          "non_pharmacological_interventions": ["intervention1", "intervention2"],
          "notes": "Important notes"
        }}
      ],
      "follow_up": {{
        "timeframe": "When patient should be reviewed (e.g., 48-72 hours, 1 week, 2 weeks)",
        "monitoring": ["What to monitor (e.g., symptom resolution, vital signs, wound healing)"],
        "referral_criteria": ["When to refer or escalate care (e.g., worsening symptoms, no improvement after X days)"]
      }}
    }}
  ]
}}

Instructions:
- ALWAYS return valid JSON, never plain text
- CRITICAL: For each diagnosis, use the guideline_url from the SPECIFIC guideline that supports that diagnosis. Do not mix up URLs between different diagnoses.
- If guidelines lack specific details, infer reasonable diagnoses from the clinical scenario
- For the scenario "{clinical_scenario}", identify the most likely diagnosis even if full guideline content is not available
- Include ALL treatment approaches: pharmacological, procedural, and supportive care
- IMPORTANT: For each treatment, specify treatment_type as:
  * "pharmacological" - medications and drugs
  * "procedural" - interventions like splinting, suturing, intubation, drainage
  * "supportive" - care like oxygen therapy, wound dressings, physiotherapy, RICE protocol
- CRITICAL: Always include non_pharmacological_interventions for appropriate conditions:
  * Fractures: splinting, immobilization, ice, elevation
  * Bleeding/hemorrhage: direct pressure, tourniquet application, elevation
  * Wounds: wound cleaning, debridement, sterile dressings, wound irrigation
  * Respiratory: oxygen therapy, positioning (semi-recumbent), nebulization
  * Musculoskeletal: RICE protocol (Rest, Ice, Compression, Elevation), physiotherapy, exercises
  * Burns: cooling, sterile dressings, fluid resuscitation
  * Infections: wound care, drainage of abscesses
- Provide comprehensive follow_up guidance for each diagnosis:
  * timeframe: specific time period for review
  * monitoring: what clinical parameters to track
  * referral_criteria: red flags requiring escalation
- Use confidence level "medium" or "low" if inferring from limited information
- Extract medication names when mentioned in the guidelines
- If no specific medications found in guidelines, leave medication_names as empty array
- If no non-pharmacological interventions apply, leave non_pharmacological_interventions as empty array
- Order diagnoses by clinical relevance to the scenario"""

    return prompt


def get_bnf_analysis_prompt(
    clinical_scenario: str,
    patient_info: Optional[dict],
    diagnoses: List[dict],
    bnf_summary_contents: List[dict]
) -> str:
    """
    Generate a prompt for analyzing BNF treatment summaries to extract prescribing guidance.

    This prompt instructs Claude to analyze BNF (British National Formulary) treatment
    summaries and extract specific medication recommendations, dosing information, and
    special considerations for prescribing.

    Args:
        clinical_scenario: Patient case description
        patient_info: Patient information dictionary with keys:
            - success: Whether patient info was successfully retrieved
            - age: Patient age
            - gender: Patient gender
            - weight_kg: Patient weight in kg
            - current_medications: List of current medications (for interaction checking)
            - existing_conditions: List of existing conditions
            - allergies: List of allergies
        diagnoses: List of diagnosis dictionaries from previous guideline analysis, each with:
            - diagnosis: Diagnosis name
        bnf_summary_contents: List of BNF treatment summary dictionaries with keys:
            - title: BNF treatment summary title
            - url: BNF URL
            - summary: Summary text
            - sections: List of section dictionaries with:
                - heading: Section heading
                - content: Section content

    Returns:
        Formatted prompt string for Claude API
    """
    # Build patient context
    patient_context = ""
    if patient_info and patient_info.get('success'):
        patient_context = f"""
Patient Information:
- Age: {patient_info.get('age')}
- Gender: {patient_info.get('gender')}
- Weight: {patient_info.get('weight_kg')}kg
- Current medications: {', '.join(patient_info.get('current_medications', [])) or 'None'}
- Existing conditions: {', '.join(patient_info.get('existing_conditions', [])) or 'None'}
- Allergies: {', '.join(patient_info.get('allergies', [])) or 'None'}
"""

    # Build diagnoses context
    diagnoses_context = ""
    if diagnoses:
        diagnoses_context = "\nPreviously identified diagnoses:\n"
        for diag in diagnoses:
            diagnoses_context += f"- {diag['diagnosis']}\n"

    # Build BNF summaries context
    bnf_context = ""
    for idx, bnf in enumerate(bnf_summary_contents, 1):
        bnf_context += f"""
--- BNF Treatment Summary {idx}: {bnf['title']} ---
URL: {bnf['url']}
Summary: {bnf['summary'][:1000]}

Treatment Recommendations:
"""
        for section in bnf['sections'][:10]:  # Include more sections for prescribing details
            bnf_context += f"\n{section.get('heading', 'Untitled')}:\n"
            if section.get('content'):
                bnf_context += f"{section['content'][:1000]}\n"

        bnf_context += "\n"

    # Create the prompt for Claude
    prompt = f"""You are a clinical pharmacist analyzing BNF treatment summaries to provide evidence-based prescribing guidance.

Clinical Scenario:
{clinical_scenario}

{patient_context}{diagnoses_context}

Available BNF Treatment Summaries:
{bnf_context}

Based on the clinical scenario, patient information, and BNF treatment summaries, extract specific prescribing recommendations in the following JSON format:

{{
  "prescribing_guidance": [
    {{
      "condition": "Condition or indication from BNF",
      "source": "BNF Treatment Summary title",
      "source_url": "BNF URL",
      "severity_assessment": "Assessment criteria if mentioned (e.g., CURB-65)",
      "first_line_treatments": [
        {{
          "medication": "Generic medication name",
          "bnf_url": "BNF URL for this specific drug (e.g., https://bnf.nice.org.uk/drugs/amoxicillin/)",
          "dose": "Specific dosing (e.g., 500mg every 8 hours)",
          "route": "Route of administration (e.g., oral, IV)",
          "duration": "Treatment duration (e.g., 5 days, 7-10 days)",
          "notes": "Additional notes or indications",
          "drug_interactions": "Interactions with current patient medications: {', '.join(patient_info.get('current_medications', [])) if patient_info else 'None'}"
        }}
      ],
      "alternative_treatments": [
        {{
          "indication": "When to use (e.g., penicillin allergy, severe infection)",
          "medication": "Alternative medication",
          "bnf_url": "BNF URL for this specific drug",
          "dose": "Dosing",
          "route": "Route",
          "duration": "Duration",
          "notes": "Notes",
          "drug_interactions": "Interactions with current patient medications"
        }}
      ],
      "special_considerations": {{
        "renal_impairment": "Dosing adjustments or contraindications",
        "hepatic_impairment": "Dosing adjustments or contraindications",
        "pregnancy": "Safety considerations",
        "elderly": "Special considerations for elderly patients"
      }}
    }}
  ]
}}

CRITICAL INSTRUCTIONS:
1. ALWAYS extract specific medication names from the BNF summaries
2. If BNF summaries mention conditions like "Community-acquired pneumonia", look for the medications listed under that section
3. BNF summaries typically list medications like "Amoxicillin", "Clarithromycin", "Doxycycline" etc. - EXTRACT THESE
4. If dosing details are in the summary, extract them. If not, use "Dosing to be determined" (NOT "Not specified")
5. NEVER return generic placeholders like "Treatment options mentioned but specific medications not provided"

For Dosing (when available):
- Extract ONLY the ADULT dose for the SPECIFIC condition being treated
- Dose must be concise: "500mg three times daily" NOT full dosing tables
- If multiple conditions mentioned, extract dose for the relevant condition only
- If paediatric and adult doses present, extract ONLY adult dose
- Example good: "500mg three times daily for 5 days"
- Example bad: Long paragraphs with every age group and condition

Other Requirements:
- ALWAYS populate medication names - this is MANDATORY
- Include first-line vs alternative treatment distinctions
- Note allergy alternatives (e.g., for penicillin allergy)
- Include routes (oral/IV) and durations when stated
- Generate BNF URL: https://bnf.nice.org.uk/drugs/[lowercase-drug-name-with-hyphens]/
- Check interactions with patient medications: {', '.join(patient_info.get('current_medications', [])) if patient_info else 'None'}

If BNF summary lacks dosing details, the medication will be enriched later from individual BNF drug pages.
- If no specific interactions mentioned in BNF, write "No specific interactions mentioned" for drug_interactions field
- Do NOT include drug_interactions in special_considerations - only include renal_impairment, hepatic_impairment, pregnancy, and elderly
- Focus on the most relevant treatments for the clinical scenario"""

    return prompt
