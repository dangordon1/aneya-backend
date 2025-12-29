# Aneya Backend

FastAPI backend with MCP (Model Context Protocol) servers for clinical decision support. Provides evidence-based clinical recommendations by integrating 22+ regional guideline servers with Claude AI analysis.

## Overview

Aneya is a **Clinical Decision Support System** that helps healthcare professionals make informed decisions by analyzing patient consultations against authoritative medical guidelines and research literature.

Key features:
- **Multi-Region Support** - UK, US, India, Australia + International fallback
- **22+ Guideline Servers** - Comprehensive healthcare coverage from authoritative sources
- **Intelligent Fallback** - Regional guidelines → PubMed when needed
- **Real-time Voice Input** - ElevenLabs Scribe v2 Realtime / Sarvam AI streaming transcription
- **Drug Safety** - BNF information with interaction and allergy warnings

## Architecture

```
┌──────────────────┐      ┌─────────────────────────────────────────────────┐
│  React Frontend  │      │        Clinical Decision Support Client         │
│    (Vercel)      │─────▶│         (Orchestration Layer)                   │
└──────────────────┘      │  • Region detection (IP geolocation)            │
                          │  • Parallel server connections                   │
                          │  • Smart fallback: Guidelines → PubMed          │
                          └─────────────────────────────────────────────────┘
                                              │
         ┌──────────────┬─────────────┬───────┴───────┬──────────────┐
         │              │             │               │              │
    ┌────▼────┐   ┌────▼────┐   ┌────▼────┐    ┌────▼────┐   ┌─────▼─────┐
    │   UK    │   │   US    │   │  India  │    │Australia│   │ Cross-    │
    │ Servers │   │ Servers │   │ Servers │    │ Servers │   │ Platform  │
    │         │   │         │   │         │    │         │   │           │
    │ • NICE  │   │ • CDC   │   │ • ICMR  │    │ • NHMRC │   │ • PubMed  │
    │ • BNF   │   │ • AAP   │   │ • FOGSI │    │         │   │ • GeoIP   │
    │         │   │ • ADA   │   │ • IAP   │    │         │   │ • Patient │
    │         │   │ • AHA   │   │ • CSI   │    │         │   │           │
    │         │   │ • IDSA  │   │ • RSSDI │    │         │   │           │
    │         │   │ • USPSTF│   │ • NCG   │    │         │   │           │
    │         │   │         │   │ • STG   │    │         │   │           │
    └─────────┘   └─────────┘   └─────────┘    └─────────┘   └───────────┘
```

### MCP Servers by Region

| Region | Servers | Description |
|--------|---------|-------------|
| **UK** | NICE, BNF | Clinical guidelines + British National Formulary |
| **US** | CDC, AAP, ADA, AHA/ACC, IDSA, USPSTF | Disease control, pediatrics, diabetes, cardiology, infectious disease, preventive services |
| **India** | ICMR, FOGSI, IAP, CSI, RSSDI, NCG, STG | Medical research, OB/GYN, pediatrics, cardiology, diabetes, cancer, standard treatment |
| **Australia** | NHMRC | National health research guidelines |
| **Cross-platform** | PubMed, Geolocation, Patient Info | 35M+ articles, IP detection, patient data |

## Development Setup

### Prerequisites

- Python 3.12+
- `uv` package manager
- Anthropic API key (required)

### Installation

```bash
# Install dependencies
uv sync

# Create .env file with your API key
echo "ANTHROPIC_API_KEY=sk-ant-xxxxx" > .env
```

### Running Locally

```bash
# Run the API server
python api.py
```

The API will be available at: http://localhost:8000

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/health` | GET | Detailed health status |
| `/api/health` | GET | Frontend compatibility health check |
| `/api/analyze` | POST | Analyze clinical consultation |
| `/api/examples` | GET | Example clinical scenarios |
| `/api/transcribe` | POST | Transcribe audio (ElevenLabs Scribe v2) |
| `/api/diarize` | POST | Diarize audio with speaker labels (ElevenLabs) |
| `/api/diarize-sarvam` | POST | Diarize audio (Sarvam - Indian languages) |
| `/api/identify-speaker-roles` | POST | Identify doctor vs patient speakers (Claude Haiku) |
| `/api/rerun-transcription` | POST | Rerun transcription/diarization on past consultations |
| `/api/get-transcription-token` | GET | Get temporary token for ElevenLabs WebSocket |
| `/api/get-sarvam-token` | GET | Get API key for Sarvam WebSocket |

## Deployment

### Google Cloud Run (Production)

- **Region:** europe-west2 (London)
- **URL:** https://aneya-backend-fhnsxp4nua-nw.a.run.app
- **Resources:** 4Gi RAM, 2 CPU, 300s timeout

```bash
# Deploy using the provided script
export GCP_PROJECT_ID=your-project-id
export ANTHROPIC_API_KEY=sk-ant-xxxxx
./deploy-cloudrun.sh
```

### Vercel (Alternative)

See `/api/README.md` for serverless deployment on Vercel.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for AI analysis |
| `ELEVENLABS_API_KEY` | Yes | ElevenLabs API key for transcription & diarization |
| `SARVAM_API_KEY` | No | Sarvam AI key for Indian language transcription |
| `NCBI_API_KEY` | No | PubMed higher rate limits |
| `SCRAPEOPS_API_KEY` | No | Cloud Run BNF proxy |

## Project Structure

```
aneya-backend/
├── api.py                    # Main FastAPI application
├── app.py                    # Streamlit web UI
├── Dockerfile                # Multi-stage Docker build
├── deploy-cloudrun.sh        # Cloud Run deployment script
├── api/                      # Vercel serverless functions
│   └── index.py
├── servers/                  # MCP servers and orchestration
│   ├── clinical_decision_support/
│   │   ├── client.py         # Main orchestration client
│   │   └── config.py         # Regional configurations
│   ├── guidelines/           # Regional guideline servers
│   │   ├── uk/               # NICE, BNF
│   │   ├── us/               # CDC, AAP, ADA, AHA, IDSA, USPSTF
│   │   ├── india/            # ICMR, FOGSI, IAP, CSI, RSSDI, NCG, STG
│   │   └── australia/        # NHMRC
│   ├── pubmed_server.py      # Medical literature (35M+ articles)
│   ├── geolocation_server.py # IP-based country detection
│   └── tests/                # Comprehensive test suite
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific region tests
pytest servers/tests/test_uk_mcp_client.py
```

## Safety Disclaimer

This tool provides reference information from clinical guidelines and drug formularies. It is designed to **assist** healthcare professionals, not replace clinical judgment. Always:
- Verify dosing before prescribing
- Consider patient-specific factors
- Follow local protocols and formularies
- Use professional clinical judgment

## Related Repositories

- **Frontend:** [aneya](https://github.com/dangordon1/aneya) - React + TypeScript UI deployed on Vercel

## License

Proprietary
