#!/usr/bin/env python3
"""
Clinical Decision Support Client Integration Tests

Tests the full clinical workflow including:
- Server connections
- Tool discovery and routing
- Diagnosis generation
- Drug lookups
- Event streaming

Usage:
    python -m pytest tests/integration/test_clinical_agent.py -v

Or run directly:
    python tests/integration/test_clinical_agent.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Add servers to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "servers"))

from clinical_decision_support.client import ClinicalDecisionSupportClient


async def test_full_clinical_workflow():
    """Test the complete clinical decision support workflow."""
    print("\n" + "="*70)
    print("🧪 CLINICAL AGENT INTEGRATION TEST")
    print("="*70)

    consultation = "30 year old pregnant woman with itching all over body"
    location = "IN"  # India

    print(f"\nConsultation: {consultation}")
    print(f"Location: {location}")

    # Track events
    events = []

    async def progress_callback(event_type: str, data: dict):
        events.append({"type": event_type, "data": data})
        if event_type == "diagnoses":
            print(f"📤 {event_type}: {len(data.get('diagnoses', []))} diagnoses")
        elif event_type == "drug_update":
            print(f"📤 {event_type}: {data.get('drug_name')} - {data.get('status')}")
        else:
            print(f"📤 {event_type}")

    # Create client and run
    client = ClinicalDecisionSupportClient()

    try:
        # Connect to servers
        print(f"\n{'─'*70}")
        print("Step 1: Connecting to servers")
        print(f"{'─'*70}")

        await client.connect_for_region(location, verbose=True)
        servers = client.get_connected_servers()
        print(f"✅ Connected to {len(servers)} servers: {', '.join(servers)}")

        # List tools
        print(f"\n{'─'*70}")
        print("Step 2: Discovering tools")
        print(f"{'─'*70}")

        tools = client.get_available_tools()
        print(f"✅ {len(tools)} tools available")

        # Run clinical analysis
        print(f"\n{'─'*70}")
        print("Step 3: Running clinical analysis")
        print(f"{'─'*70}")

        result = await client.clinical_decision_support(
            clinical_scenario=consultation,
            location_override=location,
            progress_callback=progress_callback,
            verbose=True,
            max_drugs=2  # Limit for faster testing
        )

        # Verify results
        print(f"\n{'─'*70}")
        print("Step 4: Verifying results")
        print(f"{'─'*70}")

        diagnoses = result.get('diagnoses', [])
        print(f"   Diagnoses: {len(diagnoses)}")
        for diag in diagnoses:
            print(f"   • {diag.get('diagnosis')} ({diag.get('confidence')})")

        # Check events
        event_types = [e['type'] for e in events]
        has_diagnoses = 'diagnoses' in event_types
        has_drug_updates = any(e['type'] == 'drug_update' for e in events)
        successful_drugs = [
            e for e in events
            if e['type'] == 'drug_update' and e['data'].get('status') == 'complete'
        ]

        print(f"\n   Events received: {len(events)}")
        print(f"   Event types: {' → '.join(event_types)}")
        print(f"   Diagnoses event: {'✅' if has_diagnoses else '❌'}")
        print(f"   Drug updates: {'✅' if has_drug_updates else '❌'}")
        print(f"   Successful lookups: {len(successful_drugs)}")

        # Determine pass/fail
        passed = (
            len(diagnoses) > 0 and
            has_diagnoses and
            has_drug_updates and
            len(successful_drugs) > 0
        )

        return passed, {
            'diagnoses': len(diagnoses),
            'events': len(events),
            'successful_drugs': len(successful_drugs)
        }

    finally:
        await client.cleanup()


async def test_tool_availability():
    """Test that tools are correctly available by phase."""
    print("\n" + "="*70)
    print("🧪 TOOL AVAILABILITY TEST")
    print("="*70)

    client = ClinicalDecisionSupportClient()

    try:
        await client.connect_for_region("IN", verbose=False)
        tools = client.get_available_tools()

        # Check guideline tools present
        guideline_tools = [t for t in tools if 'guideline' in t.lower() or 'fogsi' in t.lower()]
        drug_tools = [t for t in tools if 'bnf' in t.lower() or 'drug' in t.lower()]

        print(f"   Guideline tools: {len(guideline_tools)}")
        print(f"   Drug tools: {len(drug_tools)}")

        passed = len(guideline_tools) > 0 and len(drug_tools) > 0
        return passed, {'guideline_tools': len(guideline_tools), 'drug_tools': len(drug_tools)}

    finally:
        await client.cleanup()


async def test_invalid_input():
    """Test that invalid inputs are rejected."""
    print("\n" + "="*70)
    print("🧪 INPUT VALIDATION TEST")
    print("="*70)

    client = ClinicalDecisionSupportClient()

    invalid_inputs = [
        "hello how are you",
        "what is the weather today",
        "tell me a joke"
    ]

    results = []

    try:
        await client.connect_for_region("IN", verbose=False)

        for inp in invalid_inputs:
            print(f"\n   Testing: '{inp[:40]}...'")
            try:
                result = await client.clinical_decision_support(
                    clinical_scenario=inp,
                    location_override="IN",
                    verbose=False
                )
                # If we get here without error, check if it was marked invalid
                is_invalid = result.get('invalid_input', False)
                print(f"   Result: {'Rejected ✅' if is_invalid else 'Accepted ❌'}")
                results.append(is_invalid)
            except Exception as e:
                print(f"   Error (expected): {type(e).__name__}")
                results.append(True)

        passed = all(results)
        return passed, {'rejected': sum(results), 'total': len(invalid_inputs)}

    finally:
        await client.cleanup()


async def run_all_tests():
    """Run all integration tests."""
    print("\n" + "="*70)
    print("🏥 CLINICAL AGENT INTEGRATION TEST SUITE")
    print("="*70)

    all_results = {}

    # Test 1: Full workflow
    try:
        passed, details = await test_full_clinical_workflow()
        all_results['Full Workflow'] = passed
    except Exception as e:
        print(f"❌ Full workflow test failed: {e}")
        all_results['Full Workflow'] = False

    # Test 2: Tool availability
    try:
        passed, details = await test_tool_availability()
        all_results['Tool Availability'] = passed
    except Exception as e:
        print(f"❌ Tool availability test failed: {e}")
        all_results['Tool Availability'] = False

    # Summary
    print("\n" + "="*70)
    print("📊 INTEGRATION TEST SUMMARY")
    print("="*70)

    passed = sum(1 for v in all_results.values() if v)
    total = len(all_results)

    for name, result in all_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*70)

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
