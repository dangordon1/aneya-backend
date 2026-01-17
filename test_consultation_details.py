"""
Check consultation details to debug PDF generation
"""
import os
from dotenv import load_dotenv
from supabase import create_client
import json

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

# Try to fetch the consultation the same way the API does
consultation_id = "eeaa3ccb-bc70-4a09-9ad4-e98cded8a9c3"

print(f"🔍 Checking consultation: {consultation_id}")
print()

result = supabase.table("consultations")\
    .select("*, appointment:appointments(*, patient:patients(*), doctor:doctors(*))")\
    .eq("id", consultation_id)\
    .execute()

if result.data:
    print("✅ Consultation found!")
    print()
    consultation = result.data[0]

    print(f"ID: {consultation['id']}")
    print(f"Created: {consultation.get('created_at')}")
    print(f"Has appointment: {consultation.get('appointment') is not None}")

    if consultation.get('appointment'):
        apt = consultation['appointment']
        print(f"  Appointment ID: {apt.get('id')}")
        print(f"  Has patient: {apt.get('patient') is not None}")
        print(f"  Has doctor: {apt.get('doctor') is not None}")

        if apt.get('patient'):
            print(f"    Patient: {apt['patient'].get('name')}")

        if apt.get('doctor'):
            doctor = apt['doctor']
            print(f"    Doctor: {doctor.get('name')}")
            print(f"    Has clinic: {doctor.get('clinic') is not None}")

    print()
    print(f"Diagnoses: {len(consultation.get('diagnoses', []))}")
    print(f"Guidelines: {len(consultation.get('guidelines_found', []))}")

    if consultation.get('diagnoses'):
        print()
        print("Sample diagnosis structure:")
        print(json.dumps(consultation['diagnoses'][0], indent=2))
else:
    print("❌ Consultation not found in database!")
    print("   This is the same error the API would see")
