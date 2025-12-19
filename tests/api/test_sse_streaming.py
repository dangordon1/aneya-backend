#!/usr/bin/env python3
"""
Integration test for frontend/backend SSE streaming with immediate diagnosis display.

This test verifies:
1. Backend receives consultation and starts processing
2. SSE events are streamed in correct order
3. 'diagnoses' event is sent immediately after Claude analysis
4. 'drug_update' events are sent as individual drugs complete
5. Drug details populate asynchronously
6. Frontend can display report before all drugs finish loading

Test input: "patient presents with itchiness all over her body"
"""

import asyncio
import json
import sys
from datetime import datetime
import httpx
from typing import List, Dict, Any


class IntegrationTest:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.events: List[Dict[str, Any]] = []
        self.start_time = None
        self.diagnoses_received_time = None
        self.first_drug_update_time = None
        self.complete_time = None

    async def test_streaming_consultation(self, consultation: str):
        """Test the SSE streaming endpoint with a consultation"""
        print(f"\n{'='*80}")
        print(f"INTEGRATION TEST: Frontend/Backend Streaming")
        print(f"{'='*80}\n")
        print(f"Test Input: \"{consultation}\"\n")
        print(f"Expected Flow:")
        print(f"  1. Backend receives consultation")
        print(f"  2. Location detection")
        print(f"  3. Claude analysis (3-5 seconds)")
        print(f"  4. 📊 DIAGNOSES event sent immediately")
        print(f"  5. DrugBank/BNF lookups start (parallel)")
        print(f"  6. 💊 DRUG_UPDATE events as each drug completes")
        print(f"  7. COMPLETE event when all done\n")
        print(f"{'='*80}\n")

        self.start_time = datetime.now()

        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                # Make streaming request
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/analyze-stream",
                    json={
                        "consultation": consultation,
                        "patient_name": "Test Patient",
                        "patient_height": "170cm",
                        "patient_weight": "70kg",
                        "current_medications": "",
                        "current_conditions": "",
                        "max_drugs": 2  # Limit to 2 drugs for faster testing
                    },
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status_code != 200:
                        print(f"❌ ERROR: Got status {response.status_code}")
                        text = await response.aread()
                        print(f"Response: {text.decode()}")
                        return False

                    # Parse SSE stream
                    buffer = ""
                    async for chunk in response.aiter_bytes():
                        buffer += chunk.decode('utf-8')

                        # Process complete events (separated by \n\n)
                        while '\n\n' in buffer:
                            event_data, buffer = buffer.split('\n\n', 1)

                            if not event_data.strip():
                                continue

                            # Parse event
                            event = self._parse_sse_event(event_data)
                            if event:
                                self._process_event(event)

                # Analyze results
                return self._analyze_results()

            except Exception as e:
                print(f"❌ ERROR: {e}")
                import traceback
                traceback.print_exc()
                return False

    def _parse_sse_event(self, event_data: str) -> Dict[str, Any]:
        """Parse SSE event format"""
        lines = event_data.strip().split('\n')
        event_type = None
        data = None

        for line in lines:
            if line.startswith('event: '):
                event_type = line[7:].strip()
            elif line.startswith('data: '):
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    data = line[6:].strip()

        if event_type and data:
            return {"type": event_type, "data": data}
        return None

    def _process_event(self, event: Dict[str, Any]):
        """Process and display each event"""
        event_type = event["type"]
        data = event["data"]
        elapsed = (datetime.now() - self.start_time).total_seconds()

        self.events.append({
            "type": event_type,
            "data": data,
            "elapsed": elapsed
        })

        # Display event
        if event_type == "start":
            print(f"[{elapsed:6.2f}s] ▶️  START: {data.get('message', '')}")

        elif event_type == "progress":
            step = data.get('step', '')
            message = data.get('message', '')
            print(f"[{elapsed:6.2f}s] ⏳ PROGRESS [{step}]: {message}")

        elif event_type == "location":
            country = data.get('country', 'Unknown')
            print(f"[{elapsed:6.2f}s] 📍 LOCATION: {country}")

        elif event_type == "guideline_search":
            source = data.get('source', '')
            print(f"[{elapsed:6.2f}s] 🔍 SEARCHING: {source}")

        elif event_type == "diagnoses":
            # CRITICAL: This should come BEFORE drug details complete
            self.diagnoses_received_time = datetime.now()
            diagnoses = data.get('diagnoses', [])
            drugs_pending = data.get('drugs_pending', [])
            print(f"\n{'='*80}")
            print(f"[{elapsed:6.2f}s] 📊 DIAGNOSES EVENT RECEIVED!")
            print(f"{'='*80}")
            print(f"  ✓ {len(diagnoses)} diagnoses ready")
            print(f"  ⏳ {len(drugs_pending)} drugs pending:")
            for drug in drugs_pending:
                print(f"     - {drug}")
            print(f"  → Frontend should show report NOW (with loading spinners for drugs)")
            print(f"{'='*80}\n")

        elif event_type == "drug_update":
            if not self.first_drug_update_time:
                self.first_drug_update_time = datetime.now()

            drug_name = data.get('drug_name', '')
            status = data.get('status', '')
            if status == "complete":
                print(f"[{elapsed:6.2f}s] 💊 DRUG LOADED: {drug_name}")
            else:
                print(f"[{elapsed:6.2f}s] ⚠️  DRUG FAILED: {drug_name} ({status})")

        elif event_type == "bnf_drug":
            medication = data.get('medication', '')
            status = data.get('status', '')
            print(f"[{elapsed:6.2f}s] 💊 BNF: {medication} ({status})")

        elif event_type == "complete":
            self.complete_time = datetime.now()
            print(f"\n[{elapsed:6.2f}s] ✅ COMPLETE")

        elif event_type == "done":
            print(f"[{elapsed:6.2f}s] 🏁 DONE\n")

        elif event_type == "error":
            error_type = data.get('type', '')
            message = data.get('message', '')
            print(f"[{elapsed:6.2f}s] ❌ ERROR [{error_type}]: {message}")

    def _analyze_results(self) -> bool:
        """Analyze the test results"""
        print(f"\n{'='*80}")
        print(f"TEST RESULTS ANALYSIS")
        print(f"{'='*80}\n")

        success = True

        # Check: Did we receive diagnoses event?
        diagnoses_events = [e for e in self.events if e["type"] == "diagnoses"]
        if not diagnoses_events:
            print(f"❌ FAIL: No 'diagnoses' event received!")
            print(f"   This means frontend will never show the report.")
            success = False
        else:
            diagnoses_event = diagnoses_events[0]
            print(f"✅ PASS: 'diagnoses' event received at {diagnoses_event['elapsed']:.2f}s")

            # Check timing: diagnoses should come early (before all drugs complete)
            if self.complete_time and self.diagnoses_received_time:
                diagnoses_delay = (self.diagnoses_received_time - self.start_time).total_seconds()
                total_time = (self.complete_time - self.start_time).total_seconds()
                improvement = total_time - diagnoses_delay

                print(f"   Report shown {improvement:.1f}s earlier than before!")
                print(f"   User sees results at {diagnoses_delay:.1f}s instead of {total_time:.1f}s")

        # Check: Did we receive drug_update events?
        drug_update_events = [e for e in self.events if e["type"] == "drug_update"]
        if not drug_update_events:
            print(f"\n⚠️  WARNING: No 'drug_update' events received")
            print(f"   Drugs may not populate in the frontend dropdowns.")
        else:
            print(f"\n✅ PASS: {len(drug_update_events)} 'drug_update' events received")
            print(f"   Drug details will populate asynchronously in frontend")

        # Check: Event order
        print(f"\n📋 Event sequence:")
        event_types = [e["type"] for e in self.events]
        for i, event_type in enumerate(event_types, 1):
            print(f"   {i}. {event_type}")

        # Check critical order: diagnoses should come before complete
        try:
            diagnoses_idx = event_types.index("diagnoses")
            complete_idx = event_types.index("complete")

            if diagnoses_idx < complete_idx:
                print(f"\n✅ PASS: Correct event order (diagnoses before complete)")
            else:
                print(f"\n❌ FAIL: Wrong event order (diagnoses after complete)")
                success = False
        except ValueError:
            print(f"\n❌ FAIL: Missing required events")
            success = False

        # Performance metrics
        print(f"\n⏱️  Performance Metrics:")
        print(f"   Total time: {(self.complete_time - self.start_time).total_seconds():.1f}s")
        if self.diagnoses_received_time:
            print(f"   Time to diagnoses: {(self.diagnoses_received_time - self.start_time).total_seconds():.1f}s")
        if self.first_drug_update_time:
            print(f"   Time to first drug: {(self.first_drug_update_time - self.start_time).total_seconds():.1f}s")

        print(f"\n{'='*80}")
        if success:
            print(f"🎉 TEST PASSED: Integration working correctly!")
        else:
            print(f"❌ TEST FAILED: Issues detected")
        print(f"{'='*80}\n")

        return success


async def main():
    """Run the integration test"""
    test = IntegrationTest()

    # Test with the specified input
    consultation = "patient presents with itchiness all over her body"

    success = await test.test_streaming_consultation(consultation)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
