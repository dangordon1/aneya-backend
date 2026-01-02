# OB/GYN Forms API - Quick Reference

## Base URL
```
http://localhost:8000/api
```

## Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/obgyn-forms` | Create a new form |
| GET | `/obgyn-forms/{form_id}` | Get form by ID |
| GET | `/obgyn-forms/patient/{patient_id}` | Get all forms for patient |
| GET | `/obgyn-forms/appointment/{appointment_id}` | Get form for appointment |
| PUT | `/obgyn-forms/{form_id}` | Update a form |
| DELETE | `/obgyn-forms/{form_id}` | Delete a form |
| POST | `/obgyn-forms/validate` | Validate form section |

## Quick Examples

### 1. Create a Form
```bash
curl -X POST http://localhost:8000/api/obgyn-forms \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "appointment_id": "550e8400-e29b-41d4-a716-446655440001",
    "form_data": {
      "patient_demographics": {
        "age": 32,
        "date_of_birth": "1993-03-15",
        "ethnicity": "Caucasian"
      },
      "obstetric_history": {
        "gravidity": 2,
        "parity": 1,
        "abortions": 0
      },
      "gynecologic_history": {
        "menarche_age": 12,
        "last_menstrual_period": "2025-12-01",
        "cycle_length": 28,
        "menstrual_duration": 5
      }
    },
    "status": "draft"
  }'
```

### 2. Get a Form
```bash
curl http://localhost:8000/api/obgyn-forms/550e8400-e29b-41d4-a716-446655440002
```

### 3. Get All Patient Forms
```bash
curl http://localhost:8000/api/obgyn-forms/patient/550e8400-e29b-41d4-a716-446655440000
```

### 4. Get Appointment Form
```bash
curl http://localhost:8000/api/obgyn-forms/appointment/550e8400-e29b-41d4-a716-446655440001
```

### 5. Update a Form
```bash
curl -X PUT http://localhost:8000/api/obgyn-forms/550e8400-e29b-41d4-a716-446655440002 \
  -H "Content-Type: application/json" \
  -d '{
    "form_data": {
      "patient_demographics": {
        "age": 33,
        "date_of_birth": "1993-03-15",
        "ethnicity": "Caucasian"
      },
      "obstetric_history": {
        "gravidity": 2,
        "parity": 1,
        "abortions": 0
      },
      "gynecologic_history": {
        "menarche_age": 12,
        "last_menstrual_period": "2025-12-01",
        "cycle_length": 28,
        "menstrual_duration": 5
      }
    },
    "status": "completed"
  }'
```

### 6. Delete a Form
```bash
curl -X DELETE http://localhost:8000/api/obgyn-forms/550e8400-e29b-41d4-a716-446655440002
```

### 7. Validate a Form Section
```bash
curl -X POST http://localhost:8000/api/obgyn-forms/validate \
  -H "Content-Type: application/json" \
  -d '{
    "section_name": "patient_demographics",
    "section_data": {
      "age": 32,
      "date_of_birth": "1993-03-15",
      "ethnicity": "Caucasian"
    }
  }'
```

## Form Data Structure

### Required Sections
Every form must contain these three sections:

1. **patient_demographics** (object)
   - age (number or string)
   - date_of_birth (string: YYYY-MM-DD)
   - ethnicity (string)
   - occupation (string)
   - emergency_contact (string)

2. **obstetric_history** (object)
   - gravidity (number or string): Total pregnancies
   - parity (number or string): Term pregnancies
   - abortions (number or string): Spontaneous/induced abortions
   - living_children (number or string)
   - complications (array of strings)

3. **gynecologic_history** (object)
   - menarche_age (number or string): Age at first menstruation
   - last_menstrual_period (string: YYYY-MM-DD)
   - cycle_length (number): Days
   - menstrual_duration (number): Days
   - gynecologic_conditions (array of strings)

### Optional Sections
You can also include:

4. **medical_history** (object)
   - conditions (array)
   - medications (array)
   - surgeries (array)
   - allergies (array)

5. **physical_examination** (object)
   - general (string)
   - vital_signs (object)
   - abdominal_exam (string)
   - pelvic_exam (string)
   - findings (array)

6. **assessment_plan** (object)
   - diagnoses (array)
   - recommendations (array)
   - follow_up (string)

