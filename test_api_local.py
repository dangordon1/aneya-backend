#!/usr/bin/env python
"""Quick test of the streamlined API locally."""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'servers'))
from clinical_decision_support_client import ClinicalDecisionSupportClient

async def test():
    client = ClinicalDecisionSupportClient()
    await client.connect_to_servers(verbose=True)

    result = await client.clinical_decision_support(
        'prescribe amoxicillin 500mg for bacterial throat infection',
        verbose=True
    )

    print('\n✅ SUCCESS! Keys:', list(result.keys()))
    print(f"Diagnoses: {len(result.get('diagnoses', []))}")

    await client.cleanup()

asyncio.run(test())
