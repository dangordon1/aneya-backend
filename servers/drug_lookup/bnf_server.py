#!/usr/bin/env python
"""
MCP Server for British National Formulary (BNF) information.

Simplified architecture using local BNF index for fuzzy search,
then direct URL fetch for drug details. No LLM-based variation guessing.

Flow:
1. search_bnf_index(query) - fuzzy search local index -> returns slug/URL
2. get_bnf_drug_by_slug(slug) - direct fetch by slug -> returns drug info
"""

import requests
from bs4 import BeautifulSoup
from typing import Optional, List, Dict, Any
from fastmcp import FastMCP
import time
import os
import sys
import urllib3
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Handle imports - add the drug_lookup directory to path for subprocess execution
from pathlib import Path
_drug_lookup_dir = Path(__file__).parent
if str(_drug_lookup_dir) not in sys.path:
    sys.path.insert(0, str(_drug_lookup_dir))

from scrapeops_proxies import get_proxy, get_proxy_count
from bnf_index_utils import get_bnf_index, BNFIndex

# Load environment variables from .env file
load_dotenv()

# Disable SSL warnings for proxy
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# CACHE DISABLED - Using dummy cache for testing
CACHE_AVAILABLE = False
# Create a dummy cache that does nothing
class DummyCache:
    def __init__(self):
        self.enabled = False
    def get(self, *args, **kwargs):
        return None
    def set(self, *args, **kwargs):
        pass
def get_cache():
    return DummyCache()

print("⚠️  BNF cache DISABLED (using dummy cache)", file=sys.stderr)

# Initialize FastMCP server with proper name and instructions
mcp = FastMCP(
    "BNF",
    instructions="British National Formulary drug information service providing medication details, indications, dosages, contraindications, and condition-based drug searches"
)

# Base URL for BNF website
BASE_URL = "https://bnf.nice.org.uk"

# Headers to mimic a real browser and avoid 403 errors
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-GB,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

# Configure ScrapeOps Residential Proxy with Round-Robin
# Routes requests through UK residential IPs to bypass Cloudflare protection
SCRAPEOPS_API_KEY = os.getenv('SCRAPEOPS_API_KEY')

# Create session with proper headers
# Note: We'll set proxies per-request using get_proxy() for round-robin rotation
session = requests.Session()
session.headers.update(HEADERS)

if SCRAPEOPS_API_KEY:
    print(f"🔄 BNF server using ScrapeOps Round-Robin Proxy Pool", file=sys.stderr)
    print(f"   Available proxies: {get_proxy_count()}", file=sys.stderr)
    print(f"   Proxy server: residential-proxy.scrapeops.io:8181", file=sys.stderr)
else:
    print("❌ ERROR: SCRAPEOPS_API_KEY not set!", file=sys.stderr)
    print("   BNF lookups require ScrapeOps residential proxy to bypass Cloudflare.", file=sys.stderr)
    print("   Set SCRAPEOPS_API_KEY environment variable and restart.", file=sys.stderr)
    sys.exit(1)

# Initialize cache
cache = get_cache()

