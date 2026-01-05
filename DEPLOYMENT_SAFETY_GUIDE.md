# Cloud Run Deployment Safety Guide

**CRITICAL**: This document explains how to prevent production incidents caused by improper environment variable management.

## Incident Report: January 5, 2026

**What Happened**: Transcription service failed for all users with error "failed to get Sarvam API key"

**Root Cause**: Used `--set-env-vars` instead of `--update-env-vars` when adding Supabase configuration, which **wiped out all existing environment variables** including SARVAM_API_KEY and RESEND_API_KEY.

**Impact**: Users could not transcribe consultations between 10:49 UTC and 15:20 UTC (4.5 hours of downtime)

**Timeline**:
- 09:47 - Successful deployment with all env vars intact (revision 00029-mfs)
- 10:49 - **INCIDENT START**: Used `--set-env-vars` to add SUPABASE_URL → Lost SARVAM_API_KEY, RESEND_API_KEY
- 15:20 - **INCIDENT END**: Keys restored with `--update-env-vars`

## The Critical Difference

### ❌ DANGEROUS: `--set-env-vars`
```bash
# This REPLACES ALL environment variables (destructive)
gcloud run services update aneya-backend --region=asia-south1 \
  --set-env-vars "NEW_KEY=value"

# Result: ALL other env vars are DELETED
```

### ✅ SAFE: `--update-env-vars`
```bash
# This ADDS or UPDATES specific variables (preserves others)
gcloud run services update aneya-backend --region=asia-south1 \
  --update-env-vars "NEW_KEY=value"

# Result: Only NEW_KEY is added/updated, all others preserved
```

## Required Environment Variables

The aneya backend **requires** these environment variables to function:

### API Keys (Critical - Service Breaks Without These)
- `ANTHROPIC_API_KEY` - Claude AI for consultation analysis
- `ELEVENLABS_API_KEY` - Voice synthesis
- `SARVAM_API_KEY` - **Transcription service** (Indian languages)
- `SCRAPEOPS_API_KEY` - Web scraping for BNF data
- `RESEND_API_KEY` - Email notifications
- `SUPABASE_URL` - Database connection
- `SUPABASE_SERVICE_KEY` - Database admin access

### Storage
- `GCS_BUCKET_NAME` - Audio file storage (default: aneya-audio-recordings)

## Prevention Strategies

### 1. Always Use `--update-env-vars`

**RULE**: Never use `--set-env-vars` in production. Prefer `--update-env-vars`.

```bash
# ✅ CORRECT - Safe for production
gcloud run services update aneya-backend --region=asia-south1 \
  --update-env-vars "NEW_KEY=value,ANOTHER_KEY=value2"

# ❌ WRONG - Destroys existing variables
gcloud run services update aneya-backend --region=asia-south1 \
  --set-env-vars "NEW_KEY=value"
```

### 2. Use Cloud Secrets Manager (Best Practice)

Secrets are version-controlled and protected from accidental deletion:

```bash
# Create secret
gcloud secrets create MY_API_KEY --replication-policy="automatic"
echo -n "secret-value" | gcloud secrets versions add MY_API_KEY --data-file=-

# Reference secret in Cloud Run
gcloud run services update aneya-backend --region=asia-south1 \
  --update-secrets="MY_API_KEY=MY_API_KEY:latest"
```

**Benefits**:
- Can't be accidentally wiped by `--set-env-vars`
- Automatic rotation support
- Audit logs of who accessed secrets
- Version history

### 3. Validate Before Deployment

Create a pre-deployment checklist script:

```bash
#!/bin/bash
# validate-env-vars.sh

REQUIRED_VARS=(
  "ANTHROPIC_API_KEY"
  "ELEVENLABS_API_KEY"
  "SARVAM_API_KEY"
  "SCRAPEOPS_API_KEY"
  "RESEND_API_KEY"
  "SUPABASE_URL"
  "SUPABASE_SERVICE_KEY"
)

echo "Checking environment variables for aneya-backend..."

ENV_OUTPUT=$(gcloud run services describe aneya-backend --region=asia-south1 --format="value(spec.template.spec.containers[0].env)")

for var in "${REQUIRED_VARS[@]}"; do
  if echo "$ENV_OUTPUT" | grep -q "'name': '$var'"; then
    echo "✅ $var present"
  else
    echo "❌ $var MISSING"
    exit 1
  fi
done

echo "✅ All required environment variables are present"
```