## Status Values
- `draft` - Form in progress
- `completed` - Form completed
- `reviewed` - Form reviewed by clinician
- `submitted` - Form officially submitted

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request (validation error) |
| 404 | Not Found |
| 500 | Internal Server Error |

## Error Response Format
```json
{
  "detail": "Error message describing what went wrong"
}
```

## Response Format

### Single Form Response
```json
{
  "id": "form-uuid",
  "patient_id": "patient-uuid",
  "appointment_id": "appointment-uuid or null",
  "form_data": {...},
  "status": "draft|completed|reviewed|submitted",
  "created_at": "2025-12-21T12:00:00Z",
  "updated_at": "2025-12-21T12:30:00Z"
}
```

### Multiple Forms Response
```json
{
  "success": true,
  "patient_id": "patient-uuid",
  "forms": [...],
  "count": 2
}
```

### Validation Response
```json
{
  "success": true,
  "section": "patient_demographics",
  "valid": true,
  "errors": [],
  "field_count": 5
}
```

## Field Validation Rules

### patient_demographics
- `age`: number or string
- `date_of_birth`: string (YYYY-MM-DD format)
- Other fields: any string value

### obstetric_history
- `gravidity`: number or string
- `parity`: number or string
- `abortions`: number or string
- `living_children`: number or string
- `complications`: array of strings

### gynecologic_history
- `menarche_age`: number or string
- `last_menstrual_period`: string (YYYY-MM-DD format)
- `cycle_length`: number
- `menstrual_duration`: number
- Other fields: flexible

## Implementation Checklist

- [ ] Database table `obgyn_forms` created in Supabase
- [ ] Environment variables configured (SUPABASE_URL, SUPABASE_SERVICE_KEY)
- [ ] FastAPI server running
- [ ] Test endpoints with curl or Postman
- [ ] Implement frontend form UI
- [ ] Add authentication/authorization
- [ ] Set up RLS policies in Supabase
- [ ] Configure audit logging
- [ ] Set up monitoring/alerts

## Common Scenarios

### Scenario 1: Pre-visit Intake Form
Create a draft form without an appointment:
```json
{
  "patient_id": "uuid",
  "form_data": {...},
  "status": "draft"
}
```

### Scenario 2: Visit-Specific Form
Create form linked to appointment:
```json
{
  "patient_id": "uuid",
  "appointment_id": "uuid",
  "form_data": {...},
  "status": "draft"
}
```

### Scenario 3: Form Completion Workflow
1. Create draft form
2. Validate sections as user fills out
3. Update form with completed data
4. Change status to "completed"
5. Mark as "reviewed" after clinician review

### Scenario 4: Retrieve Patient History
Get all forms for patient:
```
GET /api/obgyn-forms/patient/{patient_id}
```
Returns list ordered by newest first.

## Environment Setup

Required environment variables:
```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

## Testing

Run tests with:
```bash
pytest test_obgyn_forms.py -v
```

Or test individual endpoints:
```bash
# Test create endpoint
pytest test_obgyn_forms.py::TestOBGYNFormsCreation -v

# Test validation endpoint
pytest test_obgyn_forms.py::TestOBGYNFormsValidation -v
```

## Troubleshooting

**Issue**: 500 error "Supabase configuration not available"
- **Solution**: Check SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables

**Issue**: 404 error when getting form
- **Solution**: Verify the form_id exists. Use patient or appointment endpoints to find forms.

**Issue**: 400 error "Missing required section"
- **Solution**: Ensure form_data includes patient_demographics, obstetric_history, and gynecologic_history

**Issue**: Validation errors for data types
- **Solution**: Check field types match expected types (numbers, strings, dates)

## Best Practices

1. **Always validate before saving**: Call POST /validate for sections before updates
2. **Use UUIDs**: Patient and appointment IDs should be valid UUIDs
3. **Handle timestamps**: Don't manually set created_at/updated_at - database manages these
4. **Status workflow**: Follow draft → completed → reviewed pattern
5. **Error handling**: Always check response status codes
6. **Logging**: Check backend logs for detailed error information
7. **Pagination**: For patient forms, consider implementing pagination for large datasets
8. **Caching**: Consider caching frequently accessed forms on the frontend

## Related Documentation

- See `OBGYN_FORMS_API.md` for detailed endpoint documentation
- See `test_obgyn_forms.py` for comprehensive test examples
- See `migrations/001_create_obgyn_forms_table.sql` for database schema
