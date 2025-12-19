# NHM Guidelines MCP Server

MCP server providing access to National Health Mission (NHM) clinical and operational guidelines from India's Ministry of Health & Family Welfare.

## Overview

The NHM Guidelines server provides comprehensive access to:
- Healthcare service guidelines
- Laboratory services operational documents
- Medical device specifications (Anesthesia, Cardiology, ENT, Ophthalmology, Radiotherapy)
- Disease control programs (NCDs, Dialysis, Hemoglobinopathies)
- Facility management standards (Kayakalp, Mobile Medical Units)
- Community health initiatives (Rogi Kalyan Samities, Health Melas, Telemedicine)
- Free diagnostic and drug service initiatives

## Source

**Website:** https://nhm.gov.in/index1.php?lang=1&level=1&sublinkid=197&lid=136

## Tools and Resources

### Tools (Actions)

Tools perform searches and dynamic operations.

### 1. `search_nhm_guidelines` (Tool)

Search for NHM guidelines and operational documents by keyword.

**Parameters:**
- `keyword` (string, required): Search term (e.g., "laboratory", "diagnostic services", "dialysis")
- `max_results` (int, optional): Maximum results to return (default: 20, max: 50)

**Returns:**
```json
{
  "success": true,
  "query": "diagnostic",
  "count": 3,
  "results": [
    {
      "title": "Operational Guidelines for Strengthening Laboratory Services...",
      "url": "https://nhm.gov.in/...",
      "description": "NHM Guideline: Operational Guidelines for...",
      "category": "NHM Guidelines",
      "file_size": "2.5 MB",
      "published_date": "Not available"
    }
  ],
  "error": null
}
```

### Resources (Static Data)

Resources provide read-only access to static guideline data. Unlike tools, resources don't take parameters and provide consistent data views.

### 2. `nhm://guidelines/list` (Resource)

List all available NHM guidelines and operational documents.

**URI:** `nhm://guidelines/list`

**Parameters:** None (resources don't take parameters)

**Returns:**
```json
{
  "success": true,
  "count": 45,
  "guidelines": [
    {
      "title": "Operational Guidelines for Strengthening Laboratory Services...",
      "url": "https://nhm.gov.in/...",
      "category": "NHM Guidelines",
      "file_size": "2.5 MB"
    }
  ],
  "error": null
}
```

**Note:** Returns up to 100 guidelines (fixed limit for resource).

### 3. `nhm://guidelines/categories` (Resource)

Get NHM guidelines organized by category.

**URI:** `nhm://guidelines/categories`

**Parameters:** None (resources don't take parameters)

**Returns:**
```json
{
  "success": true,
  "categories": [
    {
      "name": "Laboratory Services",
      "guideline_count": 5,
      "description": "NHM guidelines related to laboratory services"
    }
  ],
  "total_guidelines": 45,
  "error": null
}
```

## Usage Examples

### Search for specific guidelines

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python",
    args=["servers/guidelines/india/nhm_guidelines_server.py"]
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()

        # Search for laboratory guidelines
        result = await session.call_tool(
            "search_nhm_guidelines",
            arguments={"keyword": "laboratory", "max_results": 5}
        )
```

### List all guidelines (Resource)

```python
# Read the guidelines list resource
result = await session.read_resource("nhm://guidelines/list")

# Parse the JSON response
import json
data = json.loads(result.contents[0].text)
print(f"Found {data['count']} guidelines")
```

### Get categories (Resource)

```python
# Read the categories resource
result = await session.read_resource("nhm://guidelines/categories")

# Parse the JSON response
import json
data = json.loads(result.contents[0].text)
print(f"Found {len(data['categories'])} categories")
```

## Integration with Clinical Decision Support

The NHM server is automatically loaded for users in India (country code: IN) as part of the regional guideline system.

**Configuration** (`servers/clinical_decision_support/config.py`):
```python
"INDIA": RegionConfig(
    region_name="India",
    country_codes=["IN"],
    required_servers=["patient_info", "fogsi", "nhm", "drugbank", "pubmed"],
    searches=[
        SearchConfig(
            resource_type=ResourceType.GUIDELINE,
            tool_name="search_nhm_guidelines",
            tool_params={"keyword": "{clinical_scenario}", "max_results": 10},
            result_key="nhm_guidelines",
            deduplicate=False,
            required=False
        )
    ]
)
```

## Testing

Run the test suite:

```bash
# Test the NHM server directly
python test_nhm.py

# Test integration with backend
python test_nhm_integration.py
```

## Technical Details

- **Framework:** FastMCP 2.13.0.2
- **Dependencies:** httpx, beautifulsoup4, lxml
- **Transport:** STDIO
- **Parsing:** HTML table parsing with BeautifulSoup
- **Content Type:** PDF documents (linked from HTML table)

## Coverage

The server provides access to:
- ✅ Laboratory service guidelines
- ✅ Diagnostic service initiatives
- ✅ Medical device specifications
- ✅ Disease control programs
- ✅ Facility management standards
- ✅ Community health programs
- ✅ Telemedicine guidelines
- ✅ Free drug service initiatives

## Limitations

- Guidelines are primarily available as PDF downloads (links provided)
- Publication dates are not always available in the source
- Content is parsed from HTML tables on the NHM website
- Categorization is based on page structure and may be limited

## Related Servers

- **FOGSI Server** (`fogsi_server.py`): Obstetrics & gynecology guidelines
- **DrugBank Server** (`drugbank_server.py`): Drug information
- **MIMS India Server** (`mims_india_server.py`): Drug information for India

## Maintenance

The server depends on the structure of the NHM website. If the website structure changes, the HTML parsing logic in `search_nhm_guidelines()` and `list_nhm_guidelines()` may need to be updated.

## License

Part of the Aneya Clinical Decision Support System.
