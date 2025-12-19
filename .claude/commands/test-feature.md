# Test Feature Pipeline

You are guiding the user through a 5-stage testing pipeline for backend features. **Each stage must pass before progressing to the next.**

## Pipeline Overview

```
Stage 1: Unit Testing (Isolated)
    ↓ PASS
Stage 2: Client Integration Testing
    ↓ PASS
Stage 3: API Integration Testing
    ↓ PASS
Stage 4: Manual User Testing
    ↓ PASS
Stage 5: Push to Branch & Merge to Main (triggers CI/CD deployment)
```

## Your Role

1. **Identify the feature** being tested from the user's input: $ARGUMENTS
2. **Execute tests** at each stage
3. **Report results** clearly with pass/fail status
4. **Block progression** if a stage fails - help debug before continuing
5. **Track progress** using the TodoWrite tool

## Stage Definitions

### Stage 1: Unit Testing (Isolated)
Test the feature/tool in complete isolation from other components.

**Run the appropriate test:**
```bash
# BNF drug lookup
python tests/unit/drug_lookup/test_bnf.py

# DrugBank
python tests/unit/drug_lookup/test_drugbank.py

# India guidelines (FOGSI, NHM, AIIMS)
python tests/unit/guidelines/test_india.py

# Legacy individual tests (if new tests don't exist yet)
python test_bnf_amoxicillin.py
python test_drugbank.py
python test_fogsi.py
python test_nhm.py
```

**Pass Criteria:**
- Server connects successfully
- All tools listed and accessible
- Tool calls return expected data structure
- Exit code 0

### Stage 2: Client Integration Testing
Test the feature within the ClinicalDecisionSupportClient.

```bash
python tests/integration/test_clinical_agent.py
```

**Or legacy test:**
```bash
python test_full_clinical_agent.py
```

**Pass Criteria:**
- Client connects to all required servers
- Tools discovered and mapped correctly
- Feature integrates with clinical workflow
- Events streamed in correct order
- Exit code 0

### Stage 3: API Integration Testing
Test frontend-backend compatibility via HTTP/SSE.

**First, check if API is running:**
```bash
curl -s http://localhost:8000/health || echo "API not running"
```

**If not running, start it in background:**
```bash
python api.py &
sleep 5
```

**Then run API tests:**
```bash
python tests/api/test_endpoints.py
```

**Pass Criteria:**
- API endpoints respond correctly
- SSE events received in expected format
- Response JSON structure valid

### Stage 4: Manual User Testing
Prompt the user to perform manual testing.

**Instructions to give the user:**
1. Ensure backend is running: `python api.py`
2. Start frontend: `cd ../aneya-frontend && npm run dev`
3. Open http://localhost:3000 in browser
4. Test the feature manually
5. Report back: "Stage 4 passed" or describe any issues

**Ask the user to verify:**
- [ ] Feature works as expected in UI
- [ ] No visual glitches or errors
- [ ] No JavaScript console errors
- [ ] Response time acceptable

**Wait for user confirmation before proceeding.**

### Stage 5: Push to Branch & Merge to Main
This triggers the CI/CD pipeline which automatically deploys to Cloud Run.

**Step 5a: Create/switch to feature branch (if not already on one):**
```bash
git branch --show-current
# If on main, create a feature branch:
git checkout -b feature/<feature-name>
```

**Step 5b: Commit all changes:**
```bash
git add -A
git status
git commit -m "feat: <description of changes>"
```

**Step 5c: Push to remote:**
```bash
git push -u origin $(git branch --show-current)
```

**Step 5d: Create PR and merge to main:**
```bash
gh pr create --title "<PR title>" --body "## Summary
- <changes made>

## Testing
- [x] Unit tests pass
- [x] Integration tests pass
- [x] API tests pass
- [x] Manual testing completed

🤖 Generated with Claude Code"

# After PR is approved, merge:
gh pr merge --merge
```

**Step 5e: Verify CI/CD deployment:**
```bash
# Check Cloud Build status
gcloud builds list --limit=1

# Once deployed, verify health:
curl -s "$(gcloud run services describe aneya-backend --region europe-west2 --format='value(status.url)')/health"
```

**Pass Criteria:**
- PR created and merged successfully
- Cloud Build triggered and completed
- Health check returns 200
- No deployment errors

## Execution Instructions

1. **Create a todo list** tracking all 5 stages
2. **Run Stage 1** - if it fails, debug and retry before continuing
3. **Run Stage 2** - only if Stage 1 passed
4. **Run Stage 3** - only if Stage 2 passed
5. **Prompt for Stage 4** - wait for user confirmation
6. **Run Stage 5** - only after Stage 4 passed and user confirms deployment

## Output Format

After each stage, report:
```
═══════════════════════════════════════════════════════════════
STAGE X: [Stage Name] - [PASSED/FAILED]
═══════════════════════════════════════════════════════════════
[Summary of what was tested]
[Key results]
[Any issues found]

Next: [Stage X+1] or [Debug required]
═══════════════════════════════════════════════════════════════
```

## If No Arguments Provided

If the user didn't specify a feature, ask:
"Which feature would you like to test? Options include:
- BNF drug lookup
- DrugBank integration
- India guidelines (FOGSI, NHM, AIIMS)
- Full clinical agent
- API endpoints
- Custom (specify test file)"

## Test File Locations

```
tests/
├── unit/                    # Stage 1: Isolated unit tests
│   ├── drug_lookup/
│   │   ├── test_bnf.py
│   │   └── test_drugbank.py
│   └── guidelines/
│       └── test_india.py
├── integration/             # Stage 2: Client integration tests
│   └── test_clinical_agent.py
├── api/                     # Stage 3: API endpoint tests
│   └── test_endpoints.py
└── e2e/                     # Stage 4: End-to-end (manual)
```

Now begin the testing pipeline for: $ARGUMENTS
