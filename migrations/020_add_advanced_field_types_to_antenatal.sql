-- Migration: Add Advanced Field Types to Antenatal Form
-- Description: Enhance antenatal schema with dropdown, checkbox, radio, multi-select, and rating fields
-- Created: 2026-01-03

-- Update antenatal schema to include advanced field types
UPDATE form_schemas
SET schema_definition = '{
  "lmp": {
    "type": "string",
    "format": "date",
    "description": "Last Menstrual Period date",
    "extraction_hints": ["LMP", "last menstrual period", "last period", "period was"]
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
  "gestational_age_weeks": {
    "type": "number",
    "range": [0, 45],
    "description": "Gestational age in weeks",
    "extraction_hints": ["weeks pregnant", "gestational age", "GA", "weeks gestation"]
  },
  "weight_kg": {
    "type": "number",
    "range": [30, 200],
    "description": "Patient weight in kilograms",
    "extraction_hints": ["weight", "kg", "kilograms", "weighs"]
  },
  "blood_pressure_systolic": {
    "type": "number",
    "range": [60, 250],
    "description": "Systolic blood pressure (mmHg)",
    "extraction_hints": ["systolic", "BP", "blood pressure", "mmHg"]
  },
  "blood_pressure_diastolic": {
    "type": "number",
    "range": [40, 150],
    "description": "Diastolic blood pressure (mmHg)",
    "extraction_hints": ["diastolic", "BP", "blood pressure", "mmHg"]
  },
  "fetal_heart_rate": {
    "type": "number",
    "range": [100, 200],
    "description": "Fetal heart rate (beats per minute)",
    "extraction_hints": ["fetal heart rate", "FHR", "baby heartbeat", "bpm"]
  },
  "fundal_height_cm": {
    "type": "number",
    "range": [10, 50],
    "description": "Fundal height in centimeters",
    "extraction_hints": ["fundal height", "FH", "cm", "centimeters", "uterus size"]
  },
  "prenatal_vitamins": {
    "type": "boolean",
    "description": "Currently taking prenatal vitamins?",
    "extraction_hints": ["prenatal vitamins", "supplements", "folic acid", "taking vitamins"]
  },
  "planned_delivery": {
    "type": "string",
    "input_type": "dropdown",
    "description": "Planned delivery method",
    "placeholder": "Select delivery method...",
    "options": [
      "Normal vaginal delivery",
      "Elective cesarean section",
      "Trial of labor after cesarean (TOLAC)",
      "Vaginal birth after cesarean (VBAC)",
      "To be decided"
    ],
    "extraction_hints": ["delivery plan", "birth plan", "how deliver", "cesarean", "vaginal delivery"]
  },
  "current_symptoms": {
    "type": "string",
    "input_type": "checkbox",
    "description": "Current pregnancy symptoms (select all that apply)",
    "options": [
      "Nausea/vomiting",
      "Fatigue/tiredness",
      "Breast tenderness",
      "Frequent urination",
      "Heartburn/indigestion",
      "Back pain",
      "Leg cramps",
      "Mood changes",
      "Headaches",
      "Swelling (hands/feet)",
      "None"
    ],
    "extraction_hints": ["symptoms", "experiencing", "feeling", "complaints", "nausea", "tired", "pain"]
  },
  "fetal_movement": {
    "type": "string",
    "input_type": "radio",
    "description": "Fetal movement pattern",
    "options": [
      "Normal - active movements felt regularly",
      "Reduced movements (decreased from usual)",
      "No movements felt today",
      "Too early to feel movements (< 18-20 weeks)",
      "Not applicable"
    ],
    "extraction_hints": ["baby moving", "kicks", "fetal movement", "baby active", "feel baby"]
  },
  "risk_factors": {
    "type": "string",
    "input_type": "multi-select",
    "description": "Pregnancy risk factors (select all applicable)",
    "placeholder": "Select risk factors...",
    "options": [
      "None identified",
      "Gestational diabetes",
      "Gestational hypertension",
      "Pre-eclampsia",
      "Previous cesarean section",
      "Advanced maternal age (≥35 years)",
      "Multiple pregnancy (twins/triplets)",
      "Obesity (BMI ≥30)",
      "Previous preterm birth",
      "Previous stillbirth",
      "Rh incompatibility",
      "Placenta previa",
      "Anemia",
      "Thyroid disorder"
    ],
    "extraction_hints": ["risk", "complications", "medical history", "diabetes", "hypertension", "previous cesarean"]
  },
  "pain_level": {
    "type": "number",
    "input_type": "rating",
    "description": "Current pain/discomfort level (0 = no pain, 10 = severe pain)",
    "min_rating": 0,
    "max_rating": 10,
    "extraction_hints": ["pain", "discomfort", "hurts", "pain scale", "rate pain"]
  },
  "edema_severity": {
    "type": "string",
    "input_type": "radio",
    "description": "Swelling/edema severity",
    "options": [
      "None",
      "Mild (slight swelling in feet at end of day)",
      "Moderate (persistent swelling in feet/ankles)",
      "Severe (swelling in legs, hands, or face)"
    ],
    "extraction_hints": ["swelling", "edema", "feet swollen", "ankle swelling", "puffy"]
  },
  "prenatal_tests_completed": {
    "type": "string",
    "input_type": "checkbox",
    "description": "Prenatal tests/screenings completed (select all)",
    "options": [
      "First trimester screening",
      "NIPT/cell-free DNA",
      "Anomaly scan (20 weeks)",
      "Glucose tolerance test",
      "Group B Strep screening",
      "Ultrasound scans",
      "Blood type and Rh",
      "None yet"
    ],
    "extraction_hints": ["tests done", "screening", "ultrasound", "scan", "blood test", "glucose test"]
  },
  "complaints": {
    "type": "string",
    "max_length": 2000,
    "description": "Patient complaints or concerns",
    "extraction_hints": ["complaint", "concerned about", "worried", "problem", "issue"]
  },
  "plan_mother": {
    "type": "string",
    "max_length": 2000,
    "description": "Management plan for mother",
    "extraction_hints": ["plan for mother", "maternal plan", "mother should", "advise mother", "recommendations"]
  },
  "plan_fetus": {
    "type": "string",
    "max_length": 2000,
    "description": "Management plan for fetus/baby",
    "extraction_hints": ["plan for baby", "fetal plan", "monitor baby", "baby care"]
  },
  "followup_plan": {
    "type": "string",
    "max_length": 2000,
    "description": "Follow-up instructions and next appointment",
    "extraction_hints": ["follow up", "next visit", "come back", "return", "see you"]
  }
}'::jsonb,
updated_at = now()
WHERE form_type = 'antenatal' AND is_active = true;

-- Log the update
DO $$
BEGIN
  RAISE NOTICE 'Updated antenatal schema with advanced field types:';
  RAISE NOTICE '  - Dropdown: planned_delivery';
  RAISE NOTICE '  - Checkboxes: current_symptoms, prenatal_tests_completed';
  RAISE NOTICE '  - Radio: fetal_movement, edema_severity';
  RAISE NOTICE '  - Multi-select: risk_factors';
  RAISE NOTICE '  - Rating scale: pain_level';
END $$;
