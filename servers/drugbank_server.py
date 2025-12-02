#!/usr/bin/env python
"""
MCP Server for DrugBank pharmaceutical information.

Provides tools to search for drugs and medications, retrieve detailed drug information
including indications, pharmacodynamics, mechanism of action, toxicity, and drug interactions.
Uses web scraping to access the DrugBank website (https://go.drugbank.com/).
"""

import requests
from bs4 import BeautifulSoup
from typing import Optional, List, Dict, Any
from fastmcp import FastMCP
import time
import os
import sys
from urllib.parse import urljoin, quote
import urllib3

# Suppress SSL verification warnings (required for Bright Data proxy)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Try to import cache, but gracefully handle if Firebase isn't available
try:
    from drugbank_cache import get_cache
    CACHE_AVAILABLE = True
except Exception as e:
    print(f"⚠️  Cache module unavailable (will run without caching): {str(e)}", file=sys.stderr)
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

# Initialize FastMCP server with proper name and instructions
mcp = FastMCP(
    "DrugBank",
    instructions="DrugBank pharmaceutical information service providing comprehensive drug data including indications, pharmacodynamics, mechanism of action, interactions, and toxicity information"
)

# Base URL for DrugBank website
BASE_URL = "https://go.drugbank.com"

# Headers to mimic a real browser and avoid 403 errors
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

# Bright Data residential proxy configuration
# This routes requests through residential IPs to bypass Cloudflare blocking
BRIGHT_DATA_PROXY = {
    'username': 'brd-customer-hl_3dba8aa2-zone-residential_proxy1',
    'password': 'i4c5leuevuqr',
    'host': 'brd.superproxy.io',
    'port': '33335'
}

# Build proxy URL
proxy_url = f"http://{BRIGHT_DATA_PROXY['username']}:{BRIGHT_DATA_PROXY['password']}@{BRIGHT_DATA_PROXY['host']}:{BRIGHT_DATA_PROXY['port']}"
proxies = {
    'http': proxy_url,
    'https': proxy_url
}

# Create session with Bright Data proxy
session = requests.Session()
session.headers.update(HEADERS)
session.proxies.update(proxies)

print("🔄 DrugBank server using Bright Data residential proxy", file=sys.stderr)
print(f"   Proxy host: {BRIGHT_DATA_PROXY['host']}:{BRIGHT_DATA_PROXY['port']}", file=sys.stderr)
print("   Requests will route through residential IPs to bypass Cloudflare", file=sys.stderr)

# Initialize cache
cache = get_cache()


def make_request(url: str, timeout: int = 60) -> tuple[Optional[requests.Response], Dict[str, Any]]:
    """
    Make a GET request with proper error handling and rate limiting.
    Uses Bright Data residential proxy to bypass Cloudflare protection.

    Args:
        url: The URL to request
        timeout: Request timeout in seconds

    Returns:
        Tuple of (Response object or None if failed, debug_info dictionary)
    """
    debug_info = {
        "url": url,
        "bright_data_proxy": True,
        "timeout": timeout
    }

    try:
        # Add a small delay to be respectful to the server
        time.sleep(0.5)

        # Use session with Bright Data residential proxy
        # verify=False needed for Bright Data proxy SSL interception
        print(f"🌐 [BRIGHT DATA PROXY] Requesting: {url}", file=sys.stderr)
        response = session.get(url, timeout=timeout, verify=False)

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


