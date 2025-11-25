#  aneya API - Vercel Serverless Functions

This directory contains the serverless-adapted FastAPI backend for Aneya, designed to run on Vercel's serverless platform.

## Files

- **index.py** - Main FastAPI application with serverless adaptations

## Key Differences from `api.py`

The serverless version (`api/index.py`) differs from the local development version (`api.py`) in several ways:

### 1. Client Initialization

**Local (`api.py`)**:
- Uses FastAPI lifespan context manager
- Initializes client once on startup
- Maintains connection throughout app lifecycle

**Serverless (`api/index.py`)**:
- Lazy initialization via `get_client()` function
- Client cached across warm starts
- Reconnects to MCP servers on cold starts

### 2. Logging

**Local**: Verbose logging enabled by default

**Serverless**: Minimal logging to reduce execution time

### 3. CORS Configuration

**Local**: Restricted to `localhost:5173` and `localhost:3000`

**Serverless**: Allows all origins (update for production!)

## Serverless Constraints

### Execution Timeout
- **Hobby Plan**: 10 seconds
- **Pro Plan**: 60 seconds

Clinical analysis can take 30-60 seconds, so **Pro plan is recommended for production**.

### Cold Starts

First request after inactivity:
- Imports all dependencies
- Initializes MCP client
- Connects to all MCP servers
- **Total**: 3-5 seconds

Subsequent requests (warm):
- Reuses cached client
- **Total**: 0.5-1 second for analysis

### Stateless Architecture

Each function invocation is stateless. The client is cached using a global variable, which persists across warm starts but not cold starts.

## Testing Locally

You cannot run the serverless version directly. For local development, use:

```bash
# From project root
python api.py
```

## Deployment

This directory is automatically deployed to Vercel as serverless functions. See `VERCEL_DEPLOYMENT.md` for details.

## API Endpoints

All endpoints are prefixed with `/api` in production:

- **GET /api/** - Health check
- **GET /api/health** - Detailed health status
- **POST /api/analyze** - Analyze clinical consultation
- **GET /api/examples** - Get example cases

## Environment Variables

Required environment variables (set in Vercel dashboard):

- `ANTHROPIC_API_KEY` - Your Anthropic API key

## Monitoring

View function logs:

```bash
vercel logs <deployment-url>
```

Or in Vercel Dashboard: **Deployments** → **Functions** → **View Logs**
