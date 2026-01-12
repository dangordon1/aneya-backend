"""
Diagnosis prompts for Clinical Decision Support.

Contains prompts for analyzing clinical consultations and generating diagnoses.
"""


def get_diagnosis_analysis_prompt(clinical_scenario: str) -> str:
    """
    Generate the main diagnosis analysis prompt for Claude with guideline tools.

    Args:
        clinical_scenario: The clinical consultation text

    Returns:
        Formatted prompt string for diagnosis analysis
    """
    return f"""Analyze this clinical consultation and provide structured diagnosis and treatment information.

CONSULTATION: {clinical_scenario}

TASK:
1. Use the available GUIDELINE tools to search for relevant clinical guidelines (NICE, AIIMS, NHM, etc.)
2. DO NOT use drug lookup tools (BNF, DrugBank, MIMS) - just provide generic drug names
3. Based on the consultation and evidence found, identify:
   - The diagnosis (with confidence level: high/medium/low)
   - The source guideline (e.g., "NICE NG138", "BTS/SIGN Asthma Guideline")
   - The guideline URL (if available from your tool searches)
   - Appropriate treatments (pharmacological, procedural, and supportive)
   - Specific drug names mentioned or recommended (use generic names, e.g., "Amoxicillin" not "Amoxil")
   - Non-pharmacological interventions (splinting, physiotherapy, RICE, etc.)
   - Follow-up care guidance (timeframe, monitoring, referral criteria)

IMPORTANT: Return your answer QUICKLY. Drug details will be looked up separately after you respond.

Return your final answer as JSON ONLY (no other text):

{{
  "diagnoses": [
    {{
      "diagnosis": "medical condition name",
      "confidence": "high|medium|low",
      "source": "guideline name (e.g., NICE NG138)",
      "url": "full guideline URL if available from tools, otherwise empty string",

      "primary_care": {{
        "medications": ["Paracetamol", "Ibuprofen", "Amoxicillin"],
        "supportive_care": ["Ice", "Elevation", "Rest", "Physiotherapy"],
        "clinical_guidance": "Dosing and administration guidance from guidelines",
        "when_to_escalate": ["Red flag 1", "Warning sign 2", "When to seek urgent care"]
      }},

      "surgery": {{
        "indicated": true,
        "procedure": "Surgical procedure name (e.g., Open Reduction Internal Fixation)",
        "phases": {{
          "preoperative": {{
            "investigations": ["X-ray AP/lateral", "Blood work", "ECG if indicated"],
            "medications": ["Prophylactic antibiotics", "Tetanus prophylaxis"],
            "preparation": ["NPO 8 hours", "Informed consent", "Mark surgical site"]
          }},
          "operative": {{
            "technique": "Detailed surgical approach and technique",
            "anesthesia": "Type and method of anesthesia (e.g., general, regional)",
            "duration": "Estimated duration if known"
          }},
          "postoperative": {{
            "immediate_care": ["Neurovascular checks q2h", "Elevate limb", "Monitor vitals"],
            "medications": ["Antibiotic course 5-7 days", "DVT prophylaxis", "Pain management"],
            "mobilization": "Weight-bearing status and mobilization timeline",
            "complications": ["Complications to watch for"]
          }}
        }}
      }},

      "diagnostics": {{
        "required": ["Investigation 1", "Investigation 2"],
        "monitoring": ["Follow-up test 1", "Follow-up test 2"],
        "referral_criteria": ["When to refer to specialist"]
      }},

      "follow_up": {{
        "timeframe": "When patient should be reviewed (e.g., 48-72 hours, 1 week, 2 weeks)",
        "monitoring": ["What to monitor (e.g., symptom resolution, vital signs, wound healing)"],
        "referral_criteria": ["When to refer or escalate care (e.g., worsening symptoms, no improvement after X days)"]
      }}
    }}
  ]
}}

STRUCTURE GUIDELINES:

**PRIMARY CARE** (REQUIRED):
- Initial management that can be done in primary care/outpatient setting
- medications: CRITICAL - List medications as objects with name variations for BNF lookup
  * Each medication MUST be an object with:
    - drug_name: Base generic name (e.g., "Cetirizine", "Paracetamol")
    - variations: Array of chemical/salt name variations to try in BNF
  * For variations, include the base name FIRST, then common pharmaceutical salts:
    - Common salts: hydrochloride, dihydrochloride, sulfate, phosphate, sodium, potassium, citrate
    - Alternative names: INN vs USAN (e.g., "Paracetamol" vs "Acetaminophen")
  * CORRECT FORMAT:
    [
      {{"drug_name": "Cetirizine", "variations": ["Cetirizine", "Cetirizine hydrochloride", "Cetirizine dihydrochloride"]}},
      {{"drug_name": "Loratadine", "variations": ["Loratadine"]}},
      {{"drug_name": "Paracetamol", "variations": ["Paracetamol", "Acetaminophen"]}}
    ]
  * WRONG: Simple string arrays like ["Cetirizine", "Loratadine"]
  * Use GENERIC NAMES only (e.g., "Paracetamol" not "Tylenol")
- supportive_care: Non-pharmacological interventions (ice, elevation, rest, physiotherapy, wound care, etc.)
- clinical_guidance: Dosing, administration, duration from guidelines
- when_to_escalate: Red flags, warning signs, when to seek urgent/emergency care

**SURGERY** (OPTIONAL - only if surgical intervention needed):
- indicated: true if surgery is required, false otherwise
- procedure: Name of surgical procedure
- phases: Detailed pre-operative, operative, and post-operative care
  * preoperative: investigations, medications (same object format as primary_care), preparation (NPO, consent)
  * operative: technique, anesthesia type, estimated duration
  * postoperative: immediate care, medications (same object format as primary_care), mobilization instructions, complications to watch
  * NOTE: All medication fields must use the object format with drug_name and variations

**DIAGNOSTICS** (OPTIONAL - if investigations needed):
- required: Investigations needed to confirm diagnosis or assess severity
- monitoring: Follow-up tests or monitoring parameters
- referral_criteria: When to refer to specialist

IMPORTANT INSTRUCTIONS:
1. ALWAYS include primary_care for every diagnosis
2. For SIMPLE cases (UTI, minor infections): Only primary_care needed
3. For COMPLEX cases (fractures, major trauma): Include surgery and diagnostics sections
4. For trauma/injury cases, ALWAYS include supportive_care in primary_care:
   - Fractures: splinting, immobilization, ice, elevation
   - Bleeding: direct pressure, elevation
   - Wounds: wound cleaning, sterile dressings
   - Musculoskeletal: RICE protocol, physiotherapy
5. ALWAYS include follow_up guidance
6. Use empty arrays [] if no items in a list field
7. OMIT surgery section entirely if no surgical intervention needed
8. OMIT diagnostics section if no investigations required

DRUGBANK OPTIMIZATION:
- When multiple drugs need detailed information, issue PARALLEL search_drugbank tool calls in the same turn
- Example: If recommending 3 drugs, make 3 separate search_drugbank calls simultaneously
- This parallelizes lookups and automatically respects rate limits"""


