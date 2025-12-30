"""
Form schemas for auto-fill extraction from consultation transcripts.

Defines the schema structure for OBGyn, Infertility, and Antenatal forms
to enable intelligent field extraction from diarized doctor-patient conversations.
"""

from typing import Dict, Any, List, Optional

# ============================================
# OB/GYN FORM SCHEMA
# ============================================

OBGYN_FORM_SCHEMA = {
    "vital_signs": {
        "type": "object",
        "description": "Patient vital sign measurements",
        "fields": {
            "systolic_bp": {
                "type": "number",
                "unit": "mmHg",
                "range": [0, 250],
                "description": "Systolic blood pressure",
                "extraction_hints": ["BP", "blood pressure", "systolic", "120 over 80"]
            },
            "diastolic_bp": {
                "type": "number",
                "unit": "mmHg",
                "range": [0, 150],
                "description": "Diastolic blood pressure",
                "extraction_hints": ["BP", "blood pressure", "diastolic", "120 over 80"]
            },
            "heart_rate": {
                "type": "number",
                "unit": "bpm",
                "range": [0, 200],
                "description": "Heart rate in beats per minute",
                "extraction_hints": ["heart rate", "pulse", "bpm", "beats per minute"]
            },
            "respiratory_rate": {
                "type": "number",
                "unit": "breaths/min",
                "range": [0, 50],
                "description": "Respiratory rate",
                "extraction_hints": ["respiratory rate", "breathing rate", "breaths per minute"]
            },
            "temperature": {
                "type": "number",
                "unit": "celsius",
                "range": [35, 42],
                "description": "Body temperature in Celsius",
                "extraction_hints": ["temperature", "temp", "fever", "celsius", "fahrenheit"]
            },
            "spo2": {
                "type": "number",
                "unit": "%",
                "range": [0, 100],
                "description": "Oxygen saturation percentage",
                "extraction_hints": ["O2 sat", "oxygen saturation", "SpO2", "sats"]
            },
            "blood_glucose": {
                "type": "number",
                "unit": "mg/dL",
                "range": [0, 600],
                "description": "Blood glucose level",
                "extraction_hints": ["blood sugar", "glucose", "sugar level", "BSL"]
            }
        }
    },
    "physical_exam_findings": {
        "type": "object",
        "description": "Clinical examination findings",
        "fields": {
            "general_inspection": {
                "type": "string",
                "max_length": 500,
                "description": "General appearance and inspection",
                "extraction_hints": ["general appearance", "inspection", "looks", "appears"]
            },
            "abdominal_exam": {
                "type": "string",
                "max_length": 500,
                "description": "Abdominal examination findings",
                "extraction_hints": ["abdomen", "abdominal exam", "palpation", "tender"]
            },
            "speculum_exam": {
                "type": "string",
                "max_length": 500,
                "description": "Speculum examination findings",
                "extraction_hints": ["speculum", "cervix", "discharge", "vaginal exam"]
            },
            "digital_exam": {
                "type": "string",
                "max_length": 500,
                "description": "Digital/bimanual examination findings",
                "extraction_hints": ["bimanual", "digital exam", "pelvic exam"]
            },
            "breast": {
                "type": "string",
                "max_length": 500,
                "description": "Breast examination findings",
                "extraction_hints": ["breast exam", "breasts", "lumps", "masses"]
            },
            "other_findings": {
                "type": "string",
                "max_length": 500,
                "description": "Other relevant physical findings",
                "extraction_hints": ["other findings", "additionally", "also noted"]
            }
        }
    },
    "ultrasound_findings": {
        "type": "object",
        "description": "Ultrasound imaging results (pregnancy-related)",
        "conditional": "pregnancy_status == 'pregnant'",
        "fields": {
            "ultrasound_type": {
                "type": "string",
                "max_length": 100,
                "description": "Type of ultrasound performed",
                "extraction_hints": ["ultrasound", "scan", "USG", "pelvic", "transvaginal", "obstetric"]
            },
            "fetal_biometry": {
                "type": "string",
                "max_length": 500,
                "description": "Fetal measurements",
                "extraction_hints": ["biometry", "measurements", "CRL", "BPD", "crown-rump"]
            },
            "fetal_wellbeing": {
                "type": "string",
                "max_length": 500,
                "description": "Fetal well-being assessment",
                "extraction_hints": ["heart rate", "FHR", "movements", "fetal activity"]
            },
            "placental_findings": {
                "type": "string",
                "max_length": 500,
                "description": "Placental location and findings",
                "extraction_hints": ["placenta", "placental position", "anterior", "posterior"]
            },
            "amniotic_fluid": {
                "type": "string",
                "max_length": 500,
                "description": "Amniotic fluid volume",
                "extraction_hints": ["liquor", "amniotic fluid", "AFI", "oligohydramnios", "polyhydramnios"]
            },
            "anomalies_concerns": {
                "type": "string",
                "max_length": 500,
                "description": "Any anomalies or concerns",
                "extraction_hints": ["anomaly", "concern", "abnormal", "finding"]
            },
            "gestational_age_weeks": {
                "type": "number",
                "unit": "weeks",
                "range": [0, 45],
                "description": "Gestational age in weeks",
                "extraction_hints": ["weeks pregnant", "gestation", "weeks", "GA"]
            }
        }
    },
    "lab_results": {
        "type": "object",
        "description": "Laboratory test results",
        "fields": {
            "fbc": {
                "type": "string",
                "max_length": 500,
                "description": "Full Blood Count results",
                "extraction_hints": ["CBC", "FBC", "hemoglobin", "hematocrit", "WBC", "platelets"]
            },
            "coagulation": {
                "type": "string",
                "max_length": 500,
                "description": "Coagulation profile",
                "extraction_hints": ["PT", "INR", "APTT", "coagulation", "clotting"]
            },
            "glucose": {
                "type": "string",
                "max_length": 500,
                "description": "Blood glucose and HbA1c",
                "extraction_hints": ["HbA1c", "fasting glucose", "OGTT", "glucose tolerance"]
            },
            "serology": {
                "type": "string",
                "max_length": 500,
                "description": "Serology and STI tests",
                "extraction_hints": ["serology", "HIV", "hepatitis", "VDRL", "RPR", "STI"]
            },
            "pregnancy_tests": {
                "type": "string",
                "max_length": 500,
                "description": "Pregnancy-related tests",
                "extraction_hints": ["hCG", "AFP", "PAPP-A", "pregnancy test", "beta hCG"]
            },
            "other_tests": {
                "type": "string",
                "max_length": 500,
                "description": "Other relevant tests",
                "extraction_hints": ["other tests", "also tested", "additionally"]
            }
        }
    },
    "chief_complaint": {
        "type": "string",
        "max_length": 1000,
        "description": "Main reason for visit",
        "extraction_hints": ["chief complaint", "presenting with", "came in for", "here for", "complaining of"]
    },
    "symptoms_description": {
        "type": "string",
        "max_length": 2000,
        "description": "Detailed symptom description",
        "extraction_hints": ["symptoms", "experiencing", "feeling", "having"]
    },
    "diagnosis": {
        "type": "string",
        "max_length": 1000,
        "description": "Working diagnosis",
        "extraction_hints": ["diagnosis", "diagnosed with", "impression", "likely", "appears to be"]
    },
    "treatment_plan": {
        "type": "string",
        "max_length": 1000,
        "description": "Treatment plan and recommendations",
        "extraction_hints": ["plan", "treatment", "recommend", "advise", "manage with"]
    },
    "medications": {
        "type": "string",
        "max_length": 1000,
        "description": "Medications prescribed",
        "extraction_hints": ["prescribe", "medication", "tablet", "capsule", "mg", "dosage", "take"]
    },
    "follow_up_date": {
        "type": "string",  # ISO date string
        "format": "YYYY-MM-DD",
        "description": "Follow-up appointment date",
        "extraction_hints": ["follow up", "see you", "come back", "next appointment", "return in"]
    },
    "clinical_notes": {
        "type": "string",
        "max_length": 2000,
        "description": "Additional clinical observations",
        "extraction_hints": ["note", "observed", "mentioned", "additionally"]
    }
}