@mcp.tool(
    name="search_drugbank_drug",
    description="Search for drugs/medications by name in DrugBank and return matching results with links to detailed drug information pages"
)
def search_drugbank_drug(drug_name: str) -> Dict[str, Any]:
    """
    Search for a drug or medication by name in DrugBank.

    This tool searches the DrugBank database for drugs matching the provided name.
    It returns a list of matching medications with their DrugBank IDs and URLs
    for further detailed lookup.

    Args:
        drug_name: The name of the drug to search for (e.g., "aspirin", "metformin", "lisinopril")

    Returns:
        Dictionary containing:
            - query (str): The search term used
            - results (list): List of matching drugs, each with:
                - name (str): Drug name
                - drugbank_id (str): DrugBank identifier (e.g., "DB00945")
                - url (str): Full URL to the drug's DrugBank page
                - type (str): Drug type (e.g., "Small Molecule", "Biotech")
            - count (int): Number of results found
            - success (bool): Whether the search was successful
            - error (str|None): Error message if search failed, None otherwise

    Example:
        >>> search_drugbank_drug("aspirin")
        {
            "query": "aspirin",
            "results": [
                {
                    "name": "Aspirin",
                    "drugbank_id": "DB00945",
                    "url": "https://go.drugbank.com/drugs/DB00945",
                    "type": "Small Molecule"
                }
            ],
            "count": 1,
            "success": True,
            "error": None
        }
    """
    # Check cache first
    cached_result = cache.get('search_drug', drug_name)
    if cached_result:
        return cached_result

    try:
        # Use the main drugs browsing/search page
        search_url = f"{BASE_URL}/unearth/q?query={quote(drug_name)}&searcher=drugs"

        response, debug_info = make_request(search_url)
        if not response:
            return {
                'query': drug_name,
                'results': [],
                'count': 0,
                'success': False,
                'error': 'Failed to connect to DrugBank website',
                'debug_info': debug_info
            }

        soup = BeautifulSoup(response.content, 'html.parser')
        results = []

        # Look for drug links in search results
        # DrugBank uses /drugs/DBXXXXX pattern
        drug_links = soup.find_all('a', href=True)

        for link in drug_links:
            href = link.get('href', '')
            # Match DrugBank drug URL pattern: /drugs/DB##### (5 digits)
            if '/drugs/DB' in href and len(href.split('/drugs/')[-1]) >= 7:
                drug_name_text = link.get_text(strip=True)

                # Extract DrugBank ID from URL
                drugbank_id = href.split('/drugs/')[-1].split('/')[0].split('?')[0]

                # Skip if not a proper DrugBank ID (should be DB followed by 5 digits)
                if not drugbank_id.startswith('DB') or len(drugbank_id) != 7:
                    continue

                # Skip navigation links and very short text
                if (drug_name_text and len(drug_name_text) > 1 and
                    drug_name_text.lower() != 'drugs' and
                    len(drug_name_text) < 100):  # Drug names shouldn't be too long

                    full_url = urljoin(BASE_URL, href)

                    # Avoid duplicates
                    if not any(r['drugbank_id'] == drugbank_id for r in results):
                        results.append({
                            'name': drug_name_text,
                            'drugbank_id': drugbank_id,
                            'url': full_url,
                            'type': 'Drug'  # Will be updated when getting detailed info
                        })

        result = {
            'query': drug_name,
            'results': results[:10],  # Limit to top 10 results
            'count': len(results[:10]),
            'success': True,
            'error': None,
            'debug_info': debug_info
        }

        # Cache successful results
        if result['success'] and result['count'] > 0:
            cache.set('search_drug', drug_name, result)

        return result

    except Exception as e:
        result = {
            'query': drug_name,
            'results': [],
            'count': 0,
            'success': False,
            'error': f'Search error: {str(e)}'
        }
        return result