def make_request(url: str, timeout: int = 15, session_id: Optional[str] = None) -> tuple[Optional[requests.Response], Dict[str, Any]]:
    """
    Make a GET request with proper error handling and rate limiting.
    Uses ScrapeOps residential proxy (UK geotargeted) to bypass Cloudflare protection.
    Uses round-robin proxy selection for better distribution.

    Args:
        url: The URL to request
        timeout: Request timeout in seconds
        session_id: Optional (not used with ScrapeOps, kept for API compatibility)

    Returns:
        Tuple of (Response object or None if failed, debug_info dictionary)
    """
    debug_info = {
        "url": url,
        "scrapeops_proxy": bool(SCRAPEOPS_API_KEY),
        "timeout": timeout
    }

    try:
        # Add a small delay to be respectful to the server
        time.sleep(0.5)

        # Get next proxy from round-robin pool
        proxy_config = get_proxy()
        proxies = {
            'http': proxy_config['http'],
            'https': proxy_config['https']
        }

        proxy_status = "SCRAPEOPS ROUND-ROBIN" if SCRAPEOPS_API_KEY else "DIRECT"
        print(f"🌐 [{proxy_status}] Requesting: {url}", file=sys.stderr)
        # verify=False needed for proxy SSL interception
        response = session.get(url, timeout=timeout, verify=False, proxies=proxies)

        # Log response details
        print(f"✅ Response received: {response.status_code} (size: {len(response.content)} bytes)", file=sys.stderr)

        # Add success info to debug
        debug_info["status_code"] = response.status_code
        debug_info["content_length"] = len(response.content)
        debug_info["content_type"] = response.headers.get('Content-Type', 'unknown')
        debug_info["success"] = True

        response.raise_for_status()
        return response, debug_info

    except requests.Timeout as e:
        print(f"⏱️  Timeout connecting to {url}", file=sys.stderr)
        print(f"   Timeout duration: {timeout}s", file=sys.stderr)
        print(f"   Error: {str(e)}", file=sys.stderr)
        debug_info["error_type"] = "Timeout"
        debug_info["error_message"] = str(e)
        debug_info["success"] = False
        return None, debug_info

    except requests.ConnectionError as e:
        print(f"🔌 Connection error for {url}", file=sys.stderr)
        print(f"   Error type: {type(e).__name__}", file=sys.stderr)
        print(f"   Error details: {str(e)}", file=sys.stderr)
        if session.proxies:
            print(f"   Proxy configured: Yes", file=sys.stderr)
        debug_info["error_type"] = "ConnectionError"
        debug_info["error_message"] = str(e)
        debug_info["success"] = False
        return None, debug_info

    except requests.HTTPError as e:
        status_code = e.response.status_code if e.response else "unknown"
        print(f"📛 HTTP error {status_code} for {url}", file=sys.stderr)
        print(f"   Error: {str(e)}", file=sys.stderr)
        if e.response:
            print(f"   Response headers: {dict(e.response.headers)}", file=sys.stderr)
            debug_info["response_headers"] = dict(e.response.headers)
        debug_info["error_type"] = "HTTPError"
        debug_info["status_code"] = status_code
        debug_info["error_message"] = str(e)
        debug_info["success"] = False
        return None, debug_info

    except requests.RequestException as e:
        print(f"⚠️  Request error for {url}", file=sys.stderr)
        print(f"   Error type: {type(e).__name__}", file=sys.stderr)
        print(f"   Error details: {str(e)}", file=sys.stderr)
        debug_info["error_type"] = type(e).__name__
        debug_info["error_message"] = str(e)
        debug_info["success"] = False
        return None, debug_info


# =============================================================================
# SIMPLIFIED INDEX-BASED SEARCH (PRIMARY APPROACH)
# =============================================================================

# Initialize the BNF index on startup
_bnf_index: Optional[BNFIndex] = None

def get_index() -> BNFIndex:
    """Get or initialize the BNF index singleton."""
    global _bnf_index
    if _bnf_index is None:
        _bnf_index = get_bnf_index()
        print(f"✅ BNF Index loaded: {len(_bnf_index.drugs)} drugs", file=sys.stderr)
    return _bnf_index


@mcp.tool(
    name="search_bnf_index",
    description="Search for drugs in the local BNF index using fuzzy matching. Returns drug names, slugs, and URLs. Use this first, then call get_bnf_drug_by_slug with the slug."
)
def search_bnf_index(query: str, limit: int = 5) -> Dict[str, Any]:
    """
    Search the local BNF index for drugs matching the query.

    This uses fuzzy matching to find drugs even with typos or partial names.
    The index contains 1700+ drugs from the BNF.

    Args:
        query: Drug name to search for (e.g., "amoxicillin", "paracetmol", "ibuprofen")
        limit: Maximum number of results (default 5)

    Returns:
        Dictionary with:
        - success: Whether search succeeded
        - query: The original query
        - count: Number of results
        - results: List of matches with name, slug, url
    """
    try:
        index = get_index()
        results = index.search(query, limit=limit)

        formatted = []
        for r in results:
            formatted.append({
                'name': r['name'],
                'slug': r['slug'],
                'url': f"{BASE_URL}{r['url']}"
            })

        return {
            'success': True,
            'query': query,
            'count': len(formatted),
            'results': formatted,
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'query': query,
            'count': 0,
            'results': [],
            'error': str(e)
        }


@mcp.tool(
    name="get_bnf_drug_by_slug",
    description="Get detailed drug information by slug (from search_bnf_index results). This directly fetches the drug page without searching."
)
def get_bnf_drug_by_slug(slug: str) -> Dict[str, Any]:
    """
    Fetch detailed drug information directly by slug.

    Use the slug from search_bnf_index results. This is the most efficient
    way to get drug details - no search needed.

    Args:
        slug: The drug slug (e.g., "amoxicillin", "paracetamol")

    Returns:
        Dictionary with full drug information including indications, dosage, etc.
    """
    drug_url = f"{BASE_URL}/drugs/{slug}/"
    return _get_bnf_drug_info_impl(drug_url)