# ============================================
# INFERTILITY FORM SCHEMA (Simplified)
# ============================================

INFERTILITY_FORM_SCHEMA = {
    "vital_signs": OBGYN_FORM_SCHEMA["vital_signs"],  # Reuse vital signs
    "chief_complaint": OBGYN_FORM_SCHEMA["chief_complaint"],
    "diagnosis": OBGYN_FORM_SCHEMA["diagnosis"],
    "treatment_plan": OBGYN_FORM_SCHEMA["treatment_plan"],
    "medications": OBGYN_FORM_SCHEMA["medications"],
    # Infertility-specific fields
    "infertility_duration": {
        "type": "string",
        "max_length": 200,
        "description": "Duration of infertility",
        "extraction_hints": ["trying for", "unable to conceive", "years of infertility"]
    },
    "previous_treatments": {
        "type": "string",
        "max_length": 1000,
        "description": "Previous infertility treatments",
        "extraction_hints": ["previous treatment", "tried IVF", "IUI", "ovulation induction"]
    },
    "investigations_ordered": {
        "type": "string",
        "max_length": 1000,
        "description": "Investigations ordered",
        "extraction_hints": ["order", "test", "investigation", "check", "HSG", "semen analysis"]
    },
    "follow_up_date": OBGYN_FORM_SCHEMA["follow_up_date"],
    "clinical_notes": OBGYN_FORM_SCHEMA["clinical_notes"]
}

# ============================================
# ANTENATAL FORM SCHEMA (Simplified)
# ============================================

