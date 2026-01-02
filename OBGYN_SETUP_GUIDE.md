# OB/GYN Forms API - Setup & Integration Guide

## Prerequisites

- Python 3.10+
- FastAPI backend running
- Supabase project with authentication configured
- Environment variables: SUPABASE_URL, SUPABASE_SERVICE_KEY, ANTHROPIC_API_KEY

## Installation & Setup

### 1. Database Setup

Execute the migration to create the obgyn_forms table:

```bash
# Option A: Using Supabase Dashboard
1. Go to Supabase Dashboard
2. Select your project
3. Navigate to SQL Editor
4. Click "New Query"
5. Copy contents of migrations/001_create_obgyn_forms_table.sql
6. Execute the query

# Option B: Using Supabase CLI
supabase db push
```

### 2. Verify Backend API

Start the backend server:

```bash
# From /Users/dgordon/aneya/aneya-backend directory
python api.py
```

Verify endpoints are available:

```bash
curl http://localhost:8000/api/health
# Should return: {"status":"healthy","message":"All systems operational"}
```

### 3. Test Basic Connectivity

```bash
# Test health check (confirms API is running)
curl http://localhost:8000/api/health

# Test OB/GYN forms validate endpoint (minimal dependency)
curl -X POST http://localhost:8000/api/obgyn-forms/validate \
  -H "Content-Type: application/json" \
  -d '{
    "section_name": "patient_demographics",
    "section_data": {"age": 32}
  }'
```

## Quick Start

### Create Your First Form

```bash
curl -X POST http://localhost:8000/api/obgyn-forms \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "form_data": {
      "patient_demographics": {
        "age": 32,
        "date_of_birth": "1993-03-15"
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
    }
  }'
```

This should return a response with form_id, status 200.

### Retrieve the Form

Replace `{form_id}` with the ID from creation response:

```bash
curl http://localhost:8000/api/obgyn-forms/{form_id}
```

### Update the Form

```bash
curl -X PUT http://localhost:8000/api/obgyn-forms/{form_id} \
  -H "Content-Type: application/json" \
  -d '{
    "form_data": {
      "patient_demographics": {
        "age": 33,
        "date_of_birth": "1993-03-15"
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

### Delete the Form

```bash
curl -X DELETE http://localhost:8000/api/obgyn-forms/{form_id}
```

## Frontend Integration

### 1. Create React Component

```typescript
// src/components/OBGYNForm.tsx
import React, { useState } from 'react';
import axios from 'axios';

interface FormData {
  patient_demographics: Record<string, any>;
  obstetric_history: Record<string, any>;
  gynecologic_history: Record<string, any>;
}

