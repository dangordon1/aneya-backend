# SARVAM_API_KEY Configuration Fix

## Date: 2026-01-06

## Issue
Production error on `/api/get-sarvam-token` endpoint:
```
Error: Failed to get Sarvam API key
Status: 503 Service Unavailable
```

This endpoint is critical for Indian language transcription via WebSocket.

## Root Cause
`SARVAM_API_KEY` environment variable was not configured in Cloud Run, causing the endpoint to return HTTP 503.

## Investigation

### Local Environment ✅
```bash
$ curl http://localhost:8000/api/get-sarvam-token
{"api_key":"sk_nfdrtz9s_...","model":"saaras:v2","provider":"sarvam"}
```
Works locally because `.env` file contains the key.

### Production Environment ❌
```bash
$ gcloud run services describe aneya-backend --region=asia-south1
# SARVAM_API_KEY: NOT FOUND
```

## Solution

### Step 1: Verify Secret Exists
```bash
$ gcloud secrets list --filter="name:SARVAM_API_KEY"
NAME            CREATED
SARVAM_API_KEY  2026-01-05T15:14:07
```
✅ Secret already exists in Secret Manager

### Step 2: Grant IAM Permission
```bash
$ gcloud secrets add-iam-policy-binding SARVAM_API_KEY \
  --member="serviceAccount:793162120218-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```
✅ Cloud Run service account now has access

### Step 3: Update Cloud Run to Use Secret
```bash
$ gcloud run services update aneya-backend \
  --region=asia-south1 \
  --update-secrets=SARVAM_API_KEY=SARVAM_API_KEY:latest
```
✅ Deployed revision: `aneya-backend-00054-xmw`

### Step 4: Make It Permanent in cloudbuild.yaml
Added secret reference to deployment configuration:
```yaml
- '--update-secrets=ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,ELEVENLABS_API_KEY=ELEVENLABS_API_KEY:latest,SCRAPEOPS_API_KEY=SCRAPEOPS_API_KEY:latest,SARVAM_API_KEY=SARVAM_API_KEY:latest'
```

## Current Configuration

All API keys now properly configured via Secret Manager:

| Environment Variable | Source | Status |
|---------------------|--------|--------|
| ANTHROPIC_API_KEY | Secret Manager | ✅ |
| ELEVENLABS_API_KEY | Secret Manager | ✅ |
| SCRAPEOPS_API_KEY | Secret Manager | ✅ |
| SARVAM_API_KEY | Secret Manager | ✅ |
| GIT_BRANCH | Build variable | ✅ |

## Verification

### Production Test
```bash
$ curl https://aneya-backend-xao3xivzia-el.a.run.app/api/get-sarvam-token
{"api_key":"sk_nfdrtz9s_OqBLtL9y3M4lyLYwu9ToPrjY","model":"saaras:v2","provider":"sarvam"}
```
✅ Working correctly

### Future Deployments
Every deployment via Cloud Build will now:
1. Build the Docker image
2. Push to Artifact Registry
3. Deploy to Cloud Run **with all 4 API keys from Secret Manager**

## What Changed

### Files Modified
1. **cloudbuild.yaml**
   - Added `--update-secrets` flag with all API keys
   - Ensures secrets are loaded on every deployment

### Cloud Run Configuration
- Current revision: `aneya-backend-00054-xmw`
- All secrets now use `valueFrom.secretKeyRef` instead of plain text

### Secret Manager IAM
- Service account `793162120218-compute@developer.gserviceaccount.com` granted `secretAccessor` role for SARVAM_API_KEY

## Benefits

1. **Security**: API keys stored in Secret Manager, not in env vars
2. **Consistency**: All API keys use the same pattern
3. **Persistence**: Configuration survives redeployments
4. **Rotation**: Can rotate secrets without code changes

## Important Notes

⚠️ **When adding new API keys**:
1. Create secret: `gcloud secrets create KEY_NAME --data-file=-`
2. Grant access: `gcloud secrets add-iam-policy-binding KEY_NAME --member="serviceAccount:..." --role="roles/secretmanager.secretAccessor"`
3. Update `cloudbuild.yaml`: Add to `--update-secrets` list

## Commits
- `2b33c27` - Add SARVAM_API_KEY to permanent deployment config
- `7695962` - Fix Supabase client creation and add patient context to form filling

## Testing Checklist
- [x] Local endpoint works
- [x] Production endpoint works (HTTP 200)
- [x] Secret exists in Secret Manager
- [x] IAM permissions granted
- [x] cloudbuild.yaml updated
- [x] Changes committed and pushed
- [x] Auto-deployment triggered

## Related Issues
- Backend server investigation (scale-to-zero behavior)
- Supabase configuration errors (separate fix)
