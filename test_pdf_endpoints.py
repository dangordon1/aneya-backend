"""
Quick script to find test appointment and consultation IDs for PDF testing
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

if not supabase_url or not supabase_key:
    print("❌ Missing Supabase credentials")
    exit(1)

supabase = create_client(supabase_url, supabase_key)

print("🔍 Finding test data for PDF generation...")
print()

# Find an appointment with a consultation form
print("1️⃣  Looking for appointments with consultation forms...")
appointments = supabase.table("appointments")\
    .select("id, scheduled_time, patient:patients(name), consultation_forms(id, form_type)")\
    .not_.is_("consultation_forms", "null")\
    .limit(5)\
    .execute()

if appointments.data:
    print(f"   ✅ Found {len(appointments.data)} appointments with consultation forms:")
    for apt in appointments.data:
        patient_name = apt.get('patient', {}).get('name', 'Unknown')
        form_type = apt.get('consultation_forms', [{}])[0].get('form_type', 'unknown') if apt.get('consultation_forms') else 'none'
        print(f"      • Appointment ID: {apt['id'][:8]}... ({patient_name}, {form_type})")

    # Get the first one for testing
    test_appointment_id = appointments.data[0]['id']
    print()
    print(f"📄 Test consultation form PDF:")
    print(f"   curl -o test_consultation.pdf http://localhost:8000/api/appointments/{test_appointment_id}/consultation-pdf")
    print(f"   open test_consultation.pdf")
else:
    print("   ❌ No appointments with consultation forms found")

print()

# Find a consultation with diagnoses (simpler query)
print("2️⃣  Looking for consultations with diagnoses...")
consultations = supabase.table("consultations")\
    .select("id, created_at, appointment_id, diagnoses")\
    .not_.is_("appointment_id", "null")\
    .not_.is_("diagnoses", "null")\
    .limit(10)\
    .execute()

if consultations.data:
    print(f"   ✅ Found {len(consultations.data)} consultations with appointments and diagnoses:")
    # Filter to find one with actual diagnosis content
    valid_consultations = [c for c in consultations.data if c.get('diagnoses') and len(c['diagnoses']) > 0]

    for cons in valid_consultations[:5]:
        num_diagnoses = len(cons.get('diagnoses', []))
        print(f"      • Consultation ID: {cons['id'][:8]}... ({num_diagnoses} diagnoses)")

    if valid_consultations:
        # Get the first one with real diagnoses
        test_consultation_id = valid_consultations[0]['id']
    else:
        test_consultation_id = consultations.data[0]['id'] if consultations.data else None
    print()
    print(f"📊 Test analysis report PDF:")
    print(f"   curl -o test_analysis.pdf http://localhost:8000/api/consultations/{test_consultation_id}/analysis-pdf")
    print(f"   open test_analysis.pdf")
else:
    print("   ❌ No consultations with diagnoses found")

print()
print("=" * 60)
print("Ready to test! Copy and run the curl commands above.")
print("=" * 60)
