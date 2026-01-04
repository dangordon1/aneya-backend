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
    pdf_template: Dict[str, Any]  # PDF layout configuration
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
        self.model = "claude-opus-4-5-20251101"  # Using Opus 4.5 for comprehensive extraction

    def convert_heic_to_jpeg(self, heic_path: str, output_dir: Optional[str] = None, max_size_mb: float = 3.7) -> str:
        """
        Convert HEIC image to JPEG format with size optimization.

        Note: We use 3.7MB limit because base64 encoding increases size by ~33%.
        3.7MB file → ~4.9MB base64 encoded (under Claude's 5MB API limit)

        Args:
            heic_path: Path to HEIC image
            output_dir: Output directory (defaults to same dir as input)
            max_size_mb: Maximum file size in MB (default: 3.7MB to stay under 5MB when base64 encoded)

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

    def compress_image(self, image_path: str, max_size_mb: float = 3.7) -> str:
        """
        Compress an image (JPEG/PNG) to ensure it's under the size limit.

        Note: We use 3.7MB limit because base64 encoding increases size by ~33%.
        3.7MB file → ~4.9MB base64 encoded (under Claude's 5MB API limit)

        Args:
            image_path: Path to image file
            max_size_mb: Maximum file size in MB (default: 3.7MB to stay under 5MB when base64 encoded)

        Returns:
            Path to compressed image (same path if already under limit)
        """
        image_path = Path(image_path)
        max_size_bytes = int(max_size_mb * 1024 * 1024)

        # Check current size
        current_size = image_path.stat().st_size

        # Always show size info for debugging
        if current_size > max_size_bytes:
            print(f"  ⚙️  Compressing {image_path.name} ({current_size / 1024 / 1024:.2f}MB > {max_size_mb}MB limit)")
        elif current_size > max_size_bytes * 0.8:  # Close to limit
            print(f"  ℹ️  {image_path.name} is {current_size / 1024 / 1024:.2f}MB (will be ~{current_size * 1.33 / 1024 / 1024:.2f}MB base64 encoded)")

        if current_size <= max_size_bytes:
            return str(image_path)  # Already under limit

        # Open image
        image = Image.open(str(image_path))

        # Convert RGBA to RGB if needed (for PNG with transparency)
        if image.mode == 'RGBA':
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            rgb_image.paste(image, mask=image.split()[3])
            image = rgb_image

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

        # Create output path (convert to JPEG)
        output_path = image_path.with_suffix('.jpg')

        # Save with iteratively reduced quality until under size limit
        quality = 95
        while quality >= 60:
            image.save(str(output_path), 'JPEG', quality=quality, optimize=True)
            file_size = output_path.stat().st_size

            if file_size <= max_size_bytes:
                print(f"  ✓ Compressed to {file_size / 1024 / 1024:.2f}MB at quality {quality}")
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

    def extract_and_upload_logo(
        self,
        image_path: str,
        bounding_box: Dict[str, float],
        supabase_client,
        user_id: str,
        facility_name: str = "clinic"
    ) -> Optional[str]:
        """
        Extract logo from image using bounding box and upload to Supabase Storage.

        Args:
            image_path: Path to source image
            bounding_box: Dict with x_percent, y_percent, width_percent, height_percent
            supabase_client: Authenticated Supabase client
            user_id: User ID for organizing uploads
            facility_name: Name for the logo file

        Returns:
            Public URL of uploaded logo, or None if extraction fails
        """
        try:
            from datetime import datetime
            import io

            # Open source image
            image = Image.open(image_path)
            width, height = image.size

            # Calculate pixel coordinates from percentages
            x = int((bounding_box.get('x_percent', 0) / 100.0) * width)
            y = int((bounding_box.get('y_percent', 0) / 100.0) * height)
            logo_width = int((bounding_box.get('width_percent', 20) / 100.0) * width)
            logo_height = int((bounding_box.get('height_percent', 10) / 100.0) * height)

            # Crop logo region
            logo = image.crop((x, y, x + logo_width, y + logo_height))

            # Convert to RGB if RGBA
            if logo.mode == 'RGBA':
                rgb_logo = Image.new('RGB', logo.size, (255, 255, 255))
                rgb_logo.paste(logo, mask=logo.split()[3])
                logo = rgb_logo

            # Save to bytes buffer
            buffer = io.BytesIO()
            logo.save(buffer, format='PNG', optimize=True)
            logo_bytes = buffer.getvalue()

            # Generate unique filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_facility_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in facility_name.lower())
            filename = f"{user_id}/{safe_facility_name}_{timestamp}.png"

            # Upload to Supabase Storage
            print(f"  📤 Uploading logo to Supabase Storage: {filename}")
            supabase_client.storage.from_('clinic-logos').upload(
                filename,
                logo_bytes,
                file_options={"content-type": "image/png"}
            )

            # Get public URL
            logo_url = supabase_client.storage.from_('clinic-logos').get_public_url(filename)
            print(f"  ✓ Logo extracted and uploaded: {logo_url}")
            return logo_url

        except Exception as e:
            print(f"  ⚠️  Failed to extract logo: {e}")
            import traceback
            traceback.print_exc()
            return None

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

    def analyze_form_schema_only(self, image_paths: List[str]) -> Dict[str, Any]:
        """
        First call: Extract just the form schema (fields, sections, validation).

        Args:
            image_paths: All form images (2-10 JPEG images)

        Returns:
            Dict with 'form_structure' key containing sections and fields
        """
        import json

        print("\n" + "="*80)
        print("🔍 SCHEMA EXTRACTION (Call 1/2)")
        print("="*80)

        # Build image content for ALL images
        image_content = []
        for img_path in image_paths:
            img_base64 = self.encode_image_base64(img_path)
            image_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": img_base64
                }
            })

        # Schema-only prompt
        prompt = """Analyze these medical form images to extract the complete form data schema.

**IMPORTANT: DETECT TABLES**
If you see a TABLE structure (rows and columns for repeatable data like tracking visits, lab results, etc.):
- Use type: "array"  (REQUIRED - not "string"!)
- Use input_type: "table"  (REQUIRED)
- MUST include row_fields array defining ALL column/field structures (REQUIRED - never omit this!)

Return a JSON object with this exact structure:

{
  "form_structure": {
    "form_name": "suggested_form_name",
    "description": "Brief description",
    "patient_criteria": "Description of which type of patients or clinical scenarios this form is designed for (e.g., 'Pregnant women in antenatal care between 12-40 weeks gestation', 'Patients presenting with neurological symptoms requiring initial assessment', 'Follow-up consultation for chronic disease management')",
    "logo_info": {
      "has_logo": true/false,
      "logo_position": "top-left|top-center|top-right|other",
      "logo_description": "Brief description of the logo/letterhead if present (e.g., 'Hospital name with medical symbol', 'Clinic logo with tree emblem')",
      "facility_name": "Name of facility/clinic/hospital from logo or header if visible",
      "bounding_box": {
        "x_percent": 0.0,  // Left edge position as percentage of image width (0-100)
        "y_percent": 0.0,  // Top edge position as percentage of image height (0-100)
        "width_percent": 20.0,  // Logo width as percentage of image width
        "height_percent": 10.0  // Logo height as percentage of image height
      }
    },
    "sections": [
      {
        "name": "section_name_in_snake_case",
        "description": "What this section captures",
        "order": 1,
        "fields": [
          {
            "name": "field_name_in_snake_case",
            "label": "Human Readable Label",
            "type": "string|number|boolean|date|object|array",
            "input_type": "text_short|textarea|number|date|checkbox|radio|dropdown|table",
            "required": true/false,
            "unit": "mmHg|kg|cm|years (for numeric fields)",
            "range": [min, max],
            "description": "What this field captures",
            "row_fields": [
              {
                "name": "scan_type",
                "label": "Scan Type",
                "type": "string",
                "input_type": "text_short"
              },
              {
                "name": "date",
                "label": "Date",
                "type": "date",
                "input_type": "date"
              },
              {
                "name": "ga",
                "label": "GA",
                "type": "string",
                "input_type": "text_short"
              }
            ]
          }
        ]
      }
    ]
  }
}

**TABLE DETECTION - TWO PATTERNS**:

**Pattern 1: REGULAR TABLE (rows are entries)**
- **Detect**: Column headers are attribute names (Date, BP, Weight, Findings, etc.)
- **Detect**: Rows are empty/to be filled with data for each entry
- **Action**: type: "array", input_type: "table"
- **column_names**: REQUIRED - List ALL column header names EXACTLY as shown on form
- **row_fields**: REQUIRED - List ALL column headers as field definitions

Example:
```
| Date | BP  | Weight | Notes |
|------|-----|--------|-------|
|      |     |        |       |  <-- repeatable rows
|      |     |        |       |
```
REQUIRED OUTPUT:
{
  "name": "antenatal_visits",
  "type": "array",
  "input_type": "table",
  "column_names": ["Date", "BP", "Weight", "Notes"],  // MUST INCLUDE THIS!
  "row_fields": [
    {name: "date", label: "Date", type: "date", input_type: "date"},
    {name: "bp", label: "BP", type: "string", input_type: "text_short"},
    {name: "weight", label: "Weight", type: "number", input_type: "number"},
    {name: "notes", label: "Notes", type: "string", input_type: "textarea"}
  ]
}

**Pattern 2: TRANSPOSED TABLE (columns are entries)**
- **Detect**: Column headers are entry names (Dating Scan, NT Scan, Visit 1, Visit 2)
- **Detect**: Row labels are attribute names (Date, BP, Weight, GA, Findings)
- **Action**: TRANSPOSE - type: "array", input_type: "table_transposed"
- **column_names**: REQUIRED - List ALL column header names EXACTLY as shown
- **row_names**: REQUIRED - List ALL row label names EXACTLY as shown
- **row_fields**: REQUIRED - Add entry_type field + ALL row labels as fields

Example:
```
       | Dating Scan | NT Scan | Anomaly |
Date   |             |         |         |
GA     |             |         |         |
Liq    |             |         |         |
```
REQUIRED OUTPUT:
{
  "name": "usg_scans",
  "type": "array",
  "input_type": "table_transposed",  // Note: table_transposed
  "column_names": ["Dating Scan", "NT Scan", "Anomaly"],  // MUST INCLUDE!
  "row_names": ["Date", "GA", "Liq"],  // MUST INCLUDE!
  "row_fields": [
    {name: "scan_type", label: "Scan Type", type: "string", input_type: "text_short"},
    {name: "date", label: "Date", type: "date", input_type: "date"},
    {name: "ga", label: "GA", type: "string", input_type: "text_short"},
    {name: "liq", label: "Liq", type: "string", input_type: "text_short"}
  ]
}

**Example - USG Tracking Table (REQUIRED FORMAT)**:
```
Visual in form:              What you MUST return:
------------------           ---------------------
       |Dating|NT|Anom      {
Date   | X    |Y |Z           "name": "usg_scans",
Single/|      |  |             "label": "USG Scans",
Multi  |      |  |             "type": "array",                    <-- REQUIRED
GA     | A    |B |C           "input_type": "table_transposed",  <-- REQUIRED (transposed!)
Liq    | D    |E |F           "column_names": ["Dating Scan", "NT Scan", "Anomaly Scan"],  <-- REQUIRED
Pla    | G    |H |I           "row_names": ["Date", "Single/Multiple", "GA", "Liq", "Pla"],  <-- REQUIRED
                              "row_fields": [                    <-- REQUIRED (scan_type + ALL rows)
                                {"name": "scan_type", "label": "Scan Type", "type": "string", "input_type": "text_short"},
                                {"name": "date", "label": "Date", "type": "date", "input_type": "date"},
                                {"name": "single_multiple", "label": "Single/Multiple", "type": "string", "input_type": "text_short"},
                                {"name": "ga", "label": "GA", "type": "string", "input_type": "text_short"},
                                {"name": "liq", "label": "Liq", "type": "string", "input_type": "text_short"},
                                {"name": "pla", "label": "Pla", "type": "string", "input_type": "text_short"}
                              ]
                            }
```
**DO NOT return type: "string" for tables! MUST be type: "array" with row_fields!**

**CRITICAL - TABLE REQUIREMENTS**:
- ALWAYS use type="array" for tables (NEVER type="string")
- ALWAYS use input_type="table" for regular tables, input_type="table_transposed" for transposed
- ALWAYS include column_names array (NEVER omit this)
- ALWAYS include row_names array for transposed tables (NEVER omit this)
- ALWAYS include row_fields array with ALL field definitions (NEVER omit this)
- For Pattern 1 (regular): column_names + row_fields = column headers
- For Pattern 2 (transposed): column_names + row_names + row_fields (with scan_type + all row labels)
- Extract ALL fields from ALL pages of the form
- Be thorough and complete
- Return ONLY valid JSON, no additional text"""

        # Call Opus 4.5
        print("\n🤖 [CALL 1/2] Extracting form schema with Claude Opus 4.5...")
        print(f"📊 Model: {self.model}")
        print(f"📸 Processing {len(image_paths)} images")

        message = self.client.messages.create(
            model=self.model,  # claude-opus-4-5-20251101
            max_tokens=16384,  # Maximum allowed for Opus 4.5
            messages=[{
                "role": "user",
                "content": image_content + [{"type": "text", "text": prompt}]
            }]
        )

        # Parse response
        response_text = message.content[0].text
        print(f"\n✅ Received response from Claude ({len(response_text)} characters)")

        # Extract JSON from response (handle markdown code blocks)
        original_response = response_text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
            print("📝 Extracted JSON from ```json code block")
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            print("📝 Extracted JSON from ``` code block")
        else:
            print("📝 Using response as-is (no code block detected)")

        print(f"📏 JSON text length: {len(response_text)} characters")

        # Try to parse JSON with detailed error reporting
        try:
            result = json.loads(response_text)
            print("✅ Successfully parsed JSON")
            print(f"📦 Result keys: {list(result.keys())}")

            # Debug: Check for table fields with row_fields
            if 'form_structure' in result:
                table_count = 0
                for section in result['form_structure'].get('sections', []):
                    for field in section.get('fields', []):
                        if field.get('input_type') in ['table', 'table_transposed']:
                            table_count += 1
                            print(f"\n🔍 Table Field #{table_count}: {field.get('name')}")
                            print(f"   Type: {field.get('type')}")
                            print(f"   Input Type: {field.get('input_type')}")
                            print(f"   Has row_fields: {'row_fields' in field}")
                            if 'row_fields' in field:
                                print(f"   Row fields count: {len(field['row_fields'])}")
                                print(f"   Row fields: {[f.get('name') for f in field['row_fields']]}")
                            else:
                                print(f"   ⚠️  WARNING: Table/array field missing row_fields!")

                            # Check for column_names and row_names
                            print(f"   Has column_names: {'column_names' in field}")
                            if 'column_names' in field:
                                print(f"   Column names: {field['column_names']}")
                            else:
                                print(f"   ⚠️  WARNING: Missing column_names!")

                            print(f"   Has row_names: {'row_names' in field}")
                            if 'row_names' in field:
                                print(f"   Row names: {field['row_names']}")
                            elif field.get('input_type') == 'table_transposed':
                                print(f"   ⚠️  WARNING: Transposed table missing row_names!")

                            # Show full field if missing critical data
                            if not ('row_fields' in field and 'column_names' in field):
                                print(f"   Full field data: {field}")

            return result
        except json.JSONDecodeError as e:
            print(f"\n❌ JSON Parse Error at line {e.lineno}, column {e.colno}: {e.msg}")
            print(f"\n🔍 First 500 chars of JSON text:")
            print(response_text[:500])
            print(f"\n🔍 Last 500 chars of JSON text:")
            print(response_text[-500:])
            print(f"\n🔍 Error position context (±100 chars):")
            start = max(0, e.pos - 100)
            end = min(len(response_text), e.pos + 100)
            context = response_text[start:end]
            print(context)
            print(" " * (min(100, e.pos - start)) + "^ ERROR HERE")

            # Save full response to temp file for debugging
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write("=== ORIGINAL RESPONSE ===\n")
                f.write(original_response)
                f.write("\n\n=== EXTRACTED JSON ===\n")
                f.write(response_text)
                print(f"\n💾 Full response saved to: {f.name}")

            raise ValueError(f"Failed to parse JSON response from Claude: {e.msg} at position {e.pos}")

    def analyze_pdf_layout(self, image_paths: List[str], form_structure: Dict[str, Any]) -> Dict[str, Any]:
        """
        Second call: Extract detailed PDF layout template based on the form schema.

        Args:
            image_paths: All form images (2-10 JPEG images)
            form_structure: Previously extracted form structure (for context)

        Returns:
            Dict with 'pdf_template' key containing detailed layout configuration
        """
        import json

        # Build image content for ALL images
        image_content = []
        for img_path in image_paths:
            img_base64 = self.encode_image_base64(img_path)
            image_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": img_base64
                }
            })

        # Extract section names and field names for reference
        section_names = [s['name'] for s in form_structure.get('sections', [])]
        sections_str = ", ".join(section_names)

        # Extract ALL field names (especially tables) from schema
        all_fields = []
        table_fields = []
        for section in form_structure.get('sections', []):
            for field in section.get('fields', []):
                field_name = field.get('name')
                field_type = field.get('type')
                input_type = field.get('input_type', '')

                all_fields.append(field_name)

                # Track table fields specifically
                if field_type == 'array' and input_type.startswith('table'):
                    table_fields.append(f"{field_name} ({input_type})")

        fields_str = ", ".join(all_fields)
        tables_str = ", ".join(table_fields) if table_fields else "none"

        # PDF layout prompt
        prompt = f"""Analyze these medical form images to create a DETAILED PDF layout template.

The form has these sections: {sections_str}

**ALL FIELDS TO INCLUDE** (total {len(all_fields)}): {fields_str}

**TABLE FIELDS** (MUST be included): {tables_str}

Return a JSON object with this exact structure:

{{
  "pdf_template": {{
    "page_config": {{
      "size": "A4",
      "margins": {{"top": 40, "bottom": 40, "left": 50, "right": 50}},
      "header": {{
        "show_logo": true,
        "show_clinic_name": true,
        "title": "Form Title"
      }},
      "footer": {{
        "show_page_numbers": true,
        "show_timestamp": true
      }}
    }},
    "sections": [
      {{
        "id": "section_name",
        "title": "Section Title As Shown On Form",
        "layout": "single_column|two_column|three_column|table",
        "page_break_before": false,
        "fields": [
          {{
            "field_name": "field_name_from_schema",
            "label": "Field Label",
            "position": {{"column": 1, "row": 1, "order": 1}},
            "style": {{
              "font_size": 10,
              "bold": false,
              "width": 100
            }}
          }}
        ]
      }}
    ],
    "styling": {{
      "primary_color": "#0c3555",
      "accent_color": "#1d9e99",
      "section_header_size": 12,
      "field_label_size": 9,
      "field_value_size": 10
    }}
  }}
}}

**CRITICAL REQUIREMENTS**:

1. **Include EVERY field from the form** - both regular fields AND table fields:
   - Regular fields: text inputs, checkboxes, dates, etc.
   - Table fields: ALL tables must be included with field_name matching the schema
   - Do NOT skip or omit table fields - they are critical

2. **Visual layout**:
   - Match the VISUAL LAYOUT of the original form exactly
   - Preserve field positioning and column layout from the paper form
   - Use the same section ordering as the original form
   - For tables, use layout: "table" and include the field_name

3. **Field naming**:
   - field_name MUST exactly match the field names from the schema
   - For tables: use exact table names like "obstetric_history_table", "usg_scans_table", etc.

4. **Return ONLY valid JSON**, no additional text

Use Aneya color scheme: Navy #0c3555, Teal #1d9e99

**EXAMPLE for a table field**:
{{
  "id": "obstetric_history",
  "title": "Obstetric History",
  "layout": "table",
  "fields": [
    {{
      "field_name": "obstetric_history_table",
      "label": "Obstetric History Table",
      "position": {{"column": 1, "row": 1, "order": 1}},
      "style": {{"font_size": 9}}
    }}
  ]
}}"""

        # Call Opus 4.5
        print("\n🤖 [CALL 2/2] Extracting PDF layout template with Claude Opus 4.5...")
        print(f"📊 Model: {self.model}")
        print(f"📸 Processing {len(image_paths)} images")

        message = self.client.messages.create(
            model=self.model,  # claude-opus-4-5-20251101
            max_tokens=16384,  # Maximum allowed for Opus 4.5
            messages=[{
                "role": "user",
                "content": image_content + [{"type": "text", "text": prompt}]
            }]
        )

        # Parse response
        response_text = message.content[0].text
        print(f"\n✅ Received response from Claude ({len(response_text)} characters)")

        # Extract JSON from response (handle markdown code blocks)
        original_response = response_text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
            print("📝 Extracted JSON from ```json code block")
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            print("📝 Extracted JSON from ``` code block")
        else:
            print("📝 Using response as-is (no code block detected)")

        print(f"📏 JSON text length: {len(response_text)} characters")

        # Try to parse JSON with detailed error reporting
        try:
            result = json.loads(response_text)
            print("✅ Successfully parsed JSON")
            print(f"📦 Result keys: {list(result.keys())}")
            return result
        except json.JSONDecodeError as e:
            print(f"\n❌ JSON Parse Error at line {e.lineno}, column {e.colno}: {e.msg}")
            print(f"\n🔍 First 500 chars of JSON text:")
            print(response_text[:500])
            print(f"\n🔍 Last 500 chars of JSON text:")
            print(response_text[-500:])
            print(f"\n🔍 Error position context (±100 chars):")
            start = max(0, e.pos - 100)
            end = min(len(response_text), e.pos + 100)
            context = response_text[start:end]
            print(context)
            print(" " * (min(100, e.pos - start)) + "^ ERROR HERE")

            # Save full response to temp file for debugging
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write("=== ORIGINAL RESPONSE ===\n")
                f.write(original_response)
                f.write("\n\n=== EXTRACTED JSON ===\n")
                f.write(response_text)
                print(f"\n💾 Full response saved to: {f.name}")

            raise ValueError(f"Failed to parse JSON response from Claude: {e.msg} at position {e.pos}")

    def analyze_form_comprehensive(self, image_paths: List[str]) -> Dict[str, Any]:
        """
        Two-call comprehensive analysis using Opus 4.5.
        Call 1: Extract form schema
        Call 2: Extract PDF layout template

        Args:
            image_paths: All form images (2-10 JPEG images)

        Returns:
            Dict with 'form_structure' and 'pdf_template' keys
        """
        # Call 1: Extract schema
        schema_result = self.analyze_form_schema_only(image_paths)

        # Call 2: Extract PDF layout (using schema for context)
        pdf_result = self.analyze_pdf_layout(image_paths, schema_result['form_structure'])

        # Merge results
        return {
            "form_structure": schema_result['form_structure'],
            "pdf_template": pdf_result['pdf_template']
        }

    def analyze_images(self, heic_paths: List[str]) -> FormAnalysis:
        """
        Complete comprehensive analysis of form images using Opus 4.5.
        Extracts both form schema and PDF layout template.

        Args:
            heic_paths: List of paths to images (HEIC, JPEG, PNG)

        Returns:
            FormAnalysis object with complete analysis results including PDF template
        """
        # Step 1: Convert HEIC to JPEG and compress all images
        print("Processing images...")
        jpeg_paths = []
        for image_path in heic_paths:
            try:
                file_ext = Path(image_path).suffix.lower()

                # If HEIC, convert to JPEG (includes compression)
                if file_ext in ['.heic', '.heif']:
                    jpeg_path = self.convert_heic_to_jpeg(image_path)
                    jpeg_paths.append(jpeg_path)
                    print(f"  ✓ Converted {Path(image_path).name} from HEIC to JPEG")
                # If already JPEG or PNG, compress if needed
                elif file_ext in ['.jpg', '.jpeg', '.png']:
                    # Compress to ensure under 5MB Claude API limit
                    compressed_path = self.compress_image(image_path)
                    jpeg_paths.append(compressed_path)
                    print(f"  ✓ Processed {Path(image_path).name}")
                else:
                    print(f"  ⚠️  Skipping {Path(image_path).name} (unsupported format: {file_ext})")
            except Exception as e:
                print(f"  ✗ Failed to process {image_path}: {e}")

        if not jpeg_paths:
            raise ValueError("No images were successfully processed. Please upload JPEG, PNG, or HEIC images.")

        # Step 2: Comprehensive analysis with Opus 4.5
        print(f"\n🔍 Analyzing {len(jpeg_paths)} images with Claude Opus 4.5...")
        comprehensive_result = self.analyze_form_comprehensive(jpeg_paths)

        form_structure = comprehensive_result['form_structure']
        pdf_template = comprehensive_result['pdf_template']

        # Extract sections and count fields
        sections = form_structure['sections']
        total_fields = sum(len(section.get('fields', [])) for section in sections)

        print(f"  ✓ Extracted {len(sections)} sections with {total_fields} fields")
        print(f"  ✓ Generated PDF template with {len(pdf_template.get('sections', []))} layout sections")

        # Combine results
        return FormAnalysis(
            form_name=form_structure['form_name'],
            sections=sections,
            pdf_template=pdf_template,
            metadata={
                "description": form_structure.get('description', ''),
                "patient_criteria": form_structure.get('patient_criteria', ''),
                "logo_info": form_structure.get('logo_info', {
                    "has_logo": False,
                    "logo_position": None,
                    "logo_description": None,
                    "facility_name": None
                }),
                "total_fields": total_fields,
                "section_count": len(sections),
                "image_count": len(jpeg_paths),
                "model_used": "claude-opus-4-5-20251101"
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
