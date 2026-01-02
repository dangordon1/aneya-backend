"""
Form Converter CLI

Interactive command-line interface for converting medical form images
to Aneya schema definitions.
"""

import os
import sys
from pathlib import Path
from glob import glob
import click

from .image_analyzer import ImageAnalyzer
from .schema_generator import SchemaGenerator
from .migration_generator import MigrationGenerator


@click.group()
def cli():
    """Form Converter - Convert medical form images to Aneya schemas"""
    pass


@cli.command()
@click.option('--images', '-i', help='Glob pattern for HEIC images (e.g., "IMG_198*.HEIC")')
@click.option('--form-name', '-n', help='Form name in snake_case (e.g., "pediatric_assessment")')
@click.option('--specialty', '-s', help='Medical specialty (e.g., "cardiology", "obstetrics_gynecology")')
@click.option('--generate-migration/--no-migration', default=True, help='Generate SQL migration')
@click.option('--generate-typescript/--no-typescript', default=True, help='Generate TypeScript types')
@click.option('--output-dir', '-o', default=None, help='Output directory (defaults to aneya-backend)')
@click.option('--api-key', envvar='ANTHROPIC_API_KEY', help='Anthropic API key')
def convert(images, form_name, specialty, generate_migration, generate_typescript, output_dir, api_key):
    """Convert form images to Aneya schema (non-interactive mode)"""

    if not images:
        click.echo("Error: --images parameter is required", err=True)
        sys.exit(1)

    if not form_name:
        click.echo("Error: --form-name parameter is required", err=True)
        sys.exit(1)

    # Resolve image paths
    image_paths = glob(os.path.expanduser(images))
    if not image_paths:
        click.echo(f"Error: No images found matching pattern: {images}", err=True)
        sys.exit(1)

    click.echo(f"Found {len(image_paths)} images")

    # Determine output directory
    if output_dir is None:
        # Default to aneya-backend directory
        output_dir = Path(__file__).parent.parent.parent

    output_dir = Path(output_dir)

    # Run conversion
    run_conversion(
        image_paths=image_paths,
        form_name=form_name,
        specialty=specialty,
        generate_migration=generate_migration,
        generate_typescript=generate_typescript,
        output_dir=output_dir,
        api_key=api_key
    )


@cli.command()
@click.option('--api-key', envvar='ANTHROPIC_API_KEY', help='Anthropic API key')
def interactive(api_key):
    """Interactive mode - guided workflow for form conversion"""

    click.echo("=" * 60)
    click.echo("Form Converter - Interactive Mode")
    click.echo("=" * 60)
    click.echo()

    # Step 1: Get form name
    form_name = click.prompt(
        "What would you like to name this form? (snake_case)",
        type=str
    )

    # Validate form name
    if not form_name.replace('_', '').isalnum():
        click.echo("Error: Form name must be in snake_case (letters, numbers, underscores only)", err=True)
        sys.exit(1)

    # Step 2: Get specialty
    click.echo("\nAvailable specialties:")
    specialties = [
        "cardiology",
        "obstetrics_gynecology",
        "neurology",
        "pediatrics",
        "other"
    ]
    for i, spec in enumerate(specialties, 1):
        click.echo(f"  {i}. {spec}")

    specialty = click.prompt(
        "Medical specialty (or enter custom)",
        default="cardiology",
        type=str
    )

    # Step 3: Get images
    default_pattern = "/Users/dgordon/Downloads/IMG_*.HEIC"
    images_pattern = click.prompt(
        "Image files glob pattern",
        default=default_pattern,
        type=str
    )

    image_paths = glob(os.path.expanduser(images_pattern))

    if not image_paths:
        click.echo(f"Error: No images found matching: {images_pattern}", err=True)
        sys.exit(1)

    click.echo(f"\nFound {len(image_paths)} images:")
    for i, img_path in enumerate(image_paths, 1):
        click.echo(f"  {i}. {Path(img_path).name}")

    if not click.confirm("\nProceed with these images?"):
        click.echo("Cancelled.")
        sys.exit(0)

    # Step 4: Output options
    click.echo("\nOutput Options:")
    generate_migration = click.confirm("Generate SQL migration?", default=True)
    generate_typescript = click.confirm("Generate TypeScript types?", default=True)

    # Step 5: Determine output directory
    default_output = str(Path(__file__).parent.parent.parent)
    output_dir = click.prompt(
        "Output directory",
        default=default_output,
        type=click.Path(exists=True, file_okay=False, dir_okay=True)
    )

    output_dir = Path(output_dir)

    # Step 6: Confirm and run
    click.echo("\n" + "=" * 60)
    click.echo("Configuration Summary:")
    click.echo(f"  Form Name: {form_name}")
    click.echo(f"  Specialty: {specialty}")
    click.echo(f"  Images: {len(image_paths)} files")
    click.echo(f"  Generate Migration: {generate_migration}")
    click.echo(f"  Generate TypeScript: {generate_typescript}")
    click.echo(f"  Output Directory: {output_dir}")
    click.echo("=" * 60)

    if not click.confirm("\nStart conversion?"):
        click.echo("Cancelled.")
        sys.exit(0)

    # Run conversion
    run_conversion(
        image_paths=image_paths,
        form_name=form_name,
        specialty=specialty,
        generate_migration=generate_migration,
        generate_typescript=generate_typescript,
        output_dir=output_dir,
        api_key=api_key
    )