ANTENATAL_FORM_SCHEMA = {
    "vital_signs": OBGYN_FORM_SCHEMA["vital_signs"],
    "ultrasound_findings": OBGYN_FORM_SCHEMA["ultrasound_findings"],
    "lab_results": OBGYN_FORM_SCHEMA["lab_results"],
    # Antenatal-specific fields
    "fundal_height": {
        "type": "number",
        "unit": "cm",
        "range": [0, 50],
        "description": "Fundal height measurement",
        "extraction_hints": ["fundal height", "FH", "symphysis-fundal height"]
    },
    "fetal_heart_rate": {
        "type": "number",
        "unit": "bpm",
        "range": [100, 180],
        "description": "Fetal heart rate",
        "extraction_hints": ["FHR", "fetal heart", "baby's heartbeat"]
    },
    "fetal_movements": {
        "type": "string",
        "max_length": 200,
        "description": "Fetal movement assessment",
        "extraction_hints": ["movements", "kicks", "baby moving", "active"]
    },
    "edema": {
        "type": "string",
        "max_length": 200,
        "description": "Edema/swelling assessment",
        "extraction_hints": ["edema", "swelling", "puffy", "ankles", "feet"]
    },
    "presentation": {
        "type": "string",
        "max_length": 100,
        "description": "Fetal presentation",
        "extraction_hints": ["presentation", "cephalic", "breech", "transverse"]
    },
    "diagnosis": OBGYN_FORM_SCHEMA["diagnosis"],
    "treatment_plan": OBGYN_FORM_SCHEMA["treatment_plan"],
    "medications": OBGYN_FORM_SCHEMA["medications"],
    "follow_up_date": OBGYN_FORM_SCHEMA["follow_up_date"],
    "clinical_notes": OBGYN_FORM_SCHEMA["clinical_notes"]
}

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_schema_for_form_type(form_type: str) -> Dict[str, Any]:
    """
    Get the schema for a specific form type.

    Args:
        form_type: One of 'obgyn', 'infertility', 'antenatal'

    Returns:
        Dictionary containing the form schema

    Raises:
        ValueError: If form_type is not recognized
    """
    schemas = {
        'obgyn': OBGYN_FORM_SCHEMA,
        'infertility': INFERTILITY_FORM_SCHEMA,
        'antenatal': ANTENATAL_FORM_SCHEMA
    }

    if form_type not in schemas:
        raise ValueError(f"Unknown form type: {form_type}. Expected one of: {list(schemas.keys())}")

    return schemas[form_type]


def get_extractable_fields(form_type: str) -> List[str]:
    """
    Get a list of all extractable field paths for a form type.
    Returns field paths in dot notation (e.g., 'vital_signs.systolic_bp').

    Args:
        form_type: One of 'obgyn', 'infertility', 'antenatal'

    Returns:
        List of field paths in dot notation
    """
    schema = get_schema_for_form_type(form_type)
    field_paths = []

    for key, value in schema.items():
        if isinstance(value, dict) and value.get('type') == 'object':
            # Nested object (e.g., vital_signs)
            for sub_key in value.get('fields', {}).keys():
                field_paths.append(f"{key}.{sub_key}")
        else:
            # Top-level field
            field_paths.append(key)

    return field_paths


def get_field_metadata(form_type: str, field_path: str) -> Optional[Dict[str, Any]]:
    """
    Get metadata for a specific field path.

    Args:
        form_type: One of 'obgyn', 'infertility', 'antenatal'
        field_path: Field path in dot notation (e.g., 'vital_signs.systolic_bp')

    Returns:
        Dictionary containing field metadata, or None if field not found
    """
    schema = get_schema_for_form_type(form_type)

    if '.' in field_path:
        # Nested field
        parent, child = field_path.split('.', 1)
        if parent in schema and isinstance(schema[parent], dict):
            return schema[parent].get('fields', {}).get(child)
    else:
        # Top-level field
        return schema.get(field_path)

    return None


def build_extraction_prompt_hints(form_type: str) -> str:
    """
    Build a formatted string of extraction hints for use in LLM prompts.

    Args:
        form_type: One of 'obgyn', 'infertility', 'antenatal'

    Returns:
        Formatted string describing fields and extraction hints
    """
    schema = get_schema_for_form_type(form_type)
    hints = []

    for key, value in schema.items():
        if isinstance(value, dict) and value.get('type') == 'object':
            # Nested object
            hints.append(f"\n{key} (object):")
            for sub_key, sub_value in value.get('fields', {}).items():
                field_type = sub_value.get('type', 'unknown')
                description = sub_value.get('description', '')
                extraction_hints = sub_value.get('extraction_hints', [])
                hints.append(f"  - {sub_key} ({field_type}): {description}")
                if extraction_hints:
                    hints.append(f"    Hints: {', '.join(extraction_hints)}")
        else:
            # Top-level field
            field_type = value.get('type', 'unknown')
            description = value.get('description', '')
            extraction_hints = value.get('extraction_hints', [])
            hints.append(f"\n{key} ({field_type}): {description}")
            if extraction_hints:
                hints.append(f"  Hints: {', '.join(extraction_hints)}")

    return '\n'.join(hints)


# ============================================
# SCHEMA METADATA
# ============================================

FORM_TYPES = ['obgyn', 'infertility', 'antenatal']

# Fields that are commonly extracted from consultations (priority fields)
HIGH_PRIORITY_FIELDS = [
    'vital_signs.systolic_bp',
    'vital_signs.diastolic_bp',
    'vital_signs.heart_rate',
    'vital_signs.temperature',
    'chief_complaint',
    'diagnosis',
    'treatment_plan',
    'medications'
]
