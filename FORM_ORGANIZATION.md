# Form Organization by Medical Specialty

This document describes how medical forms are organized in the Aneya backend.

## Overview

Forms are now organized by medical specialty to improve maintainability and scalability as the system grows.

## Structure

### Main Data Structure

```python
FORM_SCHEMAS_BY_SPECIALTY = {
    "obstetrics_gynecology": {
        "obgyn": OBGYN_FORM_SCHEMA,
        "infertility": INFERTILITY_FORM_SCHEMA,
        "antenatal": ANTENATAL_FORM_SCHEMA,
    },
    "cardiology": {
        "consultation_form": CONSULTATION_FORM_FORM_SCHEMA,
    }
}
```

## Current Specialties

### Obstetrics & Gynecology
- **obgyn**: General OB/GYN consultation forms
- **infertility**: Infertility-specific consultation forms
- **antenatal**: Antenatal/prenatal care forms

### Cardiology
- **consultation_form**: Cardiovascular examination and consultation forms

## API Usage

### Get Schema by Specialty

```python
from mcp_servers.form_schemas import get_schema_by_specialty

# Get OBGyn form from Obstetrics & Gynecology specialty
schema = get_schema_by_specialty('obstetrics_gynecology', 'obgyn')
```

### Get Schema (Backward Compatible)

```python
from mcp_servers.form_schemas import get_schema_for_form_type

# Still works for backward compatibility
schema = get_schema_for_form_type('obgyn')
```

### List Available Specialties

```python
from mcp_servers.form_schemas import list_specialties

specialties = list_specialties()
# Returns: ['obstetrics_gynecology', 'cardiology']
```

### List Forms in a Specialty

```python
from mcp_servers.form_schemas import list_forms_by_specialty

forms = list_forms_by_specialty('obstetrics_gynecology')
# Returns: ['obgyn', 'infertility', 'antenatal']
```

## Adding New Forms

### Using Form Converter Tool

When using the form converter tool to create new forms:

```bash
python -m tools.form_converter convert \
  --images "path/to/images/*.HEIC" \
  --form-name "new_form_name" \
  --specialty "cardiology"
```

Or use interactive mode:

```bash
python -m tools.form_converter interactive
```

The tool will prompt for specialty and guide you through the process.

### Manual Addition

1. **Define the schema** in `form_schemas.py`:
   ```python
   NEW_FORM_SCHEMA = {
       "section_name": {
           "type": "object",
           "fields": {...}
       }
   }
   ```

2. **Add to specialty group** in `FORM_SCHEMAS_BY_SPECIALTY`:
   ```python
   FORM_SCHEMAS_BY_SPECIALTY = {
       "your_specialty": {
           "new_form": NEW_FORM_SCHEMA,
       }
   }
   ```

3. **Update flat mapping** for backward compatibility:
   ```python
   _FLAT_SCHEMAS = {
       ...
       'new_form': NEW_FORM_SCHEMA,
   }
   ```

4. **Update form types list**:
   ```python
   FORM_TYPES = [..., 'new_form']
   ```

5. **Update specialty mapping**:
   ```python
   SPECIALTIES = {
       ...
       'your_specialty': [..., 'new_form'],
   }
   ```

## Migration Notes

- The organization maintains **backward compatibility** via `_FLAT_SCHEMAS`
- Existing code using `get_schema_for_form_type()` continues to work
- New code should use `get_schema_by_specialty()` for clarity
- All existing API endpoints continue to function unchanged

## Future Specialties

Potential specialties to add:
- Neurology
- Pediatrics
- Internal Medicine
- Emergency Medicine
- Surgery
- Psychiatry
- Dermatology
- Orthopedics

## File Location

All form schemas are defined in:
```
/Users/dgordon/aneya/aneya-backend/mcp_servers/form_schemas.py
```

## See Also

- Form Converter Tool: `/Users/dgordon/aneya/aneya-backend/tools/form_converter/`
- Database Migrations: `/Users/dgordon/aneya/aneya-backend/migrations/`
- TypeScript Types: `/Users/dgordon/aneya/aneya-frontend/src/types/`
