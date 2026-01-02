# Custom Forms Integration Guide

This guide explains how to integrate the doctor-uploadable custom forms feature into Aneya.

## Overview

The custom forms feature allows doctors to:
1. Upload pictures of their specialty-specific forms (HEIC/JPEG/PNG)
2. Automatically generate form schemas using Claude Vision API
3. Save custom forms to their account
4. Share forms publicly with other doctors (optional)
5. Use custom forms for patient consultations

## Architecture

```
┌─────────────────┐
│   Frontend UI   │
│  (Form Upload)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  API Endpoint   │
│  /custom-forms  │
│     /upload     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Form Converter  │
│      API        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Claude Vision  │
│      API        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Database     │
│ custom_forms    │
│    table        │
└─────────────────┘
```

## Step 1: Run Database Migration

First, apply the custom forms migration:

```bash
cd /Users/dgordon/aneya/aneya-backend

# Apply migration using Supabase CLI or via API
psql $DATABASE_URL < migrations/015_create_custom_forms_table.sql
```

This creates two tables:
- `custom_forms` - Stores form schemas and metadata
- `custom_form_instances` - Stores filled form data

## Step 2: Integrate API Endpoints

Add the custom forms router to `api.py`:

```python
# Near the top of api.py, add import
from custom_forms_api import router as custom_forms_router

# Before the `if __name__ == "__main__"` block, add:
app.include_router(custom_forms_router)
```

## Step 3: Frontend Integration

### 3.1 Create Upload Form Component

Create `/Users/dgordon/aneya/aneya-frontend/src/components/doctor-portal/CustomFormUpload.tsx`:

```typescript
import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';

export function CustomFormUpload() {
  const [files, setFiles] = useState<File[]>([]);
  const [formName, setFormName] = useState('');
  const [specialty, setSpecialty] = useState('');
  const [description, setDescription] = useState('');
  const [isPublic, setIsPublic] = useState(false);
  const [uploading, setUploading] = useState(false);

  const handleUpload = async () => {
    setUploading(true);

    const formData = new FormData();
    formData.append('form_name', formName);
    formData.append('specialty', specialty);
    formData.append('description', description);
    formData.append('is_public', isPublic.toString());

    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await fetch('/api/custom-forms/upload', {
        method: 'POST',
        body: formData,
        headers: {
          // Add auth token
        }
      });

      const result = await response.json();

      if (result.success) {
        alert(`Form "${formName}" created successfully!`);
        // Reset form
        setFiles([]);
        setFormName('');
        setSpecialty('');
        setDescription('');
      } else {
        alert(`Error: ${result.error}`);
      }
    } catch (error) {
      alert(`Upload failed: ${error.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="custom-form-upload">
      <h2>Upload Custom Form</h2>

      <div>
        <label>Form Name (snake_case):</label>
        <input
          type="text"
          value={formName}
          onChange={(e) => setFormName(e.target.value)}
          placeholder="e.g., neurology_assessment"
        />
      </div>

      <div>
        <label>Specialty:</label>
        <select value={specialty} onChange={(e) => setSpecialty(e.target.value)}>
          <option value="">Select...</option>
          <option value="cardiology">Cardiology</option>
          <option value="neurology">Neurology</option>
          <option value="pediatrics">Pediatrics</option>
          <option value="orthopedics">Orthopedics</option>
          <option value="other">Other</option>
        </select>
      </div>

      <div>
        <label>Description (optional):</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Brief description of the form"
        />
      </div>

      <div>
        <label>
          <input
            type="checkbox"
            checked={isPublic}
            onChange={(e) => setIsPublic(e.target.checked)}
          />
          Make form public (available to all doctors)
        </label>
      </div>

      <div>
        <label>Upload Form Images (2-10 images):</label>
        <input
          type="file"
          multiple
          accept=".heic,.jpg,.jpeg,.png"
          onChange={(e) => setFiles(Array.from(e.target.files || []))}
        />
        <p>{files.length} files selected</p>
      </div>

      <button
        onClick={handleUpload}
        disabled={!formName || !specialty || files.length < 2 || uploading}
      >
        {uploading ? 'Uploading...' : 'Upload & Generate Form'}
      </button>

      {uploading && (
        <div className="upload-progress">
          <p>Analyzing images with AI...</p>
          <p>This may take 30-60 seconds</p>
        </div>
      )}
    </div>
  );
}
```

### 3.2 Create Form Library Component

Create `/Users/dgordon/aneya/aneya-frontend/src/components/doctor-portal/CustomFormLibrary.tsx`:

```typescript
import React, { useEffect, useState } from 'react';

interface CustomForm {
  id: string;
  form_name: string;
  specialty: string;
  description?: string;
  field_count: number;
  section_count: number;
  status: string;
  is_public: boolean;
  created_at: string;
}

