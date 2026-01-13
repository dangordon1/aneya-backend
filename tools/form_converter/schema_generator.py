"""
Schema Generator Module

Converts analyzed form data into Aneya-compatible schema format.
"""

from typing import Dict, Any, List


class SchemaGenerator:
    """Generates Aneya form schema from analyzed form data"""

    # Type mapping from form input types to Aneya schema types
    TYPE_MAPPING = {
        'text_short': 'string',
        'text_long': 'string',
        'textarea': 'string',
        'number': 'number',
        'date': 'string',
        'checkbox': 'boolean',
        'checkbox_group': 'object',
        'radio': 'string',
        'dropdown': 'string',
        'table': 'array',
        'table_transposed': 'array',
    }

    # Max length defaults by input type
    MAX_LENGTH_DEFAULTS = {
        'text_short': 200,
        'text_long': 500,
        'textarea': 2000,
        'radio': 100,
        'dropdown': 100,
    }

    def __init__(self, form_analysis):
        """
        Initialize generator with form analysis results.

        Args:
            form_analysis: FormAnalysis object from ImageAnalyzer
        """
        self.analysis = form_analysis
        self.form_name = form_analysis.form_name

    def generate_schema(self) -> Dict[str, Any]:
        """
        Generate complete Aneya form schema.

        Returns:
            Dictionary in Aneya schema format (sections as keys, each with description and fields)
        """
        schema = {}

        for section in self.analysis.sections:
            section_name = section['name']
            fields = section.get('fields', [])

            if not fields:
                continue

            # Always use object section format for consistency (frontend expects this)
            schema[section_name] = {
                "description": section.get('description', ''),
                "order": section.get('order', 0),
                "fields": [self._generate_field_schema(field) for field in fields]
            }

        return schema

    def _should_be_object_section(self, section: Dict[str, Any]) -> bool:
        """
        Determine if a section should be an object type.

        Sections like "vital_signs", "physical_exam_findings" are objects.
        Top-level fields like "chief_complaint" are not.

        Args:
            section: Section definition

        Returns:
            True if section should be type "object"
        """
        # Common object sections
        object_sections = {
            'vital_signs',
            'physical_exam_findings',
            'ultrasound_findings',
            'lab_results',
            'medical_history',
            'obstetric_history',
            'family_history',
            'menstrual_history',
            'sexual_history',
        }

        section_name = section['name']
        fields = section.get('fields', [])

        # If section name matches known patterns, it's an object
        if section_name in object_sections:
            return True

        # If section has more than 3 fields, likely an object
        if len(fields) > 3:
            return True

        # If all fields are simple types, keep flat
        return False

    def _generate_object_section(self, section: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate schema for an object-type section.

        Args:
            section: Section definition with fields

        Returns:
            Object section schema
        """
        fields_schema = {}

        for field in section.get('fields', []):
            field_name = field['name']
            fields_schema[field_name] = self._generate_field_schema(field)

        return {
            "type": "object",
            "description": section.get('description', f"{section['name']} data"),
            "fields": fields_schema
        }

    def _generate_field_schema(self, field: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate schema for a single field.

        Args:
            field: Field definition

        Returns:
            Field schema in Aneya format (includes name, label, type, etc.)
        """
        input_type = field.get('input_type', 'text_short')
        field_type = self.TYPE_MAPPING.get(input_type, 'string')

        schema = {
            "name": field.get('name'),
            "label": field.get('label', field.get('name', '')),
            "type": field_type,
            "input_type": input_type,
            "required": field.get('required', False),
            "description": field.get('description', field.get('label', '')),
        }

        # Add type-specific attributes
        if field_type == 'number':
            if 'unit' in field and field['unit']:
                schema['unit'] = field['unit']
            if 'range' in field and field['range']:
                schema['range'] = field['range']

        elif field_type == 'string':
            # Add max_length for string fields
            if 'max_length' in field:
                schema['max_length'] = field['max_length']
            elif input_type in self.MAX_LENGTH_DEFAULTS:
                schema['max_length'] = self.MAX_LENGTH_DEFAULTS[input_type]

            # Add format for date fields
            if input_type == 'date':
                schema['format'] = 'YYYY-MM-DD'

        elif field_type == 'object':
            # For checkbox groups or nested objects
            schema['fields'] = {}

        elif field_type == 'array':
            # For tables/repeatable data structures
            if 'row_fields' in field and field['row_fields']:
                # Table with defined column structure
                schema['row_fields'] = field['row_fields']
            else:
                # Simple array
                schema['item_type'] = 'string'

            # Preserve table metadata for editability
            if 'column_names' in field:
                schema['column_names'] = field['column_names']

            if 'row_names' in field:
                schema['row_names'] = field['row_names']

            # Preserve input_type to distinguish table vs table_transposed
            if 'input_type' in field:
                schema['input_type'] = field['input_type']

        # Generate extraction hints
        schema['extraction_hints'] = self._generate_extraction_hints(field)

        return schema

    def _generate_extraction_hints(self, field: Dict[str, Any]) -> List[str]:
        """
        Generate extraction hints for LLM-based auto-fill.

        Args:
            field: Field definition

        Returns:
            List of extraction hint strings
        """
        hints = []

        # Add field label
        label = field.get('label', '')
        if label:
            hints.append(label.lower())

        # Add field name variants
        field_name = field.get('name', '')
        if field_name:
            # Convert snake_case to words
            words = field_name.replace('_', ' ')
            if words.lower() not in hints:
                hints.append(words.lower())

        # Add common medical abbreviations
        abbreviations = self._get_common_abbreviations(field_name)
        hints.extend(abbreviations)

        # Remove duplicates while preserving order
        seen = set()
        unique_hints = []
        for hint in hints:
            if hint.lower() not in seen:
                seen.add(hint.lower())
                unique_hints.append(hint)

        return unique_hints[:10]  # Limit to 10 hints

    def _get_common_abbreviations(self, field_name: str) -> List[str]:
        """
        Get common medical abbreviations for a field name.

        Args:
            field_name: Field name in snake_case

        Returns:
            List of common abbreviations
        """
        # Common medical abbreviations
        abbreviations_map = {
            'blood_pressure': ['BP'],
            'systolic_bp': ['systolic', 'SBP'],
            'diastolic_bp': ['diastolic', 'DBP'],
            'heart_rate': ['HR', 'pulse', 'bpm'],
            'temperature': ['temp', 'T'],
            'respiratory_rate': ['RR', 'resp rate'],
            'oxygen_saturation': ['O2 sat', 'SpO2', 'sats'],
            'blood_glucose': ['BG', 'sugar', 'glucose'],
            'body_mass_index': ['BMI'],
            'hemoglobin': ['Hb', 'Hgb'],
            'white_blood_cell': ['WBC'],
            'red_blood_cell': ['RBC'],
            'last_menstrual_period': ['LMP'],
            'estimated_delivery_date': ['EDD'],
            'gestational_age': ['GA'],
            'fetal_heart_rate': ['FHR'],
        }

        result = []
        for key, abbrevs in abbreviations_map.items():
            if key in field_name.lower():
                result.extend(abbrevs)

        return result

    def generate_python_code(self) -> str:
        """
        Generate Python code for the schema definition.

        Returns:
            Python code string ready to add to form_schemas.py
        """
        schema = self.generate_schema()
        schema_name = f"{self.form_name.upper()}_FORM_SCHEMA"

        code_lines = [
            f"# {self.analysis.metadata.get('description', self.form_name.replace('_', ' ').title())}",
            f"{schema_name} = {{",
        ]

        # Generate schema dict
        code_lines.extend(self._dict_to_python_code(schema, indent=1))
        code_lines.append("}")

        return "\n".join(code_lines)

    def _dict_to_python_code(self, obj: Any, indent: int = 0) -> List[str]:
        """
        Convert dictionary to formatted Python code lines.

        Args:
            obj: Object to convert (dict, list, or primitive)
            indent: Indentation level

        Returns:
            List of code lines
        """
        indent_str = "    " * indent
        lines = []

        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, dict):
                    lines.append(f'{indent_str}"{key}": {{')
                    lines.extend(self._dict_to_python_code(value, indent + 1))
                    lines.append(f'{indent_str}}},')
                elif isinstance(value, list):
                    lines.append(f'{indent_str}"{key}": {repr(value)},')
                else:
                    lines.append(f'{indent_str}"{key}": {repr(value)},')
        else:
            return [f"{indent_str}{repr(obj)}"]

        return lines

    def generate_summary(self) -> str:
        """
        Generate a human-readable summary of the schema.

        Returns:
            Summary string
        """
        total_fields = self.analysis.metadata.get('total_fields', 0)
        section_count = len(self.analysis.sections)

        lines = [
            f"Form: {self.form_name}",
            f"Description: {self.analysis.metadata.get('description', 'N/A')}",
            f"Sections: {section_count}",
            f"Total Fields: {total_fields}",
            "",
            "Sections:",
        ]

        for section in self.analysis.sections:
            field_count = len(section.get('fields', []))
            lines.append(f"  - {section['name']}: {field_count} fields")
            for field in section.get('fields', [])[:5]:  # Show first 5 fields
                field_type = field.get('type', 'string')
                unit = field.get('unit', '')
                unit_str = f" ({unit})" if unit else ""
                lines.append(f"      • {field['name']}: {field_type}{unit_str}")
            if len(section.get('fields', [])) > 5:
                lines.append(f"      ... and {len(section['fields']) - 5} more")

        return "\n".join(lines)
