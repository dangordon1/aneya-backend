# OB/GYN Forms API Documentation

This document describes the OB/GYN form endpoints added to the Aneya backend API.

## Overview

The OB/GYN Forms API provides a complete set of endpoints for managing obstetric and gynecological patient intake forms. Forms are stored in Supabase and support full CRUD operations, along with validation capabilities.

## Data Models

### OBGYNFormResponse

Standard response model for form operations:

```python
{
    "id": "form_uuid",
    "patient_id": "patient_uuid",
    "appointment_id": "appointment_uuid or null",
    "form_data": {
        "patient_demographics": {...},
        "obstetric_history": {...},
        "gynecologic_history": {...}
    },
    "status": "draft|completed|reviewed",
    "created_at": "2025-12-21T12:00:00Z",
    "updated_at": "2025-12-21T12:30:00Z"
}
```

### OBGYNFormCreateRequest

Request model for creating new forms:

```python
{
    "patient_id": "required_uuid",
    "appointment_id": "optional_uuid",
    "form_data": {
        "patient_demographics": {},
        "obstetric_history": {},
        "gynecologic_history": {}
    },
    "status": "draft"  # Optional, defaults to "draft"
}
```

### OBGYNFormUpdateRequest

Request model for updating forms:

```python
{
    "form_data": {
        "patient_demographics": {},
        "obstetric_history": {},
        "gynecologic_history": {}
    },
    "status": "completed"  # Optional
}
```

### OBGYNFormSectionRequest

Request model for section validation:

```python
{
    "section_name": "patient_demographics|obstetric_history|gynecologic_history|medical_history|physical_examination|assessment_plan",
    "section_data": {},
    "patient_id": "optional_uuid"
}
```

## Endpoints

### 1. POST /api/obgyn-forms

**Create a new OB/GYN form**

Creates a new form for a patient. Form data must include three required sections: patient_demographics, obstetric_history, and gynecologic_history.

**Request:**
```json
{
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "appointment_id": "550e8400-e29b-41d4-a716-446655440001",
    "form_data": {
        "patient_demographics": {
            "age": 32,
            "date_of_birth": "1993-03-15",
            "ethnicity": "Caucasian",
            "occupation": "Teacher"
        },
        "obstetric_history": {
            "gravidity": 2,
            "parity": 1,
            "abortions": 0,
            "living_children": 1,
            "complications": []
        },
        "gynecologic_history": {
            "menarche_age": 12,
            "last_menstrual_period": "2025-12-01",
            "cycle_length": 28,
            "menstrual_duration": 5
        }
    },
    "status": "draft"
}
```

**Response:**
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440002",
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "appointment_id": "550e8400-e29b-41d4-a716-446655440001",
    "form_data": {...},
    "status": "draft",
    "created_at": "2025-12-21T12:00:00Z",
    "updated_at": "2025-12-21T12:00:00Z"
}
```

**Error Responses:**
- `400 Bad Request`: Missing required form sections or invalid data types
- `500 Internal Server Error`: Database error or Supabase unavailable

---

### 2. GET /api/obgyn-forms/{form_id}

**Retrieve a form by ID**

Fetches a specific OB/GYN form using its unique identifier.

**Request:**
```
GET /api/obgyn-forms/550e8400-e29b-41d4-a716-446655440002
```

**Response:**
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440002",
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "appointment_id": "550e8400-e29b-41d4-a716-446655440001",
    "form_data": {...},
    "status": "draft",
    "created_at": "2025-12-21T12:00:00Z",
    "updated_at": "2025-12-21T12:00:00Z"
}
```

**Error Responses:**
- `404 Not Found`: Form ID does not exist
- `500 Internal Server Error`: Database error

---

### 3. GET /api/obgyn-forms/patient/{patient_id}

**Retrieve all forms for a patient**

Fetches all OB/GYN forms associated with a specific patient, ordered by creation date (newest first).

**Request:**
```
GET /api/obgyn-forms/patient/550e8400-e29b-41d4-a716-446655440000
```

