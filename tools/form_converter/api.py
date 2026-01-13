"""
Form Converter API

Programmatic interface for the form converter tool.
Allows calling form conversion from API endpoints or other Python code.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .image_analyzer import ImageAnalyzer, FormAnalysis
from .schema_generator import SchemaGenerator
from .migration_generator import MigrationGenerator


@dataclass
class FormConversionResult:
    """Result of form conversion"""
    success: bool
    form_name: str
    specialty: str
    schema: Dict[str, Any]
    pdf_template: Dict[str, Any]  # PDF layout configuration
    schema_code: str
    migration_sql: Optional[str] = None
    typescript_types: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class FormConverterAPI:
    """Programmatic API for form conversion"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the API.

        Args:
            api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY env var.
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY env var or pass api_key parameter.")

    def convert_from_files(
        self,
        image_files: List[str],
        form_name: str,
        specialty: str,
        generate_migration: bool = True,
        generate_typescript: bool = True,
    ) -> FormConversionResult:
        """
        Convert form from image files.

        Args:
            image_files: List of paths to image files (HEIC, JPEG, or PNG)
            form_name: Name for the form in snake_case
            specialty: Medical specialty (e.g., 'cardiology', 'neurology')
            generate_migration: Whether to generate SQL migration
            generate_typescript: Whether to generate TypeScript types

        Returns:
            FormConversionResult with schema and optional migration/typescript
        """
        try:
            # Initialize analyzer
            analyzer = ImageAnalyzer(api_key=self.api_key)

            # Analyze images
            analysis = analyzer.analyze_images(image_files)

            # Override form name and add specialty to metadata
            analysis.form_name = form_name
            analysis.metadata['specialty'] = specialty

            # Generate schema
            schema_gen = SchemaGenerator(analysis)
            schema_dict = schema_gen.generate_schema()
            schema_code = schema_gen.generate_python_code()

            # Generate migration if requested
            migration_sql = None
            if generate_migration:
                migration_gen = MigrationGenerator(analysis, schema_dict)
                migration_sql = migration_gen.generate_migration()

            # Generate TypeScript types if requested
            typescript_types = None
            if generate_typescript:
                migration_gen = MigrationGenerator(analysis, schema_dict)
                typescript_types = migration_gen.generate_typescript_types()

            return FormConversionResult(
                success=True,
                form_name=form_name,
                specialty=specialty,
                schema=schema_dict,
                pdf_template=analysis.pdf_template,  # Include PDF template
                schema_code=schema_code,
                migration_sql=migration_sql,
                typescript_types=typescript_types,
                metadata=analysis.metadata
            )

        except Exception as e:
            return FormConversionResult(
                success=False,
                form_name=form_name,
                specialty=specialty,
                schema={},
                pdf_template={},  # Empty template on error
                schema_code="",
                error=str(e)
            )

    def convert_from_uploaded_files(
        self,
        uploaded_files: List[bytes],
        filenames: List[str],
        form_name: str,
        specialty: str,
        generate_migration: bool = True,
        generate_typescript: bool = True,
    ) -> FormConversionResult:
        """
        Convert form from uploaded file bytes.

        Args:
            uploaded_files: List of file bytes
            filenames: List of original filenames
            form_name: Name for the form in snake_case
            specialty: Medical specialty
            generate_migration: Whether to generate SQL migration
            generate_typescript: Whether to generate TypeScript types

        Returns:
            FormConversionResult with schema and optional migration/typescript
        """
        # Create temporary directory for uploaded files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # Save uploaded files to temp directory
            temp_files = []
            for file_bytes, filename in zip(uploaded_files, filenames):
                temp_file = temp_dir_path / filename
                temp_file.write_bytes(file_bytes)
                temp_files.append(str(temp_file))

            # Call convert_from_files with temp files
            return self.convert_from_files(
                image_files=temp_files,
                form_name=form_name,
                specialty=specialty,
                generate_migration=generate_migration,
                generate_typescript=generate_typescript
            )

    def validate_form_name(self, form_name: str) -> tuple[bool, str]:
        """
        Validate form name.

        Args:
            form_name: Proposed form name

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not form_name:
            return False, "Form name is required"

        if not form_name.replace('_', '').isalnum():
            return False, "Form name must be in snake_case (letters, numbers, underscores only)"

        if len(form_name) < 3:
            return False, "Form name must be at least 3 characters"

        if len(form_name) > 50:
            return False, "Form name must be less than 50 characters"

        # Check for reserved names
        reserved_names = ['admin', 'user', 'patient', 'doctor', 'system', 'config']
        if form_name in reserved_names:
            return False, f"'{form_name}' is a reserved name"

        return True, ""

    def validate_specialty(self, specialty: str) -> tuple[bool, str]:
        """
        Validate specialty name.

        Args:
            specialty: Proposed specialty

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not specialty:
            return False, "Specialty is required"

        if not specialty.replace('_', '').isalnum():
            return False, "Specialty must be in snake_case (letters, numbers, underscores only)"

        if len(specialty) < 3:
            return False, "Specialty must be at least 3 characters"

        if len(specialty) > 50:
            return False, "Specialty must be less than 50 characters"

        return True, ""

    def estimate_cost(self, num_images: int) -> Dict[str, Any]:
        """
        Estimate API cost for converting a form.

        Args:
            num_images: Number of images to process

        Returns:
            Dict with cost estimates
        """
        # Claude Sonnet 4.5 pricing (approximate)
        # Input: $3 per million tokens
        # Output: $15 per million tokens

        # Rough estimates based on image size and response length
        images_per_batch = 2
        batches = (num_images + images_per_batch - 1) // images_per_batch  # Ceiling division

        # Each image ~1500 tokens, each response ~1000 tokens
        input_tokens = num_images * 1500 + batches * 500  # Images + prompts
        output_tokens = batches * 1000

        input_cost = (input_tokens / 1_000_000) * 3.0
        output_cost = (output_tokens / 1_000_000) * 15.0
        total_cost = input_cost + output_cost

        return {
            "num_images": num_images,
            "estimated_batches": batches,
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": output_tokens,
            "estimated_cost_usd": round(total_cost, 4),
            "breakdown": {
                "input_cost_usd": round(input_cost, 4),
                "output_cost_usd": round(output_cost, 4)
            }
        }
