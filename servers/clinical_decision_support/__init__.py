"""
Clinical Decision Support package.

Modular clinical decision support system with regional guideline search,
Claude AI analysis, and MCP server orchestration.

Main exports:
    - ClinicalDecisionSupportClient: Main client class for clinical decision support
    - ConsultationSummary: Standalone consultation summarization with diarization support
    - RegionalSearchService: Service for region-specific guideline searches
    - ResourceType, REGION_CONFIGS: Configuration classes and constants
"""

from .config import (
    ResourceType,
    SearchConfig,
    RegionConfig,
    REGION_CONFIGS,
    COUNTRY_TO_REGION,
    MCP_SERVERS,
    REGION_SERVERS,
    SERVERS_DIR
)
from .regional_search import RegionalSearchService
from .client import ClinicalDecisionSupportClient
from .summary import ConsultationSummary

__version__ = "1.0.0"

__all__ = [
    # Config
    'ResourceType',
    'SearchConfig',
    'RegionConfig',
    'REGION_CONFIGS',
    'COUNTRY_TO_REGION',
    'MCP_SERVERS',
    'REGION_SERVERS',
    'SERVERS_DIR',
    # Classes
    'RegionalSearchService',
    'ClinicalDecisionSupportClient',
    'ConsultationSummary',
]
