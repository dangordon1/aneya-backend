"""
Clinical scenario fixtures for testing.

These scenarios represent common clinical cases used in testing
diagnosis, form extraction, and summarization.
"""

# Clinical scenarios with expected outcomes
CLINICAL_SCENARIOS = {
    "pregnant_flu": {
        "consultation": "6 weeks pregnant with flu symptoms including cough, cold, fever, and vomiting for 5 days",
        "patient_age": "28",
        "patient_sex": "Female",
        "expected_conditions": ["pregnancy", "viral upper respiratory infection"],
        "form_type": "antenatal",
        "language": "en-IN"
    },
    "pediatric_fever": {
        "consultation": "3-year-old with fever 39C for 2 days, cough, no rash",
        "patient_age": "3",
        "patient_sex": "Male",
        "expected_conditions": ["fever", "respiratory infection"],
        "form_type": "general",
        "language": "en-IN"
    },
    "diabetes_management": {
        "consultation": "45-year-old with newly diagnosed type 2 diabetes, HbA1c 8.5%",
        "patient_age": "45",
        "patient_sex": "Male",
        "expected_conditions": ["type 2 diabetes"],
        "form_type": "general",
        "language": "en-IN"
    },
    "infertility_case": {
        "consultation": "Trying to conceive for 2 years, irregular periods, no success with natural conception",
        "patient_age": "32",
        "patient_sex": "Female",
        "expected_conditions": ["infertility", "irregular menstruation"],
        "form_type": "infertility",
        "language": "en-IN"
    },
    "hypertension": {
        "consultation": "60-year-old with BP 160/95, no previous treatment, occasional headaches",
        "patient_age": "60",
        "patient_sex": "Male",
        "expected_conditions": ["hypertension"],
        "form_type": "general",
        "language": "en-IN"
    },
    "hindi_antenatal": {
        "consultation": "Main 6 week pregnant hoon, mujhe bahut zyada ulti aa rahi hai",
        "patient_age": "25",
        "patient_sex": "Female",
        "expected_conditions": ["pregnancy", "hyperemesis"],
        "form_type": "antenatal",
        "language": "hi-IN"
    },
    "hindi_general": {
        "consultation": "Doctor sahab, mujhe sar mein bahut dard ho raha hai teen din se",
        "patient_age": "35",
        "patient_sex": "Female",
        "expected_conditions": ["headache"],
        "form_type": "general",
        "language": "hi-IN"
    },
    "kannada_pregnancy": {
        "consultation": "Doctor, naanu 6 vaara garbhini. Thumba vaanti aaguttide",
        "patient_age": "28",
        "patient_sex": "Female",
        "expected_conditions": ["pregnancy", "nausea"],
        "form_type": "antenatal",
        "language": "kn-IN"
    }
}

# Form extraction test scenarios
FORM_EXTRACTION_SCENARIOS = {
    "obgyn_basic": {
        "form_type": "obgyn",
        "segments": [
            {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "What's your last menstrual period?", "start_time": 0.0},
            {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "December 1st, 2024", "start_time": 2.0},
            {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "Any history of previous pregnancies?", "start_time": 4.0},
            {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "Yes, I have two children, both normal deliveries", "start_time": 6.0},
        ],
        "expected_fields": ["last_menstrual_period", "parity"]
    },
    "antenatal_vitals": {
        "form_type": "antenatal",
        "segments": [
            {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "How many weeks pregnant are you?", "start_time": 0.0},
            {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "I'm about 28 weeks now", "start_time": 2.0},
            {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "Your blood pressure is 120/80 and weight is 65 kg", "start_time": 4.0},
        ],
        "expected_fields": ["gestational_age", "blood_pressure", "weight"]
    },
    "infertility_history": {
        "form_type": "infertility",
        "segments": [
            {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "How long have you been trying to conceive?", "start_time": 0.0},
            {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "About 2 years now", "start_time": 2.0},
            {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "Have you had any previous pregnancies?", "start_time": 4.0},
            {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "No, this would be my first", "start_time": 6.0},
            {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "Are your periods regular?", "start_time": 8.0},
            {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "No, they're quite irregular. Sometimes I skip months", "start_time": 10.0},
        ],
        "expected_fields": ["duration_trying", "previous_pregnancies", "menstrual_regularity"]
    }
}

# Speaker role test scenarios
SPEAKER_ROLE_SCENARIOS = {
    "clear_two_speaker": {
        "segments": [
            {"speaker_id": "speaker_0", "text": "Good morning. What brings you in today?", "start_time": 0.0, "end_time": 2.5},
            {"speaker_id": "speaker_1", "text": "I've been having headaches for a week.", "start_time": 3.0, "end_time": 6.0},
            {"speaker_id": "speaker_0", "text": "Can you describe the pain? Where exactly is it?", "start_time": 6.5, "end_time": 9.0},
            {"speaker_id": "speaker_1", "text": "It's on the right side, throbbing pain.", "start_time": 9.5, "end_time": 12.0},
        ],
        "expected_roles": {"speaker_0": "Doctor", "speaker_1": "Patient"},
        "expected_confidence": 0.85
    },
    "ambiguous_short": {
        "segments": [
            {"speaker_id": "speaker_0", "text": "Hi", "start_time": 0.0, "end_time": 0.5},
            {"speaker_id": "speaker_1", "text": "Hello", "start_time": 1.0, "end_time": 1.5},
        ],
        "expected_roles": None,  # Should trigger manual assignment
        "expected_confidence": 0.5
    },
    "three_speaker_with_family": {
        "segments": [
            {"speaker_id": "speaker_0", "text": "Please come in. What seems to be the problem?", "start_time": 0.0, "end_time": 2.5},
            {"speaker_id": "speaker_1", "text": "I have stomach pain.", "start_time": 3.0, "end_time": 5.0},
            {"speaker_id": "speaker_2", "text": "Doctor, she hasn't eaten in two days.", "start_time": 5.5, "end_time": 8.0},
            {"speaker_id": "speaker_0", "text": "I see. How long have you had this pain?", "start_time": 8.5, "end_time": 11.0},
            {"speaker_id": "speaker_1", "text": "Since yesterday morning.", "start_time": 11.5, "end_time": 13.0},
        ],
        "expected_roles": {"speaker_0": "Doctor", "speaker_1": "Patient", "speaker_2": "Family Member"},
        "expected_confidence": 0.75
    }
}

# Consultation type classification scenarios
CONSULTATION_TYPE_SCENARIOS = {
    "antenatal_clear": {
        "segments": [
            {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "How many weeks pregnant are you?", "start_time": 0.0},
            {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "I'm 6 weeks pregnant", "start_time": 2.0},
        ],
        "expected_type": "antenatal",
        "expected_confidence": 0.9
    },
    "infertility_clear": {
        "segments": [
            {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "How long have you been trying to conceive?", "start_time": 0.0},
            {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "We've been trying for 2 years with no success", "start_time": 2.0},
        ],
        "expected_type": "infertility",
        "expected_confidence": 0.9
    },
    "obgyn_default": {
        "segments": [
            {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "What brings you in today?", "start_time": 0.0},
            {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "I have irregular periods", "start_time": 2.0},
        ],
        "expected_type": "obgyn",
        "expected_confidence": 0.7
    }
}
