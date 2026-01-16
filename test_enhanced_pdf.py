"""
Test script for enhanced PDF generation with professional tables and logo extraction
"""

from pdf_generator import generate_consultation_pdf
from datetime import datetime

# Test data
appointment = {
    "scheduled_time": datetime.now().isoformat(),
    "duration_minutes": 30,
    "specialty": "OB/GYN",
    "status": "completed",
    "reason": "Routine antenatal checkup",
    "notes": "Patient doing well, no complications"
}

patient = {
    "name": "Jane Doe",
    "date_of_birth": "1990-05-15",
    "sex": "Female",
    "height_cm": 165,
    "weight_kg": 68,
    "allergies": "Penicillin",
    "current_medications": "Prenatal vitamins, Folic acid",
    "current_conditions": "Pregnancy (24 weeks)"
}

# Test form data with nested structures
form_data = {
    "vital_signs": {
        "blood_pressure_systolic": 120,
        "blood_pressure_diastolic": 80,
        "heart_rate": 72,
        "temperature_celsius": 37.0,
        "weight_kg": 68
    },
    "obstetric_history": {
        "gravida": 2,
        "para": 1,
        "gestational_age_weeks": 24,
        "lmp": "2024-08-01",
        "edd": "2025-05-08"
    },
    "diagnoses": [
        {
            "condition": "Intrauterine pregnancy",
            "icd_code": "Z34.0",
            "status": "active"
        },
        {
            "condition": "Previous cesarean delivery",
            "icd_code": "O34.21",
            "status": "history"
        }
    ],
    "medications_prescribed": [
        {
            "medication": "Folic acid",
            "dosage": "400 mcg",
            "frequency": "Once daily",
            "duration": "Throughout pregnancy"
        },
        {
            "medication": "Iron supplement",
            "dosage": "65 mg",
            "frequency": "Twice daily",
            "duration": "As needed"
        }
    ],
    "assessment": "Normal antenatal visit. Fetal heart rate normal. No complications.",
    "plan": "Continue current medications. Follow up in 4 weeks. Schedule glucose tolerance test."
}

# Test doctor info
doctor_info = {
    "clinic_name": "Aneya Women's Health Clinic"
}

# Test extracted facility info (from historical form)
extracted_facility_info = {
    "facility_name": "City General Hospital",
    "facility_name_from_logo": "City General Hospital - Women's Center",
    "logo_description": "Hospital logo with medical cross symbol",
    "logo_position": "top-center",
    "has_logo": True
}

# Generate PDF
print("Generating enhanced PDF with professional tables...")
pdf_buffer = generate_consultation_pdf(
    appointment=appointment,
    patient=patient,
    form_data=form_data,
    form_type="antenatal",
    doctor_info=doctor_info,
    extracted_facility_info=extracted_facility_info
)

# Save to file
output_path = "test_enhanced_consultation_report.pdf"
with open(output_path, "wb") as f:
    f.write(pdf_buffer.read())

print(f"✅ Enhanced PDF generated successfully: {output_path}")
print("   - Professional tables with borders")
print("   - Extracted facility information displayed")
print("   - Clinical styling applied")
