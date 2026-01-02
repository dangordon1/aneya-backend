#!/usr/bin/env python3
"""
Test the new classification-first extraction logic.

This test simulates the new 2-step process without needing authentication.
"""

import os
import json
from anthropic import Anthropic

# Sample pregnancy consultation transcript
ANTENATAL_TRANSCRIPT = """Doctor: Hello, how are you feeling today?
Patient: Hi doctor, I'm doing well. I'm here for my pregnancy checkup.
Doctor: Great! How many weeks pregnant are you?
Patient: I'm about 6 weeks pregnant now. My last period was on November 11th, 2024.
Doctor: Wonderful. Is this your first pregnancy?
Patient: Yes, this is my first pregnancy.
Doctor: Any symptoms? Nausea, vomiting?
Patient: I've been experiencing nausea every day, but no vomiting.
Doctor: Let me check your vital signs. Blood pressure is 120 over 80.
Patient: Okay.
Doctor: Heart rate is 86, and oxygen saturation is 99 percent.
Patient: That sounds good."""

def test_classification():
    """Test Step 1: LLM Classification"""
    print("=" * 80)
    print("TEST: LLM CLASSIFICATION (Step 1)")
    print("=" * 80)
    print()

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print("❌ ANTHROPIC_API_KEY not set")
        return False

    client = Anthropic(api_key=anthropic_key)

    classification_prompt = """You are a medical consultation classifier for OB/GYN doctors. Analyze the conversation and determine which type of OB/GYN consultation this is.

You MUST classify as ONE of these three types ONLY:

1. **antenatal**: Pregnancy-related care
   - Indicators: "pregnant", "weeks pregnant", "fetal", "prenatal", "pregnancy test positive", "ultrasound", "antenatal", "baby", "delivery", "due date", "trimester", "expecting", "LMP", "gestational age"

2. **infertility**: Fertility issues and reproductive challenges
   - Indicators: "trying to conceive", "can't get pregnant", "difficulty conceiving", "fertility", "IVF", "IUI", "ovulation", "infertility treatment"

3. **obgyn**: General gynecology (DEFAULT if not clearly antenatal or infertility)
   - Indicators: "irregular periods", "contraception", "menstrual", "pap smear", "pelvic exam"

CLASSIFICATION RULES:
- If conversation mentions CURRENT PREGNANCY → MUST be "antenatal"

Return JSON:
{
  "consultation_type": "antenatal|infertility|obgyn",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation"
}"""

    user_prompt = f"""Conversation:
{ANTENATAL_TRANSCRIPT}

Classify this consultation:"""

    print("📤 Calling Claude Haiku 4-5 for classification...")

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        system=classification_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )

    response_text = message.content[0].text.strip()
    print(f"📥 Response: {response_text}")
    print()

    # Parse JSON
    import re
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response_text

    result = json.loads(json_str)

    consultation_type = result.get("consultation_type")
    confidence = result.get("confidence", 0)
    reasoning = result.get("reasoning", "")

    print("📊 CLASSIFICATION RESULT:")
    print(f"   Type: {consultation_type}")
    print(f"   Confidence: {confidence:.2%}")
    print(f"   Reasoning: {reasoning}")
    print()

    # Verify correct classification
    if consultation_type == "antenatal":
        print("✅ TEST PASSED: Correctly classified as antenatal")
        print()
        return True
    else:
        print(f"❌ TEST FAILED: Should be 'antenatal', got '{consultation_type}'")
        print()
        return False


def test_extraction():
    """Test Step 2: Field Extraction for Antenatal"""
    print("=" * 80)
    print("TEST: FIELD EXTRACTION (Step 2)")
    print("=" * 80)
    print()

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print("❌ ANTHROPIC_API_KEY not set")
        return False

    client = Anthropic(api_key=anthropic_key)

    # Simplified schema hints for antenatal
    schema_hints = """
Available Fields:
- lmp (date): Last menstrual period
- gestational_age_weeks (number): Gestational age in weeks
- gravida (number): Total pregnancies
- para (number): Deliveries
- current_symptoms (text): Current pregnancy symptoms
- complaints (text): Patient complaints
- vital_signs.systolic_bp (number): Systolic blood pressure (mmHg)
- vital_signs.diastolic_bp (number): Diastolic blood pressure (mmHg)
- vital_signs.heart_rate (number): Heart rate (bpm)
- vital_signs.spo2 (number): Oxygen saturation (%)
"""

    extraction_prompt = f"""You are a medical data extraction specialist. Extract structured clinical data from this doctor-patient consultation for an ANTENATAL form.

Extract from BOTH doctor questions AND patient answers. Patient responses often contain critical medical information.

Form Type: ANTENATAL
{schema_hints}

Rules:
1. Extract ONLY information explicitly stated (no guessing)
2. Use dot notation for nested fields (e.g., "vital_signs.systolic_bp")
3. Skip fields with confidence < 0.7
4. Return JSON with field_updates and confidence_scores

Return JSON:
{{
  "field_updates": {{
    "field.path": value,
    ...
  }},
  "confidence_scores": {{
    "field.path": 0.0-1.0,
    ...
  }}
}}"""

    user_prompt = f"""Consultation transcript:

{ANTENATAL_TRANSCRIPT}

Extract all relevant clinical data for the antenatal form:"""

    print("📤 Calling Claude Haiku 4-5 for extraction...")

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=4096,
        system=extraction_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )

    response_text = message.content[0].text.strip()
    print(f"📥 Response: {response_text[:200]}...")
    print()

    # Parse JSON
    import re
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response_text

    result = json.loads(json_str)

    field_updates = result.get("field_updates", {})
    confidence_scores = result.get("confidence_scores", {})

    print("📊 EXTRACTION RESULT:")
    print(f"   Fields extracted: {len(field_updates)}")
    print()

    if field_updates:
        print("📝 Extracted fields:")
        for field, value in field_updates.items():
            conf = confidence_scores.get(field, 0)
            print(f"   - {field}: {value} (confidence: {conf:.2f})")

    print()

    # Verify key fields were extracted
    expected_fields = ["lmp", "gestational_age_weeks", "gravida", "para"]
    found_expected = [f for f in expected_fields if f in field_updates]

    # Check for invalid fields (obgyn-specific)
    invalid_fields = ["chief_complaint", "symptoms_description"]
    found_invalid = [f for f in invalid_fields if f in field_updates]

    if found_invalid:
        print(f"❌ TEST FAILED: Found invalid obgyn fields: {found_invalid}")
        print("   These should NOT be extracted for antenatal forms!")
        print()
        return False

    if len(found_expected) >= 2:
        print(f"✅ TEST PASSED: Extracted {len(found_expected)}/4 expected antenatal fields")
        print(f"   Found: {found_expected}")
        print()
        return True
    else:
        print(f"❌ TEST FAILED: Only found {len(found_expected)}/4 expected fields")
        print(f"   Found: {found_expected}")
        print()
        return False


if __name__ == "__main__":
    print()
    print("🔬 TESTING NEW CLASSIFICATION-FIRST LOGIC")
    print()

    test1_passed = test_classification()
    test2_passed = test_extraction()

    print("=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)
    print(f"Test 1 (Classification): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Test 2 (Extraction): {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    print()

    if test1_passed and test2_passed:
        print("🎉 ALL TESTS PASSED")
        print()
        print("✅ The new logic correctly:")
        print("   1. Classifies pregnancy consultations as 'antenatal'")
        print("   2. Extracts only antenatal-specific fields")
        print("   3. Avoids invalid obgyn fields (chief_complaint, etc.)")
        exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        exit(1)
