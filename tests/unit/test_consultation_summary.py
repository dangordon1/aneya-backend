#!/usr/bin/env python
"""
Test Consultation Summary System

This test validates the ConsultationSummary class with a diarized pregnancy consultation.
Tests speaker identification, timeline extraction, and comprehensive clinical summary generation.
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add servers directory to path
sys.path.insert(0, str(Path(__file__).parent / 'servers'))
from clinical_decision_support import ConsultationSummary


# Diarized consultation transcript - 6 weeks pregnant patient with flu symptoms
CONSULTATION_TRANSCRIPT = """1. [2.00s - 4.56s] speaker_0:
     Okay.   Uh,   come.   Uh,   what's   your   name?

  2. [4.56s - 7.20s] speaker_1:
     My   name   is,   uh,   Selene   Donimath.

  3. [7.20s - 9.70s] speaker_0:
     Okay.   Uh,   from   which   place?

  4. [9.70s - 12.50s] speaker_1:
     Uh,   I'm   from   ...   I'm   living   in   London.

  5. [12.50s - 12.60s] speaker_0:
     Okay.

  6. [12.60s - 14.48s] speaker_1:
     But,   um,   I'm   in   Bangalore   for   two   months.

  7. [14.48s - 17.98s] speaker_0:
     Two   months?   Okay.   Okay.   Any   problem?   What's   your   problem?

  8. [17.98s - 25.90s] speaker_1:
     So,   um,   I'm   six   weeks   pregnant,   but   I've   been   getting   flu,   uh,   lots   of   coughs,   lots   of   cold.

  9. [25.90s - 26.26s] speaker_0:
     Mm-hmm.

  10. [26.26s - 39.40s] speaker_1:
     Um,   I'm   coughing   so   much   I   can't   sleep   all   night.   Uh,   I've   had   fever,   vomiting,   um,   s-   very   sore
  throat,   runny   nose-

  11. [39.40s - 39.68s] speaker_0:
     Okay.   Okay.

  12. [39.68s - 45.02s] speaker_1:
     ...   uh,   since,   uh,   Wednesday   and   it's   now   Sunday,   so   five   days.

  13. [45.02s - 47.66s] speaker_0:
     Okay.   Since   five   days,   you   have   all   these   symptoms?   Okay.

  14. [47.66s - 52.46s] speaker_1:
     Uh,   look,   fever   was   only,   uh,   two   or   three   days,   but   now   it's   stopped.

  15. [52.46s - 56.24s] speaker_0:
     Okay,   so   first   it   started   as   fever.   And   did   you   have   chills?

  16. [56.24s - 56.90s] speaker_1:
     Yes.

  17. [56.90s - 57.51s] speaker_0:
     You   had   chills?

  18. [57.51s - 57.52s] speaker_1:
     Yes.

  19. [57.52s - 63.90s] speaker_0:
     Fever   with   chills?   Okay.   And   w-   would   it   be   the   whole   day   or   only   in   the   evening   or   morning?

  20. [63.90s - 72.06s] speaker_1:
     Uh,   initially,   it   was   only   in   some   parts   of   the   day,   but   w-   uh,   at   the   worst   time,   it   was,   uh,
  most   of   the   day.

  21. [72.06s - 76.28s] speaker_0:
     Okay.   Uh,   did   you   have   cold?   Uh,   running   nose?

  22. [76.28s - 77.10s] speaker_1:
     Yes,   running   nose.

  23. [77.10s - 80.88s] speaker_0:
     Running   nose?   Okay.   And   difficulty   in   swallowing,   talking?

  24. [80.88s - 85.01s] speaker_1:
     Uh,   difficulty   in   ...   P-   painful   swallowing.

  25. [85.01s - 85.10s] speaker_0:
     Okay.

  26. [85.10s - 87.20s] speaker_1:
     Um,   painful   to   talk   as   well.

  27. [87.20s - 92.04s] speaker_0:
     Okay.   Okay.   So   have   you   taken   anything   for   that?

  28. [92.04s - 93.78s] speaker_1:
     Um,   only   paracetamol.

  29. [93.78s - 97.10s] speaker_0:
     Only   paracetamol?   Okay.   How   much   was   the   dosage?

  30. [97.10s - 103.66s] speaker_1:
     Uh,   o-   one   gram   in   the   morning,   one   gram   in   the   afternoon.

  31. [103.66s - 107.50s] speaker_0:
     Okay.   Okay.   Hmm.   So   you're   six   weeks   pregnant?

  32. [107.50s - 107.96s] speaker_1:
     Yes.

  33. [107.96s - 115.36s] speaker_0:
     Six   weeks.   Oh,   it's   very   early   pregnancy.   Yes.   Have   you   got   any   blood   investigation,   ultrasound,   anywhere
  else?

  34. [115.36s - 115.56s] speaker_1:
     No.

  35. [115.56s - 117.18s] speaker_0:
     Consulted   anybody?

  36. [117.18s - 120.80s] speaker_1:
     Um,   yes,   I've   had   ultrasound   scan-

  37. [120.80s - 121.11s] speaker_0:
     Uh-huh.

  38. [121.11s - 122.62s] speaker_1:
     ...   um,   of   baby.

  39. [122.62s - 123.76s] speaker_0:
     Okay.   Okay.

  40. [123.76s - 124.30s] speaker_1:
     Um.

  41. [124.30s - 128.76s] speaker_0:
     Okay.   It's   okay.   Then   show   me   all   the   reports.

  42. [128.76s - 142.02s] speaker_1:
     Okay.   Here's   the   ultrasound.   (chair rolling)   One   minute.   I   have   to   find   it   on   my   phone.

  43. [142.02s - 155.34s] speaker_0:
     Okay.   Sure.

  44. [155.34s - 156.42s] speaker_1:
     It   is.

  45. [156.42s - 164.76s] speaker_0:
     Okay.   Yeah.   Okay.   Scan   report   looks   normal.   Okay.   Did   you   have   blood   test?

  46. [164.76s - 167.26s] speaker_1:
     Uh,   not   yet.

  47. [167.26s - 179.54s] speaker_0:
     Not   yet?   Okay.   Then   we'll   get   some   blood   tests   to   run   for   you.   Okay.   Then,   uh,   I   will   just
  examine   you   and   then   see   what   is   the   problem   and   then   we'll   go   ahead.   Okay.   Just   sleep,   huh?   Okay.

  48. [179.54s - 179.74s] speaker_1:
     Okay.

  49. [179.74s - 182.97s] speaker_0:
     Fine   now.   Okay.

  50. [182.97s - 183.00s] speaker_1:
     Yeah.

  51. [183.00s - 212.08s] speaker_0:
     Now,   I   examined   you.   I   d-   uh,   actually,   overall,   you   look   normal.   Like,   otherwise,   your   hemoglobin   and
  all   looks   normal   ............................   But,   um,   uh,   you   need   to   get   blood   test   as   a   pregnance-
  part   of   pregnancy   this   thing.   So   I'll   write   some   blood   investigation,   you   get   it   done.   And   for   your
  fever   also,   it   will   help,   like   y-   you   know?   The   blood   test   will   note   what   kind   of   fever,   which
  infection,   you   know?   So   I   want   you   to   get   some   blood   test   and   after   that   I'll   write   some   medicines
  for   you.

  52. [212.08s - 213.11s] speaker_1:
     Okay.

  53. [213.11s - 213.22s] speaker_0:
     Okay?

  54. [213.22s - 213.58s] speaker_1:
     Um-

  55. [213.58s - 229.62s] speaker_0:
     And   then,   uh,   with,   along   this,   what   medication,   because   during   the   first   trimester,   we   hardly   prescribe
  any   medicine,   so   we   want   you   to   take   the   minimum.   So   with   that,   you   can   try   some   home   remedies,
  like   hot   fomentation   and   then   gargling   with   salt   and   salt   water   and   then...

  56. [229.62s - 230.06s] speaker_1:
     Okay.

  57. [230.06s - 231.90s] speaker_0:
     Some   ginger   tea,   you   can   try.

  58. [231.90s - 240.44s] speaker_1:
     Okay.   Um,   will   the   patient   be   ...   So   will   the   baby   be   okay,   um,   while   I'm   sick?

  59. [240.44s - 265.56s] speaker_0:
     Yeah.   Uh,   no,   baby   will   be   fine.   No   problem.   Only   thing,   we   should,   uh,   try   and   be   the   medications
  to   be   minimum   so   that   they   doesn't   have   it.   But   you   should   continue   your   folic   acid   and   B12.   That
  will   really   help   the   baby   for   the   growth   of   the   brain   and   everything.   So   that,   you   should   continue.
  Okay?   And,   uh,   don't   go   outside.   Don't   be   in   the   crowd   where   you   get   it.   So   take   rest.   So   rest
  will   also   help   in   healing.

  60. [265.56s - 266.90s] speaker_1:
     Uh-

  61. [266.90s - 279.14s] speaker_0:
     And   if   vomiting   is   too   much,   I   can   prescribe   vomiting   tablets.   But   you   should   take   only   if   necessary,
  not   l-   daily   dosage.   Only   when   the   day   you   are   having   too   much   vomiting   that   day.   Otherwise,   no
  need   to   take   daily.

  62. [279.14s - 280.94s] speaker_1:
     Okay,   thank   you.

  63. [280.94s - 288.86s] speaker_0:
     So   just   after   blood   investigation,   I'll   again   review   y-   this   thing   and   then   prescribe   some   medications-

  64. [288.86s - 289.07s] speaker_1:
     Okay.

  65. [289.07s - 291.60s] speaker_0:
     ...   if   needed,   if   need   be.

  66. [291.60s - 292.10s] speaker_1:
     Okay.

  67. [292.10s - 302.22s] speaker_0:
     And   then,   along   with   that,   you   should   do,   start   doing   some   yoga,   some,   uh,   breathing   exercises.   That
  will   also   help   the   baby,   yes.

  68. [302.22s - 309.30s] speaker_1:
     Okay.   I'll   bear   that   in   mind   and   I'll,   I'll   carry   out.   I'll   follow   your   instructions.   Thank   you.

  69. [309.30s - 312.02s] speaker_0:
     Yeah.   Okay.   Yeah.

  70. [312.02s - 313.40s] speaker_1:
     Bye-bye.

  71. [313.40s - 314.72s] speaker_0:
     Yeah."""


async def main():
    """Run the consultation summary test."""

    print("\n" + "="*80)
    print("🧪 CONSULTATION SUMMARY SYSTEM TEST")
    print("="*80)
    print("\n📋 Test Case: 6-week pregnant patient with flu symptoms")
    print(f"📝 Transcript length: {len(CONSULTATION_TRANSCRIPT)} characters")
    print(f"👥 Expected speakers: doctor (speaker_0), patient (speaker_1)")
    print("\n" + "-"*80)

    # Get API key from environment
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY not found in environment")
        print("   Please ensure .env file contains ANTHROPIC_API_KEY")
        return

    print(f"\n✅ Anthropic API key loaded (ends with ...{anthropic_api_key[-4:]})")

    # Initialize the consultation summary system
    print("🔧 Initializing ConsultationSummary...")
    summarizer = ConsultationSummary(anthropic_api_key=anthropic_api_key)

    # Optional patient information - empty to test pure transcript extraction
    patient_info = None

    print("\n👤 Patient Information: None provided (testing pure transcript extraction)")

    print("\n" + "="*80)
    print("🔍 GENERATING CONSULTATION SUMMARY")
    print("="*80)

    try:
        # Generate the summary
        result = await summarizer.summarize(
            transcript=CONSULTATION_TRANSCRIPT,
            patient_info=patient_info
        )

        # Display results
        print("\n" + "="*80)
        print("✅ SUMMARY GENERATED SUCCESSFULLY")
        print("="*80)

        # Check for errors
        if 'error' in result:
            print(f"\n❌ ERROR: {result['error']}")
            print(f"   Details: {result.get('error_details', 'No details')}")
            if 'raw_response' in result:
                print(f"\n📄 Raw Response:\n{result['raw_response'][:500]}...")
            return

        # Pretty print the entire summary
        print("\n" + "="*80)
        print("📄 COMPLETE SUMMARY (JSON)")
        print("="*80)
        print(json.dumps(result, indent=2))

        # Validation checks
        print("\n" + "="*80)
        print("🔍 VALIDATION CHECKS")
        print("="*80)

        checks = []

        # Check 1: Speaker identification
        speakers = result.get('speakers', {})
        has_speakers = speakers.get('doctor') and speakers.get('patient')
        checks.append(("Speaker identification (doctor/patient)", has_speakers))
        if has_speakers:
            print(f"   ✓ Doctor: {speakers['doctor']}, Patient: {speakers['patient']}")

        # Check 2: Metadata present
        metadata = result.get('metadata', {})
        has_metadata = bool(metadata)
        checks.append(("Metadata extracted", has_metadata))
        if has_metadata:
            print(f"   ✓ Patient: {metadata.get('patient_name', 'N/A')}")
            print(f"   ✓ Duration: {metadata.get('duration_seconds', 0):.1f}s")

        # Check 3: Timeline extraction
        timeline = result.get('timeline', [])
        has_timeline = len(timeline) > 0
        checks.append(("Timeline events extracted", has_timeline))
        if has_timeline:
            print(f"   ✓ Timeline events: {len(timeline)}")
            for event in timeline[:3]:  # Show first 3
                print(f"      - {event.get('event', 'N/A')} ({event.get('timeframe', 'N/A')})")

        # Check 4: Clinical summary (SOAP components)
        clinical = result.get('clinical_summary', {})
        has_chief_complaint = bool(clinical.get('chief_complaint'))
        has_hpi = bool(clinical.get('history_present_illness'))
        has_ros = bool(clinical.get('review_of_systems'))
        has_plan = bool(clinical.get('plan'))

        checks.append(("Chief complaint", has_chief_complaint))
        checks.append(("History of present illness", has_hpi))
        checks.append(("Review of systems", has_ros))
        checks.append(("Plan", has_plan))

        if has_chief_complaint:
            print(f"   ✓ Chief complaint: {clinical['chief_complaint'][:80]}...")

        # Check 5: Key concerns
        concerns = result.get('key_concerns', [])
        has_concerns = len(concerns) > 0
        checks.append(("Key concerns identified", has_concerns))
        if has_concerns:
            print(f"   ✓ Key concerns: {len(concerns)}")

        # Check 6: Recommendations
        recommendations = result.get('recommendations_given', [])
        has_recommendations = len(recommendations) > 0
        checks.append(("Recommendations captured", has_recommendations))
        if has_recommendations:
            print(f"   ✓ Recommendations: {len(recommendations)}")

        # Check 7: Pregnancy context
        clinical_context = result.get('clinical_context', {})
        special_pop = clinical_context.get('special_populations', '')
        has_pregnancy_context = 'pregnan' in special_pop.lower()
        checks.append(("Pregnancy context noted", has_pregnancy_context))

        # Summary of validation
        print("\n" + "="*80)
        print("📊 VALIDATION SUMMARY")
        print("="*80)

        passed = sum(1 for _, result in checks if result)
        total = len(checks)

        for check_name, passed_check in checks:
            status = "✅" if passed_check else "❌"
            print(f"{status} {check_name}")

        print(f"\n✅ PASSED: {passed}/{total} checks")

        if passed == total:
            print("\n🎉 ALL VALIDATION CHECKS PASSED!")
            print("✅ The consultation summary system is working correctly!")
        else:
            print(f"\n⚠️  {total - passed} checks failed - review output above")

    except Exception as e:
        print(f"\n❌ ERROR during summary generation: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("✅ TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    print("\n🚀 Starting Consultation Summary System Test...\n")
    asyncio.run(main())
