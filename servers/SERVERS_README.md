# Heidi - Clinical Decision Support System

Multi-server MCP architecture for evidence-based clinical recommendations.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│              Clinical Decision Support Client                        │
│              (Orchestration Layer with Smart Fallback)               │
│                                                                      │
│  • Parallel server connections (4 servers)                          │
│  • Intelligent workflow: Guidelines → PubMed fallback               │
│  • Tool routing & discovery                                         │
└──────────────────────────────────────────────────────────────────────┘
                                  │
        ┌────────────────┬────────┴────────┬─────────────────┐
        │                │                 │                 │
┌───────▼────────┐ ┌────▼─────┐  ┌────────▼────────┐ ┌─────▼──────┐
│  Geolocation   │ │  NICE    │  │      BNF        │ │  PubMed    │
│     Server     │ │Guidelines│  │    Server       │ │  Server    │
│                │ │ Server   │  │                 │ │            │
│  • Country     │ │          │  │  • Drug search  │ │ • Search   │
│    detection   │ │ • Search │  │  • Drug details │ │   35M+     │
│                │ │ • Details│  │  • Conditions   │ │   articles │
│  2 tools       │ │ • Cats.  │  │  • Interactions │ │ • Retrieve │
│                │ │          │  │                 │ │   abstracts│
│                │ │ 3 tools  │  │  4 tools        │ │            │
│                │ │          │  │                 │ │ 3 tools    │
└────────────────┘ └──────────┘  └─────────────────┘ └────────────┘
```

## Components

### 1. Individual MCP Servers (FastMCP)

All servers use the FastMCP framework with `@mcp.tool(name="...", description="...")` decorators:

#### Geolocation Server (`geolocation_server.py`)
- `get_country_from_ip` - Get country from IP address
- `get_user_country` - Auto-detect user's country

#### NICE Guidelines Server (`nice_guidelines_server.py`)
- `search_nice_guidelines` - Search UK clinical guidelines
- `get_guideline_details` - Get detailed guideline information
- `list_guideline_categories` - List guideline categories

#### BNF Server (`bnf_server.py`)
- `search_bnf_drug` - Search for medications
- `get_bnf_drug_info` - Get detailed drug information
- `search_bnf_by_condition` - Search drugs by medical condition
- `get_bnf_drug_interactions` - Get drug interaction information

#### PubMed Server (`pubmed_server.py`) **NEW**
- `search_pubmed` - Search 35M+ peer-reviewed medical articles
- `get_article` - Retrieve full article details with abstract
- `get_multiple_articles` - Batch retrieve multiple articles

### 2. Clinical Decision Support Client

**File:** `clinical_decision_support_client.py`

Multi-server client that orchestrates the clinical decision support workflow:

**Key Features:**
- **Parallel Server Connections** - Connects to all 3 servers concurrently using `asyncio.gather()`
- **Tool Registry** - Builds mapping of tool_name → server_name
- **Tool Routing** - Routes tool calls to appropriate server
- **Workflow Orchestration** - Implements clinical decision support logic

**Workflow Steps (Enhanced with PubMed Fallback):**
1. Determine location (auto-detect or override)
2. Search NICE guidelines for condition (UK only)
   - **If < 2 guidelines found** → Search PubMed for evidence (fallback)
   - **If non-UK location** → Go directly to PubMed
3. Identify relevant medications from scenario
4. Search BNF for medication details (parallel execution)
5. Generate evidence-based recommendations with both guidelines and literature

### 3. Demo Script

**File:** `demo_clinical_decision_support.py`

Interactive CLI demo with:
- 4 pre-configured clinical cases
- Custom case input
- Automated testing mode (`--auto` flag)

## Quick Start

### Run Individual Servers

```bash
# Geolocation server
python geolocation_server.py

# NICE Guidelines server
python nice_guidelines_server.py

# BNF server
python bnf_server.py
```

### Test with MCP Inspector

```bash
fastmcp dev geolocation_server.py
fastmcp dev nice_guidelines_server.py
fastmcp dev bnf_server.py
```

### Run Clinical Decision Support Client

```bash
# Run example cases
python clinical_decision_support_client.py

# Interactive demo
python demo_clinical_decision_support.py