export function CustomFormLibrary() {
  const [myForms, setMyForms] = useState<CustomForm[]>([]);
  const [publicForms, setPublicForms] = useState<CustomForm[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadForms();
  }, []);

  const loadForms = async () => {
    try {
      const [myResponse, publicResponse] = await Promise.all([
        fetch('/api/custom-forms/my-forms'),
        fetch('/api/custom-forms/public-forms')
      ]);

      setMyForms(await myResponse.json());
      setPublicForms(await publicResponse.json());
    } catch (error) {
      console.error('Error loading forms:', error);
    } finally {
      setLoading(false);
    }
  };

  const activateForm = async (formId: string) => {
    try {
      await fetch(`/api/custom-forms/${formId}/activate`, {
        method: 'PATCH'
      });
      alert('Form activated!');
      loadForms();
    } catch (error) {
      alert(`Error: ${error.message}`);
    }
  };

  return (
    <div className="custom-form-library">
      <h2>My Custom Forms</h2>
      {myForms.length === 0 ? (
        <p>No custom forms yet. Upload one to get started!</p>
      ) : (
        <div className="forms-grid">
          {myForms.map(form => (
            <div key={form.id} className="form-card">
              <h3>{form.form_name}</h3>
              <p className="specialty">{form.specialty}</p>
              <p className="description">{form.description}</p>
              <div className="stats">
                <span>{form.field_count} fields</span>
                <span>{form.section_count} sections</span>
              </div>
              <div className="status">
                Status: <strong>{form.status}</strong>
              </div>
              {form.status === 'draft' && (
                <button onClick={() => activateForm(form.id)}>
                  Activate Form
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <h2>Public Forms</h2>
      {publicForms.length === 0 ? (
        <p>No public forms available.</p>
      ) : (
        <div className="forms-grid">
          {publicForms.map(form => (
            <div key={form.id} className="form-card public">
              <h3>{form.form_name}</h3>
              <p className="specialty">{form.specialty}</p>
              <p className="description">{form.description}</p>
              <div className="stats">
                <span>{form.field_count} fields</span>
                <span>{form.section_count} sections</span>
              </div>
              <button>Use This Form</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

## Step 4: API Endpoints

The custom forms API provides these endpoints:

### POST /api/custom-forms/upload
Upload form images and generate schema.

**Request:**
- `form_name`: string (snake_case)
- `specialty`: string
- `description`: string (optional)
- `is_public`: boolean
- `files`: File[] (2-10 images)

**Response:**
```json
{
  "success": true,
  "form_id": "uuid",
  "form_name": "neurology_assessment",
  "specialty": "neurology",
  "field_count": 25,
  "section_count": 5
}
```

### GET /api/custom-forms/my-forms
Get all forms created by current user.

**Query Params:**
- `specialty`: string (optional)
- `status`: string (optional: draft, active, archived)

### GET /api/custom-forms/public-forms
Get all publicly available forms.

**Query Params:**
- `specialty`: string (optional)

### GET /api/custom-forms/{form_id}
Get detailed information about a specific form.

### PATCH /api/custom-forms/{form_id}/activate
Activate a draft form to make it usable.

### DELETE /api/custom-forms/{form_id}
Delete a draft form.

## Step 5: Using Custom Forms in Consultations

To use a custom form in a consultation:

1. Doctor selects a custom form from their library
2. System retrieves form schema from `custom_forms` table
3. Frontend renders form fields dynamically based on schema
4. Filled data stored in `custom_form_instances` table

Example query:

```typescript
// Get form schema
const formResponse = await fetch(`/api/custom-forms/${formId}`);
const formData = await formResponse.json();

// Render form based on schema
const schema = formData.form_schema;

// Save filled form
await fetch('/api/custom-form-instances', {
  method: 'POST',
  body: JSON.stringify({
    custom_form_id: formId,
    patient_id: patientId,
    appointment_id: appointmentId,
    form_data: filledData
  })
});
```

## Security Considerations

1. **Authentication**: All endpoints require authenticated user
2. **Authorization**: Users can only access their own forms or public forms
3. **File Upload**: Max 10 images, 10MB each
4. **RLS Policies**: Postgres Row Level Security enabled on both tables
5. **API Key**: Anthropic API key stored securely in env vars

## Cost Estimation

Form conversion uses Claude Vision API:
- 2-3 images: ~$0.01-0.02
- 6 images: ~$0.02-0.04
- 10 images: ~$0.04-0.06

The API includes a cost estimation endpoint:

```python
from tools.form_converter.api import FormConverterAPI

converter = FormConverterAPI()
estimate = converter.estimate_cost(num_images=6)
# Returns estimated cost in USD
```

## Testing

Test the upload flow:

```bash
# 1. Start backend
cd /Users/dgordon/aneya/aneya-backend
source .env
python api.py

# 2. Test upload
curl -X POST http://localhost:8000/api/custom-forms/upload \
  -F "form_name=test_form" \
  -F "specialty=neurology" \
  -F "description=Test form" \
  -F "is_public=false" \
  -F "files=@/path/to/image1.heic" \
  -F "files=@/path/to/image2.heic"
```

## Next Steps

1. ✅ Run database migration
2. ✅ Integrate API endpoints into api.py
3. Create frontend upload component
4. Add form library view
5. Implement dynamic form rendering
6. Add form sharing/publishing workflow
7. Add form versioning support
8. Add analytics (usage tracking)

## Troubleshooting

**Error: "Anthropic API key not found"**
- Ensure `ANTHROPIC_API_KEY` is set in `.env`

**Error: "File size exceeds limit"**
- Reduce image file size or quality
- Max 10MB per image

**Error: "Form name already exists"**
- Each user can only have one form with a given name
- Change the form name or update version

**Slow upload (>2 minutes)**
- Normal for 6+ images
- Vision API analysis takes 30-60 seconds

## Support

For issues or questions:
- Check logs in console
- Review API response errors
- Test form converter CLI tool first: `python -m tools.form_converter interactive`
