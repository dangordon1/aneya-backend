#!/usr/bin/env python3
"""
Test full clinical decision support with a simple consultation.
"""
import asyncio
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent / "servers"))

from clinical_decision_support.client import ClinicalDecisionSupportClient

events = []

async def progress_callback(event_type: str, data: dict):
    events.append({'type': event_type, 'data': data})
    if event_type == "diagnoses":
        print(f"📤 {event_type}: {len(data.get('diagnoses', []))} diagnoses")
    elif event_type == "drug_update":
        print(f"📤 {event_type}: {data.get('drug_name')} - {data.get('status')}")
    elif event_type == "drug_info":
        print(f"📤 {event_type}: {data.get('medication')} - {data.get('status')}")
    else:
        print(f"📤 {event_type}: {data.get('message', '')}")

async def test_full_clinical_agent():
    print("\n" + "="*70)
    print("🧪 TEST 4: Full Clinical Agent")
    print("="*70 + "\n")

    consultation = "30 year old pregnant woman with itching all over body"
    print(f"Consultation: {consultation}")
    print(f"Location: India (IN)\n")

    client = ClinicalDecisionSupportClient()
    await client.connect_to_servers(country_code="IN", verbose=True)

    print("\n🤖 Running clinical_decision_support (this takes 10-30s)...\n")

    result = await client.clinical_decision_support(
        clinical_scenario=consultation,
        location_override="IN",
        verbose=True,
        progress_callback=progress_callback,
        max_drugs=2  # Limit for faster testing
    )

    await client.cleanup()

    # Analyze results
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70 + "\n")

    if result.get('error'):
        print(f"❌ Error: {result.get('error_message')}")
        return False

    diagnoses = result.get('diagnoses', [])
    print(f"✓ Diagnoses: {len(diagnoses)}")
    for diag in diagnoses:
        print(f"   • {diag.get('diagnosis')} ({diag.get('confidence')})")

    # Drug info is now streamed via events, not stored in result
    drug_events = [e for e in events if e['type'] == 'drug_update']
    print(f"\n✓ Drug updates streamed: {len(drug_events)}")
    for drug_event in drug_events:
        data = drug_event['data']
        status = data.get('status', 'unknown')
        drug_name = data.get('drug_name', 'Unknown')
        print(f"   • {drug_name}: {status}")
        if status == 'complete' and 'details' in data:
            details = data['details']
            url = details.get('url', 'N/A')
            has_bnf = details.get('bnf_data') is not None
            print(f"     URL: {url}")
            print(f"     Has data: {has_bnf}")

    print(f"\n✓ Events: {len(events)}")
    event_types = [e['type'] for e in events]
    print(f"   Sequence: {' → '.join(event_types)}")

    with open("test_full_clinical_output.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n✓ Output saved: test_full_clinical_output.json")

    # Verify critical requirements
    has_diagnoses = len(diagnoses) > 0
    has_diagnoses_event = 'diagnoses' in event_types
    has_drug_updates = any(e['type'] == 'drug_update' for e in events)

    # Check for successful drug updates from events (new streaming design)
    # bnf_prescribing_guidance is now always empty as drug info is streamed via events
    successful_drug_updates = [
        e for e in events
        if e['type'] == 'drug_update' and e['data'].get('status') == 'complete'
    ]
    has_successful_drug_lookups = len(successful_drug_updates) > 0

    print(f"\nVerification:")
    print(f"  ✓ Has diagnoses: {has_diagnoses}")
    print(f"  ✓ Diagnoses event sent: {has_diagnoses_event}")
    print(f"  ✓ Drug updates sent: {has_drug_updates}")
    print(f"  ✓ Successful drug lookups: {has_successful_drug_lookups} ({len(successful_drug_updates)} drugs)")

    success = has_diagnoses and has_diagnoses_event and has_drug_updates and has_successful_drug_lookups

    print("\n" + "="*70)
    if success:
        print("✅ TEST PASSED")
    else:
        print("❌ TEST FAILED")
    print("="*70 + "\n")

    return success

if __name__ == "__main__":
    result = asyncio.run(test_full_clinical_agent())
    sys.exit(0 if result else 1)