**Response:**
```json
{
    "success": true,
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "forms": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440002",
            "patient_id": "550e8400-e29b-41d4-a716-446655440000",
            "appointment_id": "550e8400-e29b-41d4-a716-446655440001",
            "form_data": {...},
            "status": "draft",
            "created_at": "2025-12-21T12:00:00Z",
            "updated_at": "2025-12-21T12:00:00Z"
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440003",
            "patient_id": "550e8400-e29b-41d4-a716-446655440000",
            "appointment_id": null,
            "form_data": {...},
            "status": "completed",
            "created_at": "2025-12-20T14:30:00Z",
            "updated_at": "2025-12-20T15:00:00Z"
        }
    ],
    "count": 2
}
```

**Error Responses:**
- `500 Internal Server Error`: Database error

---

### 4. GET /api/obgyn-forms/appointment/{appointment_id}

**Retrieve form for a specific appointment**

Fetches the OB/GYN form associated with a particular appointment.

**Request:**
```
GET /api/obgyn-forms/appointment/550e8400-e29b-41d4-a716-446655440001
```

**Response:**
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440002",
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "appointment_id": "550e8400-e29b-41d4-a716-446655440001",
    "form_data": {...},
    "status": "draft",
    "created_at": "2025-12-21T12:00:00Z",
    "updated_at": "2025-12-21T12:00:00Z"
}
```

**Error Responses:**
- `404 Not Found`: No form exists for this appointment
- `500 Internal Server Error`: Database error

---

### 5. PUT /api/obgyn-forms/{form_id}

**Update an existing form**

Updates the form data and/or status for an existing form. Form data is validated before update.

**Request:**
```json
{
    "form_data": {
        "patient_demographics": {
            "age": 32,
            "date_of_birth": "1993-03-15",
            "ethnicity": "Caucasian",
            "occupation": "Teacher",
            "emergency_contact": "John Doe"
        },
        "obstetric_history": {
            "gravidity": 2,
            "parity": 1,
            "abortions": 0,
            "living_children": 1,
            "complications": []
        },
        "gynecologic_history": {
            "menarche_age": 12,
            "last_menstrual_period": "2025-12-01",
            "cycle_length": 28,
            "menstrual_duration": 5
        }
    },
    "status": "completed"
}
```

**Response:**
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440002",
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "appointment_id": "550e8400-e29b-41d4-a716-446655440001",
    "form_data": {...},
    "status": "completed",
    "created_at": "2025-12-21T12:00:00Z",
    "updated_at": "2025-12-21T12:30:00Z"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid form data structure
- `404 Not Found`: Form ID does not exist
- `500 Internal Server Error`: Database error

---

### 6. DELETE /api/obgyn-forms/{form_id}

**Delete a form**

Permanently deletes an OB/GYN form from the database.

**Request:**
```
DELETE /api/obgyn-forms/550e8400-e29b-41d4-a716-446655440002
```

**Response:**
```json
{
    "success": true,
    "message": "Form 550e8400-e29b-41d4-a716-446655440002 has been deleted",
    "form_id": "550e8400-e29b-41d4-a716-446655440002"
}
```

**Error Responses:**
- `404 Not Found`: Form ID does not exist
- `500 Internal Server Error`: Database error

---

### 7. POST /api/obgyn-forms/validate

**Validate a form section**

Validates a specific section of an OB/GYN form for data type correctness and field presence.

**Request:**
```json
{
    "section_name": "patient_demographics",
    "section_data": {
        "age": 32,
        "date_of_birth": "1993-03-15",
        "ethnicity": "Caucasian"
    },
    "patient_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (Valid):**
```json
{
    "success": true,
    "section": "patient_demographics",
    "valid": true,
    "errors": [],
    "field_count": 3
}
```

**Response (Invalid):**
```json
{
    "success": true,
    "section": "patient_demographics",
    "valid": false,
    "errors": [
        "age must be a number or string",
        "date_of_birth must be a string"
    ],
    "field_count": 3
}
```

**Supported Sections:**

1. **patient_demographics** - Basic patient information (age, DOB, ethnicity, occupation, emergency contact)
2. **obstetric_history** - Pregnancy and birth history (gravidity, parity, abortions, complications)
3. **gynecologic_history** - Menstrual and gynecologic info (menarche age, LMP, cycle length, conditions)
4. **medical_history** - General medical background (conditions, medications, surgeries, allergies)
5. **physical_examination** - Examination findings (general, vitals, abdominal, pelvic)
6. **assessment_plan** - Clinical assessment and treatment plan (diagnoses, recommendations, follow-up)

**Error Responses:**
- `500 Internal Server Error`: Validation system error

---

## Form Data Structure

Each OB/GYN form contains a `form_data` object with nested sections:

```python
{
    "patient_demographics": {
        "age": int or str,
        "date_of_birth": "YYYY-MM-DD",
        "ethnicity": str,
        "occupation": str,
        "emergency_contact": str
    },
    "obstetric_history": {
        "gravidity": int or str,  # Total pregnancies
        "parity": int or str,     # Term pregnancies
        "abortions": int or str,  # Spontaneous/induced abortions
        "living_children": int or str,
        "complications": [str]
    },
    "gynecologic_history": {
        "menarche_age": int or str,
        "last_menstrual_period": "YYYY-MM-DD",
        "cycle_length": int,      # Days
        "menstrual_duration": int, # Days
        "gynecologic_conditions": [str]
    }
}
```

## Database Schema

The `obgyn_forms` table in Supabase should have the following columns:

```sql
CREATE TABLE obgyn_forms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id),
    appointment_id UUID REFERENCES appointments(id),
    form_data JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at_trigger TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX idx_obgyn_forms_patient_id ON obgyn_forms(patient_id);
CREATE INDEX idx_obgyn_forms_appointment_id ON obgyn_forms(appointment_id);
CREATE INDEX idx_obgyn_forms_created_at ON obgyn_forms(created_at DESC);
```

## Error Handling

All endpoints follow consistent error handling patterns:

- **400 Bad Request**: Invalid input validation failures
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Database or system errors

Error responses include a `detail` field with a descriptive message.

## Authentication & Authorization

These endpoints require:

1. **Supabase Configuration**: `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` environment variables
2. **Backend API Access**: Endpoints are part of the main FastAPI application

For production use, implement:
- JWT token validation for API requests
- Row-level security (RLS) policies in Supabase
- Patient data access controls

## Usage Examples

### Create a new form
```bash
curl -X POST http://localhost:8000/api/obgyn-forms \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "form_data": {
      "patient_demographics": {"age": 32},
      "obstetric_history": {"gravidity": 2, "parity": 1},
      "gynecologic_history": {"menarche_age": 12}
    }
  }'
```

### Retrieve all patient forms
```bash
curl http://localhost:8000/api/obgyn-forms/patient/550e8400-e29b-41d4-a716-446655440000
```

### Validate a form section
```bash
curl -X POST http://localhost:8000/api/obgyn-forms/validate \
  -H "Content-Type: application/json" \
  -d '{
    "section_name": "patient_demographics",
    "section_data": {"age": 32, "date_of_birth": "1993-03-15"}
  }'
```

### Update a form
```bash
curl -X PUT http://localhost:8000/api/obgyn-forms/550e8400-e29b-41d4-a716-446655440002 \
  -H "Content-Type: application/json" \
  -d '{
    "form_data": {
      "patient_demographics": {"age": 33},
      "obstetric_history": {"gravidity": 2},
      "gynecologic_history": {"menarche_age": 12}
    },
    "status": "completed"
  }'
```

## Implementation Notes

1. **Form Validation**: Required sections (`patient_demographics`, `obstetric_history`, `gynecologic_history`) must be present and be objects/dictionaries.

2. **Status Values**: Forms can have statuses like `draft`, `completed`, `reviewed`. The API doesn't enforce specific status values - any string is accepted.

3. **Timestamps**: `created_at` and `updated_at` are managed by Supabase (use triggers or automatic timestamp columns).

4. **Optional Appointment**: Forms can be created without an appointment ID, useful for pre-visit intake forms.

5. **Logging**: All operations include console logging with emoji indicators for easy monitoring.

## Future Enhancements

Potential additions to consider:

- Form templates for common OB/GYN scenarios
- Multi-language support for form fields
- PDF export functionality
- Form version history/audit trail
- Signature/attestation fields
- Integration with clinical decision support system
- Form archival and purge policies
