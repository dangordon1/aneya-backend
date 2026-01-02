"""
Historical Form Data Extraction Service
Extracts patient data from filled historical forms using Claude Vision API
"""

import base64
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from anthropic import Anthropic
from PIL import Image
import pillow_heif

from .pdf_processor import PDFProcessor, get_file_type_from_bytes

logger = logging.getLogger(__name__)


class HistoricalFormDataExtractor:
    """Extract structured patient data from historical form documents"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize extractor with Anthropic API key

        Args:
            api_key: Anthropic API key (if None, uses ANTHROPIC_API_KEY env var)
        """
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"
        self.pdf_processor = PDFProcessor()

    def prepare_image_for_api(self, file_bytes: bytes, file_type: str) -> Optional[Dict[str, Any]]:
        """
        Prepare image file for Claude Vision API

        Args:
            file_bytes: File content as bytes
            file_type: File type ('jpeg', 'png', 'heic', or 'pdf')

        Returns:
            API-ready image content dict, or None if processing fails
        """
        try:
            # Handle HEIC conversion
            if file_type == 'heic':
                heif_file = pillow_heif.open_heif(file_bytes)
                image = Image.frombytes(
                    heif_file.mode,
                    heif_file.size,
                    heif_file.data,
                    "raw"
                )
                # Convert to JPEG
                import io
                jpeg_buffer = io.BytesIO()
                image.save(jpeg_buffer, 'JPEG', quality=90, optimize=True)
                jpeg_buffer.seek(0)
                file_bytes = jpeg_buffer.read()
                media_type = "image/jpeg"

            elif file_type == 'png':
                media_type = "image/png"
            elif file_type == 'jpeg':
                media_type = "image/jpeg"
            else:
                logger.warning(f"Unsupported image type: {file_type}")
                return None

            # Encode to base64
            base64_data = base64.b64encode(file_bytes).decode('utf-8')

            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64_data
                }
            }

        except Exception as e:
            logger.error(f"Failed to prepare image for API: {e}")
            return None

    def extract_patient_data_from_files(
        self,
        files: List[Tuple[bytes, str, str]],  # (file_bytes, file_name, file_type)
        patient_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract structured patient data from uploaded files

        Args:
            files: List of tuples (file_bytes, file_name, file_type)
            patient_context: Optional existing patient data for context

        Returns:
            Dictionary with extracted data organized by category
        """
        try:
            # Prepare content for API
            content_blocks = []

            for file_bytes, file_name, file_type in files:
                if file_type == 'pdf':
                    # Extract text from PDF
                    pdf_result = self.pdf_processor.process_pdf_for_vision_api(file_bytes)
                    if pdf_result['success'] and pdf_result['text_content']:
                        content_blocks.append({
                            "type": "text",
                            "text": f"**PDF File: {file_name}**\n\nExtracted Text:\n{pdf_result['text_content']}"
                        })
                else:
                    # Prepare image for vision API
                    image_block = self.prepare_image_for_api(file_bytes, file_type)
                    if image_block:
                        content_blocks.append(image_block)
                        content_blocks.append({
                            "type": "text",
                            "text": f"**Image File: {file_name}**"
                        })

            if not content_blocks:
                return {
                    "success": False,
                    "error": "No valid files to process",
                    "extracted_data": {}
                }

            # Build extraction prompt
            prompt = self._build_extraction_prompt(patient_context)
            content_blocks.append({"type": "text", "text": prompt})

            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                temperature=0,
                messages=[{
                    "role": "user",
                    "content": content_blocks
                }]
            )

            response_text = message.content[0].text

            # Extract JSON from response
            extracted_data = self._parse_extraction_response(response_text)

            # Calculate confidence score
            confidence = self._calculate_confidence(extracted_data, message)

            return {
                "success": True,
                "extracted_data": extracted_data,
                "confidence": confidence,
                "fields_extracted": self._count_extracted_fields(extracted_data),
            }

        except Exception as e:
            logger.error(f"Failed to extract patient data: {e}")
            return {
                "success": False,
                "error": str(e),
                "extracted_data": {}
            }

    def _build_extraction_prompt(self, patient_context: Optional[Dict[str, Any]] = None) -> str:
        """Build the extraction prompt for Claude"""

        context_info = ""
        if patient_context:
            context_info = f"\n\n**Existing Patient Data (for reference):**\n```json\n{json.dumps(patient_context, indent=2)}\n```\n"

        return f"""Analyze the provided medical form document(s) and extract all patient data into a structured format.

{context_info}

**Extract the following categories of information:**

1. **Demographics** - Patient identifying information
2. **Vitals** - Vital signs with timestamps if available
3. **Medications** - Current and past medications
4. **Allergies** - Known allergies and reactions
5. **Medical History** - Conditions, surgeries, family history
6. **Form-specific Data** - Any specialty-specific form data (OB/GYN, cardiology, etc.)

**Output Format:**

Return a JSON object with this exact structure:

```json
{{
  "demographics": {{
    "name": "patient full name or null",
    "date_of_birth": "YYYY-MM-DD or null",
    "age_years": "number or null",
    "sex": "Male|Female|Other or null",
    "phone": "phone number or null",
    "email": "email or null",
    "height_cm": "number or null",
    "weight_kg": "number or null"
  }},
  "vitals": [
    {{
      "recorded_at": "ISO timestamp or date if available",
      "systolic_bp": "number or null",
      "diastolic_bp": "number or null",
      "heart_rate": "number or null",
      "respiratory_rate": "number or null",
      "temperature_celsius": "number or null",
      "spo2": "number or null",
      "blood_glucose_mg_dl": "number or null"
    }}
  ],
  "medications": [
    {{
      "medication_name": "medication name",
      "dosage": "dosage with units",
      "frequency": "frequency description",
      "start_date": "YYYY-MM-DD or null",
      "status": "active|discontinued|completed",
      "notes": "additional notes or null"
    }}
  ],
  "allergies": [
    {{
      "allergen": "allergen name",
      "severity": "mild|moderate|severe|unknown",
      "reaction": "description of reaction",
      "notes": "additional notes or null"
    }}
  ],
  "medical_history": {{
    "current_conditions": "comma-separated list of current conditions or null",
    "past_surgeries": "comma-separated list of past surgeries or null",
    "family_history": "relevant family history or null"
  }},
  "forms": [
    {{
      "form_type": "obgyn|cardiology|neurology|dermatology|general",
      "form_subtype": "infertility|antenatal|routine_gyn|etc or null",
      "data": {{
        // Form-specific fields extracted from the document
        // For OB/GYN: menstrual_history, obstetric_history, etc.
        // Use the existing Aneya schema structure if recognizable
      }}
    }}
  ],
  "form_metadata": {{
    "form_date": "YYYY-MM-DD - date when form was filled, or null",
    "facility_name": "facility name if visible, or null",
    "doctor_name": "doctor name if visible, or null",
    "confidence_notes": "any notes about data quality or ambiguities"
  }}
}}
```

**Important Instructions:**

1. **Be precise**: Only extract data you can clearly see in the forms
2. **Use null**: If a field is not present or unclear, use null instead of guessing
3. **Standardize units**: Convert to metric (cm, kg, celsius) if possible
4. **Parse dates**: Convert dates to YYYY-MM-DD format
5. **Normalize values**: Use standardized formats (e.g., "Male" not "M")
6. **Extract context**: If dates/timestamps are mentioned, extract them
7. **No hallucination**: Don't add information not present in the forms
8. **Confidence**: Note any ambiguous or unclear data in confidence_notes

Return ONLY the JSON object, no additional text or explanation."""

    def _parse_extraction_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's response to extract JSON"""
        try:
            # Handle markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            extracted = json.loads(response_text)

            # Ensure all expected keys exist with defaults
            return {
                "demographics": extracted.get("demographics", {}),
                "vitals": extracted.get("vitals", []),
                "medications": extracted.get("medications", []),
                "allergies": extracted.get("allergies", []),
                "medical_history": extracted.get("medical_history", {}),
                "forms": extracted.get("forms", []),
                "form_metadata": extracted.get("form_metadata", {})
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extraction response as JSON: {e}")
            logger.error(f"Response text: {response_text[:500]}")
            return {
                "demographics": {},
                "vitals": [],
                "medications": [],
                "allergies": [],
                "medical_history": {},
                "forms": [],
                "form_metadata": {"confidence_notes": f"Failed to parse response: {e}"}
            }

    def _calculate_confidence(self, extracted_data: Dict[str, Any], message: Any) -> float:
        """
        Calculate confidence score based on extracted data and API response

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Base confidence on presence of key fields
        score = 0.5  # Start at 50%

        # Boost for demographics
        demo = extracted_data.get("demographics", {})
        if demo.get("name"):
            score += 0.1
        if demo.get("date_of_birth") or demo.get("age_years"):
            score += 0.1
        if demo.get("sex"):
            score += 0.05

        # Boost for medical data
        if extracted_data.get("vitals"):
            score += 0.1
        if extracted_data.get("medications"):
            score += 0.05
        if extracted_data.get("allergies"):
            score += 0.05

        # Reduce for confidence notes indicating issues
        metadata = extracted_data.get("form_metadata", {})
        confidence_notes = metadata.get("confidence_notes", "").lower()
        if any(word in confidence_notes for word in ["unclear", "ambiguous", "unable", "failed"]):
            score -= 0.15

        # Cap between 0 and 1
        return max(0.0, min(1.0, score))

    def _count_extracted_fields(self, extracted_data: Dict[str, Any]) -> int:
        """Count total number of non-null fields extracted"""
        count = 0

        # Demographics
        demo = extracted_data.get("demographics", {})
        count += sum(1 for v in demo.values() if v is not None)

        # Vitals
        for vital in extracted_data.get("vitals", []):
            count += sum(1 for v in vital.values() if v is not None)

        # Medications
        count += len(extracted_data.get("medications", []))

        # Allergies
        count += len(extracted_data.get("allergies", []))

        # Medical history
        med_hist = extracted_data.get("medical_history", {})
        count += sum(1 for v in med_hist.values() if v is not None and v != "")

        # Forms
        count += len(extracted_data.get("forms", []))

        return count
