"""
Migration Generator Module

Generates SQL migration files for new form types following Aneya patterns.
"""

from datetime import date
from pathlib import Path
from typing import Dict, Any, List
from jinja2 import Environment, FileSystemLoader


class MigrationGenerator:
    """Generates SQL migration files for Aneya forms"""

    def __init__(self, form_analysis, schema_dict: Dict[str, Any]):
        """
        Initialize generator with form analysis and schema.

        Args:
            form_analysis: FormAnalysis object from ImageAnalyzer
            schema_dict: Generated schema dictionary
        """
        self.analysis = form_analysis
        self.schema = schema_dict
        self.form_name = form_analysis.form_name

        # Setup Jinja2 environment
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))

    def generate_migration(self, migration_number: int = None) -> str:
        """
        Generate SQL migration file content.

        Args:
            migration_number: Migration number (e.g., 14 for "014_..."). Auto-detected if None.

        Returns:
            SQL migration content
        """
        # Auto-detect migration number if not provided
        if migration_number is None:
            migration_number = self._detect_next_migration_number()

        # Prepare template variables
        template_vars = {
            'form_name': self.form_name,
            'form_name_title': self._to_title_case(self.form_name),
            'form_name_upper': self.form_name.upper(),
            'description': self.analysis.metadata.get('description', f'{self._to_title_case(self.form_name)} consultation forms'),
            'created_date': date.today().isoformat(),
            'migration_number': f"{migration_number:03d}",
            'sections': self._prepare_sections_for_template(),
        }

        # Render template
        template = self.jinja_env.get_template('migration.sql.jinja2')
        return template.render(**template_vars)

    def save_migration(self, output_dir: str, migration_number: int = None) -> str:
        """
        Save migration to file.

        Args:
            output_dir: Directory to save migration (e.g., /path/to/migrations/)
            migration_number: Migration number. Auto-detected if None.

        Returns:
            Path to saved migration file
        """
        if migration_number is None:
            migration_number = self._detect_next_migration_number()

        # Generate migration content
        migration_content = self.generate_migration(migration_number)

        # Create filename
        filename = f"{migration_number:03d}_create_{self.form_name}_forms.sql"
        filepath = Path(output_dir) / filename

        # Ensure directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Write file
        filepath.write_text(migration_content)

        return str(filepath)

    def _detect_next_migration_number(self) -> int:
        """
        Detect the next migration number by scanning existing migrations.

        Returns:
            Next migration number
        """
        # Look for migrations in standard location
        migrations_dir = Path(__file__).parent.parent.parent / "migrations"

        if not migrations_dir.exists():
            return 14  # Default starting number

        # Find highest numbered migration
        max_num = 0
        for migration_file in migrations_dir.glob("*.sql"):
            # Extract number from filename (e.g., "008_create_infertility_forms.sql" -> 8)
            try:
                num_str = migration_file.name.split('_')[0]
                num = int(num_str)
                max_num = max(max_num, num)
            except (ValueError, IndexError):
                continue

        return max_num + 1

    def _to_title_case(self, snake_case_str: str) -> str:
        """
        Convert snake_case to Title Case.

        Args:
            snake_case_str: String in snake_case

        Returns:
            String in Title Case
        """
        return ' '.join(word.capitalize() for word in snake_case_str.split('_'))

    def _prepare_sections_for_template(self) -> List[Dict[str, Any]]:
        """
        Prepare sections data for Jinja2 template.

        Returns:
            List of section dictionaries with example values
        """
        sections = []

        for section in self.analysis.sections:
            section_data = {
                'name': section['name'],
                'description': section.get('description', ''),
                'fields': []
            }

            for field in section.get('fields', []):
                field_data = {
                    'name': field['name'],
                    'description': field.get('description', field.get('label', '')),
                    'example_value': self._get_example_value(field)
                }
                section_data['fields'].append(field_data)

            sections.append(section_data)

        return sections

    def _get_example_value(self, field: Dict[str, Any]) -> str:
        """
        Get example value for a field based on its type.

        Args:
            field: Field definition

        Returns:
            Example value as string for documentation
        """
        field_type = field.get('type', 'string')
        input_type = field.get('input_type', 'text_short')

        if field_type == 'number':
            if 'range' in field and field['range']:
                # Use midpoint of range
                min_val, max_val = field['range']
                example = (min_val + max_val) // 2
            else:
                example = 0
            return str(example)

        elif field_type == 'boolean':
            return 'false'

        elif input_type == 'date':
            return '"2025-01-15"'

        elif input_type == 'textarea':
            return '"Long text description..."'

        elif input_type == 'radio' or input_type == 'dropdown':
            return '"option1"'

        else:
            # String field
            return f'"{field.get("label", "value")}"'

    def generate_typescript_types(self) -> str:
        """
        Generate TypeScript type definitions for the form.

        Returns:
            TypeScript interface definitions
        """
        form_name_pascal = ''.join(word.capitalize() for word in self.form_name.split('_'))

        lines = [
            f"// {form_name_pascal} Form Types",
            f"// Generated by form_converter tool",
            "",
            f"export interface {form_name_pascal}FormData {{",
        ]

        # Generate fields from schema
        for section in self.analysis.sections:
            section_name = section['name']
            fields = section.get('fields', [])

            if not fields:
                continue

            lines.append(f"  // {section.get('description', section_name)}")

            for field in fields:
                field_name = field['name']
                ts_type = self._get_typescript_type(field)
                is_required = field.get('required', False)
                optional = '' if is_required else '?'
                description = field.get('description', '')

                if description:
                    lines.append(f"  /** {description} */")

                lines.append(f"  {field_name}{optional}: {ts_type};")

            lines.append("")

        lines.append("}")
        lines.append("")

        # Add form input/output interfaces
        lines.extend([
            f"export interface Create{form_name_pascal}FormInput {{",
            f"  form_type: 'pre_consultation' | 'during_consultation';",
            f"  status?: 'draft' | 'partial' | 'completed';",
            f"  appointment_id?: string;",
            f"  {self.form_name}_data: Partial<{form_name_pascal}FormData>;",
            "}",
            "",
            f"export interface {form_name_pascal}Form {{",
            f"  id: string;",
            f"  patient_id: string;",
            f"  appointment_id: string | null;",
            f"  form_type: 'pre_consultation' | 'during_consultation';",
            f"  status: 'draft' | 'partial' | 'completed';",
            f"  {self.form_name}_data: {form_name_pascal}FormData;",
            f"  created_at: string;",
            f"  updated_at: string;",
            "}",
        ])

        return "\n".join(lines)

    def _get_typescript_type(self, field: Dict[str, Any]) -> str:
        """
        Get TypeScript type for a field.

        Args:
            field: Field definition

        Returns:
            TypeScript type string
        """
        field_type = field.get('type', 'string')
        input_type = field.get('input_type', 'text_short')

        if field_type == 'number':
            return 'number'
        elif field_type == 'boolean':
            return 'boolean'
        elif field_type == 'object':
            # Nested object - would need recursive handling
            return 'Record<string, any>'
        elif input_type == 'date':
            return 'string'  # ISO date string
        else:
            return 'string'
