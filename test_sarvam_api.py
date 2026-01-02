#!/usr/bin/env python3
"""
Quick test script to verify Sarvam API key and connectivity
"""

import os
from sarvamai import SarvamAI

def test_sarvam_api():
    """Test basic Sarvam API connectivity"""

    api_key = os.getenv("SARVAM_API_KEY", "sk_nfdrtz9s_OqBLtL9y3M4lyLYwu9ToPrjY")

    print(f"🔑 Testing Sarvam API key: {api_key[:15]}...")
    print(f"🌐 Attempting to connect to Sarvam API...")

    try:
        # Initialize client
        client = SarvamAI(api_subscription_key=api_key)
        print("✅ Client initialized successfully")

        # Try to create a simple job (without uploading)
        print("\n📋 Testing job creation...")
        job = client.speech_to_text_translate_job.create_job(
            model="saaras:v2.5",
            with_diarization=True,
            num_speakers=2
        )

        print(f"✅ Job created successfully!")
        print(f"   Job ID: {job.job_id}")
        print(f"   Status: {job.status if hasattr(job, 'status') else 'Unknown'}")

        # Cancel the job since we're just testing
        try:
            job.cancel()
            print("✅ Test job cancelled")
        except:
            pass

        print("\n✅ SARVAM API KEY IS VALID AND WORKING")
        return True

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n❌ SARVAM API KEY OR CONNECTION FAILED")
        return False

if __name__ == "__main__":
    test_sarvam_api()
