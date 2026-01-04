"""
Table Classifier Module

LLM-based classifier that analyzes form table structures to determine:
1. Data source type (visit_history, lab_results, scan_results, etc.)
2. Whether table references previous consultations
3. Field mappings to external data sources
"""

import json
from typing import Dict, Any, List, Optional
from anthropic import Anthropic
import os


class TableClassifier:
    """
    LLM-based classifier for medical form tables.
    Uses Claude to intelligently classify table data sources.
    """

    DATA_SOURCE_TYPES = [
        "visit_history",       # Sequential visits/appointments with dates
        "lab_results",         # Blood tests, lab investigations
        "scan_results",        # Ultrasound, MRI, CT scans
        "medication_history",  # Current/past medications
        "vitals_history",      # BP, weight, temperature tracking
        "vaccination_records", # Immunization tracking
        "previous_consultation", # References prior form completion
        "manual_entry"         # No external data source
    ]

    CLASSIFICATION_PROMPT = """Analyze this medical form table and classify its data source.

Table Information:
- Name: {table_name}
- Description: {table_description}
- Columns: {column_names}
- Row Fields: {row_fields}

Form Context:
- Form Type: {form_name}
- Specialty: {specialty}
- Form Description: {form_description}

Available Data Sources:
1. visit_history - Sequential patient visits/appointments with dates (e.g., antenatal visits tracking BP, weight over time)
2. lab_results - Blood tests, lab investigations (CBC, glucose, hemoglobin, liver function tests, etc.)
3. scan_results - Imaging results (ultrasound scans, MRI, CT scans, X-rays)
4. medication_history - Current and past medications with dosage, frequency, start/stop dates
5. vitals_history - Vital sign measurements (blood pressure, weight, temperature, heart rate)
6. vaccination_records - Immunization tracking (vaccine name, date, batch number)
7. previous_consultation - References data from a prior consultation using this same form type (look for phrases like "previous visit", "last consultation", "since last", "changes from last")
8. manual_entry - No external data, doctor manually fills in during current consultation

Analysis Instructions:
1. Based on column names and field types, which data source type best matches this table?
   - Look for temporal indicators (date columns, visit numbers, sequential data)
   - Look for result/measurement columns (test results, scan findings, vital measurements)
   - Look for medication-specific fields (dosage, frequency, route)

2. Does this table track progression/changes from previous consultations?
   - Keywords: "previous visit", "last consultation", "since last visit", "progression", "changes", "comparison"
   - Column names suggesting historical comparison
   - Description mentioning tracking over time

3. How would table columns map to available external data fields?
   - Map table column names to likely database field names
   - Example: "BP" → "blood_pressure", "Date" → "visit_date" or "test_date"

Return ONLY valid JSON in this exact format (no markdown, no code blocks):
{{
  "data_source_type": "one of the 8 types above",
  "references_previous_consultation": true or false,
  "external_data_mappings": {{
    "table_column_name": "external_field_name"
  }},
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of why you classified it this way"
}}

IMPORTANT: Return ONLY the JSON object, nothing else."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the classifier with Anthropic API key.

        Args:
            api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY env var.
        """
        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"  # Claude Sonnet 4

    async def classify_table(
        self,
        table_field: Dict[str, Any],
        form_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Classify a single table field.

        Args:
            table_field: Table definition with row_fields, column_names, etc.
            form_context: Form name, specialty, description for context

        Returns:
            {
                "data_source_type": str,
                "references_previous_consultation": bool,
                "external_data_mappings": dict,
                "confidence": float,
                "reasoning": str
            }
        """
        try:
            # Extract table information
            table_name = table_field.get("name", "unknown")
            table_description = table_field.get("description", "")
            column_names = table_field.get("column_names", [])

            # Format row fields for prompt
            row_fields_info = []
            for row_field in table_field.get("row_fields", []):
                row_fields_info.append({
                    "name": row_field.get("name"),
                    "type": row_field.get("type"),
                    "label": row_field.get("label"),
                    "unit": row_field.get("unit", "")
                })

            # Build prompt
            prompt = self.CLASSIFICATION_PROMPT.format(
                table_name=table_name,
                table_description=table_description,
                column_names=json.dumps(column_names),
                row_fields=json.dumps(row_fields_info, indent=2),
                form_name=form_context.get("form_name", ""),
                specialty=form_context.get("specialty", ""),
                form_description=form_context.get("description", "")
            )

            # Call Claude
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse response
            response_text = message.content[0].text.strip()

            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            classification = json.loads(response_text)

            # Validate classification
            if classification.get("data_source_type") not in self.DATA_SOURCE_TYPES:
                print(f"⚠️  Invalid data_source_type: {classification.get('data_source_type')}, defaulting to manual_entry")
                classification["data_source_type"] = "manual_entry"

            # Auto-correct references_previous_consultation based on data_source_type
            # These data source types inherently reference historical/previous consultation data
            historical_data_sources = [
                "visit_history",
                "vitals_history",
                "medication_history",
                "vaccination_records"
            ]

            if classification["data_source_type"] in historical_data_sources:
                if not classification.get("references_previous_consultation"):
                    print(f"  ⚙️  Auto-correcting: {classification['data_source_type']} inherently references previous consultations")
                    classification["references_previous_consultation"] = True

            refs_prev = "✓ refs prev" if classification.get("references_previous_consultation") else ""
            print(f"  ✓ Classified table '{table_name}': {classification['data_source_type']} (confidence: {classification.get('confidence', 0):.2f}) {refs_prev}")

            return classification

        except Exception as e:
            print(f"  ⚠️  Classification failed for table '{table_field.get('name')}': {e}")
            # Return safe default
            return {
                "data_source_type": "manual_entry",
                "references_previous_consultation": False,
                "external_data_mappings": {},
                "confidence": 0.0,
                "reasoning": f"Classification failed: {str(e)}"
            }

    async def classify_all_tables(
        self,
        form_schema: Dict[str, Any],
        form_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Classify all tables in a form schema.

        Args:
            form_schema: Form schema dict with sections and fields
            form_metadata: Form name, specialty, description, patient_criteria

        Returns:
            Table metadata structure for database storage:
            {
                "tables": {
                    "table_name": {
                        "data_source_type": str,
                        "references_previous_consultation": bool,
                        "external_data_mappings": dict,
                        "confidence": float,
                        "reasoning": str
                    }
                }
            }
        """
        print(f"\n🔍 Classifying tables for form: {form_metadata.get('form_name')}")

        table_classifications = {}
        table_count = 0

        # Iterate through sections and find table fields
        for section_name, section in form_schema.items():
            if not isinstance(section, dict):
                continue

            for field in section.get("fields", []):
                # Check if this is a table field
                if field.get("input_type") in ["table", "table_transposed"]:
                    table_count += 1
                    table_name = field.get("name")

                    print(f"\n  📊 Table #{table_count}: {table_name}")
                    print(f"     Input Type: {field.get('input_type')}")
                    print(f"     Columns: {field.get('column_names', [])}")

                    # Classify this table
                    classification = await self.classify_table(
                        table_field=field,
                        form_context=form_metadata
                    )

                    table_classifications[table_name] = classification

        print(f"\n✅ Classified {table_count} tables")

        return {
            "tables": table_classifications,
            "classification_timestamp": json.dumps({"$date": {"$numberLong": str(int(__import__('time').time() * 1000))}})
        }
