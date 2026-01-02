"""
Image Analyzer Module

Converts HEIC images to JPEG and uses Claude Vision API to analyze
medical form structure, fields, and relationships.
"""

import base64
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from PIL import Image
import pillow_heif
from anthropic import Anthropic


@dataclass
class FormAnalysis:
    """Structured form analysis result"""
    form_name: str
    sections: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class ImageAnalyzer:
    """Analyzes form images using Claude Vision API"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the analyzer with Anthropic API key.

        Args:
            api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY env var.
        """
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"

    def convert_heic_to_jpeg(self, heic_path: str, output_dir: Optional[str] = None, max_size_mb: float = 4.5) -> str:
        """
        Convert HEIC image to JPEG format with size optimization.

        Args:
            heic_path: Path to HEIC image
            output_dir: Output directory (defaults to same dir as input)
            max_size_mb: Maximum file size in MB (default: 4.5 to stay under 5MB API limit)

        Returns:
            Path to generated JPEG file
        """
        heic_path = Path(heic_path)
        if not heic_path.exists():
            raise FileNotFoundError(f"HEIC file not found: {heic_path}")

        # Determine output path
        if output_dir:
            output_path = Path(output_dir) / heic_path.with_suffix('.jpg').name
        else:
            output_path = heic_path.with_suffix('.jpg')

        # Convert HEIC to JPEG
        heif_file = pillow_heif.open_heif(str(heic_path))
        image = Image.frombytes(
            heif_file.mode,
            heif_file.size,
            heif_file.data,
            "raw"
        )

        # Resize if image is very large (keep aspect ratio)
        max_dimension = 3000  # Max width or height
        if image.width > max_dimension or image.height > max_dimension:
            if image.width > image.height:
                new_width = max_dimension
                new_height = int(image.height * (max_dimension / image.width))
            else:
                new_height = max_dimension
                new_width = int(image.width * (max_dimension / image.height))
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Save with iteratively reduced quality until under size limit
        quality = 95
        max_size_bytes = int(max_size_mb * 1024 * 1024)

        while quality >= 60:
            image.save(str(output_path), 'JPEG', quality=quality, optimize=True)
            file_size = output_path.stat().st_size

            if file_size <= max_size_bytes:
                break

            quality -= 5

        return str(output_path)

    def encode_image_base64(self, image_path: str) -> str:
        """
        Encode image to base64 string.

        Args:
            image_path: Path to image file

        Returns:
            Base64-encoded image data
        """
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def analyze_form_structure(self, image_paths: List[str]) -> Dict[str, Any]:
        """
        Analyze form structure from images (Stage 1).

        Args:
            image_paths: List of image paths to analyze

        Returns:
            Dict containing form structure analysis
        """
        # Build image content for API
        image_content = []
        for img_path in image_paths[:2]:  # First 2 images for structure
            img_base64 = self.encode_image_base64(img_path)
            image_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": img_base64
                }
            })

        prompt = """Analyze these medical form images to understand the overall structure. Extract:

1. **Form sections**: Identify major sections/groupings (e.g., "Patient Demographics", "Vital Signs", "Medical History")
2. **Section hierarchy**: Parent-child relationships between sections
3. **Section purposes**: What each section is used for

Return a JSON object with this structure:
{
  "form_name": "suggested_form_name",
  "description": "Brief description of what this form is for",
  "sections": [
    {
      "name": "section_name",
      "description": "What this section captures",
      "order": 1
    }
  ]
}

**Reference patterns from existing Aneya forms:**
- vital_signs: Patient vital sign measurements (BP, heart rate, temperature)
- physical_exam_findings: Clinical examination findings
- lab_results: Laboratory test results
- medical_history: Past medical conditions and surgeries
- obstetric_history: Pregnancy-related history

Use snake_case for section names (e.g., "patient_demographics" not "Patient Demographics").
Return ONLY the JSON object, no additional text."""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": image_content + [{"type": "text", "text": prompt}]
            }]
        )

        import json
        response_text = message.content[0].text

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        return json.loads(response_text)

    def analyze_field_details(self, image_paths: List[str], sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze detailed field information (Stage 2).

        Args:
            image_paths: List of image paths to analyze
            sections: Previously identified sections

        Returns:
            Dict containing detailed field information for each section
        """
        # Build image content for API
        image_content = []
        for img_path in image_paths[2:4]:  # Images 3-4 for field details
            if os.path.exists(img_path):
                img_base64 = self.encode_image_base64(img_path)
                image_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": img_base64
                    }
                })

        sections_str = "\n".join([f"- {s['name']}: {s['description']}" for s in sections])

        prompt = f"""Analyze these medical form images to extract detailed field information.

**Known sections:**
{sections_str}

For each field you find, extract:
1. **Field name**: In snake_case (e.g., "systolic_bp", "patient_age")
2. **Field label**: Human-readable label as shown on form
3. **Field type**: One of: "string", "number", "boolean", "date", "object"
4. **Input type**: text_short, text_long, textarea, number, date, checkbox, radio, dropdown
5. **Unit**: For numeric fields (e.g., "mmHg", "kg", "cm", "years")
6. **Range**: For numeric fields [min, max]
7. **Required**: Is this field mandatory?
8. **Parent section**: Which section this field belongs to

Return a JSON object:
{{
  "fields": [
    {{
      "name": "field_name",
      "label": "Field Label",
      "type": "number",
      "input_type": "number",
      "unit": "mmHg",
      "range": [0, 250],
      "required": true,
      "section": "vital_signs",
      "description": "Brief description of what this field captures"
    }}
  ]
}}

**Field type mapping:**
- Short text input (1 line) → type: "string", input_type: "text_short", max_length: 200
- Long text input (multi-line) → type: "string", input_type: "textarea", max_length: 2000
- Number input → type: "number", input_type: "number"
- Date picker → type: "string", input_type: "date", format: "YYYY-MM-DD"
- Checkbox (single) → type: "boolean", input_type: "checkbox"
- Checkbox group → type: "object", input_type: "checkbox_group"
- Radio buttons → type: "string", input_type: "radio"
- Dropdown/select → type: "string", input_type: "dropdown"

Return ONLY the JSON object, no additional text."""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            messages=[{
                "role": "user",
                "content": image_content + [{"type": "text", "text": prompt}]
            }]
        )

        import json
        response_text = message.content[0].text

        # Extract JSON from response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        return json.loads(response_text)

    def analyze_validation_and_relationships(self, image_paths: List[str], fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze validation rules and field relationships (Stage 3).

        Args:
            image_paths: List of image paths to analyze
            fields: Previously identified fields

        Returns:
            Dict containing validation rules and relationships
        """
        # Build image content for API
        image_content = []
        for img_path in image_paths[4:6]:  # Images 5-6 for validation
            if os.path.exists(img_path):
                img_base64 = self.encode_image_base64(img_path)
                image_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": img_base64
                    }
                })

        # If no images available for stage 3, return empty relationships
        if not image_content:
            return {"relationships": [], "validation_notes": []}

        fields_str = "\n".join([f"- {f['name']}: {f.get('label', 'N/A')}" for f in fields[:20]])  # Limit for prompt size

        prompt = f"""Analyze these medical form images for validation rules and field relationships.

**Known fields (partial list):**
{fields_str}

Identify:
1. **Conditional fields**: Fields that only appear based on other field values
   - Example: "If pregnancy_status = 'pregnant', show ultrasound_findings"
2. **Field groups**: Related fields that form a logical group
3. **Validation rules**: Special constraints (e.g., "start_date must be before end_date")
4. **Required field patterns**: Which fields are marked as required/mandatory

Return a JSON object:
{{
  "relationships": [
    {{
      "type": "conditional",
      "condition": "pregnancy_status == 'pregnant'",
      "show_fields": ["ultrasound_findings", "gestational_age_weeks"]
    }}
  ],
  "validation_notes": [
    "Date of birth must be in the past",
    "Blood pressure values must be positive numbers"
  ]
}}

Return ONLY the JSON object, no additional text. If you don't find specific relationships, return empty arrays."""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": image_content + [{"type": "text", "text": prompt}]
            }]
        )

        import json
        response_text = message.content[0].text

        # Extract JSON from response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        return json.loads(response_text)

    def analyze_images(self, heic_paths: List[str]) -> FormAnalysis:
        """
        Complete multi-stage analysis of form images.

        Args:
            heic_paths: List of paths to HEIC images

        Returns:
            FormAnalysis object with complete analysis results
        """
        # Step 1: Convert HEIC to JPEG
        print("Converting HEIC images to JPEG...")
        jpeg_paths = []
        for heic_path in heic_paths:
            try:
                jpeg_path = self.convert_heic_to_jpeg(heic_path)
                jpeg_paths.append(jpeg_path)
                print(f"  ✓ Converted {Path(heic_path).name}")
            except Exception as e:
                print(f"  ✗ Failed to convert {heic_path}: {e}")

        if not jpeg_paths:
            raise ValueError("No images were successfully converted")

        # Step 2: Analyze form structure
        print("\nAnalyzing form structure...")
        structure = self.analyze_form_structure(jpeg_paths)
        print(f"  ✓ Identified {len(structure['sections'])} sections")

        # Step 3: Analyze field details
        print("\nAnalyzing field details...")
        field_data = self.analyze_field_details(jpeg_paths, structure['sections'])
        print(f"  ✓ Extracted {len(field_data['fields'])} fields")

        # Step 4: Analyze relationships (if enough images)
        relationships = {"relationships": [], "validation_notes": []}
        if len(jpeg_paths) >= 5:
            print("\nAnalyzing validation rules and relationships...")
            relationships = self.analyze_validation_and_relationships(jpeg_paths, field_data['fields'])
            print(f"  ✓ Found {len(relationships['relationships'])} relationships")

        # Combine results
        return FormAnalysis(
            form_name=structure['form_name'],
            sections=self._organize_fields_by_section(structure['sections'], field_data['fields']),
            metadata={
                "description": structure.get('description', ''),
                "relationships": relationships['relationships'],
                "validation_notes": relationships['validation_notes'],
                "total_fields": len(field_data['fields']),
                "image_count": len(jpeg_paths)
            }
        )

    def _organize_fields_by_section(self, sections: List[Dict[str, Any]], fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Organize fields into their respective sections.

        Args:
            sections: List of section definitions
            fields: List of field definitions

        Returns:
            List of sections with fields organized within them
        """
        # Create section dict for easy lookup
        section_dict = {s['name']: {**s, 'fields': []} for s in sections}

        # Organize fields by section
        for field in fields:
            section_name = field.get('section')
            if section_name in section_dict:
                section_dict[section_name]['fields'].append(field)
            else:
                # Field doesn't match any section - add to 'other' section
                if 'other' not in section_dict:
                    section_dict['other'] = {
                        'name': 'other',
                        'description': 'Other fields',
                        'order': 999,
                        'fields': []
                    }
                section_dict['other']['fields'].append(field)

        # Convert back to list and sort by order
        result = list(section_dict.values())
        result.sort(key=lambda s: s.get('order', 999))

        return result
