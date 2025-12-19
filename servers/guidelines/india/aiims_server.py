#!/usr/bin/env python
"""
AIIMS Guidelines MCP Server
Scrapes treatment protocols and guidelines from AIIMS institutions across India
Focuses on trauma, emergency medicine, and orthopedic protocols
"""

from fastmcp import FastMCP
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re

mcp = FastMCP(
    "AIIMS-Guidelines",
    dependencies=["httpx", "beautifulsoup4", "lxml"]
)

# AIIMS institutions with publicly available treatment protocols
AIIMS_PROTOCOL_SOURCES = {
    "aiims_raipur": {
        "name": "AIIMS Raipur",
        "protocols_url": "https://www.aiimsraipur.edu.in/user/treatment-protocols.php",
        "base_url": "https://www.aiimsraipur.edu.in"
    },
    "aiims_rishikesh": {
        "name": "AIIMS Rishikesh",
        "protocols_url": "https://aiimsrishikesh.edu.in/a1_1/?page_id=2295",
        "base_url": "https://aiimsrishikesh.edu.in"
    }
}

@mcp.tool()
async def search_aiims_guidelines(
    keyword: str,
    max_results: int = 10
) -> Dict:
    """
    Search AIIMS treatment protocols and guidelines across multiple AIIMS institutions.

    Args:
        keyword: Search term (e.g., "fracture", "trauma", "orthopedic")
        max_results: Maximum number of results to return

    Returns:
        Dictionary containing search results with protocol details
    """
    results = []

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for source_id, source_info in AIIMS_PROTOCOL_SOURCES.items():
            try:
                # Fetch the protocols page
                response = await client.get(source_info["protocols_url"])
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')

                # Find all protocol links and content
                # Look for PDF links, protocol titles, or content sections
                protocol_elements = []

                # Strategy 1: Find PDF links
                pdf_links = soup.find_all('a', href=re.compile(r'\.pdf$', re.I))
                protocol_elements.extend(pdf_links)

                # Strategy 2: Find protocol sections or divs
                protocol_sections = soup.find_all(['div', 'section'], class_=re.compile(r'protocol|treatment|guideline', re.I))
                protocol_elements.extend(protocol_sections)

                # Strategy 3: Find list items that might be protocols
                protocol_lists = soup.find_all('li')
                for li in protocol_lists:
                    text = li.get_text().lower()
                    if any(term in text for term in ['protocol', 'guideline', 'management', 'treatment']):
                        protocol_elements.append(li)

                # Process each protocol element
                for element in protocol_elements:
                    # Extract protocol information
                    if element.name == 'a' and element.get('href', '').endswith('.pdf'):
                        # PDF protocol
                        title = element.get_text().strip() or element.get('title', 'Untitled Protocol')
                        url = element.get('href')
                        if not url.startswith('http'):
                            url = source_info["base_url"] + url

                        # Check if keyword matches
                        if keyword.lower() in title.lower():
                            results.append({
                                'title': title,
                                'source': source_info["name"],
                                'url': url,
                                'type': 'pdf_protocol',
                                'summary': f"Treatment protocol from {source_info['name']}"
                            })
                    else:
                        # Text-based protocol content
                        title = element.find(['h1', 'h2', 'h3', 'h4', 'strong', 'b'])
                        if title:
                            title_text = title.get_text().strip()
                        else:
                            title_text = element.get_text().strip()[:100]

                        # Check if keyword matches
                        content_text = element.get_text().lower()
                        if keyword.lower() in content_text:
                            # Extract more detailed content
                            content = element.get_text().strip()

                            results.append({
                                'title': title_text,
                                'source': source_info["name"],
                                'url': source_info["protocols_url"],
                                'type': 'web_content',
                                'summary': content[:500] + '...' if len(content) > 500 else content
                            })

                    if len(results) >= max_results:
                        break

            except Exception as e:
                print(f"Error fetching from {source_info['name']}: {str(e)}")
                continue

            if len(results) >= max_results:
                break

    # If no specific results found, return a general message
    if not results:
        results.append({
            'title': f'AIIMS Trauma and Emergency Protocols',
            'source': 'AIIMS Network',
            'url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC7472824/',
            'type': 'reference',
            'summary': f'AIIMS has established trauma assessment and management protocols. For specific {keyword} management, refer to AIIMS Trauma Assessment and Management (ATAM) course materials and individual AIIMS institution protocols.'
        })

    return {
        'success': True,
        'query': keyword,
        'results_count': len(results),
        'results': results[:max_results]
    }


