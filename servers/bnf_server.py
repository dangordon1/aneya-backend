#!/usr/bin/env python
"""
MCP Server for British National Formulary (BNF) information.

Provides tools to search for drugs and medications, retrieve detailed drug information
including indications, dosages, contraindications, and search by medical conditions.
Uses web scraping to access the BNF website (https://bnf.nice.org.uk/).
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
    from bnf_cache import get_cache
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

print("🔄 BNF server using Bright Data residential proxy", file=sys.stderr)
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
    name="search_bnf_drug",
    description="Search for drugs/medications by name in the British National Formulary and return matching results with links"
)
def search_bnf_drug(drug_name: str) -> Dict[str, Any]:
    """
    Search for a drug or medication by name in the BNF.

    This tool searches the British National Formulary database for drugs matching
    the provided name. It returns a list of matching medications with their URLs
    for further detailed lookup.

    Args:
        drug_name: The name of the drug to search for (e.g., "paracetamol", "aspirin", "amoxicillin")

    Returns:
        Dictionary containing:
            - query (str): The search term used
            - results (list): List of matching drugs, each with:
                - name (str): Drug name
                - url (str): Full URL to the drug's BNF page
                - type (str): Type of entry (e.g., "Drug", "Drug class")
            - count (int): Number of results found
            - success (bool): Whether the search was successful
            - error (str|None): Error message if search failed, None otherwise

    Example:
        >>> search_bnf_drug("paracetamol")
        {
            "query": "paracetamol",
            "results": [
                {
                    "name": "Paracetamol",
                    "url": "https://bnf.nice.org.uk/drugs/paracetamol/",
                    "type": "Drug"
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
        # Try direct drug URL first (most common case)
        drug_slug = drug_name.lower().replace(' ', '-')
        direct_url = f"{BASE_URL}/drugs/{drug_slug}/"

        response, debug_info = make_request(direct_url)
        if response and response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            title = soup.find('h1')
            if title and '404' not in title.get_text() and 'not found' not in title.get_text().lower():
                # Found a direct match
                result = {
                    'query': drug_name,
                    'results': [{
                        'name': title.get_text(strip=True),
                        'url': direct_url,
                        'type': 'Drug'
                    }],
                    'count': 1,
                    'success': True,
                    'error': None,
                    'debug_info': debug_info
                }
                # Cache the result
                cache.set('search_drug', drug_name, result)
                return result

        # If direct match didn't work, try search
        search_url = f"{BASE_URL}/search/?q={quote(drug_name)}"

        response, search_debug_info = make_request(search_url)
        if not response:
            return {
                'query': drug_name,
                'results': [],
                'count': 0,
                'success': False,
                'error': 'Failed to connect to BNF website',
                'debug_info': search_debug_info
            }

        soup = BeautifulSoup(response.content, 'html.parser')
        results = []

        # Look for search result links (more specific than generic drug navigation)
        # Search results are usually in a specific container
        search_results = soup.find_all('li', class_=lambda x: x and ('result' in x.lower() or 'search' in x.lower()))

        if not search_results:
            # Fallback: look for all links but filter more carefully
            drug_links = soup.find_all('a', href=True)

            for link in drug_links:
                href = link.get('href', '')
                # More specific filtering: must have /drugs/ followed by a specific drug name
                if '/drugs/' in href and href.count('/') >= 4:  # e.g., /drugs/drugname/
                    drug_name_text = link.get_text(strip=True)
                    # Skip navigation links
                    if (drug_name_text and len(drug_name_text) > 1 and
                        drug_name_text.lower() != 'drugs' and
                        'a to z' not in drug_name_text.lower() and
                        len(drug_name_text) < 50):  # Drug names shouldn't be too long

                        full_url = urljoin(BASE_URL, href)

                        # Avoid duplicates and navigation URLs
                        if (not any(r['url'] == full_url for r in results) and
                            not full_url.endswith('/drugs/') and
                            not full_url.endswith('/drugs')):
                            results.append({
                                'name': drug_name_text,
                                'url': full_url,
                                'type': 'Drug'
                            })
        else:
            # Extract from search result containers
            for result_li in search_results:
                link = result_li.find('a', href=True)
                if link and '/drugs/' in link.get('href', ''):
                    drug_name_text = link.get_text(strip=True)
                    href = link.get('href')
                    full_url = urljoin(BASE_URL, href)

                    results.append({
                        'name': drug_name_text,
                        'url': full_url,
                        'type': 'Drug'
                    })

        result = {
            'query': drug_name,
            'results': results[:10],  # Limit to top 10 results
            'count': len(results[:10]),
            'success': True,
            'error': None,
            'debug_info': search_debug_info
        }

        # Cache successful results
        if result['success']:
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
    name="get_bnf_drug_info",
    description="Get detailed information about a specific drug including indications, dosage, contraindications, side effects, and warnings"
)
def get_bnf_drug_info(drug_url: str) -> Dict[str, Any]:
    """
    Retrieve comprehensive information about a drug from its BNF page.

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
        response, debug_info = make_request(drug_url)
        if not response:
            return {
                'drug_name': 'Unknown',
                'url': drug_url,
                'success': False,
                'error': 'Failed to connect to BNF website'
            }

        soup = BeautifulSoup(response.content, 'html.parser')

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
