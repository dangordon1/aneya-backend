# Form Converter Changelog

## [1.0.0] - 2025-12-30

### Added - Initial Release

#### Core Features
- **HEIC to JPEG Conversion**: Automatic conversion with size optimization (<5MB for API)
- **Multi-Stage Vision Analysis**:
  - Stage 1: Form structure and sections
  - Stage 2: Detailed field extraction
  - Stage 3: Validation rules and relationships
- **Aneya Schema Generation**: Converts analysis to Aneya-compatible schema format
- **SQL Migration Generation**: JSONB-based migrations following Aneya patterns
- **TypeScript Type Generation**: Frontend interface definitions
- **Interactive CLI**: User-friendly wizard mode
- **Direct Mode**: Command-line arguments for automation
- **Specialty Support**: Organize forms by medical specialty

#### Components Created
- `image_analyzer.py` - HEIC conversion + Claude Vision API integration
- `schema_generator.py` - Schema format conversion and validation
- `migration_generator.py` - SQL and TypeScript code generation
- `cli.py` - Command-line interface (interactive + direct modes)
- `templates/migration.sql.jinja2` - Migration template

### Form Organization by Specialty

#### Reorganized `form_schemas.py`
- Created `FORM_SCHEMAS_BY_SPECIALTY` data structure
- Organized existing forms:
  - **Obstetrics & Gynecology**: obgyn, infertility, antenatal
  - **Cardiology**: consultation_form
- Added new helper functions:
  - `get_schema_by_specialty()` - Get schema within specialty
  - `list_specialties()` - List all specialties
  - `list_forms_by_specialty()` - List forms in a specialty
- Maintained backward compatibility via `_FLAT_SCHEMAS`
- Updated `FORM_TYPES` and `SPECIALTIES` mappings

### Testing
- Successfully converted 3 HEIC images (IMG_1986, IMG_1987, IMG_1989)
- Extracted 27 fields from cardiovascular examination form
- Generated:
  - Schema definition in `form_schemas.py`
  - Migration: `014_create_consultation_form_forms.sql`
  - TypeScript types: `consultation_form.ts`

### Documentation
- `README.md` - Comprehensive tool documentation
- `FORM_ORGANIZATION.md` - Specialty organization guide
- `CHANGELOG.md` - This file

### Dependencies
- `pillow>=10.0.0` - Image processing
- `pillow-heif>=0.10.1` - HEIC conversion
- `jinja2>=3.1.2` - Template rendering
- `anthropic==0.73.0` - Claude Vision API (already present)
- `click==8.1.8` - CLI framework (already present)

## Usage Examples

### Interactive Mode
```bash
python -m tools.form_converter interactive
```

### Direct Mode
```bash
python -m tools.form_converter convert \
  --images "/path/to/IMG_*.HEIC" \
  --form-name "new_form" \
  --specialty "cardiology"
```

### Using Reorganized Schemas
```python
from mcp_servers.form_schemas import get_schema_by_specialty, list_specialties

# List specialties
specialties = list_specialties()  # ['obstetrics_gynecology', 'cardiology']

# Get schema by specialty
schema = get_schema_by_specialty('cardiology', 'consultation_form')

# Backward compatible
schema = get_schema_for_form_type('consultation_form')  # Still works
```

## Breaking Changes
None - Full backward compatibility maintained.

## Known Issues
- Requires minimum 2 images for structure analysis (3+ recommended)
- Images must be < 5MB after conversion
- API calls may take 30-60 seconds for 6 images

## Future Enhancements
- [ ] Support for other image formats (JPEG, PNG) without conversion
- [ ] Batch processing for multiple forms
- [ ] Frontend component scaffolding
- [ ] MCP server wrapper for automation
- [ ] Support for more specialties (neurology, pediatrics, etc.)
- [ ] Schema validation against existing forms
- [ ] Auto-detection of form specialty from content
