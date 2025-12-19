"""
Consultation Summary Module

Provides standalone consultation summarization capabilities for diarized transcripts.
Extracts speaker roles, timeline, and generates comprehensive clinical summaries.
"""

import re
import json
from typing import Dict, List, Optional, Any, Tuple
from anthropic import Anthropic
import os


class ConsultationSummary:
    """
    Standalone consultation summarizer for diarized medical transcripts.

    Processes consultation transcripts with speaker diarization to extract:
    - Speaker identification (doctor vs patient)
    - Timeline of symptoms and events
    - Comprehensive clinical summary in SOAP note format
    - Key concerns and recommendations
    """

    def __init__(self, anthropic_api_key: Optional[str] = None):
        """
        Initialize the consultation summary system.

        Args:
            anthropic_api_key: Anthropic API key for Claude. If None, reads from ANTHROPIC_API_KEY env var.
        """
        api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for ConsultationSummary")

        self.anthropic = Anthropic(api_key=api_key)

    async def summarize(
        self,
        transcript: str,
        patient_info: Optional[dict] = None,
        output_in_english: bool = False,
        is_from_transcription: bool = True,
        transcription_language: Optional[str] = None
    ) -> dict:
        """
        Generate a comprehensive summary of a consultation transcript.

        Args:
            transcript: Diarized consultation transcript (format: "[timestamp] speaker_X: text")
            patient_info: Optional patient metadata (name, id, age, etc.)
            output_in_english: If True, instruct Claude to output the summary in English
                              (useful when transcript is in a non-English language)
            is_from_transcription: If True, indicates this text came from speech-to-text
                                   and may contain transcription errors
            transcription_language: Original language of the transcription (e.g., 'hi-IN', 'en-US')

        Returns:
            Dictionary containing:
            - speakers: Mapping of speaker IDs to roles (doctor/patient)
            - metadata: Consultation metadata (duration, patient info)
            - timeline: Chronological list of events/symptoms
            - clinical_summary: SOAP note components
            - key_concerns: Patient concerns extracted
            - recommendations_given: Medical advice provided
        """
        # Step 1: Parse the diarized transcript
        parsed = self._parse_diarized_transcript(transcript)

        # Step 2: Identify speaker roles (doctor vs patient)
        speaker_roles = self._identify_speakers(parsed['conversation'])

        # Step 3: Generate comprehensive summary using Claude
        summary = await self._generate_summary(
            transcript=transcript,
            parsed_data=parsed,
            speaker_roles=speaker_roles,
            patient_info=patient_info,
            output_in_english=output_in_english,
            is_from_transcription=is_from_transcription,
            transcription_language=transcription_language
        )

        return summary

    def _parse_diarized_transcript(self, transcript: str) -> dict:
        """
        Parse diarized transcript into structured format.

        Format: "[start_time - end_time] speaker_X:\n     text"

        Returns:
            {
                'conversation': [
                    {
                        'index': 1,
                        'start_time': 2.00,
                        'end_time': 4.56,
                        'speaker': 'speaker_0',
                        'text': 'Okay. Uh, come. Uh, what's your name?'
                    },
                    ...
                ],
                'duration_seconds': 314.72,
                'speakers': ['speaker_0', 'speaker_1']
            }
        """
        # Pattern: " X. [start - end] speaker_Y:\n     text"
        pattern = r'\s*(\d+)\.\s*\[([0-9.]+)s?\s*-\s*([0-9.]+)s?\]\s*(speaker_\d+):\s*\n?\s*(.+?)(?=\n\s*\d+\.\s*\[|$)'

        matches = re.findall(pattern, transcript, re.DOTALL)

        conversation = []
        speakers = set()
        max_time = 0.0

        for match in matches:
            index, start, end, speaker, text = match

            # Clean up text (remove extra whitespace)
            text = ' '.join(text.split())

            start_time = float(start)
            end_time = float(end)
            max_time = max(max_time, end_time)

            speakers.add(speaker)

            conversation.append({
                'index': int(index),
                'start_time': start_time,
                'end_time': end_time,
                'speaker': speaker,
                'text': text
            })

        return {
            'conversation': conversation,
            'duration_seconds': max_time,
            'speakers': sorted(list(speakers))
        }

    def _identify_speakers(self, conversation: List[dict]) -> Dict[str, str]:
        """
        Identify which speaker is the doctor vs patient.

        Uses heuristics:
        - Doctor asks more questions
        - Doctor uses medical terminology
        - Doctor gives instructions/recommendations
        - Patient describes symptoms
        - First speaker is often the doctor

        Args:
            conversation: List of conversation turns

        Returns:
            {'doctor': 'speaker_0', 'patient': 'speaker_1'}
        """
        speaker_stats = {}

        for turn in conversation:
            speaker = turn['speaker']
            text = turn['text'].lower()

            if speaker not in speaker_stats:
                speaker_stats[speaker] = {
                    'questions': 0,
                    'medical_terms': 0,
                    'instructions': 0,
                    'symptom_descriptions': 0,
                    'turn_count': 0
                }

            stats = speaker_stats[speaker]
            stats['turn_count'] += 1

            # Count questions (doctor typically asks more)
            stats['questions'] += text.count('?')

            # Medical terminology (suggests doctor)
            medical_terms = ['examination', 'investigation', 'ultrasound', 'hemoglobin',
                           'prescribe', 'dosage', 'medication', 'diagnosis', 'trimester',
                           'blood test', 'scan', 'examine']
            stats['medical_terms'] += sum(1 for term in medical_terms if term in text)

            # Instructions/recommendations (suggests doctor)
            instruction_words = ['should', 'need to', 'get it done', 'take', 'continue',
                               "i'll write", 'try', 'avoid', 'do some']
            stats['instructions'] += sum(1 for word in instruction_words if word in text)

            # Symptom descriptions (suggests patient)
            symptom_words = ['cough', 'fever', 'pain', 'vomit', "can't sleep", 'sore',
                           "i've been", "i'm getting", 'headache', 'cold']
            stats['symptom_descriptions'] += sum(1 for word in symptom_words if word in text)

        # Score each speaker (higher score = more likely to be doctor)
        speaker_scores = {}
        for speaker, stats in speaker_stats.items():
            score = (
                stats['questions'] * 2 +
                stats['medical_terms'] * 3 +
                stats['instructions'] * 2 -
                stats['symptom_descriptions'] * 1
            )
            speaker_scores[speaker] = score

        # Assign roles based on scores
        speakers_sorted = sorted(speaker_scores.items(), key=lambda x: x[1], reverse=True)

        if len(speakers_sorted) >= 2:
            doctor = speakers_sorted[0][0]
            patient = speakers_sorted[1][0]
        elif len(speakers_sorted) == 1:
            # Only one speaker? Assume it's the doctor (unusual case)
            doctor = speakers_sorted[0][0]
            patient = None
        else:
            doctor = None
            patient = None

        return {
            'doctor': doctor,
            'patient': patient
        }

    async def _generate_summary(
        self,
        transcript: str,
        parsed_data: dict,
        speaker_roles: dict,
        patient_info: Optional[dict],
        output_in_english: bool = False,
        is_from_transcription: bool = True,
        transcription_language: Optional[str] = None
    ) -> dict:
        """
        Generate comprehensive clinical summary using Claude.

        Args:
            transcript: Original diarized transcript
            parsed_data: Parsed conversation structure
            speaker_roles: Doctor/patient speaker mapping
            patient_info: Optional patient metadata
            output_in_english: If True, instruct Claude to output in English
            is_from_transcription: If True, indicates text came from speech-to-text
            transcription_language: Original language of the transcription

        Returns:
            Comprehensive summary with all structured components
        """
        # Build the prompt for Claude
        prompt = self._build_summary_prompt(
            transcript=transcript,
            speaker_roles=speaker_roles,
            duration=parsed_data['duration_seconds'],
            patient_info=patient_info,
            output_in_english=output_in_english,
            is_from_transcription=is_from_transcription,
            transcription_language=transcription_language
        )

        # Call Claude with JSON mode for structured output
        try:
            message = self.anthropic.messages.create(
                model="claude-sonnet-4-20250514",  # Latest Sonnet model
                max_tokens=4000,
                temperature=0.3,  # Lower temperature for more consistent medical summaries
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Extract the response
            response_text = message.content[0].text

            # Parse JSON response
            # Try to extract JSON if Claude wrapped it in markdown
            if '```json' in response_text:
                json_match = re.search(r'```json\s*(\{.+?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            elif '```' in response_text:
                json_match = re.search(r'```\s*(\{.+?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)

            summary = json.loads(response_text)

            # Add metadata
            summary['metadata'] = summary.get('metadata', {})
            summary['metadata']['duration_seconds'] = parsed_data['duration_seconds']
            summary['metadata']['total_turns'] = len(parsed_data['conversation'])

            return summary

        except json.JSONDecodeError as e:
            # Fallback: return basic structure with error
            return {
                'error': 'Failed to parse summary JSON',
                'error_details': str(e),
                'raw_response': response_text if 'response_text' in locals() else None,
                'speakers': speaker_roles,
                'metadata': {
                    'duration_seconds': parsed_data['duration_seconds'],
                    'total_turns': len(parsed_data['conversation'])
                }
            }
        except Exception as e:
            return {
                'error': 'Summary generation failed',
                'error_details': str(e),
                'speakers': speaker_roles,
                'metadata': {
                    'duration_seconds': parsed_data['duration_seconds'],
                    'total_turns': len(parsed_data['conversation'])
                }
            }

    def _build_summary_prompt(
        self,
        transcript: str,
        speaker_roles: dict,
        duration: float,
        patient_info: Optional[dict],
        output_in_english: bool = False,
        is_from_transcription: bool = True,
        transcription_language: Optional[str] = None
    ) -> str:
        """
        Build the specialized prompt for medical consultation summarization.

        Args:
            transcript: The consultation transcript text
            speaker_roles: Mapping of speaker IDs to roles
            duration: Duration of the consultation in seconds
            patient_info: Optional patient metadata
            output_in_english: If True, add instruction to output in English
            is_from_transcription: If True, indicates text came from speech-to-text
            transcription_language: Original language of the transcription

        Returns:
            Prompt string for Claude
        """
        # Add patient context if available
        patient_context = ""
        if patient_info:
            patient_context = f"\n\nPatient Information (if not in transcript):\n"
            if patient_info.get('patient_id'):
                patient_context += f"- Patient ID: {patient_info['patient_id']}\n"
            if patient_info.get('patient_age'):
                patient_context += f"- Age/Status: {patient_info['patient_age']}\n"
            if patient_info.get('allergies'):
                patient_context += f"- Known Allergies: {patient_info['allergies']}\n"

        # Add English output instruction if needed
        language_instruction = ""
        if output_in_english:
            language_instruction = """

IMPORTANT LANGUAGE INSTRUCTION:
The transcript below is in a non-English language. You MUST output ALL text in the JSON response in ENGLISH.
- Translate all content to English while preserving medical accuracy
- Use standard English medical terminology
- Maintain the meaning and clinical significance of all statements
- All JSON field values must be in English
"""

        # Add transcription error handling instruction
        transcription_instruction = ""
        if is_from_transcription:
            lang_note = ""
            if transcription_language:
                lang_note = f" The original language was {transcription_language}."
            transcription_instruction = f"""

IMPORTANT - TRANSCRIPTION SOURCE:
This text was generated from speech-to-text transcription and may contain errors.{lang_note}
When interpreting the transcript:
- Be aware that some words may be incorrectly transcribed due to homophones (words that sound alike but have different meanings)
- Medical terms, drug names, and numbers are especially prone to transcription errors
- Consider phonetically similar alternatives when something doesn't make medical sense
- For example: "paracetamol" might appear as "pair acetamol", "blood pressure" as "blood presher", "fever" as "fevers"
- Names of medications may be misspelled or phonetically represented
- Numbers and dosages may be transcribed incorrectly (e.g., "fifty" as "15", "two hundred" as "200")
- Use your medical knowledge to infer the most likely intended meaning when transcription errors are apparent
- If a word or phrase doesn't make sense in context, consider what similar-sounding word would be medically appropriate
"""

        prompt = f"""You are a medical transcription documentation tool that converts diarized consultation transcripts into structured clinical reports.{language_instruction}{transcription_instruction}

CRITICAL INSTRUCTIONS:
- Extract ONLY information explicitly stated in the transcript below
- Do NOT add medical knowledge, assumptions, or information from external sources
- Do NOT infer conditions, diagnoses, or facts not mentioned in the conversation
- If information is not discussed in the transcript, mark it as "Not discussed" or leave blank
- Your role is to structure what was said, not to provide medical analysis

Speaker Identification:
- Doctor: {speaker_roles.get('doctor', 'Unknown')}
- Patient: {speaker_roles.get('patient', 'Unknown')}
- Consultation Duration: {duration:.1f} seconds{patient_context}

Your task is to convert this consultation transcript into a structured clinical summary following the SOAP (Subjective, Objective, Assessment, Plan) note format.

TRANSCRIPT:
{transcript}

Generate a complete structured summary in the following JSON format:

{{
  "speakers": {{
    "doctor": "{speaker_roles.get('doctor', 'speaker_0')}",
    "patient": "{speaker_roles.get('patient', 'speaker_1')}"
  }},
  "metadata": {{
    "patient_name": "extracted from transcript or 'Not mentioned'",
    "patient_location": "extracted if mentioned or 'Not mentioned'",
    "consultation_date": "extracted if mentioned or 'Not specified'",
    "key_demographic": "e.g., '6 weeks pregnant' or other relevant demographic info"
  }},
  "timeline": [
    {{
      "event": "Symptom onset - description",
      "timeframe": "5 days ago / since Wednesday / 2 months",
      "description": "Detailed description of what started"
    }}
  ],
  "clinical_summary": {{
    "chief_complaint": "Primary reason for visit in one sentence",
    "history_present_illness": "Detailed chronological description of current illness, including onset, duration, progression, severity, and associated symptoms",
    "review_of_systems": {{
      "constitutional": "Fever, chills, fatigue, etc.",
      "respiratory": "Cough, dyspnea, etc.",
      "cardiovascular": "Chest pain, palpitations, etc.",
      "gastrointestinal": "Nausea, vomiting, diarrhea, etc.",
      "genitourinary": "Relevant GU symptoms",
      "musculoskeletal": "Pain, weakness, etc.",
      "neurological": "Headache, dizziness, etc.",
      "ent": "Sore throat, ear pain, etc.",
      "other": "Any other relevant systems"
    }},
    "past_medical_history": "Relevant past medical conditions mentioned (or 'Not discussed')",
    "medications_current": ["List current medications mentioned", "with dosages if provided"],
    "allergies": "Known allergies or 'None reported' or 'Not discussed'",
    "physical_examination": "Examination findings mentioned by physician (vitals, inspection, palpation, etc.)",
    "investigations_ordered": ["Blood tests", "Ultrasound", "etc."],
    "investigations_reviewed": ["Ultrasound scan - normal", "etc."],
    "assessment": "Physician's clinical assessment and working diagnosis",
    "plan": {{
      "diagnostic": ["Further tests or investigations ordered"],
      "therapeutic": ["Medications prescribed", "Home remedies recommended"],
      "patient_education": ["Advice given to patient"],
      "follow_up": "Follow-up instructions"
    }}
  }},
  "key_concerns": [
    "Patient's primary concerns or questions",
    "Special considerations (pregnancy, age, comorbidities)"
  ],
  "recommendations_given": [
    "Specific advice or instructions from physician",
    "Lifestyle modifications",
    "When to return or seek emergency care"
  ],
  "clinical_context": {{
    "special_populations": "Pregnancy, pediatric, geriatric, immunocompromised, etc.",
    "safety_considerations": "Medication safety in pregnancy, drug interactions, etc.",
    "red_flags": "Any concerning symptoms or findings requiring urgent attention"
  }}
}}

Important Instructions:
1. Extract ONLY information explicitly stated in the transcript - do NOT add external medical knowledge
2. If something is not mentioned in the transcript, write "Not discussed" or leave the field empty
3. Preserve exact medical terminology, measurements, and dosages as stated in the transcript
4. Extract ALL temporal references (days, weeks, months ago) and create timeline entries
5. Differentiate between symptoms REPORTED by patient vs OBSERVED/STATED by physician
6. For review of systems, only include systems that were specifically discussed in the conversation
7. Capture the physician's statements and recommendations exactly as given
8. Extract patient's concerns and questions verbatim when possible
9. Do NOT infer diagnoses - only capture what the doctor explicitly stated as their assessment
10. Return ONLY valid JSON, no additional text before or after

Generate the structured clinical report from the transcript now:"""

        return prompt
