# NICE Guidelines MCP Server

An MCP server that provides access to UK NICE (National Institute for Health and Care Excellence) clinical guidelines through web scraping.

## Overview

This server enables AI assistants to search and retrieve clinical guidelines from NICE, the UK's authoritative source for evidence-based healthcare guidance. The server scrapes the NICE website to provide access to thousands of published guidelines across multiple categories.

## Features

- **Search Guidelines**: Search for NICE guidelines by keyword or topic
- **Get Guideline Details**: Retrieve comprehensive information about specific guidelines
- **List Categories**: Browse available guideline categories and types

## Tools

### 1. search_nice_guidelines

Search NICE guidelines by keyword or topic.

**Parameters:**
- `keyword` (required): Search term or topic (e.g., "diabetes", "pregnancy", "ng235")
- `max_results` (optional): Maximum number of results to return (default: 20, max: 100)

**Returns:**
- `success`: Boolean indicating if search was successful
- `query`: The search keyword used
- `count`: Number of results found
- `results`: Array of matching guidelines containing:
  - `reference`: Guideline reference number (e.g., "NG235")
  - `title`: Full title of the guideline
  - `url`: Direct URL to the guideline page
  - `published_date`: Publication date
  - `last_updated`: Last update date
- `error`: Error message if search failed

**Example:**
```python
{
    "keyword": "diabetes",
    "max_results": 5
}
```

### 2. get_guideline_details

Get detailed information about a specific NICE guideline.

**Parameters:**
- `identifier` (required): Guideline reference number (e.g., "NG235", "TA1109") or full URL

**Returns:**
- `success`: Boolean indicating if retrieval was successful
- `reference`: Guideline reference number
- `title`: Full title of the guideline
- `url`: Direct URL to the guideline
- `overview`: Summary/overview of the guideline (truncated to 500 chars)
- `published_date`: Publication date
- `last_updated`: Last update date
- `guideline_type`: Type of guidance (e.g., "NICE guideline")
- `sections`: Available sections/chapters in the guideline (up to 15)
- `related_guidance`: Links to related NICE guidelines (up to 5)
- `error`: Error message if retrieval failed

**Example:**
```python
{
    "identifier": "NG235"
}
```

### 3. list_guideline_categories

List available NICE guideline categories and types.

**Parameters:** None

**Returns:**
- `success`: Boolean indicating if retrieval was successful
- `categories`: Array of guideline categories containing:
  - `name`: Category name (e.g., "Clinical guidelines")
  - `code`: Category code/abbreviation (e.g., "NG", "TA")
  - `count`: Number of guidelines in category (if available)
  - `description`: Brief description of the category
  - `url`: URL to browse this category
- `error`: Error message if retrieval failed

**Categories include:**
- All published guidance (ALL)
- Clinical guidelines (NG)
- Technology appraisal guidance (TA)
- Interventional procedures guidance (IPG)
- Medical technologies guidance (MTG)
- Diagnostics guidance (DG)
- Quality standards (QS)
- Public health guidelines (PH)
- Social care guidelines (SC)

## Installation

The server requires Python 3.12+ and the following dependencies:

```bash
pip install mcp httpx beautifulsoup4 lxml
```

Or using the project's pyproject.toml:

```bash
uv sync
```

## Usage

### Running the Server

```bash
python /Users/dgordon/python/hackathons/heidi/servers/nice_guidelines_server.py
```

### Configuration

Add to your MCP client configuration (e.g., Claude Desktop config):

```json
{
  "mcpServers": {
    "nice-guidelines": {
      "command": "python",
      "args": [
        "/Users/dgordon/python/hackathons/heidi/servers/nice_guidelines_server.py"
      ],
      "cwd": "/Users/dgordon/python/hackathons/heidi/servers"
    }
  }
}
```

## Technical Details

### Web Scraping Approach

The server uses web scraping instead of an API because:
- NICE does not provide a public API for guideline access
- Web scraping ensures access to the most up-to-date content
- All public information on the NICE website is accessible

### Implementation

- **Async/Await**: Uses Python's asyncio for efficient concurrent operations
- **HTTP Client**: httpx for async HTTP requests
- **HTML Parsing**: BeautifulSoup4 with lxml parser for robust HTML parsing
- **Error Handling**: Comprehensive error handling with fallback strategies
- **Timeout Settings**: 30-second timeout to prevent hanging requests
- **User Agent**: Custom user agent header for proper web scraping etiquette

### Rate Limiting

The server implements reasonable delays and timeouts to avoid overwhelming the NICE website. For production use, consider implementing:
- Request rate limiting
- Response caching
- Respectful crawling delays

## Guideline Reference Numbers

NICE uses different prefixes for different types of guidance:
- **NG**: NICE guidelines (clinical)
- **TA**: Technology appraisal guidance
- **IPG**: Interventional procedures guidance
- **MTG**: Medical technologies guidance
- **DG**: Diagnostics guidance
- **QS**: Quality standards
- **PH**: Public health guidelines
- **SC**: Social care guidelines

## Example Use Cases

1. **Search for diabetes guidelines:**
   ```python
   search_nice_guidelines(keyword="diabetes", max_results=10)
   ```

2. **Get details of a specific guideline:**
   ```python
   get_guideline_details(identifier="NG235")
   ```

3. **Browse available categories:**
   ```python
   list_guideline_categories()
   ```

## Limitations

- Web scraping is subject to website structure changes
- Some detailed content may require additional requests
- Date formats may vary across different guideline pages
- Network connectivity required for all operations

## License

This server is for educational and research purposes. Please ensure compliance with NICE's terms of service when using this server.

## Credits

Developed for the Heidi healthcare assistant project.