@mcp.tool(
    name="get_bnf_drug_for_patient",
    description="Get drug information tailored for a specific patient. Fetches BNF data and uses LLM to extract relevant dosing based on patient context."
)
def get_bnf_drug_for_patient(
    slug: str,
    patient_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Fetch drug info and tailor it to the patient in one call.

    This combines BNF data fetching with LLM-based personalization:
    1. Fetches raw BNF data by slug
    2. Uses Claude to extract patient-specific dosing and warnings

    Args:
        slug: Drug slug from search_bnf_index
        patient_context: Dictionary with:
            - clinical_scenario: Full consultation text
            - patient_age: Patient's age
            - allergies: Known allergies
            - diagnosis: The diagnosis this drug is for

    Returns:
        Dictionary with personalized drug guidance
    """
    import anthropic
    import json as json_module

    # Step 1: Fetch raw BNF data
    drug_url = f"{BASE_URL}/drugs/{slug}/"
    bnf_data = _get_bnf_drug_info_impl(drug_url)

    if not bnf_data.get('success'):
        return {
            'success': False,
            'drug_name': slug,
            'error': bnf_data.get('error', 'Failed to fetch BNF data')
        }

    # Step 2: Use LLM to tailor to patient
    api_key = os.getenv('ANTHROPIC_API_KEY')
    print(f"🎯 Personalizing {slug} for patient context (API key: {'set' if api_key else 'NOT SET'})", file=sys.stderr)

    if not api_key:
        # Return raw data if no API key
        print(f"⚠️  No API key - returning raw data for {slug}", file=sys.stderr)
        return {
            'success': True,
            'drug_name': bnf_data.get('drug_name', slug),
            'personalized': False,
            'bnf_data': bnf_data,
            'error': 'No ANTHROPIC_API_KEY for personalization'
        }

    try:
        client = anthropic.Anthropic(api_key=api_key)

        # Build prompt
        clinical_scenario = patient_context.get('clinical_scenario', '')
        patient_age = patient_context.get('patient_age', 'Not specified')
        allergies = patient_context.get('allergies', 'None known')
        diagnosis = patient_context.get('diagnosis', 'Not specified')

        # Format BNF sections
        bnf_sections = []
        for key in ['indications', 'dosage', 'contraindications', 'cautions', 'side_effects', 'interactions', 'pregnancy', 'renal_impairment', 'hepatic_impairment']:
            if bnf_data.get(key) and bnf_data[key] != 'Not specified':
                bnf_sections.append(f"{key.upper()}: {bnf_data[key]}")
        bnf_text = "\n".join(bnf_sections)

        prompt = f"""You are a clinical pharmacist providing personalized prescribing guidance.

PATIENT:
- Clinical Presentation: {clinical_scenario[:1500]}
- Age: {patient_age}
- Allergies: {allergies}
- Diagnosis: {diagnosis}

DRUG: {bnf_data.get('drug_name', slug)}

BNF DATA:
{bnf_text[:3000]}

Extract the SPECIFIC dosing and warnings for THIS patient. Consider:
1. Age-appropriate dosing
2. Renal/hepatic adjustments if indicated in presentation
3. Drug interactions with any medications mentioned
4. Contraindications based on comorbidities
5. Relevant monitoring

Respond with ONLY JSON:
{{
  "drug_name": "{bnf_data.get('drug_name', slug)}",
  "recommended_dose": "Specific dose for this patient",
  "route": "oral/IV/etc",
  "frequency": "dosing frequency",
  "duration": "treatment duration",
  "warnings": ["patient-specific warnings"],
  "contraindication_check": {{"safe": true/false, "concerns": ["any concerns"]}},
  "interactions": ["relevant drug interactions"],
  "monitoring": ["what to monitor"],
  "clinical_note": "brief clinical insight for this case"
}}"""

        print(f"📨 Calling Claude Haiku for {slug}...", file=sys.stderr)
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text
        print(f"✅ Claude response received for {slug} ({len(response_text)} chars)", file=sys.stderr)

        # Extract JSON
        import re
        if '```json' in response_text:
            match = re.search(r'```json\s*(\{.+?\})\s*```', response_text, re.DOTALL)
            if match:
                response_text = match.group(1)
        elif '```' in response_text:
            match = re.search(r'```\s*(\{.+?\})\s*```', response_text, re.DOTALL)
            if match:
                response_text = match.group(1)

        personalized = json_module.loads(response_text)

        return {
            'success': True,
            'drug_name': bnf_data.get('drug_name', slug),
            'url': bnf_data.get('url'),
            'personalized': True,
            'guidance': personalized,
            'raw_bnf': bnf_data
        }

    except Exception as e:
        print(f"⚠️  Personalization error for {slug}: {e}", file=sys.stderr)
        return {
            'success': True,
            'drug_name': bnf_data.get('drug_name', slug),
            'url': bnf_data.get('url'),
            'personalized': False,
            'bnf_data': bnf_data,
            'error': f'Personalization failed: {str(e)}'
        }


# =============================================================================
# LEGACY SEARCH (kept for backwards compatibility)
# =============================================================================

def _search_bnf_drug_impl(drug_name: str, variations: list[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    LEGACY: Search for drug using the old multi-step approach.
    Prefer using search_bnf_index + get_bnf_drug_by_slug instead.
    """
    # Use index-based search (simplified)
    try:
        index = get_index()
        results = index.search(drug_name, limit=5)

        if results:
            formatted = []
            for r in results:
                formatted.append({
                    'name': r['name'],
                    'url': f"{BASE_URL}{r['url']}",
                    'type': 'Drug'
                })

            return {
                'query': drug_name,
                'results': formatted,
                'count': len(formatted),
                'success': True,
                'error': None,
                'source': 'index'
            }

        return {
            'query': drug_name,
            'results': [],
            'count': 0,
            'success': False,
            'error': f'Drug "{drug_name}" not found in BNF index'
        }

    except Exception as e:
        return {
            'query': drug_name,
            'results': [],
            'count': 0,
            'success': False,
            'error': f'Search error: {str(e)}'
        }


@mcp.tool(
    name="search_bnf_drug",
    description="[LEGACY] Search for drugs by name. Prefer search_bnf_index + get_bnf_drug_by_slug for better results."
)
def search_bnf_drug(drug_name: str, variations: list[str] = None) -> Dict[str, Any]:
    """
    LEGACY: Search for a drug by name.
    Prefer using search_bnf_index + get_bnf_drug_by_slug instead.
    """
    return _search_bnf_drug_impl(drug_name, variations=variations)


def _get_bnf_drug_info_impl(drug_url: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve comprehensive information about a drug from its BNF page.

    Args:
        drug_url: URL to the drug's BNF page
        session_id: Optional Bright Data session ID for IP pinning

    This tool scrapes detailed drug information from a BNF drug page URL,
    including indications, dosage recommendations, contraindications, cautions,
    side effects, interactions, and prescribing information.

    Args:
        drug_url: The full URL to the drug's BNF page (e.g., from search_bnf_drug results)

    Returns:
        Dictionary containing:
            - drug_name (str): Official drug name
            - url (str): The BNF page URL
            - indications (str): Medical indications and licensed uses
            - dosage (str): Dosage information for different routes and patient groups
            - contraindications (str): Absolute contraindications
            - cautions (str): Warnings and cautions for use
            - side_effects (str): Known side effects and adverse reactions
            - interactions (str): Drug interactions information
            - pregnancy (str): Pregnancy category and information
            - breast_feeding (str): Breast-feeding information
            - renal_impairment (str): Dosage adjustments for renal impairment
            - hepatic_impairment (str): Dosage adjustments for hepatic impairment
            - prescribing_info (str): Additional prescribing and dispensing information
            - success (bool): Whether the retrieval was successful
            - error (str|None): Error message if retrieval failed, None otherwise

    Example:
        >>> get_bnf_drug_info("https://bnf.nice.org.uk/drugs/paracetamol/")
        {
            "drug_name": "Paracetamol",
            "url": "https://bnf.nice.org.uk/drugs/paracetamol/",
            "indications": "Mild to moderate pain; pyrexia",
            "dosage": "Adult: 500-1000mg every 4-6 hours; max 4g daily",
            ...
            "success": True,
            "error": None
        }
    """
    try:
        # Use requests with ScrapeOps proxy
        response, debug_info = make_request(drug_url)
        if not response:
            return {
                'drug_name': 'Unknown',
                'url': drug_url,
                'success': False,
                'error': 'Failed to connect to BNF website'
            }

        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')

        # Extract drug name from title or heading
        drug_name = 'Unknown'
        title_tag = soup.find('h1')
        if title_tag:
            drug_name = title_tag.get_text(strip=True)

        # Helper function to extract section content
        def extract_section(section_name: str) -> str:
            """Extract text from a section by heading name."""
            content = []

            # Try to find section by heading
            headings = soup.find_all(['h2', 'h3', 'h4'])
            for heading in headings:
                heading_text = heading.get_text(strip=True).lower()
                if section_name.lower() in heading_text:
                    # Get all following siblings until next heading
                    for sibling in heading.find_next_siblings():
                        if sibling.name in ['h2', 'h3', 'h4']:
                            break
                        # Use separator=' ' to properly space text from adjacent elements
                        text = sibling.get_text(separator=' ', strip=True)
                        if text:
                            content.append(text)

            return '\n'.join(content) if content else 'Not specified'

        # Extract various sections
        drug_info = {
            'drug_name': drug_name,
            'url': drug_url,
            'indications': extract_section('indications'),
            'dosage': extract_section('dose'),
            'contraindications': extract_section('contraindications'),
            'cautions': extract_section('cautions'),
            'side_effects': extract_section('side effects'),
            'interactions': extract_section('interactions'),
            'pregnancy': extract_section('pregnancy'),
            'breast_feeding': extract_section('breast feeding'),
            'renal_impairment': extract_section('renal impairment'),
            'hepatic_impairment': extract_section('hepatic impairment'),
            'prescribing_info': extract_section('prescribing'),
            'success': True,
            'error': None
        }

        return drug_info

    except Exception as e:
        return {
            'drug_name': 'Unknown',
            'url': drug_url,
            'success': False,
            'error': f'Error retrieving drug information: {str(e)}'
        }


@mcp.tool(
    name="get_bnf_drug_info",
    description="Get detailed information about a specific drug including indications, dosage, contraindications, side effects, and warnings"
)
def get_bnf_drug_info(drug_url: str) -> Dict[str, Any]:
    """
    Retrieve comprehensive information about a drug from its BNF page.

    Args:
        drug_url: The full URL to the drug's BNF page (e.g., from search_bnf_drug results)

    Returns:
        Dictionary containing detailed drug information
    """
    return _get_bnf_drug_info_impl(drug_url)


@mcp.tool(
    name="search_bnf_by_condition",
    description="Search for drugs/treatments by medical condition or indication in the British National Formulary"
)
def search_bnf_by_condition(condition: str) -> Dict[str, Any]:
    """
    Search for medications and treatments by medical condition or indication.

    This tool searches the BNF for drugs that are indicated for treating a specific
    medical condition. It helps find appropriate medications for various diseases,
    symptoms, or medical indications.

    Args:
        condition: The medical condition or indication to search for (e.g., "hypertension",
                  "diabetes", "pain", "infection")

    Returns:
        Dictionary containing:
            - condition (str): The condition searched for
            - treatments (list): List of relevant treatments/drugs, each with:
                - name (str): Drug or treatment name
                - url (str): Full URL to the BNF page
                - description (str): Brief description if available
            - count (int): Number of treatments found
            - success (bool): Whether the search was successful
            - error (str|None): Error message if search failed, None otherwise

    Example:
        >>> search_bnf_by_condition("hypertension")
        {
            "condition": "hypertension",
            "treatments": [
                {
                    "name": "Amlodipine",
                    "url": "https://bnf.nice.org.uk/drugs/amlodipine/",
                    "description": "Calcium-channel blocker for hypertension"
                },
                ...
            ],
            "count": 15,
            "success": True,
            "error": None
        }
    """
    try:
        # Search using the condition as a query term
        search_url = f"{BASE_URL}/treatment-summaries/?q={quote(condition)}"

        response, debug_info = make_request(search_url)
        if not response:
            # Fallback to regular search if treatment summaries don't work
            search_url = f"{BASE_URL}/search/?q={quote(condition)}"
            response, debug_info = make_request(search_url)

        if not response:
            return {
                'condition': condition,
                'treatments': [],
                'count': 0,
                'success': False,
                'error': 'Failed to connect to BNF website'
            }

        soup = BeautifulSoup(response.content, 'html.parser')
        treatments = []

        # Find treatment-related links
        links = soup.find_all('a', href=True)

        for link in links:
            href = link.get('href', '')
            # Look for drug, treatment, or medicine pages
            if any(path in href for path in ['/drugs/', '/drug/', '/medicines/', '/treatment-summary/']):
                name = link.get_text(strip=True)
                if name and len(name) > 1:
                    full_url = urljoin(BASE_URL, href)

                    # Get description from nearby text if available
                    description = ''
                    parent = link.find_parent(['li', 'div', 'p'])
                    if parent:
                        # Use separator=' ' to properly space text from adjacent elements
                        desc_text = parent.get_text(separator=' ', strip=True)
                        # Limit description length
                        if len(desc_text) > len(name) and len(desc_text) < 300:
                            description = desc_text

                    # Avoid duplicates
                    if not any(t['url'] == full_url for t in treatments):
                        treatments.append({
                            'name': name,
                            'url': full_url,
                            'description': description if description else 'No description available'
                        })

        return {
            'condition': condition,
            'treatments': treatments[:20],  # Limit to top 20 results
            'count': len(treatments[:20]),
            'success': True,
            'error': None
        }

    except Exception as e:
        return {
            'condition': condition,
            'treatments': [],
            'count': 0,
            'success': False,
            'error': f'Search error: {str(e)}'
        }


@mcp.tool(
    name="get_bnf_drug_interactions",
    description="Get detailed drug interaction information for a specific medication from the BNF"
)
def get_bnf_drug_interactions(drug_name: str) -> Dict[str, Any]:
    """
    Retrieve drug interaction information for a specific medication.

    This tool specifically focuses on drug-drug interactions, providing detailed
    information about which medications should not be combined with the queried drug
    and what precautions should be taken when combining medications.

    Args:
        drug_name: The name of the drug to check interactions for (e.g., "warfarin", "metformin")

    Returns:
        Dictionary containing:
            - drug_name (str): The drug queried
            - interactions (list): List of interaction entries, each with:
                - interacting_drug (str): Name of the interacting medication
                - severity (str): Severity level if specified
                - description (str): Description of the interaction
            - count (int): Number of interactions found
            - success (bool): Whether the retrieval was successful
            - error (str|None): Error message if retrieval failed, None otherwise

    Example:
        >>> get_bnf_drug_interactions("warfarin")
        {
            "drug_name": "warfarin",
            "interactions": [
                {
                    "interacting_drug": "Aspirin",
                    "severity": "Severe",
                    "description": "Increased risk of bleeding"
                },
                ...
            ],
            "count": 25,
            "success": True,
            "error": None
        }
    """
    try:
        # First search for the drug
        search_result = search_bnf_drug(drug_name)

        if not search_result['success'] or search_result['count'] == 0:
            return {
                'drug_name': drug_name,
                'interactions': [],
                'count': 0,
                'success': False,
                'error': 'Drug not found in BNF'
            }

        # Get the first matching drug URL
        drug_url = search_result['results'][0]['url']

        # Try to find interactions page (often a subpage or section)
        interactions_url = drug_url.rstrip('/') + '/interactions/'

        response, debug_info = make_request(interactions_url)
        if not response:
            # Fallback: get interactions from main drug page
            response, debug_info = make_request(drug_url)

        if not response:
            return {
                'drug_name': drug_name,
                'interactions': [],
                'count': 0,
                'success': False,
                'error': 'Failed to retrieve interaction information'
            }

        soup = BeautifulSoup(response.content, 'html.parser')
        interactions_list = []

        # Look for interactions section
        interaction_section = None
        headings = soup.find_all(['h2', 'h3', 'h4'])
        for heading in headings:
            if 'interaction' in heading.get_text(strip=True).lower():
                interaction_section = heading
                break

        if interaction_section:
            # Extract interaction entries
            for sibling in interaction_section.find_next_siblings():
                if sibling.name in ['h2', 'h3']:
                    break

                # Look for drug names and descriptions in lists or paragraphs
                if sibling.name in ['ul', 'ol']:
                    for item in sibling.find_all('li'):
                        # Use separator=' ' to properly space text from adjacent elements
                        text = item.get_text(separator=' ', strip=True)
                        if text:
                            # Try to parse drug name and description
                            parts = text.split(':', 1) if ':' in text else [text, '']
                            interactions_list.append({
                                'interacting_drug': parts[0].strip(),
                                'severity': 'Not specified',
                                'description': parts[1].strip() if len(parts) > 1 else text
                            })
                elif sibling.name == 'p':
                    # Use separator=' ' to properly space text from adjacent elements
                    text = sibling.get_text(separator=' ', strip=True)
                    if text and len(text) > 10:
                        interactions_list.append({
                            'interacting_drug': 'Multiple',
                            'severity': 'Not specified',
                            'description': text
                        })

        return {
            'drug_name': drug_name,
            'interactions': interactions_list,
            'count': len(interactions_list),
            'success': True,
            'error': None if interactions_list else 'No interaction information found'
        }

    except Exception as e:
        return {
            'drug_name': drug_name,
            'interactions': [],
            'count': 0,
            'success': False,
            'error': f'Error retrieving interactions: {str(e)}'
        }


@mcp.tool(
    name="get_multiple_bnf_drugs_parallel",
    description="Look up multiple drugs using the BNF index for fuzzy search, then fetch details. More efficient than individual lookups."
)
def get_multiple_bnf_drugs_parallel(drug_names: List[str]) -> Dict[str, Any]:
    """
    Look up multiple drugs from the BNF using simplified index-based search.

    Flow for each drug:
    1. Fuzzy search in local index -> get best matching slug
    2. Fetch drug details by slug -> get full info

    Args:
        drug_names: List of drug names to look up

    Returns:
        Dictionary with results for all drugs
    """
    try:
        index = get_index()

        def lookup_single_drug(drug_name: str) -> Dict[str, Any]:
            """Look up a single drug using index + direct fetch."""
            try:
                # Step 1: Search index for best match
                matches = index.search(drug_name, limit=1)

                if not matches:
                    return {
                        'drug_name': drug_name,
                        'status': 'not_found',
                        'data': None,
                        'error': f'Drug "{drug_name}" not found in BNF index'
                    }

                # Get the best match
                best_match = matches[0]
                slug = best_match['slug']

                print(f"🔍 {drug_name} -> {best_match['name']} (slug: {slug})", file=sys.stderr)

                # Step 2: Fetch drug details by slug
                drug_url = f"{BASE_URL}/drugs/{slug}/"
                drug_info = _get_bnf_drug_info_impl(drug_url)

                if drug_info.get('success'):
                    return {
                        'drug_name': drug_name,
                        'status': 'success',
                        'data': drug_info,
                        'error': None
                    }
                else:
                    return {
                        'drug_name': drug_name,
                        'status': 'error',
                        'data': None,
                        'error': drug_info.get('error', 'Failed to fetch drug info')
                    }

            except Exception as e:
                return {
                    'drug_name': drug_name,
                    'status': 'error',
                    'data': None,
                    'error': str(e)
                }

        # Execute lookups sequentially (proxy tier limitation)
        results = []
        for drug_name in drug_names:
            result = lookup_single_drug(drug_name)
            results.append(result)

        # Calculate stats
        successful = sum(1 for r in results if r['status'] == 'success')
        failed = len(results) - successful

        return {
            'success': True,
            'total_drugs': len(drug_names),
            'successful_lookups': successful,
            'failed_lookups': failed,
            'drugs': results,
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'total_drugs': len(drug_names) if drug_names else 0,
            'successful_lookups': 0,
            'failed_lookups': len(drug_names) if drug_names else 0,
            'drugs': [],
            'error': f'Lookup error: {str(e)}'
        }


@mcp.tool(
    name="search_bnf_treatment_summaries",
    description="Search for BNF treatment summaries by condition (e.g., pneumonia, sepsis, UTI). Treatment summaries provide evidence-based prescribing guidance including first-line treatments, alternatives, and dosing."
)
def search_bnf_treatment_summaries(condition: str, max_results: int = 10) -> Dict[str, Any]:
    """
    Search for BNF treatment summaries by medical condition.

    Treatment summaries provide comprehensive prescribing guidance organized by
    condition, including recommended antibacterial therapy, treatment durations,
    and alternatives for patients with allergies.

    Args:
        condition: Medical condition to search for (e.g., "pneumonia", "sepsis", "UTI")
        max_results: Maximum number of results to return (default: 10)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - condition (str): The condition searched for
            - count (int): Number of treatment summaries found
            - results (list): List of treatment summaries with:
                - title (str): Treatment summary title
                - url (str): Full URL to the treatment summary
                - description (str): Brief description
            - error (str|None): Error message if search failed
    """
    try:
        # Search the treatment summaries index
        search_url = f"{BASE_URL}/treatment-summaries/"

        response, debug_info = make_request(search_url)
        if not response:
            return {
                'success': False,
                'condition': condition,
                'count': 0,
                'results': [],
                'error': 'Failed to connect to BNF website'
            }

        soup = BeautifulSoup(response.content, 'html.parser')
        summaries = []

        # Find all treatment summary links
        links = soup.find_all('a', href=lambda x: x and '/treatment-summaries/' in x)

        for link in links:
            href = link.get('href', '')
            title = link.get_text(strip=True)

            # Filter by condition keyword
            if condition.lower() in title.lower() or condition.lower() in href.lower():
                full_url = urljoin(BASE_URL, href)

                # Get description from nearby text
                description = ''
                parent = link.find_parent(['li', 'div', 'p'])
                if parent:
                    # Use separator=' ' to properly space text from adjacent elements
                    desc_text = parent.get_text(separator=' ', strip=True)
                    if len(desc_text) > len(title) and len(desc_text) < 300:
                        description = desc_text

                # Avoid duplicates
                if not any(s['url'] == full_url for s in summaries):
                    summaries.append({
                        'title': title,
                        'url': full_url,
                        'description': description if description else 'BNF treatment summary'
                    })

                if len(summaries) >= max_results:
                    break

        # If no direct matches, search more broadly
        if len(summaries) == 0:
            for link in links:
                title = link.get_text(strip=True)
                href = link.get('href', '')

                # More flexible matching
                condition_words = condition.lower().split()
                title_lower = title.lower()

                if any(word in title_lower for word in condition_words if len(word) > 3):
                    full_url = urljoin(BASE_URL, href)

                    if not any(s['url'] == full_url for s in summaries):
                        summaries.append({
                            'title': title,
                            'url': full_url,
                            'description': 'BNF treatment summary'
                        })

                    if len(summaries) >= max_results:
                        break

        return {
            'success': True,
            'condition': condition,
            'count': len(summaries),
            'results': summaries,
            'error': None if summaries else 'No treatment summaries found for this condition'
        }

    except Exception as e:
        return {
            'success': False,
            'condition': condition,
            'count': 0,
            'results': [],
            'error': f'Search error: {str(e)}'
        }


@mcp.tool(
    name="get_bnf_treatment_summary",
    description="Get detailed content from a specific BNF treatment summary including treatment recommendations, antibacterial choices, dosing, and alternatives for allergies."
)
def get_bnf_treatment_summary(url: str) -> Dict[str, Any]:
    """
    Retrieve full content from a BNF treatment summary page.

    Args:
        url: Full URL to the treatment summary (from search results)

    Returns:
        Dictionary containing:
            - success (bool): Whether retrieval was successful
            - title (str): Treatment summary title
            - url (str): The URL requested
            - summary (str): Main treatment guidance text
            - sections (list): List of sections with:
                - heading (str): Section heading
                - content (str): Section text content
            - error (str|None): Error message if retrieval failed
    """
    try:
        response, debug_info = make_request(url)
        if not response:
            return {
                'success': False,
                'title': '',
                'url': url,
                'summary': '',
                'sections': [],
                'error': 'Failed to retrieve treatment summary page'
            }

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract title
        title = ''
        title_elem = soup.find('h1')
        if title_elem:
            title = title_elem.get_text(strip=True)

        # Extract main content
        summary = ''
        sections = []

        # Find main content area
        main_content = soup.find(['main', 'article', 'div'], class_=lambda x: x and ('content' in x.lower() or 'main' in x.lower()))
        if not main_content:
            main_content = soup.find('body')

        if main_content:
            # Extract sections
            current_heading = None
            current_content = []

            for elem in main_content.find_all(['h2', 'h3', 'h4', 'p', 'ul', 'ol', 'table']):
                if elem.name in ['h2', 'h3', 'h4']:
                    # Save previous section
                    if current_heading:
                        sections.append({
                            'heading': current_heading,
                            'content': ' '.join(current_content)
                        })

                    current_heading = elem.get_text(strip=True)
                    current_content = []

                elif elem.name in ['p', 'ul', 'ol']:
                    # Use separator=' ' to properly space text from adjacent elements
                    text = elem.get_text(separator=' ', strip=True)
                    if text:
                        current_content.append(text)

            # Save last section
            if current_heading and current_content:
                sections.append({
                    'heading': current_heading,
                    'content': ' '.join(current_content)
                })

            # Create summary from first few paragraphs
            # Use separator=' ' to properly space text from adjacent elements
            paragraphs = main_content.find_all('p', limit=3)
            summary = ' '.join([p.get_text(separator=' ', strip=True) for p in paragraphs if p.get_text(strip=True)])

        return {
            'success': True,
            'title': title,
            'url': url,
            'summary': summary[:1000] if summary else 'No summary available',
            'sections': sections[:15],  # Limit to first 15 sections
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'title': '',
            'url': url,
            'summary': '',
            'sections': [],
            'error': f'Error retrieving treatment summary: {str(e)}'
        }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
