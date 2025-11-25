"""
Utility functions for clinical decision support.

Contains helper functions for data enrichment, special considerations,
and other utility operations.
"""

from typing import Dict, List, Optional, Any


def needs_enrichment(treatment: dict) -> bool:
    """
    Check if a treatment needs additional BNF data enrichment.

    Args:
        treatment: Treatment dictionary

    Returns:
        True if enrichment is needed
    """
    medications = treatment.get('medications_detailed', [])
    if not medications:
        return True

    for med in medications:
        # Check if we have minimal viable data
        if not med.get('drug_name'):
            return True
        if not med.get('indications') and not med.get('dosage'):
            return True

    return False


def needs_special_considerations_enrichment(special_considerations: dict) -> bool:
    """
    Check if special considerations section needs enrichment.

    Args:
        special_considerations: Special considerations dictionary

    Returns:
        True if enrichment is needed
    """
    # If completely empty, needs enrichment
    if not special_considerations:
        return True

    # Check if all fields are empty/minimal
    empty_count = 0
    for key, value in special_considerations.items():
        if not value or value == "Not specified" or value == []:
            empty_count += 1

    # If more than half the fields are empty, enrichment recommended
    return empty_count > len(special_considerations) / 2


__all__ = [
    'needs_enrichment',
    'needs_special_considerations_enrichment'
]