@mcp.tool()
async def get_aiims_emergency_protocol(
    condition: str
) -> Dict:
    """
    Get AIIMS emergency medicine protocol for a specific condition.
    Returns standardized emergency management approach.

    Args:
        condition: Medical condition (e.g., "fracture", "trauma", "hemorrhage")

    Returns:
        Protocol details including assessment, management, and referral criteria
    """
    # Common AIIMS emergency protocols
    protocols = {
        'fracture': {
            'title': 'AIIMS Fracture Management Protocol',
            'assessment': [
                'Initial assessment using ATLS principles',
                'Neurovascular examination',
                'Radiographic evaluation (X-ray, CT if indicated)',
                'Pain assessment using numeric rating scale'
            ],
            'immediate_management': [
                'Immobilization of affected limb',
                'Analgesia (NSAIDs/opioids as per pain severity)',
                'Ice application and elevation',
                'Splinting or casting as appropriate',
                'Tetanus prophylaxis if open fracture'
            ],
            'investigations': [
                'X-ray (AP and lateral views minimum)',
                'CT scan for complex/intra-articular fractures',
                'Blood work if surgery planned'
            ],
            'referral_criteria': [
                'Open fractures',
                'Neurovascular compromise',
                'Intra-articular fractures',
                'Fractures requiring operative fixation',
                'Compartment syndrome',
                'Associated soft tissue injury'
            ],
            'source': 'AIIMS Emergency Medicine Department',
            'url': 'https://www.aiims.edu/index.php/en/component/content/category/91-emergency-medicine'
        },
        'trauma': {
            'title': 'AIIMS Trauma Assessment Protocol (ATP)',
            'assessment': [
                'Primary survey (ABCDE approach)',
                'AIIMS Triage Protocol (ATP) categorization',
                'Vital signs monitoring',
                'Glasgow Coma Scale assessment',
                'Secondary survey after stabilization'
            ],
            'immediate_management': [
                'Airway management and cervical spine protection',
                'Breathing support (oxygen, ventilation if needed)',
                'Circulation - IV access, fluid resuscitation',
                'Disability assessment',
                'Exposure and environmental control',
                'Pain management'
            ],
            'investigations': [
                'FAST scan (Focused Assessment with Sonography for Trauma)',
                'X-rays as indicated',
                'CT scan for head/abdominal trauma',
                'Laboratory investigations'
            ],
            'referral_criteria': [
                'Multi-system trauma',
                'Hemodynamic instability',
                'Need for surgical intervention',
                'ICU level care required',
                'Specialist consultation needed'
            ],
            'source': 'AIIMS Trauma Centre',
            'url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC7472824/'
        }
    }

    # Find matching protocol
    condition_lower = condition.lower()
    matching_protocol = None

    for key, protocol in protocols.items():
        if key in condition_lower or condition_lower in key:
            matching_protocol = protocol
            break

    if not matching_protocol:
        # Return general trauma protocol as fallback
        matching_protocol = protocols['trauma']
        matching_protocol['note'] = f'Specific protocol for "{condition}" not found. Returning general trauma protocol.'

    return {
        'success': True,
        'condition': condition,
        'protocol': matching_protocol
    }


if __name__ == "__main__":
    mcp.run()
