#!/bin/bash
set -e

# aneya Backend - Google Cloud Run Deployment Script
# Deploys FastAPI backend to Cloud Run in europe-west2

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project)}"
REGION="europe-west2"
SERVICE_NAME="aneya-backend"
IMAGE_NAME="aneya-backend"
REGISTRY="europe-west2-docker.pkg.dev"
REPOSITORY="aneya"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}aneya Backend - Cloud Run Deployment${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}ERROR: gcloud CLI is not installed${NC}"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}ERROR: Docker is not installed${NC}"
    exit 1
fi

# Get project ID
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: GCP project ID not set${NC}"
    echo "Set it with: export GCP_PROJECT_ID=your-project-id"
    echo "Or configure gcloud: gcloud config set project your-project-id"
    exit 1
fi

echo -e "${YELLOW}Project ID: ${PROJECT_ID}${NC}"
echo -e "${YELLOW}Region: ${REGION}${NC}"
echo -e "${YELLOW}Service: ${SERVICE_NAME}${NC}"

# Run pre-deployment tests
echo -e "${YELLOW}Running pre-deployment tests...${NC}"
if [ -f "./test_before_deploy.sh" ]; then
    if ! bash ./test_before_deploy.sh; then
        echo -e "${RED}ERROR: Pre-deployment tests failed${NC}"
        echo -e "${RED}Aborting deployment${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ No test script found (test_before_deploy.sh)${NC}"
    echo -e "${YELLOW}  Proceeding without tests...${NC}"
fi

# Check for Anthropic API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${RED}ERROR: ANTHROPIC_API_KEY environment variable not set${NC}"
    echo "Set it with: export ANTHROPIC_API_KEY=sk-ant-xxxxx"
    exit 1
fi

echo -e "${GREEN}✓ ANTHROPIC_API_KEY found${NC}"

# Enable required APIs
echo -e "${YELLOW}Enabling required Google Cloud APIs...${NC}"
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    --project="${PROJECT_ID}"

# Create Artifact Registry repository if it doesn't exist
echo -e "${YELLOW}Ensuring Artifact Registry repository exists...${NC}"
if ! gcloud artifacts repositories describe "${REPOSITORY}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" &> /dev/null; then

    echo -e "${YELLOW}Creating Artifact Registry repository: ${REPOSITORY}${NC}"
    gcloud artifacts repositories create "${REPOSITORY}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="aneya clinical decision support system" \
        --project="${PROJECT_ID}"
else
    echo -e "${GREEN}✓ Repository ${REPOSITORY} already exists${NC}"
fi

# Configure Docker for Artifact Registry
echo -e "${YELLOW}Configuring Docker authentication...${NC}"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Build the Docker image
IMAGE_TAG="${REGISTRY}/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest"
echo -e "${YELLOW}Building Docker image: ${IMAGE_TAG}${NC}"

docker build \
    --platform linux/amd64 \
    -t "${IMAGE_TAG}" \
    -f Dockerfile \
    .

# Push the image to Artifact Registry
echo -e "${YELLOW}Pushing image to Artifact Registry...${NC}"
docker push "${IMAGE_TAG}"

# Deploy to Cloud Run
echo -e "${YELLOW}Deploying to Cloud Run...${NC}"

# Build environment variables string
ENV_VARS="ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}"

# Add ScrapeOps API key if available (preferred for Cloud Run)
if [ ! -z "${SCRAPEOPS_API_KEY}" ]; then
    echo -e "${GREEN}✓ SCRAPEOPS_API_KEY configured (BNF access via residential proxy)${NC}"
    ENV_VARS="${ENV_VARS},SCRAPEOPS_API_KEY=${SCRAPEOPS_API_KEY}"
elif [ ! -z "${BNF_PROXY_URL}" ]; then
    echo -e "${GREEN}✓ BNF_PROXY_URL configured (legacy proxy)${NC}"
    ENV_VARS="${ENV_VARS},BNF_PROXY_URL=${BNF_PROXY_URL}"
else
    echo -e "${YELLOW}⚠ No proxy configured (BNF will be blocked on Cloud Run)${NC}"
    echo -e "${YELLOW}  Set SCRAPEOPS_API_KEY to enable BNF access via proxy${NC}"
fi

gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_TAG}" \
    --platform=managed \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --allow-unauthenticated \
    --memory=2Gi \
    --cpu=2 \
    --timeout=300 \
    --max-instances=10 \
    --min-instances=0 \
    --set-env-vars="${ENV_VARS}" \
    --port=8080

# Get the service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --platform=managed \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --format='value(status.url)')

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Service URL: ${SERVICE_URL}${NC}"
echo -e "${GREEN}Health Check: ${SERVICE_URL}/health${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Test the API: curl ${SERVICE_URL}/health"
echo "2. Update frontend API URL in frontend/src/App.tsx"
echo "3. Update CORS origins in api.py to include ${SERVICE_URL}"
echo ""
echo -e "${YELLOW}To view logs:${NC}"
echo "gcloud run services logs read ${SERVICE_NAME} --region=${REGION} --project=${PROJECT_ID}"
