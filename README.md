# aneya Backend

FastAPI backend with MCP (Model Context Protocol) servers for clinical decision support.

## Overview

This is the backend service for aneya, providing:
- **FastAPI REST API** - Main application server
- **MCP Servers** - Specialized healthcare data servers for guidelines, drug information, and patient data
- **Claude AI Integration** - AI-powered analysis and recommendations

## Architecture

```
┌──────────────────┐         ┌─────────────────────┐
│  FastAPI Backend │ ───────▶│  MCP Servers        │
│  (Port 8000)     │         │  + Claude AI        │
└──────────────────┘         └─────────────────────┘
```

### MCP Servers

The backend connects to multiple independent FastMCP servers organized by country:

#### UK
- **NICE Guidelines** - UK clinical guidelines
- **BNF** - British National Formulary drug information

#### US
- **CDC Guidelines** - Disease prevention and control
- **AAP Guidelines** - American Academy of Pediatrics
- **ADA Standards** - American Diabetes Association
- **AHA/ACC** - Heart disease guidelines
- **IDSA** - Infectious disease guidelines
- **USPSTF** - Preventive services task force

#### India
- **ICMR** - Indian Council of Medical Research
- **FOGSI** - Obstetrics and gynecology
- **IAP** - Pediatrics guidelines
- **CSI** - Cardiology
- **RSSDI** - Diabetes
- **NCG** - Clinical guidelines
- **STG** - Standard treatment guidelines

#### Australia
- **NHMRC** - National Health and Medical Research Council

#### Cross-platform
- **PubMed** - 35M+ medical research articles
- **Patient Info** - Patient data management
- **Geolocation** - IP-based country detection

## Development Setup

### Prerequisites

- Python 3.12+ with `uv` package manager
- Anthropic API key (required for AI features)

### Installation

```bash
# Install dependencies
uv sync

# Create .env file
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
```

### Running Locally

```bash
# Run with uv
uv run python api.py

# Or run directly
python api.py
```

Backend runs on: http://localhost:8000

### API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check (verifies MCP connections)
- `POST /api/analyze` - Main consultation analysis endpoint
- `GET /api/examples` - Example clinical scenarios
- `GET /ws/transcribe` - WebSocket for real-time transcription

## Deployment

Deployed on **Google Cloud Run** (containerized FastAPI + MCP servers)
- **Region:** europe-west2 (London)
- **URL:** https://aneya-backend-fhnsxp4nua-nw.a.run.app

### Deploy to Cloud Run

```bash
# Set required environment variables
export GCP_PROJECT_ID=your-project-id
export ANTHROPIC_API_KEY=sk-ant-xxxxx

# Deploy using the provided script
./deploy-cloudrun.sh
```

See `CLOUDRUN_DEPLOYMENT.md` for detailed deployment instructions.

## Environment Variables

Required:
- `ANTHROPIC_API_KEY` - Claude API key for AI analysis

Optional:
- `DEEPGRAM_API_KEY` - For voice transcription features

## Related Repositories

- **Frontend:** [aneya](https://github.com/dangordon1/aneya) - React + TypeScript UI deployed on Vercel

## License

Proprietary