@mcp.tool(
    name="get_drugbank_drug_info",
    description="Get comprehensive information about a specific drug including indications, pharmacodynamics, mechanism of action, absorption, toxicity, half-life, and metabolism"
)
def get_drugbank_drug_info(drug_url: str) -> Dict[str, Any]:
    """
    Retrieve comprehensive pharmaceutical information about a drug from its DrugBank page.

    This tool scrapes detailed drug information from a DrugBank drug page URL,
    including clinical indications, pharmacodynamics, mechanism of action, absorption,
    distribution, metabolism, elimination, toxicity, and other pharmaceutical properties.

    Args:
        drug_url: The full URL to the drug's DrugBank page (e.g., from search_drugbank_drug results)
                 Format: https://go.drugbank.com/drugs/DB#####

    Returns:
        Dictionary containing:
            - drug_name (str): Official drug name
            - drugbank_id (str): DrugBank identifier (e.g., "DB00945")
            - url (str): The DrugBank page URL
            - type (str): Drug type (Small Molecule, Biotech, etc.)
            - description (str): Drug description and background
            - indications (str): Medical indications and approved uses
            - pharmacodynamics (str): Pharmacological effects and therapeutic actions
            - mechanism_of_action (str): How the drug works at molecular level
            - absorption (str): Absorption characteristics and bioavailability
            - protein_binding (str): Protein binding information
            - metabolism (str): Metabolic pathways and enzymes involved
            - half_life (str): Elimination half-life
            - toxicity (str): Toxicity information and adverse effects
            - targets (list): Drug targets (proteins, enzymes)
            - success (bool): Whether the retrieval was successful
            - error (str|None): Error message if retrieval failed, None otherwise

    Example:
        >>> get_drugbank_drug_info("https://go.drugbank.com/drugs/DB00945")
        {
            "drug_name": "Aspirin",
            "drugbank_id": "DB00945",
            "url": "https://go.drugbank.com/drugs/DB00945",
            "type": "Small Molecule",
            "indications": "For use in the temporary relief of various forms of pain...",
            "mechanism_of_action": "Salicylate, the active metabolite of aspirin...",
            ...
            "success": True,
            "error": None
        }
    """
    try:
        # Extract DrugBank ID from URL
        drugbank_id = drug_url.split('/drugs/')[-1].split('/')[0].split('?')[0]

        response, debug_info = make_request(drug_url)
        if not response:
            return {
                'drug_name': 'Unknown',
                'drugbank_id': drugbank_id,
                'url': drug_url,
                'success': False,
                'error': 'Failed to connect to DrugBank website',
                'debug_info': debug_info
            }

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract drug name from h1 tag
        drug_name = 'Unknown'
        h1_tag = soup.find('h1')
        if h1_tag:
            drug_name = h1_tag.get_text(strip=True)

        # Helper function to extract content from dt/dd pairs
        def extract_dt_section(section_name: str) -> str:
            """
            Extract text from a dt/dd pair by searching for dt with matching text.
            DrugBank uses definition lists (dt/dd) for structured data.
            """
            # Find all dt elements
            dts = soup.find_all('dt')
            for dt in dts:
                dt_text = dt.get_text(strip=True).lower()
                # Match the section name (case-insensitive, flexible matching)
                if section_name.lower() in dt_text:
                    # Get the corresponding dd element
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        # Extract text with proper spacing
                        text = dd.get_text(separator=' ', strip=True)
                        if text:
                            return text

            return 'Not specified'

        # Extract drug type/modality
        drug_type = 'Unknown'
        modality_text = extract_dt_section('modality')
        if modality_text and modality_text != 'Not specified':
            drug_type = modality_text

        # Extract various pharmacological sections
        drug_info = {
            'drug_name': drug_name,
            'drugbank_id': drugbank_id,
            'url': drug_url,
            'type': drug_type,
            'description': extract_dt_section('description'),
            'indications': extract_dt_section('indication'),
            'pharmacodynamics': extract_dt_section('pharmacodynamics'),
            'mechanism_of_action': extract_dt_section('mechanism of action'),
            'absorption': extract_dt_section('absorption'),
            'protein_binding': extract_dt_section('protein binding'),
            'metabolism': extract_dt_section('metabolism'),
            'half_life': extract_dt_section('half-life'),  # Note: hyphenated in HTML
            'toxicity': extract_dt_section('toxicity'),
            'targets': [],  # Will be populated below
            'success': True,
            'error': None,
            'debug_info': debug_info
        }

        # Extract drug targets (polypeptide links)
        # DrugBank links to polypeptides at /polypeptides/PXXXXX
        targets = []
        target_links = soup.find_all('a', href=lambda x: x and '/polypeptides/' in x)
        seen_targets = set()
        for link in target_links:
            target_name = link.get_text(strip=True)
            # Avoid duplicates and ensure valid target names
            if target_name and len(target_name) > 2 and target_name not in seen_targets:
                targets.append(target_name)
                seen_targets.add(target_name)
                if len(targets) >= 10:  # Limit to first 10 targets
                    break

        drug_info['targets'] = targets

        return drug_info

    except Exception as e:
        return {
            'drug_name': 'Unknown',
            'drugbank_id': drugbank_id if 'drugbank_id' in locals() else 'Unknown',
            'url': drug_url,
            'success': False,
            'error': f'Error retrieving drug information: {str(e)}'
        }


