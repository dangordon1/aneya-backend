# US Medical Guideline Servers - FastMCP Implementation

This directory contains 6 production-ready FastMCP servers for accessing US medical guideline organizations. All servers follow the established pattern from `nice_guidelines_server.py` and use the FastMCP framework.

## Created Servers

### 1. USPSTF Server (`uspstf_server.py`)
**US Preventive Services Task Force**
- **Server Name**: `USPSTF-Guidelines`
- **Base URL**: https://www.uspreventiveservicestaskforce.org
- **API Support**: Structured for REST API (requires approval from uspstfpda@ahrq.gov)
- **Tools**:
  - `search_preventive_recommendations` - Search by topic with grade ratings (A, B, C, D, I)
  - `get_uspstf_recommendation` - Get detailed recommendation with rationale and evidence
  - `list_recommendation_topics` - List categories (cancer screening, cardiovascular, etc.)

**Key Features**:
- API-first design with web scraping fallback
- Grade-based recommendations (A=strong, B=moderate, C=selective, D=don't, I=insufficient)
- 8 major categories including cancer screening, cardiovascular prevention, behavioral counseling

### 2. CDC Guidelines Server (`cdc_guidelines_server.py`)
**Centers for Disease Control and Prevention**
- **Server Name**: `CDC-Guidelines`
- **Base URLs**:
  - Main: https://www.cdc.gov
  - STI: https://www.cdc.gov/std
  - TB: https://www.cdc.gov/tb
  - HIV: https://www.cdc.gov/hiv
- **Tools**:
  - `search_cdc_guidelines` - Search by topic/disease with category filtering
  - `get_guideline_content` - Get detailed content with recommendations
  - `list_cdc_topics` - List 8 major topics (STI, TB, HIV, immunizations, infection control, etc.)

**Key Features**:
- Multi-URL strategy for specialized topics (STI, TB, HIV)
- Automatic categorization by URL pattern
- 8 major topics including STI treatment, TB, HIV, immunizations, infection control, COVID-19

### 3. IDSA Server (`idsa_server.py`)
**Infectious Diseases Society of America**
- **Server Name**: `IDSA-Guidelines`
- **Base URL**: https://www.idsociety.org
- **Tools**:
  - `search_idsa_guidelines` - Search by disease/infection with automatic categorization
  - `get_guideline_detail` - Get detailed guideline with recommendations and sections
  - `list_idsa_categories` - List 12 categories organized by infection site and organism

**Key Features**:
- 12 infection categories (respiratory, bloodstream, CNS, fungal, antimicrobial stewardship)
- Automatic categorization by keywords (pneumonia, sepsis, UTI, etc.)
- Rate limiting: 0.5s between requests

### 4. ADA Standards Server (`ada_standards_server.py`)
**American Diabetes Association**
- **Server Name**: `ADA-Standards`
- **Base URLs**:
  - Main: https://professional.diabetes.org
  - Journal: https://diabetesjournals.org/care
- **Tools**:
  - `search_diabetes_standards` - Search Standards of Care by topic
  - `get_standards_section` - Get detailed section with recommendations and evidence grades
  - `list_standards_sections` - List all 16 sections of Standards of Care

**Key Features**:
- Annual Standards of Medical Care in Diabetes (16 sections)
- Evidence grading system (A, B, C, E)
- Categories: diagnosis, glycemic targets, medications, complications, special populations
- Rate limiting: 0.7s between requests

### 5. AHA/ACC Server (`aha_acc_server.py`)
**American Heart Association / American College of Cardiology**
- **Server Name**: `AHA-ACC-Guidelines`
- **Base URLs**:
  - AHA: https://professional.heart.org
  - ACC: https://www.acc.org
- **Tools**:
  - `search_cardiovascular_guidelines` - Search joint AHA/ACC guidelines
  - `get_guideline_content` - Get detailed content with Class/Level of Evidence
  - `list_guideline_categories` - List 11 cardiovascular categories

**Key Features**:
- Dual-source search (AHA and ACC websites)
- Class of Recommendation (I, IIa, IIb, III) and Level of Evidence (A, B, C)
- 11 categories including heart failure, arrhythmias, CAD, hypertension, valvular disease
- Rate limiting: 0.6s between requests

### 6. AAP Guidelines Server (`aap_guidelines_server.py`)
**American Academy of Pediatrics**
- **Server Name**: `AAP-Guidelines`
- **Base URLs**:
  - Main: https://www.aap.org
  - Journal: https://publications.aap.org/pediatrics
- **Tools**:
  - `search_pediatric_guidelines` - Search clinical practice guidelines and policy statements
  - `get_guideline_content` - Get detailed guideline with recommendations and evidence quality
  - `list_pediatric_topics` - List 12 pediatric care categories

**Key Features**:
- Multiple document types (Clinical Practice Guideline, Policy Statement, Clinical Report, Technical Report)
- Evidence quality ratings (Strong, Moderate, Weak)
- 12 categories including preventive care, immunizations, developmental health, infections
- Rate limiting: 0.8s between requests

## Common Features Across All Servers

### FastMCP Framework
All servers use the FastMCP library with:
- `@mcp.tool()` decorator pattern
- Structured return dictionaries with `success` and `error` fields
- Comprehensive docstrings with Args and Returns
- `mcp.run()` in `__main__` block

### Web Scraping Strategy
- **HTTP Client**: `httpx` with async support
- **HTML Parsing**: BeautifulSoup4 with lxml parser
- **Rate Limiting**: 0.5-0.8 second delays between requests
- **Timeout**: 30 seconds per request
- **User-Agent**: Modern browser headers to avoid blocking

### Error Handling
- Graceful fallbacks when primary scraping fails
- Structured error messages in return dictionaries
- Try-except blocks around all external calls
- Informative error messages for users

### Return Structure
All tools return dictionaries with:
```python
{
    'success': bool,        # Whether operation succeeded
    'error': str|None,      # Error message if failed
    # ... tool-specific data fields
}
```

## Running the Servers

### Standalone Testing
```bash
cd /Users/dgordon/python/hackathons/aneya/backend/servers

# Run individual server
python uspstf_server.py
python cdc_guidelines_server.py
python idsa_server.py
python ada_standards_server.py
python aha_acc_server.py
python aap_guidelines_server.py
```

### FastMCP Inspector
Test with the FastMCP development tool:
```bash
fastmcp dev uspstf_server.py
```

### MCP Client Configuration
Add to MCP client configuration (e.g., Claude Desktop):
```json
{
  "mcpServers": {
    "uspstf": {
      "command": "python",
      "args": ["/path/to/uspstf_server.py"]
    },
    "cdc": {
      "command": "python",
      "args": ["/path/to/cdc_guidelines_server.py"]
    },
    "idsa": {
      "command": "python",
      "args": ["/path/to/idsa_server.py"]
    },
    "ada": {
      "command": "python",
      "args": ["/path/to/ada_standards_server.py"]
    },
    "aha-acc": {
      "command": "python",
      "args": ["/path/to/aha_acc_server.py"]
    },
    "aap": {
      "command": "python",
      "args": ["/path/to/aap_guidelines_server.py"]
    }
  }
}
```

## Environment Variables

### USPSTF Server
- `USPSTF_API_KEY` - API key for official USPSTF REST API (optional, requires approval)

## Coverage Summary

| Organization | Focus Area | Guidelines Count | Evidence System |
|--------------|-----------|------------------|-----------------|
| USPSTF | Preventive Services | 100+ recommendations | Grades A-D, I |
| CDC | Infectious Diseases | 100+ guidelines | Evidence-based |
| IDSA | Infectious Diseases | 50+ guidelines | GRADE system |
| ADA | Diabetes Care | 16 sections annually | Grades A-E |
| AHA/ACC | Cardiovascular | 50+ guidelines | Class I-III, Level A-C |
| AAP | Pediatric Care | 100+ guidelines | Strong/Moderate/Weak |

## Architecture Notes

### Differences from NICE Guidelines Server
While these servers follow the NICE pattern, they use **FastMCP exclusively** (not the standard MCP protocol). This is consistent with the project's global instructions to always use FastMCP for new servers.

### Rate Limiting Strategy
Each server implements delays to respect source websites:
- USPSTF: No delay (designed for API)
- CDC: 0.5s between requests
- IDSA: 0.5s between requests
- ADA: 0.7s between requests
- AHA/ACC: 0.6s between requests
- AAP: 0.8s between requests

### Categorization
All servers implement intelligent categorization based on:
1. URL patterns (CDC, IDSA)
2. Title keywords (all servers)
3. Document metadata when available

## Testing Recommendations

### Unit Testing
Test each tool with representative queries:
```python
# USPSTF
search_preventive_recommendations("breast cancer screening")

# CDC
search_cdc_guidelines("STI treatment")

# IDSA
search_idsa_guidelines("pneumonia")

# ADA
search_diabetes_standards("glycemic targets")

# AHA/ACC
search_cardiovascular_guidelines("heart failure")

# AAP
search_pediatric_guidelines("asthma")
```

### Integration Testing
Test all servers together in the clinical_decision_support_client.py workflow.

## Future Enhancements

### USPSTF
- Implement full API integration once credentials obtained
- Add support for draft recommendations

### CDC
- Add support for MMWR (Morbidity and Mortality Weekly Report)
- Implement ACIP recommendation tracking

### IDSA
- Add journal article parsing for full guideline text
- Implement systematic review integration

### ADA
- Add automatic year detection and archival access
- Implement comparison tools between Standards years

### AHA/ACC
- Add pocket guidelines support
- Implement focused updates tracking

### AAP
- Add Bright Futures integration
- Implement Red Book (infectious diseases) access

## Maintenance

### Regular Updates Needed
- URL patterns may change (monitor for 404s)
- HTML structure changes require BeautifulSoup selector updates
- New guideline categories should be added to categorization logic

### Monitoring
- Track success/failure rates of searches
- Monitor response times and adjust timeouts if needed
- Watch for rate limiting or blocking issues

## License and Usage

These servers are designed for healthcare professional use as clinical decision support tools. All guidelines remain property of their respective organizations:
- USPSTF: Public domain (US Government)
- CDC: Public domain (US Government)
- IDSA: © Infectious Diseases Society of America
- ADA: © American Diabetes Association
- AHA/ACC: © American Heart Association / American College of Cardiology
- AAP: © American Academy of Pediatrics

## Contact and Support

For issues specific to:
- **USPSTF API access**: uspstfpda@ahrq.gov
- **Server implementation**: See project maintainers
- **Guideline content questions**: Contact respective organizations

---

**Created**: November 24, 2024
**Framework**: FastMCP 2.x
**Python Version**: 3.12+
**Status**: Production Ready
