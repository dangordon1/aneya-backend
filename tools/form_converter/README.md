# Form Converter Tool

Convert medical form pictures (HEIC images) to Aneya form definitions using Claude's vision API.

## Features

- **HEIC to JPEG Conversion**: Automatically converts Apple HEIC images to JPEG
- **Multi-Stage Vision Analysis**: Uses Claude Vision API to analyze form structure, fields, and validation rules
- **Aneya Schema Generation**: Generates schemas matching existing Aneya patterns
- **SQL Migration Creation**: Creates JSONB-based migrations following Aneya conventions
- **TypeScript Type Generation**: Generates TypeScript interfaces for frontend integration
- **Interactive Mode**: User-friendly wizard for guided conversion

## Installation

Dependencies are already added to `requirements.txt`:
- `pillow>=10.0.0`
- `pillow-heif>=0.10.1`
- `jinja2>=3.1.2`

Install with:
```bash
cd /Users/dgordon/aneya/aneya-backend
pip install pillow pillow-heif jinja2
```

## Usage

### Interactive Mode (Recommended)

```bash
cd /Users/dgordon/aneya/aneya-backend
python -m tools.form_converter interactive
```

The wizard will guide you through:
1. Choosing a form name
2. Selecting images to analyze
3. Configuring output options
4. Reviewing generated schema
5. Saving outputs

### Direct Mode

```bash
python -m tools.form_converter convert \
  --images "/Users/dgordon/Downloads/IMG_198*.HEIC" \
  --form-name "pediatric_assessment" \
  --generate-migration \
  --generate-typescript
```

### Options

- `--images, -i`: Glob pattern for HEIC images (e.g., `"IMG_*.HEIC"`)
- `--form-name, -n`: Form name in snake_case (e.g., `"pediatric_assessment"`)
- `--generate-migration/--no-migration`: Generate SQL migration (default: yes)
- `--generate-typescript/--no-typescript`: Generate TypeScript types (default: yes)
- `--output-dir, -o`: Output directory (defaults to aneya-backend)
- `--api-key`: Anthropic API key (or use `ANTHROPIC_API_KEY` env var)

## Output Files

The tool generates:

1. **Schema Definition** - Added to `mcp_servers/form_schemas.py`:
   ```python
   PEDIATRIC_ASSESSMENT_FORM_SCHEMA = {
       "vital_signs": {
           "type": "object",
           "fields": {...}
       },
       ...
   }
   ```

2. **SQL Migration** - Created in `migrations/014_create_{form_name}_forms.sql`:
   - JSONB-based table structure
   - Indexes for performance
   - Triggers for updated_at
   - Documentation comments

3. **TypeScript Types** - Created in `aneya-frontend/src/types/{form_name}.ts`:
   - Form data interfaces
   - Input/output types
   - Field type definitions

## How It Works

### Stage 1: Form Structure Analysis
Analyzes first 2 images to identify:
- Major sections (e.g., "vital_signs", "medical_history")
- Section hierarchy and purpose
- Overall form structure

### Stage 2: Field Detail Extraction
Analyzes images 3-4 to extract:
- Field names and labels
- Field types (string, number, boolean, date)
- Input types (text, textarea, number, checkbox, etc.)
- Units and ranges for numeric fields
- Required vs optional fields

### Stage 3: Validation & Relationships
Analyzes images 5-6 to identify:
- Conditional fields (e.g., "show ultrasound if pregnant")
- Field groups and relationships
- Validation rules

### Schema Generation
Converts analysis to Aneya format:
- Maps field types to Aneya conventions
- Generates extraction hints for LLM auto-fill
- Follows existing patterns from OBGyn/Infertility/Antenatal forms

## Example Workflow

```bash
# 1. Run interactive mode
python -m tools.form_converter interactive

# Enter when prompted:
# Form name: pediatric_assessment
# Images: /Users/dgordon/Downloads/IMG_198*.HEIC
# Generate migration: Yes
# Generate TypeScript: Yes

# 2. Review generated schema
# 3. Confirm to save files

# 4. Update form_schemas.py:
# Add to get_schema_for_form_type():
#   'pediatric_assessment': PEDIATRIC_ASSESSMENT_FORM_SCHEMA

# Add to FORM_TYPES:
#   FORM_TYPES = ['obgyn', 'infertility', 'antenatal', 'pediatric_assessment']

# 5. Run migration on database
# 6. Create React form components
```

## Architecture

```
form_converter/
├── __init__.py                 # Package initialization
├── __main__.py                 # Module entry point
├── cli.py                      # Click-based CLI interface
├── image_analyzer.py           # HEIC conversion + Vision API
├── schema_generator.py         # Analysis → Aneya schema
├── migration_generator.py      # SQL + TypeScript generation
├── templates/
│   └── migration.sql.jinja2    # SQL migration template
└── README.md                   # This file
```

## Requirements

- Python 3.8+
- Anthropic API key (set `ANTHROPIC_API_KEY` env var)
- HEIC images (or JPEG/PNG also supported)
- Existing Aneya backend structure

## Troubleshooting

### "No images found"
- Check glob pattern matches your files
- Use absolute paths or expand ~ properly
- Ensure files have correct extensions

### "HEIC conversion failed"
- Ensure `pillow-heif` is installed: `pip install pillow-heif`
- Images must be readable HEIC format

### "Vision API error"
- Verify `ANTHROPIC_API_KEY` is set
- Check API quota and limits
- Ensure images are < 5MB each

### "Schema not generated correctly"
- Review image quality (should be clear scans)
- Try with more images (6 recommended, 3 minimum)
- Manually review and adjust generated schema

## Development

Run tests:
```bash
cd /Users/dgordon/aneya/aneya-backend
python -m pytest tools/form_converter/
```

## License

Part of the Aneya clinical decision support system.