@mcp.tool(
    name="search_drugbank_by_condition",
    description="Search for drugs/treatments by medical condition or therapeutic indication in DrugBank"
)
def search_drugbank_by_condition(condition: str) -> Dict[str, Any]:
    """
    Search for medications by medical condition or therapeutic indication.

    This tool searches DrugBank for drugs that are indicated for treating a specific
    medical condition. It helps find appropriate medications for various diseases,
    symptoms, or medical indications by searching through drug indications.

    Args:
        condition: The medical condition or indication to search for (e.g., "hypertension",
                  "diabetes", "heart failure", "depression", "pain")

    Returns:
        Dictionary containing:
            - condition (str): The condition searched for
            - treatments (list): List of relevant treatments/drugs, each with:
                - name (str): Drug name
                - drugbank_id (str): DrugBank identifier
                - url (str): Full URL to the DrugBank page
                - indication_text (str): Relevant indication text if available
            - count (int): Number of treatments found
            - success (bool): Whether the search was successful
            - error (str|None): Error message if search failed, None otherwise

    Example:
        >>> search_drugbank_by_condition("hypertension")
        {
            "condition": "hypertension",
            "treatments": [
                {
                    "name": "Amlodipine",
                    "drugbank_id": "DB00381",
                    "url": "https://go.drugbank.com/drugs/DB00381",
                    "indication_text": "Treatment of hypertension and chronic stable angina"
                },
                ...
            ],
            "count": 15,
            "success": True,
            "error": None
        }
    """
    try:
        # Search using advanced search with indication filter
        search_url = f"{BASE_URL}/unearth/q?query={quote(condition)}&searcher=drugs"

        response, debug_info = make_request(search_url)
        if not response:
            return {
                'condition': condition,
                'treatments': [],
                'count': 0,
                'success': False,
                'error': 'Failed to connect to DrugBank website',
                'debug_info': debug_info
            }

        soup = BeautifulSoup(response.content, 'html.parser')
        treatments = []

        # Find drug links and extract context about the condition
        drug_links = soup.find_all('a', href=True)

        for link in drug_links:
            href = link.get('href', '')
            # Look for drug pages
            if '/drugs/DB' in href and len(href.split('/drugs/')[-1]) >= 7:
                name = link.get_text(strip=True)

                # Extract DrugBank ID
                drugbank_id = href.split('/drugs/')[-1].split('/')[0].split('?')[0]

                # Skip if not a proper DrugBank ID
                if not drugbank_id.startswith('DB') or len(drugbank_id) != 7:
                    continue

                if name and len(name) > 1 and len(name) < 100:
                    full_url = urljoin(BASE_URL, href)

                    # Get indication context from nearby text
                    indication_text = ''
                    parent = link.find_parent(['li', 'div', 'p', 'td'])
                    if parent:
                        text = parent.get_text(separator=' ', strip=True)
                        # Check if condition is mentioned in the context
                        if condition.lower() in text.lower() and len(text) < 500:
                            indication_text = text

                    # Avoid duplicates
                    if not any(t['drugbank_id'] == drugbank_id for t in treatments):
                        treatments.append({
                            'name': name,
                            'drugbank_id': drugbank_id,
                            'url': full_url,
                            'indication_text': indication_text if indication_text else 'See drug page for details'
                        })

        result = {
            'condition': condition,
            'treatments': treatments[:20],  # Limit to top 20 results
            'count': len(treatments[:20]),
            'success': True,
            'error': None if treatments else 'No treatments found for this condition',
            'debug_info': debug_info
        }

        return result

    except Exception as e:
        return {
            'condition': condition,
            'treatments': [],
            'count': 0,
            'success': False,
            'error': f'Search error: {str(e)}'
        }


