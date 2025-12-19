#!/usr/bin/env python
"""
MCP Server for MIMS India drug information.

Provides tools to search for drugs and medications in the Indian market,
retrieve detailed drug information including indications, dosages, contraindications,
and check drug interactions. Uses web scraping to access MIMS India (https://www.mims.com/india/).
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
    from mims_cache import get_cache
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
    "MIMS_India",
    instructions="MIMS India drug information service providing medication details for the Indian market, including indications, dosages, contraindications, interactions, and drug searches"
)

# Base URL for MIMS India website
BASE_URL = "https://www.mims.com/india"

# Headers to mimic a real browser and avoid 403 errors
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-IN,en;q=0.5',
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

print("🔄 MIMS India server using Bright Data residential proxy", file=sys.stderr)
print(f"   Proxy host: {BRIGHT_DATA_PROXY['host']}:{BRIGHT_DATA_PROXY['port']}", file=sys.stderr)
print("   Requests will route through residential IPs to bypass Cloudflare", file=sys.stderr)

# Check for MIMS credentials in environment variables
MIMS_USERNAME = os.environ.get('MIMS_USERNAME')
MIMS_PASSWORD = os.environ.get('MIMS_PASSWORD')

if MIMS_USERNAME and MIMS_PASSWORD:
    print("✅ MIMS credentials found in environment variables", file=sys.stderr)
else:
    print("⚠️  MIMS credentials not found (set MIMS_USERNAME and MIMS_PASSWORD)", file=sys.stderr)
    print("   Server will work with publicly available content only", file=sys.stderr)

# Initialize cache
cache = get_cache()


def login_to_mims() -> bool:
    """
    Attempt to log in to MIMS India if credentials are available.

    Returns:
        True if login successful or no credentials provided (public mode)
        False if login failed
    """
    if not MIMS_USERNAME or not MIMS_PASSWORD:
        return True  # Public mode

    try:
        login_url = f"{BASE_URL}/login"
        print(f"🔐 Attempting MIMS login...", file=sys.stderr)

        # Get login page to extract CSRF token if needed
        response = session.get(login_url, timeout=30, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract CSRF token if present
        csrf_token = None
        csrf_input = soup.find('input', {'name': '_token'}) or soup.find('input', {'name': 'csrf_token'})
        if csrf_input:
            csrf_token = csrf_input.get('value')

        # Prepare login payload
        login_data = {
            'username': MIMS_USERNAME,
            'password': MIMS_PASSWORD,
        }
        if csrf_token:
            login_data['_token'] = csrf_token

        # Submit login
        response = session.post(login_url, data=login_data, timeout=30, verify=False)

        # Check if login successful (look for redirect or success indicator)
        if response.status_code == 200 and ('logout' in response.text.lower() or 'sign out' in response.text.lower()):
            print("✅ MIMS login successful", file=sys.stderr)
            return True
        else:
            print("⚠️  MIMS login may have failed, continuing in public mode", file=sys.stderr)
            return True  # Continue anyway

    except Exception as e:
        print(f"⚠️  MIMS login error: {str(e)}, continuing in public mode", file=sys.stderr)
        return True  # Continue anyway


# Attempt login on server start
login_to_mims()


def make_request(url: str, timeout: int = 15) -> tuple[Optional[requests.Response], Dict[str, Any]]:
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
    name="search_mims_drugs",
    description="Search for drugs/medications by name in MIMS India and return matching results with links"
)
def search_mims_drugs(drug_name: str) -> Dict[str, Any]:
    """
    Search for a drug or medication by name in MIMS India.

    This tool searches the MIMS India database for drugs matching the provided name.
    It returns a list of matching medications with their URLs for further detailed lookup.

    Args:
        drug_name: The name of the drug to search for (e.g., "paracetamol", "metformin", "amoxicillin")

    Returns:
        Dictionary containing:
            - query (str): The search term used
            - results (list): List of matching drugs, each with:
                - name (str): Drug name
                - url (str): Full URL to the drug's MIMS page
                - type (str): Type of entry (e.g., "Drug", "Generic")
                - strength (str|None): Drug strength if available
            - count (int): Number of results found
            - success (bool): Whether the search was successful
            - error (str|None): Error message if search failed, None otherwise

    Example:
        >>> search_mims_drugs("paracetamol")
        {
            "query": "paracetamol",
            "results": [
                {
                    "name": "Paracetamol",
                    "url": "https://www.mims.com/india/drug/info/paracetamol",
                    "type": "Generic",
                    "strength": "500mg"
                }
            ],
            "count": 1,
            "success": True,
            "error": None
        }
    """
    print(f"🔍 Searching MIMS India for drug: {drug_name}", file=sys.stderr)

    # Check cache first
    cache_key = f"mims_search_{drug_name.lower()}"
    if cache.enabled:
        cached_result = cache.get(cache_key)
        if cached_result:
            print(f"📦 Cache hit for MIMS search: {drug_name}", file=sys.stderr)
            return cached_result

    # Construct search URL - correct MIMS India URL pattern
    search_url = f"{BASE_URL}/drug/search?q={quote(drug_name)}"

    # Make request
    response, debug_info = make_request(search_url)

    if response is None:
        error_result = {
            "query": drug_name,
            "results": [],
            "count": 0,
            "success": False,
            "error": debug_info.get("error_message", "Unknown error"),
            "debug_info": debug_info
        }
        return error_result

    # Parse HTML
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []

        # MIMS India structure: Find all links with /drug/info/ in href
        drug_links = soup.find_all('a', href=lambda x: x and '/drug/info/' in x if x else False)

        # Deduplicate by URL
        seen_urls = set()

        for link in drug_links:
            try:
                drug_url = link.get('href', '')
                if not drug_url or drug_url in seen_urls:
                    continue

                seen_urls.add(drug_url)

                # Build full URL
                if not drug_url.startswith('http'):
                    drug_url = urljoin(BASE_URL, drug_url)

                # Extract drug name from link text
                drug_name_text = link.get_text(strip=True)
                if not drug_name_text:
                    continue

                # Determine type based on URL parameters
                drug_type = "Generic" if "mtype=generic" in drug_url else "Drug"

                # Look for strength info near the link (in parent or siblings)
                strength = None
                parent = link.parent
                if parent:
                    # Check for strength in parent's text
                    parent_text = parent.get_text()
                    # Simple pattern matching for common strength formats
                    import re
                    strength_match = re.search(r'(\d+\s*(?:mg|g|ml|mcg|%))', parent_text, re.IGNORECASE)
                    if strength_match:
                        strength = strength_match.group(1)

                results.append({
                    "name": drug_name_text,
                    "url": drug_url,
                    "type": drug_type,
                    "strength": strength
                })

                # Limit results
                if len(results) >= 10:
                    break

            except Exception as e:
                print(f"⚠️  Error parsing search result item: {str(e)}", file=sys.stderr)
                continue

        result_data = {
            "query": drug_name,
            "results": results,
            "count": len(results),
            "success": True,
            "error": None
        }

        # Cache the result
        if cache.enabled and results:
            cache.set(cache_key, result_data, ttl=86400)  # Cache for 24 hours

        print(f"✅ Found {len(results)} MIMS search results for: {drug_name}", file=sys.stderr)
        return result_data

    except Exception as e:
        print(f"❌ Error parsing MIMS search results: {str(e)}", file=sys.stderr)
        return {
            "query": drug_name,
            "results": [],
            "count": 0,
            "success": False,
            "error": f"Parsing error: {str(e)}"
        }


@mcp.tool(
    name="get_mims_drug_details",
    description="Get detailed information about a specific drug from MIMS India including indications, dosage, contraindications, and side effects"
)
def get_mims_drug_details(drug_url: str) -> Dict[str, Any]:
    """
    Retrieve detailed information about a drug from its MIMS India page.

    Args:
        drug_url: The full URL to the drug's MIMS page (from search_mims_drugs results)

    Returns:
        Dictionary containing:
            - drug_name (str): Name of the drug
            - generic_name (str|None): Generic/scientific name
            - indications (str): What the drug is used for
            - dosage (str): Dosage information
            - contraindications (str): When not to use the drug
            - side_effects (str): Possible side effects
            - interactions (str): Drug interactions
            - pregnancy_category (str|None): Pregnancy safety category
            - manufacturer (str|None): Drug manufacturer
            - url (str): The MIMS page URL
            - success (bool): Whether retrieval was successful
            - error (str|None): Error message if failed
    """
    print(f"📄 Fetching MIMS drug details from: {drug_url}", file=sys.stderr)

    # Check cache first
    cache_key = f"mims_details_{drug_url}"
    if cache.enabled:
        cached_result = cache.get(cache_key)
        if cached_result:
            print(f"📦 Cache hit for MIMS drug details", file=sys.stderr)
            return cached_result

    # Make request
    response, debug_info = make_request(drug_url)

    if response is None:
        return {
            "drug_name": "Unknown",
            "url": drug_url,
            "success": False,
            "error": debug_info.get("error_message", "Unknown error"),
            "debug_info": debug_info
        }

    # Parse HTML
    try:
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract drug name
        drug_name = "Unknown"
        title_elem = soup.find('h1') or soup.find('h2', class_='drug-name')
        if title_elem:
            drug_name = title_elem.get_text(strip=True)

        # Extract generic name
        generic_name = None
        generic_elem = soup.find('span', class_='generic-name') or soup.find('div', class_='generic')
        if generic_elem:
            generic_name = generic_elem.get_text(strip=True)

        # Helper function to extract section content
        def extract_section(section_name: str) -> str:
            """Extract content from a section by looking for headers with the section name."""
            section_content = ""

            # Try different header tags
            for header_tag in ['h2', 'h3', 'h4', 'strong', 'b']:
                headers = soup.find_all(header_tag)
                for header in headers:
                    if section_name.lower() in header.get_text().lower():
                        # Get content after this header
                        content_parts = []
                        next_elem = header.find_next_sibling()

                        while next_elem:
                            if next_elem.name in ['h2', 'h3', 'h4']:
                                break  # Stop at next section

                            text = next_elem.get_text(strip=True)
                            if text:
                                content_parts.append(text)

                            next_elem = next_elem.find_next_sibling()

                        if content_parts:
                            section_content = " ".join(content_parts)
                            break

                if section_content:
                    break

            return section_content or "Not specified"

        # Extract main sections
        indications = extract_section("indications") or extract_section("uses")
        dosage = extract_section("dosage") or extract_section("dose")
        contraindications = extract_section("contraindications") or extract_section("contraindicated")
        side_effects = extract_section("side effects") or extract_section("adverse")
        interactions = extract_section("interactions") or extract_section("drug interactions")

        # Extract pregnancy category
        pregnancy_category = None
        preg_elem = soup.find('span', class_='pregnancy') or soup.find('div', class_='pregnancy-category')
        if preg_elem:
            pregnancy_category = preg_elem.get_text(strip=True)

        # Extract manufacturer
        manufacturer = None
        mfr_elem = soup.find('span', class_='manufacturer') or soup.find('div', class_='company')
        if mfr_elem:
            manufacturer = mfr_elem.get_text(strip=True)

        result_data = {
            "drug_name": drug_name,
            "generic_name": generic_name,
            "indications": indications,
            "dosage": dosage,
            "contraindications": contraindications,
            "side_effects": side_effects,
            "interactions": interactions,
            "pregnancy_category": pregnancy_category,
            "manufacturer": manufacturer,
            "url": drug_url,
            "success": True,
            "error": None
        }

        # Cache the result
        if cache.enabled:
            cache.set(cache_key, result_data, ttl=604800)  # Cache for 7 days

        print(f"✅ Successfully retrieved MIMS drug details for: {drug_name}", file=sys.stderr)
        return result_data

    except Exception as e:
        print(f"❌ Error parsing MIMS drug details: {str(e)}", file=sys.stderr)
        return {
            "drug_name": "Unknown",
            "url": drug_url,
            "success": False,
            "error": f"Parsing error: {str(e)}"
        }


@mcp.tool(
    name="check_mims_interactions",
    description="Check drug interactions between multiple medications using MIMS India"
)
def check_mims_interactions(drug_names: List[str]) -> Dict[str, Any]:
    """
    Check for interactions between multiple drugs using MIMS India.

    Args:
        drug_names: List of drug names to check for interactions (e.g., ["aspirin", "warfarin"])

    Returns:
        Dictionary containing:
            - drugs (list): List of drugs being checked
            - interactions (list): List of interactions found, each with:
                - drug1 (str): First drug name
                - drug2 (str): Second drug name
                - severity (str): Interaction severity (e.g., "Major", "Moderate", "Minor")
                - description (str): Description of the interaction
            - count (int): Number of interactions found
            - success (bool): Whether the check was successful
            - error (str|None): Error message if failed
    """
    print(f"🔬 Checking MIMS drug interactions for: {', '.join(drug_names)}", file=sys.stderr)

    # Check cache first
    cache_key = f"mims_interactions_{'_'.join(sorted([d.lower() for d in drug_names]))}"
    if cache.enabled:
        cached_result = cache.get(cache_key)
        if cached_result:
            print(f"📦 Cache hit for MIMS interactions check", file=sys.stderr)
            return cached_result

    # Construct interactions URL
    # MIMS may have a specific interactions checker - adjust URL as needed
    drug_params = "&".join([f"drug[]={quote(drug)}" for drug in drug_names])
    interactions_url = f"{BASE_URL}/interactions?{drug_params}"

    # Make request
    response, debug_info = make_request(interactions_url)

    if response is None:
        return {
            "drugs": drug_names,
            "interactions": [],
            "count": 0,
            "success": False,
            "error": debug_info.get("error_message", "Unknown error"),
            "debug_info": debug_info
        }

    # Parse HTML
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        interactions = []

        # Find interaction results
        # This structure will need adjustment based on actual MIMS HTML
        interaction_items = soup.find_all('div', class_='interaction') or soup.find_all('li', class_='interaction-item')

        for item in interaction_items:
            try:
                # Extract drug pair
                drugs_elem = item.find('div', class_='drug-pair') or item.find('h4')
                if not drugs_elem:
                    continue

                drugs_text = drugs_elem.get_text(strip=True)

                # Extract severity
                severity = "Unknown"
                severity_elem = item.find('span', class_='severity') or item.find('div', class_='level')
                if severity_elem:
                    severity = severity_elem.get_text(strip=True)

                # Extract description
                description = ""
                desc_elem = item.find('p', class_='description') or item.find('div', class_='detail')
                if desc_elem:
                    description = desc_elem.get_text(strip=True)

                # Parse drug pair from text
                drug1, drug2 = drug_names[0], drug_names[1] if len(drug_names) > 1 else "Unknown"
                if " and " in drugs_text.lower():
                    parts = drugs_text.split(" and ", 1)
                    drug1, drug2 = parts[0].strip(), parts[1].strip()

                interactions.append({
                    "drug1": drug1,
                    "drug2": drug2,
                    "severity": severity,
                    "description": description
                })

            except Exception as e:
                print(f"⚠️  Error parsing interaction item: {str(e)}", file=sys.stderr)
                continue

        result_data = {
            "drugs": drug_names,
            "interactions": interactions,
            "count": len(interactions),
            "success": True,
            "error": None
        }

        # Cache the result
        if cache.enabled:
            cache.set(cache_key, result_data, ttl=86400)  # Cache for 24 hours

        print(f"✅ Found {len(interactions)} MIMS interactions", file=sys.stderr)
        return result_data

    except Exception as e:
        print(f"❌ Error parsing MIMS interactions: {str(e)}", file=sys.stderr)
        return {
            "drugs": drug_names,
            "interactions": [],
            "count": 0,
            "success": False,
            "error": f"Parsing error: {str(e)}"
        }