def get_pubmed_fallback_prompt(clinical_scenario: str) -> str:
    """
    Generate a prompt for PubMed fallback when guidelines don't provide sufficient info.

    Args:
        clinical_scenario: The clinical consultation text

    Returns:
        Formatted prompt string for PubMed search
    """
    return f"""The local guidelines did not provide sufficient information for this clinical scenario.
Search PubMed medical literature for evidence-based guidance.

CONSULTATION: {clinical_scenario}

Use the available PubMed tools to search for relevant medical literature and provide evidence-based recommendations.
Return the same JSON structure as before with diagnoses, treatments, and guidance based on the literature you find."""


def get_literature_fallback_prompt(clinical_scenario: str, source_name: str, quartile_filter: str = None) -> str:
    """
    Generate a prompt for BMJ/Scopus fallback when guidelines don't provide sufficient info.

    Args:
        clinical_scenario: The clinical consultation text
        source_name: Name of the literature source (BMJ, Scopus)
        quartile_filter: Optional quartile filter (Q1, Q2) for Scopus

    Returns:
        Formatted prompt string for literature search
    """
    quartile_guidance = ""
    if quartile_filter:
        quartile_desc = "top 25% (Q1)" if quartile_filter == "Q1" else "top 50% (Q1-Q2)"
        quartile_guidance = f"""
IMPORTANT: Focus on HIGH-IMPACT RESEARCH from {quartile_desc} journals.
Use the quartile filtering tools to ensure you're citing the most reputable sources."""

    return f"""The local guidelines did not provide sufficient information for this clinical scenario.
Search {source_name} medical literature for evidence-based guidance.

CONSULTATION: {clinical_scenario}
{quartile_guidance}

Use the available {source_name} tools to:
1. Search for relevant medical literature (recent systematic reviews, meta-analyses, clinical trials)
2. Retrieve full article details for the most relevant papers
3. Extract evidence-based recommendations for diagnosis and treatment

Return the same JSON structure as before with diagnoses, treatments, and guidance.
For each diagnosis, include:
- The source article title and DOI
- The level of evidence (systematic review, RCT, cohort study, etc.)
- Evidence-based recommendations from the literature"""
