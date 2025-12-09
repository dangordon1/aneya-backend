"""
Clinical Decision Support Client - Backward Compatibility Shim

This file provides backward compatibility for code that imports from the original
clinical_decision_support_client.py location.

The actual implementation has been refactored into a modular package structure:
    - clinical_decision_support/config.py - Configuration and constants
    - clinical_decision_support/regional_search.py - Regional search service
    - clinical_decision_support/client.py - Main client class
    - clinical_decision_support/utils.py - Utility functions

For new code, prefer importing directly from the package:
    from clinical_decision_support import ClinicalDecisionSupportClient
"""

# Import everything from the new modular package
from clinical_decision_support import (
    ClinicalDecisionSupportClient,
    RegionalSearchService,
    ResourceType,
    SearchConfig,
    RegionConfig,
    REGION_CONFIGS,
    COUNTRY_TO_REGION,
    MCP_SERVERS,
    REGION_SERVERS,
    SERVERS_DIR
)

# Re-export for backward compatibility
__all__ = [
    'ClinicalDecisionSupportClient',
    'RegionalSearchService',
    'ResourceType',
    'SearchConfig',
    'RegionConfig',
    'REGION_CONFIGS',
    'COUNTRY_TO_REGION',
    'MCP_SERVERS',
    'REGION_SERVERS',
    'SERVERS_DIR'
]