def run_conversion(
    image_paths: list,
    form_name: str,
    specialty: str = None,
    generate_migration: bool = True,
    generate_typescript: bool = True,
    output_dir: Path = None,
    api_key: str = None
):
    """
    Run the complete conversion workflow.

    Args:
        image_paths: List of image file paths
        form_name: Form name in snake_case
        generate_migration: Whether to generate SQL migration
        generate_typescript: Whether to generate TypeScript types
        output_dir: Output directory path
        api_key: Anthropic API key
    """
    try:
        # Initialize analyzer
        click.echo("\n" + "=" * 60)
        click.echo("Step 1: Analyzing Images")
        click.echo("=" * 60)

        analyzer = ImageAnalyzer(api_key=api_key)

        # Sort images by filename for consistent ordering
        image_paths = sorted(image_paths)

        # Analyze images
        analysis = analyzer.analyze_images(image_paths)

        # Override form name if provided
        if form_name:
            analysis.form_name = form_name

        # Generate schema
        click.echo("\n" + "=" * 60)
        click.echo("Step 2: Generating Schema")
        click.echo("=" * 60)

        schema_gen = SchemaGenerator(analysis)
        schema_dict = schema_gen.generate_schema()

        # Show summary
        click.echo("\n" + schema_gen.generate_summary())

        # Preview schema (skip prompts in non-interactive mode)
        schema_code = schema_gen.generate_python_code()
        click.echo("\n--- Schema Preview (first 1500 chars) ---")
        click.echo(schema_code[:1500])
        if len(schema_code) > 1500:
            click.echo(f"\n... ({len(schema_code) - 1500} more characters)")
        click.echo("--- End Preview ---")

        # Step 3: Save outputs
        click.echo("\n" + "=" * 60)
        click.echo("Step 3: Saving Outputs")
        click.echo("=" * 60)

        saved_files = []

        # Save schema to form_schemas.py
        schema_file = output_dir / "mcp_servers" / "form_schemas.py"
        if schema_file.exists():
            # Append to existing file
            schema_code = "\n\n" + schema_gen.generate_python_code()

            with open(schema_file, 'a') as f:
                f.write(schema_code)

            click.echo(f"  ✓ Updated {schema_file}")
            saved_files.append(str(schema_file))
        else:
            click.echo(f"  ⚠ Warning: {schema_file} not found. Schema not saved to file.")
            click.echo(f"    Please manually add the schema to form_schemas.py")

        # Generate migration
        if generate_migration:
            migration_gen = MigrationGenerator(analysis, schema_dict)
            migrations_dir = output_dir / "migrations"

            migration_file = migration_gen.save_migration(str(migrations_dir))
            click.echo(f"  ✓ Created {migration_file}")
            saved_files.append(migration_file)

        # Generate TypeScript types
        if generate_typescript:
            migration_gen = MigrationGenerator(analysis, schema_dict)
            ts_types = migration_gen.generate_typescript_types()

            # Save to types directory
            types_dir = output_dir.parent / "aneya-frontend" / "src" / "types"
            if types_dir.exists():
                ts_file = types_dir / f"{form_name}.ts"
                ts_file.write_text(ts_types)
                click.echo(f"  ✓ Created {ts_file}")
                saved_files.append(str(ts_file))
            else:
                click.echo(f"  ⚠ Warning: Types directory not found at {types_dir}")
                click.echo(f"    TypeScript types generated but not saved")

        # Summary
        click.echo("\n" + "=" * 60)
        click.echo("Conversion Complete!")
        click.echo("=" * 60)
        click.echo(f"\nGenerated {len(saved_files)} files:")
        for filepath in saved_files:
            click.echo(f"  • {filepath}")

        click.echo("\nNext Steps:")
        click.echo("  1. Review the generated schema in form_schemas.py")
        if specialty:
            click.echo(f"  2. Add '{form_name}' to the '{specialty}' specialty in FORM_SCHEMAS_BY_SPECIALTY")
        else:
            click.echo("  2. Add the form to appropriate specialty in FORM_SCHEMAS_BY_SPECIALTY")
        click.echo("  3. Update _FLAT_SCHEMAS and FORM_TYPES lists")
        click.echo("  4. Update SPECIALTIES mapping")
        if generate_migration:
            click.echo("  5. Review and run the migration on your database")
        if generate_typescript:
            click.echo("  6. Create React form components using the TypeScript types")

        click.echo("\n✨ Done!")

    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        if click.confirm("\nShow full traceback?"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
def version():
    """Show version information"""
    from . import __version__
    click.echo(f"Form Converter v{__version__}")


if __name__ == '__main__':
    cli()
