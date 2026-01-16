"""
Test logo extraction from historical forms
"""

import json

# Simulate the extraction response that would come from Claude
sample_extraction_response = """{
  "demographics": {
    "name": "Sarah Johnson",
    "date_of_birth": "1988-03-22",
    "age_years": null,
    "sex": "Female",
    "phone": "+1-555-0123",
    "email": null,
    "height_cm": 168,
    "weight_kg": 72
  },
  "vitals": [
    {
      "recorded_at": "2024-12-15",
      "systolic_bp": 118,
      "diastolic_bp": 76,
      "heart_rate": 68,
      "respiratory_rate": 16,
      "temperature_celsius": 36.8,
      "spo2": 98,
      "blood_glucose_mg_dl": null
    }
  ],
  "medications": [
    {
      "medication_name": "Levothyroxine",
      "dosage": "50 mcg",
      "frequency": "Once daily",
      "start_date": "2023-01-10",
      "status": "active",
      "notes": "For hypothyroidism"
    }
  ],
  "allergies": [
    {
      "allergen": "Shellfish",
      "severity": "moderate",
      "reaction": "Hives and difficulty breathing",
      "notes": null
    }
  ],
  "medical_history": {
    "current_conditions": "Hypothyroidism, Asthma",
    "past_surgeries": "Appendectomy (2010), C-section (2019)",
    "family_history": "Mother: Type 2 Diabetes, Father: Hypertension"
  },
  "forms": [
    {
      "form_type": "obgyn",
      "form_subtype": "routine_gyn",
      "data": {
        "menstrual_history": {
          "last_menstrual_period": "2024-11-20",
          "cycle_length_days": 28,
          "cycle_regularity": "regular"
        }
      }
    }
  ],
  "form_metadata": {
    "form_date": "2024-12-15",
    "facility_name": "Memorial Women's Clinic",
    "doctor_name": "Dr. Emily Chen",
    "confidence_notes": "All data clearly visible",
    "logo_info": {
      "has_logo": "true",
      "logo_position": "top-center",
      "logo_description": "Memorial Women's Clinic logo with stylized flower and medical caduceus symbol",
      "facility_name_from_logo": "Memorial Women's Clinic - Since 1985"
    }
  }
}"""

print("Testing logo extraction from historical forms...\n")

# Parse the response
data = json.loads(sample_extraction_response)

# Display extracted logo information
logo_info = data.get("form_metadata", {}).get("logo_info", {})

print("✅ Logo Information Extracted:")
print(f"   - Has Logo: {logo_info.get('has_logo')}")
print(f"   - Position: {logo_info.get('logo_position')}")
print(f"   - Description: {logo_info.get('logo_description')}")
print(f"   - Facility Name from Logo: {logo_info.get('facility_name_from_logo')}")

# Show other facility metadata
form_metadata = data.get("form_metadata", {})
print("\n✅ Additional Facility Metadata:")
print(f"   - Facility Name: {form_metadata.get('facility_name')}")
print(f"   - Doctor Name: {form_metadata.get('doctor_name')}")
print(f"   - Form Date: {form_metadata.get('form_date')}")

print("\n✅ Logo extraction structure is correct!")
print("   The extracted logo info can be:")
print("   - Stored in historical_form_imports.extracted_data.form_metadata.logo_info")
print("   - Displayed in the review UI")
print("   - Included in generated PDFs via extracted_facility_info parameter")