### 4. Monitor for Missing Variables

Add health check that validates critical env vars:

```python
# In api.py
@app.get("/health")
async def health_check():
    missing_vars = []
    required = [
        "ANTHROPIC_API_KEY",
        "SARVAM_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY"
    ]

    for var in required:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        return {
            "status": "unhealthy",
            "missing_vars": missing_vars
        }

    return {"status": "healthy"}
```

### 5. Use Cloud Build for Consistent Deployments

Instead of manual `gcloud` commands, use Cloud Build triggers:

```yaml
# cloudbuild.yaml
steps:
  # Build image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'asia-south1-docker.pkg.dev/$PROJECT_ID/aneya/aneya-backend:$COMMIT_SHA', '.']

  # Push image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'asia-south1-docker.pkg.dev/$PROJECT_ID/aneya/aneya-backend:$COMMIT_SHA']

  # Deploy to Cloud Run (preserves existing env vars)
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'aneya-backend'
      - '--image'
      - 'asia-south1-docker.pkg.dev/$PROJECT_ID/aneya/aneya-backend:$COMMIT_SHA'
      - '--region'
      - 'asia-south1'
      # Note: No env var flags here - they're managed separately
```

**Important**: When using Cloud Build, manage env vars separately through:
- Cloud Run console UI
- Infrastructure as Code (Terraform)
- One-time setup commands (documented)

## Recovery Procedure

If environment variables are accidentally deleted:

### Step 1: Identify Last Working Revision
```bash
gcloud run revisions list --service=aneya-backend --region=asia-south1 --limit=10
```

### Step 2: Check Which Variables Were Lost
```bash
# Compare old vs new
OLD_REV="aneya-backend-00024-c26"  # Last working
NEW_REV="aneya-backend-00031-vdw"  # Broken

gcloud run revisions describe $OLD_REV --region=asia-south1 --format="value(spec.containers[0].env)" > old.txt
gcloud run revisions describe $NEW_REV --region=asia-south1 --format="value(spec.containers[0].env)" > new.txt

diff old.txt new.txt
```

### Step 3: Restore Missing Variables
```bash
# Get values from backend .env or old revision
gcloud run services update aneya-backend --region=asia-south1 \
  --update-env-vars "SARVAM_API_KEY=value,RESEND_API_KEY=value"
```

### Step 4: Verify Service Recovery
```bash
# Test health endpoint
curl https://aneya-backend-xao3xivzia-el.a.run.app/health

# Test transcription (requires auth)
curl -X POST https://aneya-backend-xao3xivzia-el.a.run.app/api/transcribe
```

## Current Environment Variable Status

Last verified: 2026-01-05 15:20 UTC
Revision: aneya-backend-00040-c67

**All Required Variables**: ✅ Present
- ✅ ANTHROPIC_API_KEY (from secret)
- ✅ ELEVENLABS_API_KEY (from secret)
- ✅ SARVAM_API_KEY (plain text)
- ✅ SCRAPEOPS_API_KEY (from secret)
- ✅ RESEND_API_KEY (plain text)
- ✅ SUPABASE_URL (plain text)
- ✅ SUPABASE_SERVICE_KEY (plain text)

**Action Item**: Migrate SARVAM_API_KEY, RESEND_API_KEY, SUPABASE_SERVICE_KEY, and SUPABASE_URL to Secrets Manager

## Lessons Learned

1. **Never trust `--set-env-vars`** - It's a footgun waiting to happen
2. **Always use `--update-env-vars`** - Safe for production
3. **Migrate to Secrets Manager** - Protected from accidental deletion
4. **Validate before deploy** - Catch issues before they hit production
5. **Monitor env vars** - Health checks should validate critical configs
6. **Document recovery** - Have a runbook ready

## References

- [Cloud Run Environment Variables](https://cloud.google.com/run/docs/configuring/environment-variables)
- [Cloud Run Secrets](https://cloud.google.com/run/docs/configuring/secrets)
- [gcloud run services update](https://cloud.google.com/sdk/gcloud/reference/run/services/update)

---

**Last Updated**: 2026-01-05
**Author**: Claude Sonnet 4.5
**Status**: Active - Must Be Followed
