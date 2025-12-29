# Medical Literature MCP Servers

This directory contains FastMCP servers for accessing medical literature databases.

## Available Servers

### 1. PubMed Server (`pubmed_server.py`)

Access to PubMed's 35M+ peer-reviewed medical literature via NCBI E-utilities.

**Features:**
- Search PubMed articles
- Retrieve full article details including abstracts
- Batch retrieve multiple articles

**Environment Variables:**
- `NCBI_API_KEY` (optional, but recommended for higher rate limits)

**Usage:**
```bash
python pubmed_server.py
```

### 2. BMJ Server (`bmj_server.py`)

Access to British Medical Journal publications via Europe PMC API.

**Features:**
- Search BMJ publications (BMJ, BMJ Open, BMJ Case Reports)
- Retrieve full article details with abstracts
- Get download URLs for articles (HTML and PDF)
- Access open access content freely

**Environment Variables:**
- `BMJ_API_KEY` (optional, for direct BMJ API access)

**Usage:**
```bash
python bmj_server.py
```

**Note:** Uses Europe PMC API which indexes BMJ content. Some content may require institutional subscription.

### 3. Scopus Server (`scopus_server.py`)

Access to Scopus database with journal quartile filtering capabilities.

**Features:**
- Search Scopus articles with quartile filtering (Q1/Q2)
- Retrieve full article details with citations
- Get journal quartile rankings (SJR and CiteScore)
- Filter by top-tier journals (Q1 = top 25%, Q2 = 25-50%)
- Search high-impact articles only

**Environment Variables:**
- `SCOPUS_API_KEY` (required) - Get your API key from https://dev.elsevier.com/

**Usage:**
```bash
export SCOPUS_API_KEY='your-key-here'
python scopus_server.py
```

**Quartile Filtering:**
- Q1: Top 25% of journals in their field
- Q2: 25-50% percentile journals
- Q1-Q2: Top 50% of journals (high-impact)

## Testing

Each server has a corresponding test file:

```bash
# Test BMJ server (no API key required)
python test_bmj_server.py

# Test Scopus server (requires SCOPUS_API_KEY)
export SCOPUS_API_KEY='your-key-here'
python test_scopus_server.py
```

## API Keys

### NCBI API Key (PubMed)
- **Optional** but recommended
- Sign up at: https://www.ncbi.nlm.nih.gov/account/
- Increases rate limit from 3 to 10 requests per second

### Scopus API Key
- **Required** for Scopus server
- Register at: https://dev.elsevier.com/
- Free tier available for academic/research use

## Rate Limits

- **PubMed**: 3 req/sec without key, 10 req/sec with key
- **Europe PMC** (BMJ): ~5 req/sec recommended
- **Scopus**: 2 req/sec (free tier), varies by subscription

## Architecture

All servers are built using FastMCP, which provides:
- Standardized tool interface
- Automatic JSON schema generation
- Built-in error handling
- Easy integration with MCP clients

## Example Usage

### Search for high-impact diabetes research in Q1 journals

```python
# Using Scopus server
result = await search_scopus(
    query="diabetes treatment",
    max_results=10,
    quartile_filter="Q1"
)
```

### Get BMJ article with download URLs

```python
# Using BMJ server
article = await get_bmj_article(
    article_id="33526403",
    id_type="MED"
)

download_info = await download_bmj_article(
    doi=article['doi'],
    pmcid=article.get('pmcid', '')
)
```

### Search PubMed for recent COVID research

```python
# Using PubMed server
result = await search_pubmed(
    query="COVID-19 treatment 2024",
    max_results=20
)
```

## Integration

These servers can be integrated with:
- Claude Code MCP
- Other MCP-compatible clients
- Direct API integration via FastMCP

For remote deployment, these servers can be run as standalone services accessible via HTTP/SSE.

## Notes

- BMJ server uses Europe PMC as an intermediary for broader access
- Scopus quartile data is based on latest SJR and CiteScore metrics
- All servers implement proper rate limiting to be respectful of API providers
- Error handling is built in for missing API keys and network issues
