# Aneya MCP Servers - Clinical Decision Support System

Multi-server MCP architecture for evidence-based clinical recommendations with 22+ regional guideline servers.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│              Clinical Decision Support Client                        │
│              (Orchestration Layer with Smart Fallback)               │
│                                                                      │
│  • Region detection (IP geolocation)                                │
│  • Parallel server connections (region-specific)                    │
│  • Intelligent workflow: Guidelines → PubMed fallback               │
│  • Tool routing & discovery                                         │
└──────────────────────────────────────────────────────────────────────┘
                                  │
    ┌─────────────┬───────────────┼───────────────┬─────────────┐
    │             │               │               │             │
┌───▼───┐    ┌───▼───┐      ┌────▼────┐    ┌────▼────┐   ┌────▼────┐
│  UK   │    │  US   │      │  India  │    │Australia│   │ Cross-  │
│Servers│    │Servers│      │ Servers │    │ Servers │   │Platform │
│       │    │       │      │         │    │         │   │         │
│• NICE │    │• CDC  │      │• ICMR   │    │• NHMRC  │   │• PubMed │
│• BNF  │    │• AAP  │      │• FOGSI  │    │         │   │• GeoIP  │
│       │    │• ADA  │      │• IAP    │    │         │   │• Patient│
│       │    │• AHA  │      │• CSI    │    │         │   │         │
│       │    │• IDSA │      │• RSSDI  │    │         │   │         │
│       │    │• USPSTF│     │• NCG    │    │         │   │         │
│       │    │       │      │• STG    │    │         │   │         │
└───────┘    └───────┘      └─────────┘    └─────────┘   └─────────┘
```

## Components

### 1. Regional MCP Servers (FastMCP)

All servers use the FastMCP framework with `@mcp.tool(name="...", description="...")` decorators.

#### UK Servers (`guidelines/uk/`)
| Server | Tools | Description |
|--------|-------|-------------|
| `nice_guidelines_server.py` | search, details, categories | NICE clinical guidelines (100+ topics) |
| `bnf_server.py` | search, info, conditions, interactions | British National Formulary drug info |

#### US Servers (`guidelines/us/`)
| Server | Source | Description |
|--------|--------|-------------|
| `cdc_guidelines_server.py` | CDC | Disease prevention & control |
| `aap_guidelines_server.py` | AAP | American Academy of Pediatrics |
| `ada_standards_server.py` | ADA | American Diabetes Association |
| `aha_acc_server.py` | AHA/ACC | Heart disease guidelines |
| `idsa_server.py` | IDSA | Infectious disease guidelines |
| `uspstf_server.py` | USPSTF | Preventive services screening |

#### India Servers (`guidelines/india/`)
| Server | Source | Description |
|--------|--------|-------------|
| `icmr_server.py` | ICMR | Medical research council |
| `fogsi_server.py` | FOGSI | Obstetrics & gynecology |
| `iap_guidelines_server.py` | IAP | Pediatrics guidelines |
| `csi_server.py` | CSI | Cardiology society |
| `rssdi_server.py` | RSSDI | Diabetes standards |
| `ncg_server.py` | NCG | Clinical guidelines |
| `stg_server.py` | STG | Standard treatment |

#### Australia Servers (`guidelines/australia/`)
| Server | Source | Description |
|--------|--------|-------------|
| `nhmrc_guidelines_server.py` | NHMRC | National health research council |

#### Cross-Platform Servers
| Server | Tools | Description |
|--------|-------|-------------|
| `geolocation_server.py` | get_country_from_ip, get_user_country | IP-based location detection |
| `pubmed_server.py` | search, get_article, get_multiple | 35M+ medical articles |
| `patient_info_server.py` | manage patient data | Demographics, allergies, medications |

### 2. Clinical Decision Support Client

**File:** `clinical_decision_support/client.py`

Multi-server client that orchestrates the clinical decision support workflow:

**Key Features:**
- **Region Detection** - Auto-detects user location from IP address
- **Parallel Server Connections** - Connects to region-specific servers using `asyncio.gather()`
- **Tool Registry** - Builds mapping of tool_name → server_name
- **Tool Routing** - Routes tool calls to appropriate server
- **Smart Fallback** - Falls back to PubMed when regional guidelines insufficient

**Workflow Steps:**
1. Detect location (IP geolocation or manual override)
2. Connect to region-specific MCP servers
3. Search regional guidelines for condition
   - **If < 2 results** → Fallback to PubMed search
   - **If non-supported region** → Go directly to PubMed
4. Identify relevant medications from scenario
5. Search drug database for details (parallel execution)
6. Generate Claude-based evidence-based recommendations

## Quick Start

### Run Individual Servers

```bash
# UK servers
python guidelines/uk/nice_guidelines_server.py
python guidelines/uk/bnf_server.py

