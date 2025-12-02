"""
Regional search service for clinical guidelines.

Handles region-specific guideline searches with configuration-driven approach,
parallel execution, deduplication, and PubMed fallback logic.
"""

import asyncio
from typing import List, Dict, Any, Tuple, TYPE_CHECKING

from .config import (
    REGION_CONFIGS,
    COUNTRY_TO_REGION,
    SearchConfig
)

if TYPE_CHECKING:
    from .client import ClinicalDecisionSupportClient


class RegionalSearchService:
    """
    Service for executing region-specific clinical guideline searches.

    Uses configuration-driven approach to route searches based on geographic region,
    handling parallel execution, deduplication, and PubMed fallback logic.
    """

    def __init__(self, client: 'ClinicalDecisionSupportClient'):
        """
        Initialize the regional search service.

        Args:
            client: The ClinicalDecisionSupportClient instance to use for tool calls
        """
        self.client = client

    async def search_by_region(
        self,
        country_code: str,
        clinical_scenario: str,
        verbose: bool = True
    ) -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
        """
        Execute searches for a specific region based on configuration.

        Args:
            country_code: ISO country code (e.g., 'GB', 'IN', 'US')
            clinical_scenario: Clinical query or patient description
            verbose: Whether to print progress messages

        Returns:
            Tuple of (guidelines, cks_topics, bnf_summaries, pubmed_articles)
        """
        # Get region configuration
        region_key = COUNTRY_TO_REGION.get(country_code, "INTERNATIONAL")
        config = REGION_CONFIGS[region_key]

        if verbose:
            print(f"\n{'='*80}")
            print(f"🌍 Regional Search: {config.region_name} ({country_code})")
            print(f"{'='*80}")

        # Initialize result containers with support for dynamic treatment keys
        results = {
            'guidelines': [],
            'cks_topics': [],
            'bnf_summaries': [],
            'drugbank_drugs': [],  # Support for DrugBank (India/International)
            'pubmed_articles': []
        }

        # Execute configured searches in parallel
        search_tasks = []
        for search_config in config.searches:
            # Substitute clinical_scenario into tool params
            params = {
                key: value.format(clinical_scenario=clinical_scenario) if isinstance(value, str) else value
                for key, value in search_config.tool_params.items()
            }

            search_tasks.append(
                self._execute_search(search_config, params, verbose)
            )

        # Wait for all searches to complete
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Process results
        for search_config, search_result in zip(config.searches, search_results):
            if isinstance(search_result, Exception):
                if verbose:
                    print(f"⚠️  Search failed for {search_config.tool_name}: {search_result}")
                continue

            if search_result:
                # Store in appropriate result key
                result_list = results[search_config.result_key]

                if search_config.deduplicate:
                    # Deduplicate by title
                    existing_titles = {item.get('title', '').lower() for item in result_list}
                    new_items = [
                        item for item in search_result
                        if item.get('title', '').lower() not in existing_titles
                    ]
                    result_list.extend(new_items)
                else:
                    result_list.extend(search_result)

        # Check if we need PubMed fallback
        guideline_count = len(results['guidelines'])
        needs_pubmed_fallback = (
            config.pubmed_fallback and
            guideline_count < config.min_results_threshold
        )

        if needs_pubmed_fallback:
            if verbose:
                print(f"\n📚 PubMed Fallback: Only {guideline_count} guideline(s) found")

            pubmed_result = await self._search_pubmed(clinical_scenario, verbose)
            if pubmed_result:
                results['pubmed_articles'].extend(pubmed_result)

        # For India, always search PubMed in addition to FOGSI
        if region_key == "INDIA" and not needs_pubmed_fallback:
            if verbose:
                print(f"\n📚 Searching PubMed (India region)")

            pubmed_result = await self._search_pubmed(clinical_scenario, verbose)
            if pubmed_result:
                results['pubmed_articles'].extend(pubmed_result)

        # Return treatment data (BNF for UK, DrugBank for India/International)
        treatment_data = results.get('bnf_summaries', []) or results.get('drugbank_drugs', [])

        return (
            results['guidelines'],
            results['cks_topics'],
            treatment_data,
            results['pubmed_articles']
        )

    async def _execute_search(
        self,
        search_config: SearchConfig,
        params: Dict[str, Any],
        verbose: bool
    ) -> List[dict]:
        """Execute a single configured search operation."""
        try:
            if verbose:
                print(f"  🔍 {search_config.resource_type.value}: {search_config.tool_name}")

            result = await self.client.call_tool(search_config.tool_name, params)

            if isinstance(result, dict):
                # Handle different response formats
                if 'summaries' in result:
                    return result['summaries']
                elif 'guidelines' in result:
                    return result['guidelines']
                elif 'topics' in result:
                    return result['topics']
                elif 'treatments' in result:
                    # DrugBank-style response format
                    return result['treatments']
                elif 'results' in result:
                    # FOGSI-style response format (and others using 'results' key)
                    return result['results']
                elif 'success' in result and result['success']:
                    # Generic success response with no data
                    return []

            return []

        except Exception as e:
            if verbose:
                print(f"    ⚠️  Error: {str(e)}")
            return []

    async def _search_pubmed(
        self,
        clinical_scenario: str,
        verbose: bool
    ) -> List[dict]:
        """Search PubMed for additional evidence."""
        try:
            result = await self.client.call_tool(
                "search_pubmed",
                {"query": clinical_scenario, "max_results": 5}
            )

            if isinstance(result, dict) and result.get('success'):
                articles = result.get('articles', [])
                if verbose and articles:
                    print(f"    ✓ Found {len(articles)} PubMed article(s)")
                return articles

            return []

        except Exception as e:
            if verbose:
                print(f"    ⚠️  PubMed search error: {str(e)}")
            return []


__all__ = ['RegionalSearchService']
