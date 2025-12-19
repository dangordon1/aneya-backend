# MIMS India MCP Server

Production-grade MCP server for retrieving drug information from MIMS India (www.mims.com/india).

## Current Status

⚠️ **NOT CURRENTLY IN USE** - The India region is temporarily using BNF for drug information until MIMS API access is obtained. The server code is ready and tested, reserved for future integration when API credentials become available.

## Features

- **Drug Search**: Search for medications by name in the Indian market
- **Bright Data Proxy**: Uses residential proxy to bypass Cloudflare protection
- **Caching**: In-memory caching to reduce API calls
- **Authentication Support**: Optional login for premium content (via environment variables)

## Tools

### 1. `search_mims_drugs`
Search for drugs/medications by name and return matching results.

**Parameters**:
- `drug_name` (string): Name of the drug to search for

**Returns**:
```json
{
  "query": "paracetamol",
  "results": [
    {
      "name": "Paracetamol",
      "url": "https://www.mims.com/india/drug/info/paracetamol",
      "type": "Generic",
      "strength": null
    }
  ],
  "count": 1,
  "success": true,
  "error": null
}
```

### 2. `get_mims_drug_details`
Get detailed information about a specific drug (indications, dosage, contraindications, etc.).

**Parameters**:
- `drug_url` (string): Full URL to the drug's MIMS page

**Returns**:
```json
{
  "drug_name": "Paracetamol",
  "generic_name": null,
  "indications": "...",
  "dosage": "...",
  "contraindications": "...",
  "side_effects": "...",
  "interactions": "...",
  "pregnancy_category": null,
  "manufacturer": null,
  "url": "https://www.mims.com/india/drug/info/paracetamol",
  "success": true,
  "error": null
}
```

### 3. `check_mims_interactions`
Check for drug interactions between multiple medications.

**Parameters**:
- `drug_names` (array): List of drug names to check

**Returns**:
```json
{
  "drugs": ["aspirin", "warfarin"],
  "interactions": [],
  "count": 0,
  "success": false,
  "error": "Feature may require authentication or not be publicly available"
}
```

## Configuration

### Environment Variables

- `MIMS_USERNAME` (optional): MIMS account username for premium features
- `MIMS_PASSWORD` (optional): MIMS account password for premium features

If credentials are not provided, the server operates in public mode with limited access.

### Proxy

The server uses Bright Data residential proxy (same as BNF server):
- **Host**: brd.superproxy.io:33335
- **Zone**: residential_proxy1
- Credentials are embedded in the server code

## Testing

Run the test script:
```bash
python test_mims.py
```

This will test:
1. Drug search for "paracetamol" and "metformin"
2. Drug details retrieval
3. Drug interactions check

## Integration with Aneya

**Current**: India region uses BNF for drug information (lines 84-108 in config.py)

**Future**: When MIMS API access is obtained, switch the India region configuration to:

**File**: `servers/clinical_decision_support/config.py`

```python
"INDIA": RegionConfig(
    region_name="India",
    country_codes=["IN"],
    required_servers=["patient_info", "fogsi", "mims", "pubmed"],  # Change "bnf" to "mims"
    searches=[
        SearchConfig(
            resource_type=ResourceType.GUIDELINE,
            tool_name="search_fogsi_guidelines",
            tool_params={"keyword": "{clinical_scenario}", "max_results": 10},
            result_key="guidelines",
            deduplicate=False,
            required=True
        ),
        SearchConfig(
            resource_type=ResourceType.TREATMENT,
            tool_name="search_mims_drugs",  # Change from "search_bnf_treatment_summaries"
            tool_params={"drug_name": "{medication_name}"},
            result_key="drug_info",
            deduplicate=True,
            required=False
        )
    ],
    min_results_threshold=1,
    pubmed_fallback=True
)
```

## Known Limitations

1. **Detailed Drug Information**: MIMS website uses JavaScript/AJAX for loading detailed content. The `get_mims_drug_details` function currently returns basic information. Full details may require:
   - MIMS account authentication
   - JavaScript rendering (Selenium/Playwright)
   - API access (if available)

2. **Drug Interactions**: The interactions checker feature is not publicly available on the MIMS India website structure we discovered. This may require:
   - Premium/authenticated access
   - Different URL structure we haven't found
   - May not exist for India region

3. **Rate Limiting**: Bright Data proxy handles rate limiting, but excessive requests may still trigger blocks. The server includes 0.5s delays between requests.

## Architecture Pattern

The MIMS server follows the same professional pattern as the BNF server:

1. **Bright Data Proxy Integration**: All requests route through residential IPs
2. **Graceful Cache Fallback**: If Firebase unavailable, uses simple in-memory cache
3. **Comprehensive Error Handling**: Returns structured error objects
4. **Logging to stderr**: All debug output goes to stderr for MCP protocol compliance
5. **SSL Verification Disabled**: Required for proxy SSL interception

## Future Enhancements

1. **Authentication**: Implement MIMS login flow to access premium content
2. **JavaScript Rendering**: Use Playwright for dynamic content extraction
3. **Enhanced Parsing**: Improve detection of drug detail sections
4. **Formulary Data**: Extract additional Indian formulary information
5. **Drug Pricing**: Add Indian market pricing information if available