# US servers
python guidelines/us/cdc_guidelines_server.py

# Cross-platform
python geolocation_server.py
python pubmed_server.py
```

### Test with MCP Inspector

```bash
fastmcp dev guidelines/uk/nice_guidelines_server.py
fastmcp dev guidelines/uk/bnf_server.py
fastmcp dev pubmed_server.py
```

### Run via API

The servers are typically accessed through the main FastAPI application:

```bash
# From project root
python api.py
```

## Example Clinical Cases

### Case 1: Pediatric Croup (UK)
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

### Case 2: Post-Operative Sepsis (UK, with Allergy)
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

| Region | Servers | Est. Tools |
|--------|---------|------------|
| UK | NICE, BNF | ~7 |
| US | CDC, AAP, ADA, AHA, IDSA, USPSTF | ~12 |
| India | ICMR, FOGSI, IAP, CSI, RSSDI, NCG, STG | ~14 |
| Australia | NHMRC | ~2 |
| Cross-Platform | Geolocation, PubMed, Patient | ~7 |
| **Total** | **22+ servers** | **50+ tools** |

## Benefits of Multi-Server Architecture

1. **Modularity** - Each server is independently testable and deployable
2. **Scalability** - Easy to add new regional servers
3. **Performance** - Parallel execution where possible
4. **Regional Specificity** - Region-appropriate guidelines and drug info
5. **Separation of Concerns** - Data access (servers) vs orchestration (client)
6. **Flexibility** - Servers can be used independently or together

## Dependencies

```
python >= 3.12
fastmcp >= 2.13.0.2
mcp >= 1.0.0
httpx >= 0.27.0
beautifulsoup4 >= 4.14.2
lxml >= 6.0.2
requests >= 2.32.5
anthropic >= 0.43.1
```

Install with:
```bash
uv sync
```

## Directory Structure

```
servers/
├── clinical_decision_support/     # Main orchestration package
│   ├── client.py                  # ClinicalDecisionSupportClient
│   ├── config.py                  # Regional configurations
│   └── utils.py                   # Utility functions
├── guidelines/                    # Regional guideline servers
│   ├── uk/                        # NICE, BNF
│   ├── us/                        # CDC, AAP, ADA, AHA, IDSA, USPSTF
│   ├── india/                     # ICMR, FOGSI, IAP, CSI, RSSDI, NCG, STG
│   └── australia/                 # NHMRC
├── geolocation_server.py          # IP-based country detection
├── pubmed_server.py               # Medical literature (35M+ articles)
├── patient_info_server.py         # Patient data management
└── tests/                         # Comprehensive test suite
```

## Testing

```bash
# Run all tests
pytest tests/

# Run specific region tests
pytest tests/test_uk_mcp_client.py
pytest tests/test_india_mcp_client.py

# Run with coverage
pytest --cov=. --cov-report=html
```

## Safety Disclaimer

This tool provides reference information from clinical guidelines and drug formularies. It is designed to **assist** healthcare professionals, not replace clinical judgment. Always:

- Verify dosing before prescribing
- Consider patient-specific factors
- Follow local protocols and formularies
- Use professional clinical judgment

## Credits

Developed for the Aneya Clinical Decision Support project.
Built using FastMCP, regional clinical guidelines, and drug formulary resources.
