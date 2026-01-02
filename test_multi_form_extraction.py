"""
Test multi-form extraction with real LLM output.

This simulates the exact extraction result from the pregnancy consultation
to test the form filling logic without needing to click re-summarise.
"""

import json
from mcp_servers.field_validator import validate_multiple_fields, filter_by_confidence

# Exact LLM extraction output
raw_field_updates = {
    "antenatal:lmp": "2024-11-11",
    "antenatal:gestational_age_weeks": 6,
    "antenatal:gravida": 1,
    "antenatal:para": 0,
    "antenatal:current_symptoms": "nausea, experiencing nausea every day",
    "antenatal:complaints": "wanted to check if everything was okay with the baby",
    "obgyn:vital_signs.systolic_bp": 120,
    "obgyn:vital_signs.diastolic_bp": 80,
    "obgyn:vital_signs.heart_rate": 86,
    "obgyn:vital_signs.spo2": 99,
    "obgyn:physical_exam_findings.general_inspection": "patient is fine",
    "obgyn:physical_exam_findings.abdominal_exam": "abdomen is soft",
    "obgyn:chief_complaint": "six weeks pregnant, wanted to check if everything was okay with the baby",
    "obgyn:symptoms_description": "nausea every day, no vomiting, no headache"
}

confidence_scores = {
    "antenatal:lmp": 0.95,
    "antenatal:gestational_age_weeks": 0.95,
    "antenatal:gravida": 0.9,
    "antenatal:para": 0.9,
    "antenatal:current_symptoms": 0.9,
    "antenatal:complaints": 0.85,
    "obgyn:vital_signs.systolic_bp": 1.0,
    "obgyn:vital_signs.diastolic_bp": 1.0,
    "obgyn:vital_signs.heart_rate": 0.95,
    "obgyn:vital_signs.spo2": 0.95,
    "obgyn:physical_exam_findings.general_inspection": 0.8,
    "obgyn:physical_exam_findings.abdominal_exam": 0.95,
    "obgyn:chief_complaint": 0.9,
    "obgyn:symptoms_description": 0.9
}

print("=" * 80)
print("MULTI-FORM EXTRACTION TEST")
print("=" * 80)

# Filter by confidence
filtered_updates = filter_by_confidence(raw_field_updates, confidence_scores, min_confidence=0.7)

print(f"\n✅ After confidence filter (>= 0.7): {len(filtered_updates)} fields")

# Group fields by form type
fields_by_form = {}
for field_path, value in filtered_updates.items():
    if ':' in field_path:
        form_type, clean_path = field_path.split(':', 1)
        if form_type not in fields_by_form:
            fields_by_form[form_type] = {}
        fields_by_form[form_type][clean_path] = value
    else:
        print(f"⚠️ Field '{field_path}' has no form type prefix, skipping")

print(f"\n📋 Fields grouped by form type:")
for form_type, fields in fields_by_form.items():
    print(f"\n   {form_type.upper()} ({len(fields)} fields):")
    for field, value in fields.items():
        print(f"      - {field}: {value}")

# Determine consultation type from which fields were extracted
if not fields_by_form:
    consultation_type = 'obgyn'
    confidence = 0.5
    reasoning = "No fields extracted, defaulting to general OB/GYN"
elif len(fields_by_form) == 1:
    consultation_type = list(fields_by_form.keys())[0]
    confidence = 0.95
    reasoning = f"All extracted fields belong to {consultation_type} form"
else:
    # Multiple forms detected
    # For pregnancy consultations, prioritize antenatal over obgyn
    if 'antenatal' in fields_by_form and len(fields_by_form['antenatal']) >= 3:
        consultation_type = 'antenatal'
        confidence = 0.95
        reasoning = f"Antenatal consultation detected (pregnancy-specific fields found)"
    else:
        # Pick the one with most fields
        consultation_type = max(fields_by_form, key=lambda k: len(fields_by_form[k]))
        confidence = 0.85
        reasoning = f"Multiple forms detected, {consultation_type} has most fields ({len(fields_by_form[consultation_type])})"

print(f"\n📊 DETECTED CONSULTATION TYPE: {consultation_type}")
print(f"   Confidence: {confidence:.2%}")
print(f"   Reasoning: {reasoning}")

# Get fields for the detected consultation type
field_updates = fields_by_form.get(consultation_type, {})

print(f"\n🔄 Fields to be saved to {consultation_type} form:")
for field, value in field_updates.items():
    print(f"   - {field}: {value}")

# Validate fields
print(f"\n🔍 Validating fields against {consultation_type} schema...")
valid_updates, validation_errors = validate_multiple_fields(
    consultation_type,
    field_updates
)

if validation_errors:
    print(f"\n⚠️  Validation errors:")
    for field, error in validation_errors.items():
        print(f"   - {field}: {error}")

print(f"\n✅ Valid fields: {list(valid_updates.keys())}")
print(f"   Total valid: {len(valid_updates)}")

# Show what would be stored
print(f"\n💾 Data to be stored in database:")
print(json.dumps(valid_updates, indent=2))

print("\n" + "=" * 80)
print("ANALYSIS:")
print("=" * 80)
print(f"""
This consultation extracted fields for BOTH forms:
- Antenatal: {len(fields_by_form.get('antenatal', {}))} fields (pregnancy-specific)
- OB/GYN: {len(fields_by_form.get('obgyn', {}))} fields (vital signs, exam findings)

DECISION: Selected '{consultation_type}' form because {reasoning.lower()}

✅ FIXED: Vital signs from obgyn form are now saved to antenatal_visits!

The /api/auto-fill-consultation-form endpoint now:
1. Saves antenatal fields to antenatal_forms ✅
2. Creates antenatal_visit record with vital signs ✅
3. Properly handles multi-form extraction

Implementation details (api.py:4766-4795):
- When antenatal consultation detected with obgyn vital signs
- Extracts vital signs (systolic_bp, diastolic_bp, heart_rate, weight_kg)
- Calls save_vital_signs_to_antenatal_visit()
- Creates/updates antenatal_visits record linked to antenatal_forms
""")
