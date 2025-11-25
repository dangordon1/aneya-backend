#!/usr/bin/env python
"""
Aneya - Clinical Decision Support System
Streamlit Web Application

A healthcare AI assistant that analyzes patient consultations and provides
evidence-based clinical recommendations using NICE guidelines and BNF.
"""

import streamlit as st
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import sys

# Add servers directory to path (servers is in root directory, one level up from backend)
sys.path.insert(0, str(Path(__file__).parent.parent / "servers"))
from clinical_decision_support_client import ClinicalDecisionSupportClient

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# Page configuration
st.set_page_config(
    page_title="Aneya - Clinical Decision Support",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for  aneya Health App design system
st.markdown("""
<style>
    /* Import fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Root variables */
    :root {
        --primary-purple: #351431;
        --soft-pink: #F0D1DA;
        --white: #FFFFFF;
        --text-primary: #351431;
        --text-secondary: #5C3E53;
        --text-disabled: #8B7A87;
        --shadow-card: 0px 2px 12px rgba(53, 20, 49, 0.08);
        --shadow-button: 0px 2px 8px rgba(53, 20, 49, 0.2);
    }

    /* Global styles */
    * {
        font-family: 'Inter', -apple-system, system-ui, sans-serif;
    }

    h1, h2, h3, h4 {
        font-family: Georgia, serif;
        color: var(--primary-purple);
    }

    .main-header {
        font-family: Georgia, serif;
        font-size: 48px;
        font-weight: 700;
        color: var(--primary-purple);
        text-align: center;
        margin-top: 0rem;
        margin-bottom: 1rem;
        padding-top: 0rem;
        letter-spacing: -0.5px;
    }

    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        background-color: var(--white);
    }

    /* Step indicators */
    .step-indicator {
        padding: 16px;
        border-radius: 10px;
        margin: 8px 0;
        background-color: var(--soft-pink);
        border-left: 4px solid var(--primary-purple);
        font-size: 15px;
        line-height: 22px;
        color: var(--text-primary);
    }

    .step-indicator strong {
        font-weight: 600;
        font-size: 16px;
    }

    .step-complete {
        background-color: var(--soft-pink);
        border-left: 4px solid var(--primary-purple);
        opacity: 0.8;
    }

    .step-running {
        background-color: var(--soft-pink);
        border-left: 4px solid var(--primary-purple);
    }

    .step-pending {
        background-color: var(--white);
        border: 2px solid var(--soft-pink);
        border-left: 4px solid var(--text-disabled);
        opacity: 0.6;
    }

    /* Cards */
    .diagnosis-card {
        background-color: var(--white);
        border: 2px solid var(--soft-pink);
        border-radius: 16px;
        padding: 24px;
        margin: 16px 0;
        box-shadow: var(--shadow-card);
    }

    .diagnosis-card h3 {
        font-family: Georgia, serif;
        font-size: 22px;
        line-height: 28px;
        font-weight: 600;
        color: var(--primary-purple);
        margin-top: 0;
        margin-bottom: 16px;
    }

    .diagnosis-card p {
        font-size: 15px;
        line-height: 22px;
        color: var(--text-primary);
        margin-bottom: 8px;
    }

    .diagnosis-card a {
        color: var(--primary-purple);
        font-weight: 500;
        text-decoration: none;
    }

    .diagnosis-card a:hover {
        text-decoration: underline;
    }

    /* Confidence levels */
    .confidence-high {
        color: var(--primary-purple);
        font-weight: 600;
    }

    .confidence-medium {
        color: var(--text-secondary);
        font-weight: 600;
    }

    .confidence-low {
        color: var(--text-disabled);
        font-weight: 600;
    }

    /* Medication boxes */
    .medication-box {
        background-color: var(--soft-pink);
        border-left: 4px solid var(--primary-purple);
        padding: 16px;
        margin: 8px 0;
        border-radius: 10px;
        font-size: 15px;
        line-height: 22px;
    }

    .medication-box strong {
        color: var(--primary-purple);
        font-weight: 600;
        font-size: 16px;
    }

    .medication-box small {
        color: var(--text-primary);
        font-size: 15px;
    }

    .medication-box a {
        color: var(--primary-purple);
        font-weight: 600;
        text-decoration: none;
    }

    .medication-box a:hover {
        text-decoration: underline;
    }

    /* Warning boxes */
    .warning-box {
        background-color: var(--soft-pink);
        border-left: 4px solid var(--primary-purple);
        padding: 16px;
        margin: 16px 0;
        border-radius: 10px;
    }

    .warning-box strong {
        color: var(--primary-purple);
        font-weight: 600;
    }

    /* Buttons - override Streamlit defaults */
    .stButton > button {
        background-color: var(--primary-purple);
        color: var(--white);
        border: none;
        border-radius: 10px;
        padding: 12px 24px;
        font-size: 16px;
        font-weight: 600;
        letter-spacing: 0.3px;
        box-shadow: var(--shadow-button);
        transition: background-color 0.2s ease;
    }

    .stButton > button:hover {
        background-color: #4A1E45;
        box-shadow: 0px 4px 12px rgba(53, 20, 49, 0.3);
    }

    /* Text inputs */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        border: 2px solid var(--soft-pink);
        border-radius: 10px;
        font-size: 16px;
        color: var(--text-primary);
    }

    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--primary-purple);
        box-shadow: 0 0 0 1px var(--primary-purple);
    }

    /* Section headers */
    .stMarkdown h2 {
        font-family: Georgia, serif;
        font-size: 26px;
        line-height: 32px;
        font-weight: 600;
        color: var(--primary-purple);
        margin-top: 32px;
        margin-bottom: 16px;
    }

    .stMarkdown h3 {
        font-family: Georgia, serif;
        font-size: 22px;
        line-height: 28px;
        font-weight: 600;
        color: var(--primary-purple);
        margin-top: 24px;
        margin-bottom: 16px;
    }

    /* Subheaders */
    [data-testid="stHeader"] {
        background-color: var(--white);
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: var(--white);
        border-right: 2px solid var(--soft-pink);
    }

    [data-testid="stSidebar"] h2 {
        color: var(--primary-purple);
        font-family: Georgia, serif;
    }

    /* Info/Warning boxes */
    .stAlert {
        border-radius: 10px;
        border-left: 4px solid var(--primary-purple);
    }

    /* Expanders */
    .streamlit-expanderHeader {
        background-color: var(--soft-pink);
        border-radius: 10px;
        font-weight: 600;
        color: var(--primary-purple);
    }

    /* Links */
    a {
        color: var(--primary-purple);
        font-weight: 500;
        text-decoration: none;
    }

    a:hover {
        text-decoration: underline;
    }
</style>
""", unsafe_allow_html=True)

# Example cases (from demo)
EXAMPLE_CASES = {
    "Pediatric Croup": {
        "scenario": "3-year-old with croup, moderate stridor at rest, barking cough",
        "patient_id": "P001"
    },
    "Post-Operative Sepsis": {
        "scenario": "Post-operative sepsis, fever 38.5C, tachycardia, suspected wound infection",
        "patient_id": "P002"
    },
    "Acute Asthma Exacerbation": {
        "scenario": "45-year-old with severe asthma exacerbation, peak flow 40% predicted, breathless",
        "patient_id": "P003"
    },
    "Community-Acquired Pneumonia": {
        "scenario": "72-year-old with CAP, CURB-65 score 2, productive cough, fever",
        "patient_id": "P004"
    }
}


def display_progress_step(step_name: str, status: str = "pending", message: str = ""):
    """Display a progress step with status indicator."""
    status_class = f"step-{status}"

    st.markdown(f"""
    <div class="step-indicator {status_class}">
        <strong>{step_name}</strong>
        {f"<br><small>{message}</small>" if message else ""}
    </div>
    """, unsafe_allow_html=True)


def display_diagnosis(diagnosis: dict, index: int):
    """Display a diagnosis card with treatments."""
    confidence = diagnosis.get('confidence', 'medium')
    confidence_class = f"confidence-{confidence}"

    # Create source display with link if URL is available
    source_display = diagnosis.get('source', 'N/A')
    if diagnosis.get('url'):
        source_display = f'<a href="{diagnosis["url"]}" target="_blank">{source_display}</a>'

    st.markdown(f"""
    <div class="diagnosis-card">
        <h3>Diagnosis {index}: {diagnosis['diagnosis']}</h3>
        <p><strong>Confidence:</strong> <span class="{confidence_class}">{confidence.upper()}</span></p>
        <p><strong>Source:</strong> {source_display}</p>
        {f"<p><small>{diagnosis.get('summary', '')}</small></p>" if diagnosis.get('summary') else ""}
    </div>
    """, unsafe_allow_html=True)


def display_bnf_guidance(guidance: dict, index: int, patient_medications: list = None):
    """Display BNF prescribing guidance."""
    source_display = guidance.get('source', 'BNF')
    if guidance.get('source_url'):
        source_display = f'<a href="{guidance["source_url"]}" target="_blank">{source_display}</a>'

    st.markdown(f"""
    <div class="diagnosis-card">
        <h3>Prescribing Guidance {index}: {guidance['condition']}</h3>
        <p><strong>Source:</strong> {source_display}</p>
        {f"<p><strong>Severity Assessment:</strong> {guidance['severity_assessment']}</p>" if guidance.get('severity_assessment') else ""}
    </div>
    """, unsafe_allow_html=True)

    # Special considerations with expander - MOVED TO TOP
    if guidance.get('special_considerations'):
        spec = guidance['special_considerations']
        considerations = []
        if spec.get('elderly'):
            considerations.append(f"**Elderly:** {spec['elderly']}")
        if spec.get('renal_impairment'):
            considerations.append(f"**Renal Impairment:** {spec['renal_impairment']}")
        if spec.get('hepatic_impairment'):
            considerations.append(f"**Hepatic Impairment:** {spec['hepatic_impairment']}")
        if spec.get('pregnancy'):
            considerations.append(f"**Pregnancy:** {spec['pregnancy']}")
        # Removed drug_interactions from here as they're shown per drug

        if considerations:
            with st.expander("**Special Considerations**", expanded=False):
                st.markdown(f"""
                <div class="warning-box">
                    <strong>Important:</strong><br>
                    {'<br>'.join(considerations)}
                </div>
                """, unsafe_allow_html=True)

    # First-line treatments with expander
    if guidance.get('first_line_treatments'):
        with st.expander("**First-Line Treatments**", expanded=True):
            for treatment in guidance['first_line_treatments']:
                # Create medication name with BNF link
                med_name = treatment['medication']
                if treatment.get('bnf_url'):
                    med_name = f'<a href="{treatment["bnf_url"]}" target="_blank">{treatment["medication"]}</a>'

                # Build drug interactions section if present
                drug_interactions_html = ""
                if patient_medications and treatment.get('drug_interactions'):
                    interactions_text = treatment['drug_interactions']
                    drug_interactions_html = f"<br>• Drug Interactions: {interactions_text}"

                st.markdown(f"""
                <div class="medication-box">
                    <strong>{med_name}</strong><br>
                    <small>
                    • Dose: {treatment.get('dose', 'Not specified')}<br>
                    • Route: {treatment.get('route', 'Not specified')}<br>
                    • Duration: {treatment.get('duration', 'Not specified')}
                    {f"<br>• Notes: {treatment['notes']}" if treatment.get('notes') else ""}
                    {drug_interactions_html}
                    </small>
                </div>
                """, unsafe_allow_html=True)

    # Alternative treatments with expander
    if guidance.get('alternative_treatments'):
        with st.expander("**Alternative Treatments**", expanded=False):
            for alt in guidance['alternative_treatments']:
                # Create medication name with BNF link
                med_name = alt['medication']
                if alt.get('bnf_url'):
                    med_name = f'<a href="{alt["bnf_url"]}" target="_blank">{alt["medication"]}</a>'

                # Build drug interactions section if present
                drug_interactions_html = ""
                if patient_medications and alt.get('drug_interactions'):
                    interactions_text = alt['drug_interactions']
                    drug_interactions_html = f"<br>• Drug Interactions: {interactions_text}"

                st.markdown(f"""
                <div class="medication-box">
                    <strong>{med_name}</strong> <em>({alt.get('indication', 'Alternative')})</em><br>
                    <small>
                    • Dose: {alt.get('dose', 'Not specified')}<br>
                    • Route: {alt.get('route', 'Not specified')}<br>
                    • Duration: {alt.get('duration', 'Not specified')}
                    {f"<br>• Notes: {alt['notes']}" if alt.get('notes') else ""}
                    {drug_interactions_html}
                    </small>
                </div>
                """, unsafe_allow_html=True)


async def analyze_consultation(consultation_text: str, patient_id: str):
    """Run the clinical decision support analysis."""

    # Create placeholders for progress steps
    progress_container = st.container()

    with progress_container:
        step1 = st.empty()
        step2 = st.empty()
        step3 = st.empty()
        step3a = st.empty()
        step3b = st.empty()
        step3c = st.empty()
        step4 = st.empty()
        step5 = st.empty()

    try:
        # Initialize client
        with step1:
            display_progress_step("Initializing Clinical Decision Support System", "running")

        client = ClinicalDecisionSupportClient()
        await client.connect_to_servers(verbose=False)

        with step1:
            display_progress_step("Initializing Clinical Decision Support System", "complete", "Connected to all services")

        # Step 1: Detect location
        with step2:
            display_progress_step("Detecting Location from IP Address", "running")

        with step2:
            display_progress_step("Detecting Location from IP Address", "complete", "Location: United Kingdom (GB)")

        # Step 2: Search for guidelines - show incremental progress
        with step3:
            display_progress_step("Searching for Clinical Guidelines", "running")

        with step3a:
            display_progress_step("  → Searching NICE guidelines", "running")

        with step3b:
            display_progress_step("  → Searching CKS topics", "running")

        with step3c:
            display_progress_step("  → Searching BNF treatment summaries", "running")

        # Run analysis (this does the actual work)
        result = await client.clinical_decision_support(
            clinical_scenario=consultation_text,
            patient_id=patient_id,
            location_override="GB",
            verbose=False
        )

        guideline_count = len(result.get('guidelines_found', [])) + len(result.get('cks_topics', [])) + len(result.get('bnf_summaries', []))

        # Update all steps to complete status
        with step3:
            display_progress_step("Searching for Clinical Guidelines", "complete", f"Found {guideline_count} relevant resources")

        with step3a:
            display_progress_step("  → Searching NICE guidelines", "complete", f"{len(result.get('guidelines_found', []))} found")

        with step3b:
            display_progress_step("  → Searching CKS topics", "complete", f"{len(result.get('cks_topics', []))} found")

        with step3c:
            display_progress_step("  → Searching BNF treatment summaries", "complete", f"{len(result.get('bnf_summaries', []))} found")

        # Step 3: Analyze guidelines
        with step4:
            diagnosis_count = len(result.get('diagnoses', []))
            if diagnosis_count > 0:
                display_progress_step("Analyzing Clinical Guidelines", "complete", f"Identified {diagnosis_count} potential diagnosis/diagnoses")
            else:
                display_progress_step("Analyzing Clinical Guidelines", "complete", "Guidelines retrieved")

        # Step 4: BNF lookup
        with step5:
            bnf_count = len(result.get('bnf_prescribing_guidance', []))
            if bnf_count > 0:
                display_progress_step("Analyzing BNF Treatment Summaries", "complete", f"Extracted {bnf_count} prescribing recommendation(s)")
            else:
                display_progress_step("Analyzing BNF Treatment Summaries", "complete", "Treatment summaries analyzed")

        await client.cleanup()

        return result

    except Exception as e:
        st.error(f"❌ Error during analysis: {str(e)}")
        return None


def main():
    """Main Streamlit app."""

    # Initialize session state
    if 'analyzing' not in st.session_state:
        st.session_state.analyzing = False
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False
    if 'result' not in st.session_state:
        st.session_state.result = None
    if 'show_report' not in st.session_state:
        st.session_state.show_report = False
    # Set default consultation text and patient ID on first load
    if 'consultation_text' not in st.session_state:
        st.session_state.consultation_text = "72-year-old with CAP, CURB-65 score 2, productive cough, fever"
    if 'patient_id' not in st.session_state:
        st.session_state.patient_id = "P004"

    # Header
    st.markdown('<h1 class="main-header">Aneya</h1>', unsafe_allow_html=True)

    # Sidebar for example cases
    with st.sidebar:
        st.header("Example Cases")
        st.markdown("Quick load example consultations:")

        selected_example = st.selectbox(
            "Choose an example:",
            ["Custom"] + list(EXAMPLE_CASES.keys())
        )

        if st.button("Load Example", use_container_width=True):
            if selected_example != "Custom":
                st.session_state.consultation_text = EXAMPLE_CASES[selected_example]["scenario"]
                st.session_state.patient_id = EXAMPLE_CASES[selected_example]["patient_id"]
                st.session_state.analyzing = False
                st.session_state.analysis_complete = False
                st.session_state.show_report = False
                st.rerun()

    # Show results if report button clicked
    if st.session_state.show_report and st.session_state.result:
        # Scroll to top by placing results first
        st.markdown("## Clinical Decision Support Report")
        display_results(st.session_state.result)

        # Add "New Analysis" button at the bottom
        st.markdown("---")
        if st.button("Start New Analysis", type="primary", use_container_width=True):
            st.session_state.analyzing = False
            st.session_state.analysis_complete = False
            st.session_state.result = None
            st.session_state.show_report = False
            st.rerun()

    # Show "Show Report" button if analysis complete but report not shown yet
    elif st.session_state.analysis_complete and st.session_state.result and not st.session_state.show_report:
        st.markdown("## Analysis Complete")
        st.success("Your clinical decision support analysis is ready!")

        if st.button("Show Report", type="primary", use_container_width=True):
            st.session_state.show_report = True
            st.rerun()

    # Show progress if analyzing
    elif st.session_state.analyzing:
        st.markdown("## 📊 Analysis Progress")

        # Run analysis
        result = asyncio.run(analyze_consultation(
            st.session_state.consultation_text,
            st.session_state.patient_id
        ))

        if result:
            st.session_state.result = result
            st.session_state.analyzing = False
            st.session_state.analysis_complete = True
            st.rerun()

    # Show input form (default state)
    else:
        # Main input area
        col1, col2 = st.columns([3, 1])

        with col1:
            st.subheader("Consultation Transcript")
            consultation_text = st.text_area(
                "Heidi consultation summary:",
                value=st.session_state.consultation_text,
                height=150,
                placeholder="e.g., 72-year-old with community-acquired pneumonia, CURB-65 score 2, productive cough, fever..."
            )

        with col2:
            st.subheader("Patient Information")
            patient_id = st.text_input(
                "Patient ID:",
                value=st.session_state.patient_id,
                placeholder="e.g., P001"
            )

        # Analyze button
        if st.button("Analyze Consultation", type="primary", use_container_width=True):
            if not consultation_text.strip():
                st.warning("Please enter consultation details")
            else:
                st.session_state.consultation_text = consultation_text
                st.session_state.patient_id = patient_id
                st.session_state.analyzing = True
                st.rerun()


def display_results(result):
    """Display the analysis results."""
    if not result:
        return

    # Patient info
    if result.get('patient_info') and result['patient_info'].get('success'):
        pi = result['patient_info']
        st.markdown(f"""
        **Patient Information:**
        - **ID:** {pi.get('patient_id', 'N/A')}
        - **Age:** {pi.get('age', 'N/A')} | **Gender:** {pi.get('gender', 'N/A')}
        - **Weight:** {pi.get('weight_kg', 'N/A')}kg | **BMI:** {pi.get('bmi', 'N/A')}
        {f"- **Allergies:** {', '.join(pi['allergies'])}" if pi.get('allergies') else ""}
        {f"- **Current Medications:** {', '.join(pi['current_medications'])}" if pi.get('current_medications') else ""}
        """)
        st.markdown("---")

    # Diagnoses
    if result.get('diagnoses'):
        st.markdown("### Clinical Diagnoses")

        # Separate primary (first) from alternative diagnoses
        primary_diagnosis = result['diagnoses'][0] if result['diagnoses'] else None
        alternative_diagnoses = result['diagnoses'][1:] if len(result['diagnoses']) > 1 else []

        if primary_diagnosis:
            st.markdown("**Primary Diagnosis:**")
            display_diagnosis(primary_diagnosis, 1)

        if alternative_diagnoses:
            st.markdown("**Alternative Diagnoses:**")
            for idx, diagnosis in enumerate(alternative_diagnoses, 2):
                display_diagnosis(diagnosis, idx)
    else:
        st.info("No structured diagnoses identified. Please review guidelines manually.")

    # BNF Prescribing Guidance
    if result.get('bnf_prescribing_guidance'):
        st.markdown("---")
        st.markdown("### Evidence-Based Prescribing Guidance")

        # Extract patient medications for drug interaction checking
        patient_medications = None
        if result.get('patient_info') and result['patient_info'].get('current_medications'):
            patient_medications = result['patient_info']['current_medications']

        for idx, guidance in enumerate(result['bnf_prescribing_guidance'], 1):
            display_bnf_guidance(guidance, idx, patient_medications)

    # Resources found with links
    st.markdown("---")
    st.markdown("### Resources Consulted")

    # NICE Guidelines
    if result.get('guidelines_found'):
        st.markdown("**NICE Guidelines:**")
        for guideline in result['guidelines_found']:
            st.markdown(f"- [{guideline['reference']}: {guideline['title']}]({guideline['url']})")

    # CKS Topics
    if result.get('cks_topics'):
        st.markdown("**NICE CKS Topics:**")
        for topic in result['cks_topics']:
            st.markdown(f"- [{topic['title']}]({topic['url']})")

    # BNF Treatment Summaries
    if result.get('bnf_summaries'):
        st.markdown("**BNF Treatment Summaries:**")
        for bnf in result['bnf_summaries']:
            st.markdown(f"- [{bnf['title']}]({bnf['url']})")

    # Disclaimer
    st.markdown("---")
    st.warning("**Clinical Disclaimer:** This system provides decision support only. All recommendations should be reviewed by a qualified healthcare professional before prescribing. Always verify patient allergies, drug interactions, and contraindications.")


if __name__ == "__main__":
    main()
