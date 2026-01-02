#!/bin/bash
# Test the /api/auto-fill-consultation-form endpoint
# Requires: FIREBASE_ID_TOKEN environment variable

if [ -z "$FIREBASE_ID_TOKEN" ]; then
    echo "❌ FIREBASE_ID_TOKEN not set"
    echo ""
    echo "To get a token:"
    echo "1. Login at https://aneya.vercel.app"
    echo "2. Open DevTools → Application → IndexedDB → firebaseLocalStorage"
    echo "3. Copy stsTokenManager.accessToken"
    echo "4. Run: export FIREBASE_ID_TOKEN='your-token-here'"
    echo ""
    exit 1
fi

echo "Testing /api/auto-fill-consultation-form..."
echo ""

curl -X POST http://localhost:8000/api/auto-fill-consultation-form \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FIREBASE_ID_TOKEN" \
  -d '{
    "consultation_id": "test-'$(uuidgen)'",
    "appointment_id": "test-'$(uuidgen)'",
    "patient_id": "test-'$(uuidgen)'",
    "original_transcript": "[0.0s] Doctor: Hello, how are you feeling?\n[3.5s] Patient: Hi doctor, I am here for my pregnancy checkup.\n[8.2s] Doctor: How many weeks pregnant are you?\n[10.5s] Patient: I am about 6 weeks pregnant. My last period was on November 11th, 2024.\n[14.0s] Doctor: Is this your first pregnancy?\n[16.5s] Patient: Yes, this is my first pregnancy.\n[20.0s] Doctor: Any symptoms?\n[22.5s] Patient: I have been experiencing nausea every day.\n[28.0s] Doctor: Let me check your vitals. Blood pressure is 120 over 80.\n[32.0s] Patient: Okay.\n[34.0s] Doctor: Heart rate is 86, oxygen saturation is 99 percent.",
    "consultation_text": "Patient for 6-week antenatal checkup. First pregnancy. LMP: 2024-11-11. Vital signs stable.",
    "patient_snapshot": {
      "name": "Test Patient",
      "age": 28
    }
  }' | python -m json.tool

echo ""
echo "Check the logs for:"
echo "1. 🔍 Step 1: Classifying consultation type..."
echo "2. 📊 Detected consultation type: antenatal"
echo "3. 🔍 Step 2: Extracting fields for antenatal form..."
echo "4. NO 'chief_complaint' or 'symptoms_description' in valid fields"
