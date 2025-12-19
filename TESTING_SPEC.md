# Backend Testing Specification

This document defines the testing workflow for backend features. **All tests at each stage must pass before progressing to the next stage.**

## Test Directory Structure

```
tests/
├── unit/                           # Stage 1: Isolated unit tests
│   ├── drug_lookup/
│   │   ├── test_bnf.py            # BNF drug lookup (search, info, parallel)
│   │   └── test_drugbank.py       # DrugBank integration
│   ├── guidelines/
│   │   └── test_india.py          # FOGSI, NHM, AIIMS servers
│   └── test_consultation_summary.py
│
├── integration/                    # Stage 2: Client integration tests
│   ├── test_clinical_agent.py     # Full workflow with events
│   └── test_full_clinical_agent.py # Legacy integration test
│
├── api/                            # Stage 3: API endpoint tests
│   ├── test_endpoints.py          # Health, analyze, summarize endpoints
│   ├── test_sse_streaming.py      # SSE event streaming
│   └── test_diarization.py        # Diarization endpoint
│
└── e2e/                            # Stage 4+: End-to-end tests
    └── test_cloudrun_proxy.py     # Cloud Run proxy verification
```

## Testing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TESTING PIPELINE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Stage 1: Unit Testing (Isolated)                                           │
│  ─────────────────────────────────                                          │
│  python tests/unit/drug_lookup/test_bnf.py                                  │
│                                                                             │
│                              ▼ PASS                                         │
│                                                                             │
│  Stage 2: Client Integration Testing                                        │
│  ────────────────────────────────────                                       │
│  python tests/integration/test_clinical_agent.py                            │
│                                                                             │
│                              ▼ PASS                                         │
│                                                                             │
│  Stage 3: API Integration Testing                                           │
│  ────────────────────────────────                                           │
│  python api.py &  # Start server                                            │
│  python tests/api/test_endpoints.py                                         │
│                                                                             │
│                              ▼ PASS                                         │
│                                                                             │
│  Stage 4: Manual User Testing                                               │
│  ────────────────────────────                                               │
│  Human verification on locally running frontend                             │
│                                                                             │
│                              ▼ PASS                                         │
│                                                                             │
│  Stage 5: Push & Deploy (CI/CD)                                             │
│  ──────────────────────────────                                             │
│  git push → PR → merge to main → Cloud Build → Cloud Run                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Stage 1: Unit Testing (Isolated)

**Purpose:** Verify the feature/tool works correctly in isolation

### Test Commands

```bash
# BNF drug lookup
python tests/unit/drug_lookup/test_bnf.py

# DrugBank
python tests/unit/drug_lookup/test_drugbank.py

# India guidelines (FOGSI, NHM, AIIMS)
python tests/unit/guidelines/test_india.py

# Consultation summary
python tests/unit/test_consultation_summary.py
```

### Pass Criteria
- [ ] Server connects successfully
- [ ] All tools listed and accessible
- [ ] Tool calls return expected data structure
- [ ] Data content is valid (not empty, properly formatted)
- [ ] Exit code 0

---

## Stage 2: Client Integration Testing

**Purpose:** Verify the feature works within the ClinicalDecisionSupportClient

### Test Commands

```bash
# Main integration test
python tests/integration/test_clinical_agent.py

# Legacy full workflow test
python tests/integration/test_full_clinical_agent.py
```

### Pass Criteria
- [ ] Client connects to all required servers
- [ ] Tools discovered and mapped correctly
- [ ] Feature integrates with clinical workflow
- [ ] Events streamed in correct order (diagnoses → drug_update → complete)
- [ ] Exit code 0

---

## Stage 3: API Integration Testing

**Purpose:** Verify frontend-backend compatibility via HTTP/SSE

### Test Commands

```bash
# Start backend first
python api.py &
sleep 5

# Run API tests
python tests/api/test_endpoints.py
python tests/api/test_sse_streaming.py
```

### Pass Criteria
- [ ] API endpoints respond correctly
- [ ] SSE events received in expected format
- [ ] Response JSON structure valid
- [ ] No CORS or connectivity issues

---

## Stage 4: Manual User Testing

**Purpose:** Human verification of end-to-end functionality

### Setup

```bash
# Terminal 1: Backend
python api.py

# Terminal 2: Frontend
cd ../aneya-frontend
npm run dev
```

### Test Checklist
- [ ] Open http://localhost:3000 in browser
- [ ] Enter test consultation
- [ ] Diagnoses appear in the UI
- [ ] Drug information loads and displays
- [ ] Summary is generated
- [ ] No visual glitches or errors
- [ ] No JavaScript console errors
- [ ] Response time acceptable (<30s)

---

## Stage 5: Push & Deploy (CI/CD)

**Purpose:** Deploy via Git workflow triggering Cloud Build

### Commands

```bash
# 1. Create feature branch (if on main)
git checkout -b feature/<feature-name>

# 2. Commit changes
git add -A
git commit -m "feat: <description>"

# 3. Push to remote
git push -u origin $(git branch --show-current)

# 4. Create PR
gh pr create --title "<title>" --body "..."

# 5. Merge to main (triggers Cloud Build)
gh pr merge --merge

# 6. Verify deployment
gcloud builds list --limit=1
curl -s "$(gcloud run services describe aneya-backend --region europe-west2 --format='value(status.url)')/health"
```

### Pass Criteria
- [ ] PR created and merged successfully
- [ ] Cloud Build triggered and completed
- [ ] Health check returns 200
- [ ] No deployment errors

---

## Quick Reference: Test by Feature

| Feature | Stage 1 | Stage 2 | Stage 3 |
|---------|---------|---------|---------|
| BNF Drug Lookup | `tests/unit/drug_lookup/test_bnf.py` | `tests/integration/test_clinical_agent.py` | `tests/api/test_endpoints.py` |
| DrugBank | `tests/unit/drug_lookup/test_drugbank.py` | `tests/integration/test_clinical_agent.py` | `tests/api/test_endpoints.py` |
| India Guidelines | `tests/unit/guidelines/test_india.py` | `tests/integration/test_clinical_agent.py` | `tests/api/test_endpoints.py` |
| Full Clinical Agent | - | `tests/integration/test_clinical_agent.py` | `tests/api/test_sse_streaming.py` |

---

## Using the /test-feature Skill

The `/test-feature` slash command guides you through this pipeline automatically:

```bash
/test-feature BNF drug lookup
/test-feature India guidelines
/test-feature Full clinical agent
```

The skill will:
1. Run appropriate tests at each stage
2. Block progression if any stage fails
3. Help debug failures
4. Guide through manual testing
5. Assist with PR creation and deployment

---

## Troubleshooting

### Stage 1 Failures
- Check MCP server can start: `python servers/drug_lookup/bnf_server.py`
- Verify environment variables: `SCRAPEOPS_API_KEY`, `ANTHROPIC_API_KEY`
- Check network connectivity to external APIs

### Stage 2 Failures
- Verify server paths in `servers/clinical_decision_support/config.py`
- Check all required servers can connect
- Review tool routing in client logs

### Stage 3 Failures
- Ensure API is running on port 8000
- Check CORS configuration in `api.py`
- Verify SSE event format

### Stage 4 Failures
- Check browser console for JavaScript errors
- Verify frontend environment variables
- Test with different browsers

### Stage 5 Failures
- Check Cloud Build logs: `gcloud builds log <build-id>`
- Verify secrets in Cloud Run
- Check service account permissions