export const OBGYNForm: React.FC<{ patientId: string }> = ({ patientId }) => {
  const [formData, setFormData] = useState<FormData>({
    patient_demographics: {},
    obstetric_history: {},
    gynecologic_history: {}
  });
  const [status, setStatus] = useState('draft');
  const [loading, setLoading] = useState(false);

  const handleSectionChange = (section: string, data: any) => {
    setFormData(prev => ({
      ...prev,
      [section]: { ...prev[section as keyof FormData], ...data }
    }));
  };

  const handleValidateSection = async (section: string) => {
    try {
      const response = await axios.post('/api/obgyn-forms/validate', {
        section_name: section,
        section_data: formData[section as keyof FormData]
      });

      if (response.data.valid) {
        console.log(`${section} is valid`);
      } else {
        console.error(`Validation errors: ${response.data.errors.join(', ')}`);
      }
    } catch (error) {
      console.error('Validation error:', error);
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const response = await axios.post('/api/obgyn-forms', {
        patient_id: patientId,
        form_data: formData,
        status: status
      });

      console.log('Form created:', response.data);
      // Handle success - maybe navigate or show confirmation
    } catch (error) {
      console.error('Form submission error:', error);
      // Handle error - show error message to user
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
      {/* Form inputs for each section */}
      <button
        type="button"
        onClick={() => handleValidateSection('patient_demographics')}
      >
        Validate Demographics
      </button>

      <button type="submit" disabled={loading}>
        {loading ? 'Saving...' : 'Save Form'}
      </button>
    </form>
  );
};
```

### 2. API Client Service

```typescript
// src/services/obgynFormService.ts
import axios from 'axios';

const API_BASE = '/api';

export const obgynFormService = {
  // Create form
  async createForm(patientId: string, formData: any, appointmentId?: string) {
    const response = await axios.post(`${API_BASE}/obgyn-forms`, {
      patient_id: patientId,
      appointment_id: appointmentId,
      form_data: formData,
      status: 'draft'
    });
    return response.data;
  },

  // Get form by ID
  async getForm(formId: string) {
    const response = await axios.get(`${API_BASE}/obgyn-forms/${formId}`);
    return response.data;
  },

  // Get all patient forms
  async getPatientForms(patientId: string) {
    const response = await axios.get(`${API_BASE}/obgyn-forms/patient/${patientId}`);
    return response.data;
  },

  // Get appointment form
  async getAppointmentForm(appointmentId: string) {
    const response = await axios.get(`${API_BASE}/obgyn-forms/appointment/${appointmentId}`);
    return response.data;
  },

  // Update form
  async updateForm(formId: string, formData: any, status?: string) {
    const response = await axios.put(`${API_BASE}/obgyn-forms/${formId}`, {
      form_data: formData,
      status: status
    });
    return response.data;
  },

  // Delete form
  async deleteForm(formId: string) {
    const response = await axios.delete(`${API_BASE}/obgyn-forms/${formId}`);
    return response.data;
  },

  // Validate section
  async validateSection(sectionName: string, sectionData: any) {
    const response = await axios.post(`${API_BASE}/obgyn-forms/validate`, {
      section_name: sectionName,
      section_data: sectionData
    });
    return response.data;
  }
};
```

### 3. Hook for Form Management

```typescript
// src/hooks/useOBGYNForm.ts
import { useState, useCallback } from 'react';
import { obgynFormService } from '../services/obgynFormService';

export const useOBGYNForm = (patientId: string) => {
  const [form, setForm] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createForm = useCallback(async (formData: any) => {
    setLoading(true);
    setError(null);
    try {
      const result = await obgynFormService.createForm(patientId, formData);
      setForm(result);
      return result;
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create form');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  const updateForm = useCallback(async (formId: string, formData: any) => {
    setLoading(true);
    setError(null);
    try {
      const result = await obgynFormService.updateForm(formId, formData);
      setForm(result);
      return result;
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update form');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const validateSection = useCallback(async (sectionName: string, sectionData: any) => {
    try {
      return await obgynFormService.validateSection(sectionName, sectionData);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Validation error');
      throw err;
    }
  }, []);

  return {
    form,
    loading,
    error,
    createForm,
    updateForm,
    validateSection
  };
};
```

## Testing the Integration

### Run Unit Tests

```bash
# From backend directory
pytest test_obgyn_forms.py -v
```

### Test with Postman

1. Import endpoints into Postman
2. Create environment variables:
   - patient_id: "550e8400-e29b-41d4-a716-446655440000"
   - appointment_id: "550e8400-e29b-41d4-a716-446655440001"
   - form_id: (will be generated)

3. Run requests in sequence:
   - POST /api/obgyn-forms (create)
   - GET /api/obgyn-forms/{form_id} (retrieve)
   - PUT /api/obgyn-forms/{form_id} (update)
   - DELETE /api/obgyn-forms/{form_id} (delete)

### Manual Testing Workflow

```bash
# 1. Validate a section
curl -X POST http://localhost:8000/api/obgyn-forms/validate \
  -H "Content-Type: application/json" \
  -d '{
    "section_name": "patient_demographics",
    "section_data": {"age": 32, "date_of_birth": "1993-03-15"}
  }'

# 2. Create form
FORM_ID=$(curl -X POST http://localhost:8000/api/obgyn-forms \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
    "form_data": {
      "patient_demographics": {"age": 32},
      "obstetric_history": {"gravidity": 2, "parity": 1, "abortions": 0},
      "gynecologic_history": {"menarche_age": 12, "last_menstrual_period": "2025-12-01", "cycle_length": 28, "menstrual_duration": 5}
    }
  }' | jq -r '.id')

echo "Created form: $FORM_ID"

# 3. Retrieve form
curl http://localhost:8000/api/obgyn-forms/$FORM_ID | jq .

# 4. Get all patient forms
curl http://localhost:8000/api/obgyn-forms/patient/550e8400-e29b-41d4-a716-446655440000 | jq .

# 5. Update form
curl -X PUT http://localhost:8000/api/obgyn-forms/$FORM_ID \
  -H "Content-Type: application/json" \
  -d '{
    "form_data": {
      "patient_demographics": {"age": 33},
      "obstetric_history": {"gravidity": 2, "parity": 1, "abortions": 0},
      "gynecologic_history": {"menarche_age": 12, "last_menstrual_period": "2025-12-01", "cycle_length": 28, "menstrual_duration": 5}
    },
    "status": "completed"
  }' | jq .

# 6. Delete form
curl -X DELETE http://localhost:8000/api/obgyn-forms/$FORM_ID | jq .
```

## Troubleshooting

### Issue: "Supabase configuration not available"

**Solution**: Verify environment variables:
```bash
echo $SUPABASE_URL
echo $SUPABASE_SERVICE_KEY
```

Both must be set. Add to `.env`:
```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
```

### Issue: "Missing required section"

**Solution**: Ensure form_data includes:
- patient_demographics (object)
- obstetric_history (object)
- gynecologic_history (object)

All three are required.

### Issue: "404 Form with ID not found"

**Solution**:
- Check that form was actually created (look for form_id in create response)
- Verify you're using the correct form_id
- Check that the form hasn't been deleted

### Issue: Validation always passes even with bad data

**Solution**: The validation endpoint is lenient by design:
- Checks for required sections
- Checks that sections are objects
- Checks specific field types
- Doesn't enforce all fields to be present in every section
This allows for progressive form filling.

## Security Considerations

### Authentication

Add authentication middleware to protect endpoints:

```python
from fastapi import Depends, HTTPException, status
from firebase_admin import auth as firebase_auth

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        return decoded_token['uid']
    except:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

@app.post("/api/obgyn-forms")
async def create_obgyn_form(
    request: OBGYNFormCreateRequest,
    current_user: str = Depends(get_current_user)
):
    # Implementation with user_id from current_user
```

### Authorization

Implement checks to ensure users can only access their own data:

```python
# Verify patient belongs to current user
patient = supabase.table("patients").select("user_id").eq("id", request.patient_id).execute()
if patient.data[0]["user_id"] != current_user:
    raise HTTPException(status_code=403, detail="Unauthorized")
```

### Data Validation

All endpoints validate input:
- Required sections must be present
- Data types are checked
- Invalid UUIDs will fail on foreign key constraints

## Performance Tips

1. **Pagination**: For large patient form lists, implement pagination:
   ```python
   result = supabase.table("obgyn_forms").select("*")\
     .eq("patient_id", patient_id)\
     .range(0, 9)\  # First 10 forms
     .order("created_at", desc=True)\
     .execute()
   ```

2. **Caching**: Cache frequently accessed forms client-side
3. **Lazy Loading**: Load form sections progressively rather than all at once
4. **Indexed Queries**: Queries on patient_id, appointment_id, and created_at are indexed

## Production Checklist

- [ ] Database migration applied to Supabase
- [ ] Environment variables configured on server
- [ ] RLS policies configured and tested
- [ ] Authentication/authorization implemented
- [ ] Error tracking (Sentry) configured
- [ ] API rate limiting implemented
- [ ] Input sanitization reviewed
- [ ] CORS settings configured appropriately
- [ ] API documentation (OpenAPI/Swagger) generated
- [ ] Load testing completed
- [ ] Security audit performed
- [ ] Monitoring and alerts configured
- [ ] Backup strategy in place
- [ ] Disaster recovery plan documented

## Support

For issues or questions:
1. Check OBGYN_FORMS_QUICK_REFERENCE.md for common issues
2. Review test cases in test_obgyn_forms.py for usage examples
3. Check backend logs for detailed error messages
4. Consult OBGYN_FORMS_API.md for endpoint details

## Additional Resources

- FastAPI Documentation: https://fastapi.tiangolo.com/
- Supabase Documentation: https://supabase.com/docs
- Pydantic Documentation: https://docs.pydantic.dev/
- Pytest Documentation: https://docs.pytest.org/
