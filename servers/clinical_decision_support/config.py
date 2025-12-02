"""
Configuration module for Clinical Decision Support system.

Contains all configuration constants, enums, and region-specific settings
for the clinical decision support workflow.
"""

from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum


# ============================================================================
# Configuration-Driven Regional Search System
# ============================================================================

class ResourceType(Enum):
    """Types of medical resources that can be searched."""
    GUIDELINE = "guideline"      # Clinical guidelines (NICE, FOGSI)
    CKS = "cks"                  # Clinical Knowledge Summaries (UK)
    TREATMENT = "treatment"       # Treatment summaries (BNF)
    LITERATURE = "literature"     # Research articles (PubMed)


@dataclass
class SearchConfig:
    """Configuration for a single search operation."""
    resource_type: ResourceType
    tool_name: str
    tool_params: Dict[str, Any]
    result_key: str              # Key in results dict (e.g., 'guidelines', 'cks_topics')
    deduplicate: bool = False    # Whether to deduplicate results
    required: bool = True         # Whether this search is required for the region


@dataclass
class RegionConfig:
    """Complete configuration for a geographic region."""
    region_name: str
    country_codes: List[str]
    required_servers: List[str]  # MCP servers needed for this region
    searches: List[SearchConfig]
    min_results_threshold: int = 2  # Minimum results before falling back to PubMed
    pubmed_fallback: bool = True    # Whether to use PubMed as fallback


# Regional search configurations
REGION_CONFIGS = {
    "UK": RegionConfig(
        region_name="United Kingdom",
        country_codes=["GB", "UK"],
        required_servers=["patient_info", "nice", "bnf", "pubmed"],
        searches=[
            SearchConfig(
                resource_type=ResourceType.GUIDELINE,
                tool_name="search_nice_guidelines",
                tool_params={"keyword": "{clinical_scenario}", "max_results": 10},
                result_key="guidelines",
                deduplicate=False,
                required=True
            ),
            SearchConfig(
                resource_type=ResourceType.CKS,
                tool_name="search_cks_topics",
                tool_params={"keyword": "{clinical_scenario}", "max_results": 5},
                result_key="cks_topics",
                deduplicate=False,
                required=False
            ),
            SearchConfig(
                resource_type=ResourceType.TREATMENT,
                tool_name="search_bnf_treatment_summaries",
                tool_params={"condition": "{clinical_scenario}"},
                result_key="bnf_summaries",
                deduplicate=True,
                required=False
            )
        ],
        min_results_threshold=2,
        pubmed_fallback=True
    ),

    "INDIA": RegionConfig(
        region_name="India",
        country_codes=["IN"],
        required_servers=["patient_info", "fogsi", "drugbank", "pubmed"],
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
                tool_name="search_drugbank_by_condition",
                tool_params={"condition": "{clinical_scenario}"},
                result_key="drugbank_drugs",
                deduplicate=True,
                required=False
            )
        ],
        min_results_threshold=1,
        pubmed_fallback=True  # Always search PubMed for India
    ),

    "INTERNATIONAL": RegionConfig(
        region_name="International",
        country_codes=["default"],
        required_servers=["patient_info", "drugbank", "pubmed"],
        searches=[
            SearchConfig(
                resource_type=ResourceType.TREATMENT,
                tool_name="search_drugbank_by_condition",
                tool_params={"condition": "{clinical_scenario}"},
                result_key="drugbank_drugs",
                deduplicate=True,
                required=False
            )
        ],
        min_results_threshold=0,
        pubmed_fallback=True
    )
}


# Map country codes to regions
COUNTRY_TO_REGION = {}
for region_key, config in REGION_CONFIGS.items():
    for country_code in config.country_codes:
        COUNTRY_TO_REGION[country_code] = region_key


# Server paths
SERVERS_DIR = Path(__file__).parent.parent  # Go up from clinical_decision_support/ to servers/
MCP_SERVERS = {
    "patient_info": str(SERVERS_DIR / "patient_info_server.py"),
    "nice": str(SERVERS_DIR / "nice_guidelines_server.py"),
    "bnf": str(SERVERS_DIR / "bnf_server.py"),  # UK only
    "fogsi": str(SERVERS_DIR / "fogsi_server.py"),  # FOGSI Guidelines (India)
    "drugbank": str(SERVERS_DIR / "drugbank_server.py"),  # DrugBank (India + International)
    "mims": str(SERVERS_DIR / "mims_india_server.py"),  # MIMS Drug Info (India) - reserved for future API access
    "pubmed": str(SERVERS_DIR / "pubmed_server.py")
}

# Region-specific server mapping (generated from REGION_CONFIGS)
REGION_SERVERS = {}
for region_key, config in REGION_CONFIGS.items():
    for country_code in config.country_codes:
        REGION_SERVERS[country_code] = config.required_servers


__all__ = [
    'ResourceType',
    'SearchConfig',
    'RegionConfig',
    'REGION_CONFIGS',
    'COUNTRY_TO_REGION',
    'SERVERS_DIR',
    'MCP_SERVERS',
    'REGION_SERVERS'
]
