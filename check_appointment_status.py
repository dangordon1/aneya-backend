import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(supabase_url, supabase_key)

# Get recent appointments with consultations that have forms
result = supabase.table("appointments")\
    .select("id, patient_id, appointment_type, status, scheduled_time")\
    .order("scheduled_time", desc=True)\
    .limit(10)\
    .execute()

print("Recent Appointments:")
print("=" * 100)
for appt in result.data:
    # Check if there's a consultation
    consult = supabase.table("consultations")\
        .select("id")\
        .eq("appointment_id", appt['id'])\
        .execute()

    # Check if there's a form
    form = None
    if appt['appointment_type']:
        if 'antenatal' in appt['appointment_type']:
            form = supabase.table("antenatal_forms")\
                .select("id")\
                .eq("appointment_id", appt['id'])\
                .execute()
        elif 'obgyn' in appt['appointment_type']:
            form = supabase.table("obgyn_consultation_forms")\
                .select("id")\
                .eq("appointment_id", appt['id'])\
                .execute()

    has_consult = len(consult.data) > 0 if consult.data else False
    has_form = len(form.data) > 0 if form and form.data else False

    print(f"ID: {appt['id'][:8]}...")
    print(f"  Type: {appt['appointment_type']}")
    print(f"  Status: {appt['status']}")
    print(f"  Has Consultation: {has_consult}")
    print(f"  Has Form: {has_form}")
    print()
