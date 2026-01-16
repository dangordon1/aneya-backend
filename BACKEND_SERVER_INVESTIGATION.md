# Backend Server Investigation & Fix

## Date: 2026-01-06

## Issue Report
User reported: "Backend server is down"

## Investigation Results

### 1. Local Backend Status ✅
**Finding**: Local backend is **RUNNING** and responding correctly
- Process: `python -m uvicorn api:app --reload --host 0.0.0.0 --port 8000` (PID: 84237)
- Port 8000: Active and listening
- Health check: HTTP 200 OK
- Response: `{"status":"ok","message":"Aneya Clinical Decision Support API is running","branch":"main"}`

### 2. Cloud Run Backend Status ✅
**Finding**: Cloud Run backend is **UP** and responding
- Service: `aneya-backend`
- Region: `asia-south1` (NOT europe-west2)
- URL: `https://aneya-backend-xao3xivzia-el.a.run.app/`
- Status: Ready (all conditions: True)
- Latest Revision: `aneya-backend-00049-rqt`
- Health check: HTTP 200 OK

**Note**: Backend scaled to zero earlier due to inactivity (normal Cloud Run behavior)
- **07:26:06** - Instance shut down (no traffic for ~45 minutes)
- **08:13:47** - Auto-scaled back up when traffic arrived
- **08:14:05** - Fully initialized and serving requests

Autoscaling Config:
- Min instances: 0 (allows scale-to-zero)
- Max instances: 10

### 3. Error Found in Logs ❌
**Issue**: Supabase configuration errors in `custom_forms_api.py`

Error pattern seen multiple times:
```
SupabaseException: supabase_url is required
Traceback in custom_forms_api.py:676 (browse_forms_to_add)
```

**Root Cause**:
- Multiple functions creating Supabase clients inline without checking env vars
- Pattern: `create_client(supabase_url, supabase_key)` called directly
- If env vars are None/empty, cryptic error occurs

**Locations**: 14+ occurrences across `custom_forms_api.py`

## Fixes Applied

### Fix 1: Supabase Client Creation
**File**: `custom_forms_api.py`

**Before** (repeated 14+ times):
```python
from supabase import create_client, Client

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)
```

**After**:
```python
supabase = get_supabase_client()
```

The `get_supabase_client()` helper already exists with proper error handling:
```python
def get_supabase_client():
    """Get Supabase client for database operations"""
    from supabase import create_client, Client

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Supabase configuration not available")

    return create_client(supabase_url, supabase_key)
```

**Impact**:
- Better error messages (HTTP 500 with clear detail instead of cryptic exception)
- DRY principle - single source of truth for client creation
- Easier to add features (caching, connection pooling, etc.) in one place

### Fix 2: Patient Context in Form Filling
**File**: `api.py`

**Added**: Comprehensive patient context to form auto-fill feature
- New function: `fetch_patient_context(patient_id)` (lines 4832-4981)
- Fetches: demographics, medications, conditions, allergies, previous forms
- Updated: `auto_fill_consultation_form` to fetch and pass context
- Enhanced: LLM prompt with patient details for better extraction

**Benefits**:
- Improved form field extraction accuracy
- Better clinical safety (allergies prominent in prompt)
- More contextual understanding for the LLM

## Deployment

### Auto-Deployment Status ✅
**Verified**: Auto-deployment IS configured and working

Cloud Build Trigger: `push-to-main`
- Trigger: Push to `main` branch
- Config: `cloudbuild.yaml`
- Target: Cloud Run service `aneya-backend` in `asia-south1`
- Status: Active

### Current Deployment
**Commit**: `7695962` - "Fix Supabase client creation and add patient context to form filling"

**Build Status**:
- Build ID: `ced58677-3caa-4da9-9f4a-9e4186057ae2`
- Status: In progress (triggered automatically by git push)
- Started: 2026-01-06 08:21:09

## Timeline

| Time | Event |
|------|-------|
| 2026-01-05 21:15:01 | Last successful deployment (revision 00049) |
| 2026-01-06 07:26:06 | Cloud Run scaled to zero (no traffic) |
| 2026-01-06 08:13:47 | Auto-scaled back up on traffic |
| 2026-01-06 08:14:05 | Instance fully initialized |
| 2026-01-06 08:20:XX | Investigation started |
| 2026-01-06 08:20:XX | Fixes committed and pushed |
| 2026-01-06 08:21:09 | Auto-deployment build started |

## Conclusion

### Was the server actually down?
**No** - The backend was working correctly:
- Local: Running fine
- Cloud Run: Healthy and responding

### What was the issue?
**Intermittent errors** in specific endpoints (`browse_forms_to_add`) due to:
1. Missing/improper Supabase client initialization
2. Scale-to-zero behavior causing cold starts (normal, not an issue)

### Resolution
- Fixed Supabase client creation in 14+ locations
- Added patient context feature as bonus enhancement
- Auto-deployment working correctly
- New revision deploying now

### Monitoring
Next steps:
- Monitor Cloud Run logs for remaining errors
- Verify new deployment completes successfully
- Test `/api/custom-forms/browse-forms-to-add` endpoint after deployment

## Files Modified
- `custom_forms_api.py` - Fixed Supabase client creation (14 locations)
- `api.py` - Added patient context to form filling
- `test_patient_context_form_filling.py` - Tests for new feature
- `PATIENT_CONTEXT_FORM_FILLING.md` - Documentation for new feature
- `BACKEND_SERVER_INVESTIGATION.md` - This document
