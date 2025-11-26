#!/bin/bash
# Pre-deployment test script for aneya-backend
# This script tests the API locally before deploying to Cloud Run

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Pre-Deployment Tests${NC}"
echo -e "${YELLOW}========================================${NC}"

# Check if API is running locally
API_URL="${TEST_API_URL:-http://localhost:8000}"

echo -e "${YELLOW}Testing API at: ${API_URL}${NC}"

# Test 1: Health check
echo -e "\n${YELLOW}Test 1: Health Check${NC}"
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "${API_URL}/health" 2>/dev/null || echo "FAILED\n000")
HEALTH_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
HEALTH_BODY=$(echo "$HEALTH_RESPONSE" | head -n-1)

if [ "$HEALTH_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${RED}✗ Health check failed (HTTP $HEALTH_CODE)${NC}"
    echo -e "${YELLOW}  Is the API running? Start it with: uv run python api.py${NC}"
    exit 1
fi

# Test 2: Pneumonia clinical scenario (tests BNF drug lookup)
echo -e "\n${YELLOW}Test 2: Pneumonia Case Analysis (BNF Drug Lookup)${NC}"

PNEUMONIA_CASE='Patient presents with a three-day history of productive cough with green sputum and fever 38.5 and shortness of breath. They reported feeling generally unwell with fatigue and reduced appetite. Past medical history includes type 2 diabetes mellitus well controlled on metformin, hypertension on ramipril, no known drug allergies, non-smoker. On examination respiratory rate 22 per minute, oxygen saturation 94% on air, crackles heard in right lower zone on auscultation.'

RESPONSE=$(curl -s -X POST "${API_URL}/api/analyze" \
    -H "Content-Type: application/json" \
    -d "{\"consultation\": \"${PNEUMONIA_CASE}\"}" \
    --max-time 120 2>/dev/null || echo "TIMEOUT_OR_ERROR")

if [ "$RESPONSE" = "TIMEOUT_OR_ERROR" ]; then
    echo -e "${RED}✗ API request failed or timed out${NC}"
    exit 1
fi

# Check for diagnoses
if echo "$RESPONSE" | jq -e '.diagnoses | length > 0' > /dev/null 2>&1; then
    DIAGNOSIS_COUNT=$(echo "$RESPONSE" | jq '.diagnoses | length')
    FIRST_DIAGNOSIS=$(echo "$RESPONSE" | jq -r '.diagnoses[0].name // "Unknown"')
    echo -e "${GREEN}✓ Got $DIAGNOSIS_COUNT diagnosis(es)${NC}"
    echo -e "  Primary: $FIRST_DIAGNOSIS"
else
    echo -e "${RED}✗ No diagnoses returned${NC}"
    exit 1
fi

# Check for BNF prescribing guidance
if echo "$RESPONSE" | jq -e '.bnf_prescribing_guidance | length > 0' > /dev/null 2>&1; then
    BNF_COUNT=$(echo "$RESPONSE" | jq '.bnf_prescribing_guidance | length')
    echo -e "${GREEN}✓ Got $BNF_COUNT BNF drug entries${NC}"

    # List medications found
    echo "$RESPONSE" | jq -r '.bnf_prescribing_guidance[].medication // "Unknown"' | while read med; do
        echo -e "  - $med"
    done

    # Check text doesn't have spacing issues (e.g., "forparacetamol")
    BNF_TEXT=$(echo "$RESPONSE" | jq -r '.bnf_prescribing_guidance[0].dosing // ""')
    if echo "$BNF_TEXT" | grep -q "for[a-z]" 2>/dev/null; then
        echo -e "${RED}✗ BNF text has spacing issues (words joined together)${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ BNF text formatting looks correct${NC}"
    fi
else
    echo -e "${YELLOW}⚠ No BNF prescribing guidance returned (may need proxy for BNF access)${NC}"
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}All tests passed!${NC}"
echo -e "${GREEN}========================================${NC}"