@mcp.tool(
    name="get_drugbank_interactions",
    description="Get detailed drug-drug interaction information for a specific medication from DrugBank"
)
def get_drugbank_interactions(drug_name: str) -> Dict[str, Any]:
    """
    Retrieve drug-drug interaction information for a specific medication.

    This tool specifically focuses on drug-drug interactions, providing detailed
    information about which medications should not be combined with the queried drug,
    what precautions should be taken, and the clinical significance of interactions.

    Args:
        drug_name: The name of the drug to check interactions for (e.g., "warfarin", "metformin", "aspirin")

    Returns:
        Dictionary containing:
            - drug_name (str): The drug queried
            - drugbank_id (str): DrugBank identifier
            - interactions (list): List of interaction entries, each with:
                - interacting_drug (str): Name of the interacting medication
                - drugbank_id (str): DrugBank ID of interacting drug
                - description (str): Description of the interaction
                - severity (str): Severity level if available
            - count (int): Number of interactions found
            - interaction_checker_url (str): URL to DrugBank's interaction checker tool
            - success (bool): Whether the retrieval was successful
            - error (str|None): Error message if retrieval failed, None otherwise

    Example:
        >>> get_drugbank_interactions("warfarin")
        {
            "drug_name": "warfarin",
            "drugbank_id": "DB00682",
            "interactions": [
                {
                    "interacting_drug": "Aspirin",
                    "drugbank_id": "DB00945",
                    "description": "Increased risk of bleeding when combined",
                    "severity": "Major"
                },
                ...
            ],
            "count": 48,
            "interaction_checker_url": "https://go.drugbank.com/drug-interaction-checker",
            "success": True,
            "error": None
        }
    """
    try:
        # First search for the drug
        search_result = search_drugbank_drug(drug_name)

        if not search_result['success'] or search_result['count'] == 0:
            return {
                'drug_name': drug_name,
                'drugbank_id': 'Unknown',
                'interactions': [],
                'count': 0,
                'success': False,
                'error': 'Drug not found in DrugBank'
            }

        # Get the first matching drug
        drug_data = search_result['results'][0]
        drug_url = drug_data['url']
        drugbank_id = drug_data['drugbank_id']

        response, debug_info = make_request(drug_url)
        if not response:
            return {
                'drug_name': drug_name,
                'drugbank_id': drugbank_id,
                'interactions': [],
                'count': 0,
                'success': False,
                'error': 'Failed to retrieve interaction information',
                'debug_info': debug_info
            }

        soup = BeautifulSoup(response.content, 'html.parser')
        interactions_list = []

        # Look for interactions section
        interaction_section = None
        headings = soup.find_all(['h2', 'h3', 'h4', 'dt'])
        for heading in headings:
            heading_text = heading.get_text(strip=True).lower()
            if 'interaction' in heading_text and 'drug' in heading_text:
                interaction_section = heading
                break

        if interaction_section:
            # Extract interaction entries
            # Check if it's a dt element
            if interaction_section.name == 'dt':
                dd = interaction_section.find_next_sibling('dd')
                if dd:
                    # Look for links to other drugs
                    interaction_links = dd.find_all('a', href=lambda x: x and '/drugs/' in x)
                    for int_link in interaction_links[:50]:  # Limit to 50 interactions
                        int_drug_name = int_link.get_text(strip=True)
                        int_href = int_link.get('href', '')
                        int_drugbank_id = int_href.split('/drugs/')[-1].split('/')[0].split('?')[0]

                        if int_drugbank_id.startswith('DB'):
                            # Get description from surrounding text
                            parent = int_link.find_parent(['li', 'p', 'div'])
                            description = ''
                            if parent:
                                text = parent.get_text(separator=' ', strip=True)
                                if len(text) < 500:
                                    description = text

                            interactions_list.append({
                                'interacting_drug': int_drug_name,
                                'drugbank_id': int_drugbank_id,
                                'description': description if description else 'Drug-drug interaction exists',
                                'severity': 'See details'
                            })
            else:
                # Standard heading - look for following content
                for sibling in interaction_section.find_next_siblings():
                    if sibling.name in ['h2', 'h3']:
                        break

                    # Look for drug names in lists or tables
                    if sibling.name in ['ul', 'ol', 'table']:
                        interaction_links = sibling.find_all('a', href=lambda x: x and '/drugs/' in x)
                        for int_link in interaction_links[:50]:
                            int_drug_name = int_link.get_text(strip=True)
                            int_href = int_link.get('href', '')
                            int_drugbank_id = int_href.split('/drugs/')[-1].split('/')[0].split('?')[0]

                            if int_drugbank_id.startswith('DB') and len(int_drugbank_id) == 7:
                                # Get description
                                parent = int_link.find_parent(['li', 'td', 'tr'])
                                description = ''
                                if parent:
                                    text = parent.get_text(separator=' ', strip=True)
                                    if len(text) < 500:
                                        description = text

                                # Avoid duplicates
                                if not any(i['drugbank_id'] == int_drugbank_id for i in interactions_list):
                                    interactions_list.append({
                                        'interacting_drug': int_drug_name,
                                        'drugbank_id': int_drugbank_id,
                                        'description': description if description else 'Drug-drug interaction exists',
                                        'severity': 'See details'
                                    })

        return {
            'drug_name': drug_name,
            'drugbank_id': drugbank_id,
            'interactions': interactions_list,
            'count': len(interactions_list),
            'interaction_checker_url': f"{BASE_URL}/drug-interaction-checker",
            'success': True,
            'error': None if interactions_list else 'No interaction information found on drug page',
            'debug_info': debug_info
        }

    except Exception as e:
        return {
            'drug_name': drug_name,
            'drugbank_id': 'Unknown',
            'interactions': [],
            'count': 0,
            'success': False,
            'error': f'Error retrieving interactions: {str(e)}'
        }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
