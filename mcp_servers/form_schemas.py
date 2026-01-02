"""
Form schemas for auto-fill extraction from consultation transcripts.

Defines the schema structure for medical forms organized by specialty
to enable intelligent field extraction from diarized doctor-patient conversations.

Specialties:
- Obstetrics & Gynecology: OBGyn, Infertility, Antenatal forms
- Cardiology: Consultation forms
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
    # Obstetric History
    "number_of_pregnancies": {
        "type": "number",
        "range": [0, 20],
        "description": "Total number of pregnancies (gravida)",
        "extraction_hints": ["pregnancies", "gravida", "pregnant before", "how many times pregnant", "G"]
    },
    "number_of_live_births": {
        "type": "number",
        "range": [0, 20],
        "description": "Number of live births (para)",
        "extraction_hints": ["live births", "para", "delivered", "children", "P"]
    },
    "number_of_miscarriages": {
        "type": "number",
        "range": [0, 10],
        "description": "Number of miscarriages",
        "extraction_hints": ["miscarriage", "miscarried", "lost pregnancy", "spontaneous abortion"]
    },
    "number_of_abortions": {
        "type": "number",
        "range": [0, 10],
        "description": "Number of induced abortions/terminations",
        "extraction_hints": ["abortion", "termination", "terminated pregnancy"]
    },
    "previous_delivery_methods": {
        "type": "string",
        "max_length": 500,
        "description": "Previous delivery methods (vaginal, C-section, etc.)",
        "extraction_hints": ["delivery", "C-section", "cesarean", "vaginal delivery", "forceps", "ventouse"]
    },
    "previous_pregnancy_complications": {
        "type": "string",
        "max_length": 1000,
        "description": "Previous pregnancy complications",
        "extraction_hints": ["complications", "problems", "gestational diabetes", "preeclampsia", "hemorrhage"]
    },
    # Menstrual History
    "last_menstrual_period": {
        "type": "string",  # ISO date string
        "format": "YYYY-MM-DD",
        "description": "Last menstrual period date (LMP)",
        "extraction_hints": ["LMP", "last period", "last menstrual period", "period started"]
    },
    "cycle_length_days": {
        "type": "number",
        "range": [14, 60],
        "description": "Menstrual cycle length in days",
        "extraction_hints": ["cycle length", "days apart", "every X days", "regular cycle"]
    },
    "cycle_regularity": {
        "type": "string",
        "max_length": 100,
        "description": "Cycle regularity (regular, irregular, variable)",
        "extraction_hints": ["regular", "irregular", "variable", "predictable", "unpredictable"]
    },
    "menstrual_pain_severity": {
        "type": "string",
        "max_length": 100,
        "description": "Severity of menstrual pain (none, mild, moderate, severe)",
        "extraction_hints": ["period pain", "cramps", "dysmenorrhea", "painful periods"]
    },
    "menstrual_notes": {
        "type": "string",
        "max_length": 1000,
        "description": "Additional menstrual history notes",
        "extraction_hints": ["period", "menstruation", "bleeding", "flow"]
    },
    # Contraception
    "using_contraception": {
        "type": "boolean",
        "description": "Currently using contraception",
        "extraction_hints": ["contraception", "birth control", "family planning", "preventing pregnancy"]
    },
    "contraception_method": {
        "type": "string",
        "max_length": 200,
        "description": "Current contraception method",
        "extraction_hints": ["pill", "IUD", "condom", "implant", "injection", "patch", "ring"]
    },
    "contraception_notes": {
        "type": "string",
        "max_length": 500,
        "description": "Notes about contraception usage and satisfaction",
        "extraction_hints": ["side effects", "satisfied", "problems", "switching"]
    },
    # Sexual and Reproductive Health
    "sexual_activity_status": {
        "type": "string",
        "max_length": 100,
        "description": "Sexual activity status",
        "extraction_hints": ["sexually active", "not active", "abstinent"]
    },
    "std_history": {
        "type": "string",
        "max_length": 500,
        "description": "STD/STI history and testing",
        "extraction_hints": ["STD", "STI", "sexually transmitted", "chlamydia", "gonorrhea", "HPV"]
    },
    # Current Pregnancy (if applicable)
    "currently_pregnant": {
        "type": "boolean",
        "description": "Patient is currently pregnant",
        "extraction_hints": ["pregnant", "expecting", "pregnancy", "weeks pregnant"]
    },
    "gestational_age_weeks": {
        "type": "number",
        "range": [0, 45],
        "description": "Current gestational age in weeks",
        "extraction_hints": ["weeks pregnant", "gestation", "weeks", "GA"]
    },
    "pregnancy_notes": {
        "type": "string",
        "max_length": 1000,
        "description": "Current pregnancy notes and observations",
        "extraction_hints": ["pregnancy", "antenatal", "prenatal"]
    },
    # Gynecological Symptoms
    "chronic_pelvic_pain": {
        "type": "boolean",
        "description": "Experiencing chronic pelvic pain",
        "extraction_hints": ["pelvic pain", "chronic pain", "ongoing pain"]
    },
    "pelvic_pain_description": {
        "type": "string",
        "max_length": 1000,
        "description": "Description of pelvic pain",
        "extraction_hints": ["pain", "discomfort", "cramping", "aching", "sharp"]
    },
    "abnormal_discharge": {
        "type": "boolean",
        "description": "Experiencing abnormal vaginal discharge",
        "extraction_hints": ["discharge", "abnormal discharge", "unusual discharge"]
    },
    "discharge_description": {
        "type": "string",
        "max_length": 500,
        "description": "Description of vaginal discharge",
        "extraction_hints": ["discharge color", "odor", "consistency", "amount"]
    },
    "bleeding_pattern": {
        "type": "string",
        "max_length": 500,
        "description": "Abnormal bleeding patterns",
        "extraction_hints": ["bleeding", "spotting", "heavy", "light", "intermenstrual"]
    },
    # Clinical Assessment
    "clinical_impression": {
        "type": "string",
        "max_length": 1000,
        "description": "Clinical impression and diagnosis",
        "extraction_hints": ["impression", "diagnosis", "diagnosed with", "likely", "appears to be"]
    },
    "gynecological_notes": {
        "type": "string",
        "max_length": 2000,
        "description": "General gynecological notes and observations",
        "extraction_hints": ["note", "observed", "mentioned", "additionally", "findings"]
    },
    # Fertility and Planning
    "fertility_concerns": {
        "type": "string",
        "max_length": 1000,
        "description": "Fertility concerns or questions",
        "extraction_hints": ["fertility", "trying to conceive", "difficulty getting pregnant", "infertility"]
    },
    "planning_pregnancy": {
        "type": "boolean",
        "description": "Planning to become pregnant",
        "extraction_hints": ["planning pregnancy", "trying to conceive", "want to get pregnant"]
    }
}

# ============================================
# INFERTILITY FORM SCHEMA (Simplified)
# ============================================

INFERTILITY_FORM_SCHEMA = {
    "vital_signs": OBGYN_FORM_SCHEMA["vital_signs"],  # Reuse vital signs
    "clinical_impression": OBGYN_FORM_SCHEMA["clinical_impression"],  # Reuse from OBGYN
    "gynecological_notes": OBGYN_FORM_SCHEMA["gynecological_notes"],  # Reuse from OBGYN
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
    "treatment_plan": {
        "type": "string",
        "max_length": 1000,
        "description": "Treatment plan and recommendations",
        "extraction_hints": ["plan", "treatment", "recommend", "advise", "manage with", "next steps"]
    },
    "medications": {
        "type": "string",
        "max_length": 1000,
        "description": "Medications prescribed",
        "extraction_hints": ["prescribe", "medication", "tablet", "capsule", "mg", "dosage", "take", "clomid", "letrozole"]
    }
}

# ============================================
# ANTENATAL FORM SCHEMA (Simplified)
# ============================================

ANTENATAL_FORM_SCHEMA = {
    # Database table fields (matching antenatal_forms columns)
    "lmp": {
        "type": "string",
        "format": "YYYY-MM-DD",
        "description": "Last Menstrual Period date",
        "extraction_hints": ["LMP", "last menstrual period", "last period", "period was"]
    },
    "gestational_age_weeks": {
        "type": "number",
        "unit": "weeks",
        "range": [0, 45],
        "description": "Gestational age in weeks",
        "extraction_hints": ["weeks pregnant", "gestational age", "GA", "weeks gestation"]
    },
    "gravida": {
        "type": "number",
        "range": [0, 20],
        "description": "Total number of pregnancies (including current)",
        "extraction_hints": ["gravida", "G", "number of pregnancies", "pregnant before"]
    },
    "para": {
        "type": "number",
        "range": [0, 20],
        "description": "Number of deliveries beyond 20 weeks",
        "extraction_hints": ["para", "P", "deliveries", "births"]
    },
    "current_symptoms": {
        "type": "string",
        "max_length": 2000,
        "description": "Current pregnancy symptoms",
        "extraction_hints": ["symptoms", "experiencing", "feeling", "nausea", "pain", "discomfort"]
    },
    "complaints": {
        "type": "string",
        "max_length": 2000,
        "description": "Patient complaints or concerns",
        "extraction_hints": ["complaint", "concerned about", "worried", "problem"]
    },
    "plan_mother": {
        "type": "string",
        "max_length": 2000,
        "description": "Management plan for mother",
        "extraction_hints": ["plan for mother", "maternal plan", "mother should", "advise"]
    },
    "plan_fetus": {
        "type": "string",
        "max_length": 2000,
        "description": "Management plan for fetus",
        "extraction_hints": ["plan for baby", "fetal plan", "monitor baby", "baby's"]
    },
    "followup_plan": {
        "type": "string",
        "max_length": 2000,
        "description": "Follow-up instructions",
        "extraction_hints": ["follow up", "next visit", "come back", "return"]
    },
    # Vital signs (nested object)
    "vital_signs": {
        "type": "object",
        "description": "Vital signs measurements",
        "fields": {
            "systolic_bp": {
                "type": "number",
                "unit": "mmHg",
                "range": [60, 250],
                "description": "Systolic blood pressure",
                "extraction_hints": ["systolic", "BP", "blood pressure", "mmHg"]
            },
            "diastolic_bp": {
                "type": "number",
                "unit": "mmHg",
                "range": [40, 150],
                "description": "Diastolic blood pressure",
                "extraction_hints": ["diastolic", "BP", "blood pressure", "mmHg"]
            },
            "weight_kg": {
                "type": "number",
                "unit": "kg",
                "range": [30, 200],
                "description": "Patient weight in kilograms",
                "extraction_hints": ["weight", "kg", "kilograms", "weighs"]
            }
        }
    },
    # Fetal measurements
    "fetal_heart_rate": {
        "type": "number",
        "unit": "bpm",
        "range": [100, 200],
        "description": "Fetal heart rate",
        "extraction_hints": ["fetal heart rate", "FHR", "baby's heart rate", "beats per minute", "bpm"]
    },
    "fundal_height_cm": {
        "type": "number",
        "unit": "cm",
        "range": [10, 50],
        "description": "Fundal height in centimeters",
        "extraction_hints": ["fundal height", "FH", "cm", "centimeters", "uterus size"]
    },
    # Laboratory investigations (nested object)
    "lab_investigations": {
        "type": "object",
        "description": "Laboratory test results",
        "fields": {
            "hemoglobin_g_dl": {
                "type": "number",
                "unit": "g/dL",
                "range": [5, 20],
                "description": "Hemoglobin level in g/dL",
                "extraction_hints": ["hemoglobin", "Hb", "g/dL", "anemia"]
            },
            "blood_group": {
                "type": "string",
                "max_length": 10,
                "description": "Blood group",
                "extraction_hints": ["blood group", "blood type", "A+", "B+", "O+", "AB+", "A-", "B-", "O-", "AB-"]
            },
            "random_blood_glucose_mg_dl": {
                "type": "number",
                "unit": "mg/dL",
                "range": [50, 400],
                "description": "Random blood glucose in mg/dL",
                "extraction_hints": ["blood glucose", "blood sugar", "RBS", "random glucose", "mg/dL"]
            }
        }
    }
}

# Comprehensive medical history intake form capturing patient symptoms, cardiovascular history, and comorbid conditions
CONSULTATION_FORM_FORM_SCHEMA = {
    "other": {
        "type": 'object',
        "description": 'Other fields',
        "fields": {
            "treatment_history": {
                "type": 'string',
                "description": 'Free text field for documenting prior treatment history',
                "max_length": 2000,
                "extraction_hints": ['treatment history'],
            },
            "pulse": {
                "type": 'number',
                "description": "Patient's pulse rate",
                "unit": 'bpm',
                "range": [0, 300],
                "extraction_hints": ['pulse'],
            },
            "pulse_per_min": {
                "type": 'number',
                "description": "Patient's pulse rate per minute",
                "unit": 'bpm',
                "range": [0, 300],
                "extraction_hints": ['pulse/min', 'pulse per min'],
            },
            "examination_description": {
                "type": 'string',
                "description": 'Detailed description of examination findings',
                "max_length": 2000,
                "extraction_hints": ['description', 'examination description'],
            },
            "carotid_right": {
                "type": 'string',
                "description": 'Right carotid pulse examination findings',
                "max_length": 200,
                "extraction_hints": ['carotid - right', 'carotid right'],
            },
            "radial_right": {
                "type": 'string',
                "description": 'Right radial pulse examination findings',
                "max_length": 200,
                "extraction_hints": ['radial - right', 'radial right'],
            },
            "brachial_right": {
                "type": 'string',
                "description": 'Right brachial pulse examination findings',
                "max_length": 200,
                "extraction_hints": ['brachial - right', 'brachial right'],
            },
            "femoral_right": {
                "type": 'string',
                "description": 'Right femoral pulse examination findings',
                "max_length": 200,
                "extraction_hints": ['femoral - right', 'femoral right'],
            },
            "popliteal_right": {
                "type": 'string',
                "description": 'Right popliteal pulse examination findings',
                "max_length": 200,
                "extraction_hints": ['popliteal - right', 'popliteal right'],
            },
            "pta_right": {
                "type": 'string',
                "description": 'Right posterior tibial artery pulse examination findings',
                "max_length": 200,
                "extraction_hints": ['pta - right', 'pta right'],
            },
            "dpa_right": {
                "type": 'string',
                "description": 'Right dorsalis pedis artery pulse examination findings',
                "max_length": 200,
                "extraction_hints": ['dpa - right', 'dpa right'],
            },
            "carotid_left": {
                "type": 'string',
                "description": 'Left carotid pulse examination findings',
                "max_length": 200,
                "extraction_hints": ['carotid - left', 'carotid left'],
            },
            "radial_left": {
                "type": 'string',
                "description": 'Left radial pulse examination findings',
                "max_length": 200,
                "extraction_hints": ['radial - left', 'radial left'],
            },
            "brachial_left": {
                "type": 'string',
                "description": 'Left brachial pulse examination findings',
                "max_length": 200,
                "extraction_hints": ['brachial - left', 'brachial left'],
            },
            "femoral_left": {
                "type": 'string',
                "description": 'Left femoral pulse examination findings',
                "max_length": 200,
                "extraction_hints": ['femoral - left', 'femoral left'],
            },
            "popliteal_left": {
                "type": 'string',
                "description": 'Left popliteal pulse examination findings',
                "max_length": 200,
                "extraction_hints": ['popliteal - left', 'popliteal left'],
            },
            "pta_left": {
                "type": 'string',
                "description": 'Left posterior tibial artery pulse examination findings',
                "max_length": 200,
                "extraction_hints": ['pta - left', 'pta left'],
            },
            "dpa_left": {
                "type": 'string',
                "description": 'Left dorsalis pedis artery pulse examination findings',
                "max_length": 200,
                "extraction_hints": ['dpa - left', 'dpa left'],
            },
            "bp_right_upper_limb_supine": {
                "type": 'string',
                "description": 'Blood pressure measurement for right upper limb in supine position',
                "max_length": 200,
                "extraction_hints": ['blood pressure (mmhg) - right upper limb - supine', 'bp right upper limb supine'],
            },
            "bp_right_upper_limb_sitting": {
                "type": 'string',
                "description": 'Blood pressure measurement for right upper limb in sitting position',
                "max_length": 200,
                "extraction_hints": ['blood pressure (mmhg) - right upper limb - sitting', 'bp right upper limb sitting'],
            },
            "bp_right_upper_limb_standing": {
                "type": 'string',
                "description": 'Blood pressure measurement for right upper limb in standing position',
                "max_length": 200,
                "extraction_hints": ['blood pressure (mmhg) - right upper limb - standing', 'bp right upper limb standing'],
            },
            "bp_left_upper_limb_supine": {
                "type": 'string',
                "description": 'Blood pressure measurement for left upper limb in supine position',
                "max_length": 200,
                "extraction_hints": ['blood pressure (mmhg) - left upper limb - supine', 'bp left upper limb supine'],
            },
            "bp_left_upper_limb_sitting": {
                "type": 'string',
                "description": 'Blood pressure measurement for left upper limb in sitting position',
                "max_length": 200,
                "extraction_hints": ['blood pressure (mmhg) - left upper limb - sitting', 'bp left upper limb sitting'],
            },
            "bp_left_upper_limb_standing": {
                "type": 'string',
                "description": 'Blood pressure measurement for left upper limb in standing position',
                "max_length": 200,
                "extraction_hints": ['blood pressure (mmhg) - left upper limb - standing', 'bp left upper limb standing'],
            },
            "bp_right_lower_limb_supine": {
                "type": 'string',
                "description": 'Blood pressure measurement for right lower limb in supine position',
                "max_length": 200,
                "extraction_hints": ['blood pressure (mmhg) - right lower limb - supine', 'bp right lower limb supine'],
            },
            "bp_right_lower_limb_sitting": {
                "type": 'string',
                "description": 'Blood pressure measurement for right lower limb in sitting position',
                "max_length": 200,
                "extraction_hints": ['blood pressure (mmhg) - right lower limb - sitting', 'bp right lower limb sitting'],
            },
            "bp_right_lower_limb_standing": {
                "type": 'string',
                "description": 'Blood pressure measurement for right lower limb in standing position',
                "max_length": 200,
                "extraction_hints": ['blood pressure (mmhg) - right lower limb - standing', 'bp right lower limb standing'],
            },
        },
    },
}
# ============================================
# FORM SCHEMAS BY SPECIALTY
# ============================================

FORM_SCHEMAS_BY_SPECIALTY = {
    "obstetrics_gynecology": {
        "obgyn": OBGYN_FORM_SCHEMA,
        "infertility": INFERTILITY_FORM_SCHEMA,
        "antenatal": ANTENATAL_FORM_SCHEMA,
    },
    "cardiology": {
        "consultation_form": CONSULTATION_FORM_FORM_SCHEMA,
    }
}

# Flat mapping for backward compatibility
_FLAT_SCHEMAS = {
    'obgyn': OBGYN_FORM_SCHEMA,
    'infertility': INFERTILITY_FORM_SCHEMA,
    'antenatal': ANTENATAL_FORM_SCHEMA,
    'consultation_form': CONSULTATION_FORM_FORM_SCHEMA,
}

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_schema_for_form_type(form_type: str) -> Dict[str, Any]:
    """
    Get the schema for a specific form type.

    Args:
        form_type: One of 'obgyn', 'infertility', 'antenatal', 'consultation_form'

    Returns:
        Dictionary containing the form schema

    Raises:
        ValueError: If form_type is not recognized
    """
    if form_type not in _FLAT_SCHEMAS:
        raise ValueError(f"Unknown form type: {form_type}. Expected one of: {list(_FLAT_SCHEMAS.keys())}")

    return _FLAT_SCHEMAS[form_type]


def get_all_schemas_for_specialty(specialty: str) -> Dict[str, Dict[str, Any]]:
    """
    Get all form schemas for a given specialty.

    Args:
        specialty: Medical specialty (e.g., 'obstetrics_gynecology', 'cardiology')

    Returns:
        Dictionary mapping form_type to schema for all forms in the specialty

    Example:
        >>> schemas = get_all_schemas_for_specialty('obstetrics_gynecology')
        >>> # Returns: {'obgyn': {...}, 'infertility': {...}, 'antenatal': {...}}
    """
    if specialty not in FORM_SCHEMAS_BY_SPECIALTY:
        raise ValueError(f"Unknown specialty: {specialty}. Expected one of: {list(FORM_SCHEMAS_BY_SPECIALTY.keys())}")

    return FORM_SCHEMAS_BY_SPECIALTY[specialty]


def get_schema_by_specialty(specialty: str, form_type: str) -> Dict[str, Any]:
    """
    Get the schema for a specific form type within a specialty.

    Args:
        specialty: Medical specialty (e.g., 'obstetrics_gynecology', 'cardiology')
        form_type: Form type within that specialty (e.g., 'obgyn', 'consultation_form')

    Returns:
        Dictionary containing the form schema

    Raises:
        ValueError: If specialty or form_type is not recognized
    """
    if specialty not in FORM_SCHEMAS_BY_SPECIALTY:
        raise ValueError(f"Unknown specialty: {specialty}. Expected one of: {list(FORM_SCHEMAS_BY_SPECIALTY.keys())}")

    specialty_forms = FORM_SCHEMAS_BY_SPECIALTY[specialty]

    if form_type not in specialty_forms:
        raise ValueError(f"Unknown form type '{form_type}' for specialty '{specialty}'. Expected one of: {list(specialty_forms.keys())}")

    return specialty_forms[form_type]


def list_specialties() -> List[str]:
    """
    Get list of all available specialties.

    Returns:
        List of specialty names
    """
    return list(FORM_SCHEMAS_BY_SPECIALTY.keys())


def list_forms_by_specialty(specialty: str) -> List[str]:
    """
    Get list of all form types for a specific specialty.

    Args:
        specialty: Medical specialty

    Returns:
        List of form type names

    Raises:
        ValueError: If specialty is not recognized
    """
    if specialty not in FORM_SCHEMAS_BY_SPECIALTY:
        raise ValueError(f"Unknown specialty: {specialty}. Expected one of: {list(FORM_SCHEMAS_BY_SPECIALTY.keys())}")

    return list(FORM_SCHEMAS_BY_SPECIALTY[specialty].keys())


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
    # Try to get schema from database first
    try:
        from api import get_form_schema_from_db
        schema = get_form_schema_from_db(form_type, full_metadata=False)
    except Exception:
        # Fallback to Python file if database fetch fails
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


def build_multi_form_extraction_hints(specialty: str) -> str:
    """
    Build extraction hints for ALL form types in a specialty.

    This allows the LLM to see all available forms and extract fields
    for whichever form(s) match the consultation content.

    Args:
        specialty: Medical specialty (e.g., 'obstetrics_gynecology')

    Returns:
        Formatted string with all form schemas organized by form type

    Example output:
        === OBGYN FORM ===
        vital_signs (object):
          - systolic_bp (number): Systolic blood pressure
            Hints: BP, blood pressure, systolic
        ...

        === INFERTILITY FORM ===
        infertility_duration (string): Duration of infertility
        ...

        === ANTENATAL FORM ===
        lmp (string): Last Menstrual Period date
        ...
    """
    all_schemas = get_all_schemas_for_specialty(specialty)
    sections = []

    for form_type, schema in all_schemas.items():
        # Create header for this form type
        form_display_name = form_type.upper().replace('_', ' ')
        sections.append(f"\n=== {form_display_name} FORM ===")

        # Build hints for this form
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

        sections.append('\n'.join(hints))

    return '\n'.join(sections)


# ============================================
# SCHEMA METADATA
# ============================================

# All form types (flat list for backward compatibility)
FORM_TYPES = ['obgyn', 'infertility', 'antenatal', 'consultation_form']

# Specialty mapping
SPECIALTIES = {
    'obstetrics_gynecology': ['obgyn', 'infertility', 'antenatal'],
    'cardiology': ['consultation_form'],
}

# Fields that are commonly extracted from consultations (priority fields)
HIGH_PRIORITY_FIELDS = [
    'vital_signs.systolic_bp',
    'vital_signs.diastolic_bp',
    'vital_signs.heart_rate',
    'vital_signs.temperature',
    'clinical_impression',
    'gynecological_notes',
    'number_of_pregnancies',
    'number_of_live_births',
    'gestational_age_weeks',
    'currently_pregnant'
]


