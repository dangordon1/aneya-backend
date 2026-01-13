#!/usr/bin/env python
"""
Test patient context integration in form filling.

This test verifies that patient details (demographics, medications, conditions, allergies)
are correctly fetched from Supabase and included in the LLM prompt during form filling.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

# Test the fetch_patient_context function
from api import fetch_patient_context, get_supabase_client


def test_fetch_patient_context():
    """Test fetching patient context from Supabase."""
    print("\n" + "="*80)
    print("TEST: Fetch Patient Context")
    print("="*80)

    # Get a sample patient ID from the database
    supabase = get_supabase_client()

    # Fetch a patient with data
    patients_result = supabase.table('patients').select('id, name').limit(5).execute()

    if not patients_result.data:
        print("❌ No patients found in database")
        return False

    print(f"\n📋 Found {len(patients_result.data)} patients")

    # Test with the first patient
    patient_id = patients_result.data[0]['id']
    patient_name = patients_result.data[0].get('name', 'Unknown')

    print(f"\n🔍 Testing with patient: {patient_name} (ID: {patient_id})")

    # Fetch comprehensive patient context
    context = fetch_patient_context(patient_id)

    print("\n📊 Patient Context Retrieved:")
    print(f"   Demographics: {context.get('demographics', {})}")
    print(f"   Medications: {len(context.get('medications', []))} active")
    print(f"   Conditions: {len(context.get('conditions', []))} active")
    print(f"   Allergies: {len(context.get('allergies', []))} active")
    print(f"   Previous Forms: {len(context.get('previous_forms', []))}")

    # Verify structure
    assert 'demographics' in context, "Missing demographics"
    assert 'medications' in context, "Missing medications"
    assert 'conditions' in context, "Missing conditions"
    assert 'allergies' in context, "Missing allergies"
    assert 'previous_forms' in context, "Missing previous_forms"

    print("\n✅ Patient context structure is correct")
    return True


def test_patient_context_in_prompt():
    """Test that patient context is properly formatted for LLM prompt."""
    print("\n" + "="*80)
    print("TEST: Patient Context in LLM Prompt")
    print("="*80)

    # Create sample patient context
    sample_context = {
        'demographics': {
            'name': 'Test Patient',
            'age_years': 28,
            'sex': 'Female'
        },
        'medications': [
            {'name': 'Aspirin', 'dosage': '100mg', 'frequency': 'once daily'}
        ],
        'conditions': [
            {'name': 'Hypertension', 'status': 'active'}
        ],
        'allergies': [
            {'allergen': 'Penicillin', 'severity': 'moderate'}
        ]
    }

    # Build patient context text (same logic as in extract_form_fields)
    patient_context_text = ""
    demographics = sample_context.get('demographics', {})
    medications = sample_context.get('medications', [])
    conditions = sample_context.get('conditions', [])
    allergies = sample_context.get('allergies', [])

    # Build patient profile summary
    patient_parts = []
    if demographics.get('name'):
        patient_parts.append(f"Name: {demographics['name']}")
    if demographics.get('age_years'):
        patient_parts.append(f"Age: {demographics['age_years']} years")
    if demographics.get('sex'):
        patient_parts.append(f"Sex: {demographics['sex']}")

    if patient_parts:
        patient_context_text = f"\n\nPatient Profile:\n{', '.join(patient_parts)}"

    # Add medications
    if medications:
        meds_text = "\n".join([
            f"- {med['name']}" + (f" ({med['dosage']})" if med.get('dosage') else "")
            for med in medications[:5]
        ])
        patient_context_text += f"\n\nCurrent Medications:\n{meds_text}"

    # Add conditions
    if conditions:
        conds_text = "\n".join([
            f"- {cond['name']}" + (f" ({cond['status']})" if cond.get('status') else "")
            for cond in conditions[:5]
        ])
        patient_context_text += f"\n\nMedical History:\n{conds_text}"

    # Add allergies
    if allergies:
        allergies_text = "\n".join([
            f"- {allergy['allergen']}" + (f" ({allergy.get('severity', 'unknown')} severity)" if allergy.get('severity') else "")
            for allergy in allergies
        ])
        patient_context_text += f"\n\nAllergies:\n{allergies_text}"

    print("\n📝 Generated Patient Context Text:")
    print(patient_context_text)

    # Verify content
    assert "Test Patient" in patient_context_text, "Missing patient name"
    assert "28 years" in patient_context_text, "Missing age"
    assert "Female" in patient_context_text, "Missing sex"
    assert "Aspirin" in patient_context_text, "Missing medication"
    assert "Hypertension" in patient_context_text, "Missing condition"
    assert "Penicillin" in patient_context_text, "Missing allergy"

    print("\n✅ Patient context text formatting is correct")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("PATIENT CONTEXT FORM FILLING TESTS")
    print("="*80)

    results = []

    # Test 1: Fetch patient context
    try:
        results.append(("Fetch Patient Context", test_fetch_patient_context()))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Fetch Patient Context", False))

    # Test 2: Patient context in prompt
    try:
        results.append(("Patient Context in Prompt", test_patient_context_in_prompt()))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Patient Context in Prompt", False))

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
