#!/usr/bin/env python3
"""Test the consultation type classification endpoint with a sample antenatal conversation."""

import requests
import json

# Reconstruct the conversation from the logs
# This is clearly an antenatal (pregnancy) consultation
diarized_segments = [
    {
        "speaker": "Patient",
        "text": "Hi, doctor. I'm here for my checkup.",
        "timestamp": "00:00:05"
    },
    {
        "speaker": "Doctor",
        "text": "Hello! How are you feeling today?",
        "timestamp": "00:00:08"
    },
    {
        "speaker": "Patient",
        "text": "Pregnant, been nine weeks pregnant and my first trimester. And I'm having a lot of headache and fever.",
        "timestamp": "00:00:15"
    },
    {
        "speaker": "Doctor",
        "text": "Well, congratulations on the pregnancy. The fever is slightly concerning. Let me ask you a few questions.",
        "timestamp": "00:00:22"
    },
    {
        "speaker": "Patient",
        "text": "Okay.",
        "timestamp": "00:00:26"
    },
    {
        "speaker": "Doctor",
        "text": "Have you had any nausea or vomiting?",
        "timestamp": "00:00:28"
    },
    {
        "speaker": "Patient",
        "text": "Yes, quite a bit in the mornings.",
        "timestamp": "00:00:32"
    },
    {
        "speaker": "Doctor",
        "text": "That's a common symptom of morning sickness, especially in the first trimester. Now, about the fever - when did it start?",
        "timestamp": "00:00:38"
    },
    {
        "speaker": "Patient",
        "text": "About two days ago.",
        "timestamp": "00:00:42"
    },
    {
        "speaker": "Doctor",
        "text": "Okay. Let me check your vitals. Your heart rate is 62 beats per minute. Fetal heart rate is 184 beats per minute, which is good. Your temperature is 38.2, so slightly high.",
        "timestamp": "00:00:55"
    },
    {
        "speaker": "Patient",
        "text": "Is the baby okay?",
        "timestamp": "00:01:00"
    },
    {
        "speaker": "Doctor",
        "text": "The fetal heart rate looks good. We'll monitor the fever though. Have you had any prior pregnancies?",
        "timestamp": "00:01:05"
    },
    {
        "speaker": "Patient",
        "text": "No, this is my first pregnancy.",
        "timestamp": "00:01:10"
    },
    {
        "speaker": "Doctor",
        "text": "Alright. We'll do some blood work to check for infection. I'll also prescribe something safe for the fever during pregnancy.",
        "timestamp": "00:01:18"
    }
]

# Build the request payload
payload = {
    "diarized_segments": diarized_segments,
    "doctor_specialty": "obgyn",
    "patient_context": {
        "patient_name": "Test Patient",
        "patient_age": 28,
        "gender": "female"
    }
}

# Make the request to the local backend
url = "http://localhost:8000/api/determine-consultation-type"

print("="*80)
print("TESTING CONSULTATION TYPE CLASSIFICATION")
print("="*80)
print("\nConversation Summary:")
print("- Patient mentions: 'nine weeks pregnant', 'first trimester'")
print("- Doctor says: 'congratulations on the pregnancy'")
print("- Doctor measures: 'fetal heart rate is 184 beats per minute'")
print("- Patient asks: 'Is the baby okay?'")
print("- Doctor asks: 'Have you had any prior pregnancies?'")
print("\nEXPECTED CLASSIFICATION: antenatal (confidence > 0.9)")
print("="*80 + "\n")

print(f"Sending POST request to: {url}\n")

try:
    response = requests.post(url, json=payload, timeout=30)

    print(f"Status Code: {response.status_code}\n")

    if response.status_code == 200:
        result = response.json()
        print("✅ RESPONSE:")
        print(json.dumps(result, indent=2))

        print("\n" + "="*80)
        print("ANALYSIS:")
        print("="*80)

        consultation_type = result.get('consultation_type')
        confidence = result.get('confidence', 0)
        reasoning = result.get('reasoning', '')

        print(f"Type: {consultation_type}")
        print(f"Confidence: {confidence}")
        print(f"Reasoning: {reasoning}")

        # Validate the result
        if consultation_type == 'antenatal':
            if confidence > 0.85:
                print("\n✅ CORRECT: Classified as antenatal with high confidence")
            else:
                print(f"\n⚠️  WARNING: Classified as antenatal but confidence is low ({confidence})")
        else:
            print(f"\n❌ ERROR: Should be 'antenatal' but got '{consultation_type}'")
            print("This conversation clearly mentions:")
            print("  - Current pregnancy (9 weeks)")
            print("  - First trimester")
            print("  - Fetal heart rate measurement")
            print("  - Pregnancy-related questions")
    else:
        print(f"❌ ERROR: Request failed with status {response.status_code}")
        print(f"Response: {response.text}")

except requests.exceptions.ConnectionError:
    print("❌ ERROR: Could not connect to backend at http://localhost:8000")
    print("Make sure the backend is running with: python -m uvicorn api:app --reload")
except Exception as e:
    print(f"❌ ERROR: {type(e).__name__}: {e}")

print("\n" + "="*80)
print("Check the backend console for the raw LLM response")
print("="*80 + "\n")