# Automated demo (all cases)
python demo_clinical_decision_support.py --auto
```

## Example Clinical Cases

### Case 1: Pediatric Croup (Simple)
```python
await client.clinical_decision_support(
    clinical_scenario="3-year-old with croup, moderate stridor at rest, barking cough",
    patient_age="3 years",
    location_override="GB"
)
```

**Expected Output:**
- Location: United Kingdom (GB)
- NICE guidelines for croup
- Medications: dexamethasone, prednisolone
- Evidence-based recommendations

### Case 2: Post-Operative Sepsis (Complex with Allergy)
```python
await client.clinical_decision_support(
    clinical_scenario="Post-operative sepsis, fever 38.5C, tachycardia, suspected wound infection",
    patient_age="65 years",
    allergies="penicillin",
    location_override="GB"
)
```

**Expected Output:**
- Location: United Kingdom (GB)
- NICE sepsis guidelines
- Alternative antibiotics (avoiding penicillins)
- Allergy warnings in recommendations

## Parallel Execution

The client uses `asyncio.gather()` for parallelization:

### Server Connections (Parallel)
```python
connection_tasks = [
    self._connect_single_server("geolocation", ...),
    self._connect_single_server("nice", ...),
    self._connect_single_server("bnf", ...)
]
await asyncio.gather(*connection_tasks)
```

### Tool Discovery (Parallel)
```python
list_tasks = [(name, session.list_tools()) for name, session in self.sessions.items()]
results = await asyncio.gather(*[task[1] for task in list_tasks])
```

### Medication Searches (Parallel)
```python
search_tasks = [
    self.call_tool("search_bnf_drug", {"drug_name": med})
    for med in medications_to_search
]
results = await asyncio.gather(*search_tasks, return_exceptions=True)
```

## Tool Count Summary

| Server | Tools | Description |
|--------|-------|-------------|
| Geolocation | 2 | IP-based location detection |
| NICE Guidelines | 3 | UK clinical guidelines |
| BNF | 4 | British National Formulary |
| PubMed | 3 | Medical literature (35M+ articles) |
| **Total** | **12** | All tools available to client |

## Configuration for Claude Desktop

Add all three servers to your MCP configuration:

```json
{
  "mcpServers": {
    "geolocation": {
      "command": "python",
      "args": ["/path/to/heidi/servers/geolocation_server.py"],
      "cwd": "/path/to/heidi/servers"
    },
    "nice-guidelines": {
      "command": "python",
      "args": ["/path/to/heidi/servers/nice_guidelines_server.py"],
      "cwd": "/path/to/heidi/servers"
    },
    "bnf": {
      "command": "python",
      "args": ["/path/to/heidi/servers/bnf_server.py"],
      "cwd": "/path/to/heidi/servers"
    }
  }
}
```

Or use the client-based orchestration directly in your application.

## Benefits of Multi-Server Architecture

1. **Modularity** - Each server is independently testable and deployable
2. **Scalability** - Easy to add new specialized servers
3. **Performance** - Parallel execution where possible
4. **Separation of Concerns** - Data access (servers) vs orchestration (client)
5. **Flexibility** - Servers can be used independently or together

## Dependencies

```
python >= 3.12
fastmcp >= 2.13.0.2
mcp >= 1.0.0
httpx >= 0.27.0
beautifulsoup4 >= 4.14.2
lxml >= 6.0.2
requests >= 2.32.5
anthropic (optional, for Claude integration)
```

Install with:
```bash
uv sync
```

## Files

- `geolocation_server.py` - Geolocation MCP server
- `nice_guidelines_server.py` - NICE Guidelines MCP server (refactored to FastMCP)
- `bnf_server.py` - BNF MCP server
- `clinical_decision_support_client.py` - Multi-server orchestration client
- `demo_clinical_decision_support.py` - Interactive demo script
- `test_nice_guidelines.py` - Test script for NICE server
- `heidi_server.py` - Legacy single-server implementation (deprecated)

## Documentation

- `NICE_GUIDELINES_README.md` - Detailed NICE Guidelines server documentation
- `HEIDI_README.md` - Legacy orchestrator documentation
- `CLAUDE.md` - Claude Code instructions

## Future Enhancements

- [ ] Add caching for frequently accessed guidelines
- [ ] Support for international guidelines (not just UK)
- [ ] Drug interaction checking across multiple medications
- [ ] Integration with local hospital formularies
- [ ] Real-time alert systems for guideline updates
- [ ] More sophisticated NLP for scenario parsing
- [ ] Claude-based agentic workflow for complex cases

## Safety and Disclaimers

⚠️ **Important:** This tool provides reference information from clinical guidelines and drug formularies. It is designed to assist healthcare professionals, not replace clinical judgment. Always:

- Verify dosing before prescribing
- Consider patient-specific factors
- Follow local protocols and formularies
- Use professional clinical judgment
- Ensure appropriate patient consent

## Credits

Developed for the Heidi healthcare assistant project.
Built using FastMCP, NICE guidelines, and BNF resources.
