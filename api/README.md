# Aneya API - Vercel Serverless Functions

This directory contains the serverless-adapted FastAPI backend for Aneya, designed to run on Vercel's serverless platform.

## Files

- **index.py** - Main FastAPI application with serverless adaptations

## Key Differences from `api.py`

The serverless version (`api/index.py`) differs from the main version (`api.py`) in several ways:

| Aspect | Local (`api.py`) | Serverless (`api/index.py`) |
|--------|------------------|----------------------------|
| **Initialization** | Lifespan context manager | Lazy `get_client()` function |
| **Client lifecycle** | Persistent connection | Reconnects on cold starts |
| **Logging** | Verbose | Minimal (reduces execution time) |
| **CORS** | Restricted origins | All origins (update for production!) |
| **Transcription** | NVIDIA Parakeet TDT | Not available (model too large) |

## Serverless Constraints

### Execution Timeout
| Plan | Timeout |
|------|---------|
| Hobby | 10 seconds |
| Pro | 60 seconds |

Clinical analysis typically takes 30-60 seconds, so **Pro plan is recommended**.

### Cold Starts

| Phase | Time |
|-------|------|
| First request (cold) | 3-5 seconds |
| Subsequent (warm) | 0.5-1 second |

Cold start includes:
- Import dependencies
- Initialize MCP client
- Connect to region-specific servers

### Stateless Architecture

The client is cached via global variable, persisting across warm starts but not cold starts.

## Local Development

You cannot run the serverless version directly. For local development:

```bash
# From project root
python api.py
```

## Deployment

This directory is automatically deployed to Vercel as serverless functions.

## API Endpoints

All endpoints are prefixed with `/api` in production:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/` | GET | Health check |
| `/api/health` | GET | Detailed health status |
| `/api/analyze` | POST | Analyze clinical consultation |
| `/api/examples` | GET | Get example cases |

**Note:** `/api/transcribe` is not available on Vercel (model too large for serverless).

## Environment Variables

Set in Vercel dashboard:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |

## Monitoring

```bash
# View function logs
vercel logs <deployment-url>
```

Or via Vercel Dashboard: **Deployments** → **Functions** → **View Logs**

## Recommended: Use Cloud Run Instead

For production with voice transcription, use Google Cloud Run instead of Vercel:
- Supports NVIDIA Parakeet TDT model
- Longer timeout (300s)
- More memory (4Gi)

See main `README.md` for Cloud Run deployment instructions.
