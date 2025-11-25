#!/usr/bin/env python
"""
NHSRC Standard Treatment Guidelines MCP Server

This MCP server provides tools to search and access India's Standard Treatment
Guidelines (STG) from NHSRC (National Health Systems Resource Centre). These
are evidence-based treatment protocols organized by medical specialty for use
in Indian healthcare facilities, particularly for government health programs.

Uses web scraping to retrieve published guidelines from qps.nhsrcindia.org.
"""

import asyncio
import time
from typing import Any, Optional, List, Dict
from urllib.parse import quote, urljoin
import httpx
from bs4 import BeautifulSoup
import re
from datetime import datetime
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(
    "NHSRC-STG",
    instructions="""Search and retrieve India's Standard Treatment Guidelines (STG) from NHSRC
    with evidence-based treatment protocols organized by medical specialty. These guidelines
    are designed for Indian healthcare settings and cover common conditions across specialties
    like medicine, surgery, pediatrics, obstetrics, ophthalmology, etc. Widely used in
    government healthcare facilities across India."""
)

# NHSRC STG URLs
BASE_URL = "https://qps.nhsrcindia.org"
STG_URL = f"{BASE_URL}/standard-treatment-guidelines"
TIMEOUT = 30.0
RATE_LIMIT_DELAY = 0.5  # 500ms delay between requests


async def fetch_page(url: str) -> Optional[str]:
    """
    Fetch a webpage and return its HTML content.

    Args:
        url: The URL to fetch

    Returns:
        HTML content as string or None if failed
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=TIMEOUT) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            await asyncio.sleep(RATE_LIMIT_DELAY)  # Rate limiting
            return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


@mcp.tool(
    name="search_stg_guidelines",
    description="Search India's Standard Treatment Guidelines by condition, specialty, or keyword. Returns matching guidelines with titles, specialties, and URLs for conditions like pneumonia, diabetes, hypertension, malaria, etc. across all medical specialties."
)
async def search_stg_guidelines(keyword: str, specialty: Optional[str] = None, max_results: int = 20) -> dict:
    """
    Search Standard Treatment Guidelines by keyword or topic.

    Args:
        keyword: Search term or condition to find guidelines (e.g., "pneumonia", "diabetes", "hypertension")
        specialty: Optional specialty filter (e.g., "medicine", "pediatrics", "surgery", "obstetrics")
        max_results: Maximum number of results to return (default: 20, max: 50)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - query (str): The search keyword used
            - specialty_filter (str|None): Specialty filter applied
            - count (int): Number of results found
            - results (list): List of matching guidelines with title, specialty, url, condition, document_type
            - error (str|None): Error message if search failed
    """
    max_results = min(max_results, 50)
    keyword_clean = " ".join(keyword.split())
    specialty_clean = " ".join(specialty.split()) if specialty else None

    results = []

    # Fetch the main STG page
    html = await fetch_page(STG_URL)
    if not html:
        return {
            'success': False,
            'query': keyword,
            'specialty_filter': specialty_clean,
            'count': 0,
            'results': [],
            'error': 'Failed to fetch NHSRC STG page'
        }

    soup = BeautifulSoup(html, 'html.parser')

    # Look for guideline links - typically organized by specialty
    # Find all links that might lead to guidelines
    guideline_links = soup.find_all('a', href=True)

    seen_urls = set()
    keyword_lower = keyword_clean.lower()
    specialty_lower = specialty_clean.lower() if specialty_clean else None

    for link in guideline_links:
        href = link.get('href', '')
        if not href:
            continue

        link_text = link.get_text(strip=True)

        # Skip navigation and footer links
        if len(link_text) < 5:
            continue

        # Build full URL
        full_url = urljoin(BASE_URL, href)

        # Skip duplicates
        if full_url in seen_urls:
            continue

        # Get parent context for additional information
        parent = link.find_parent(['li', 'tr', 'div', 'section', 'article'])
        context_text = parent.get_text(strip=True) if parent else link_text

        # Check if keyword matches
        keyword_match = keyword_lower in context_text.lower() or keyword_lower in link_text.lower()

        # Check specialty filter if provided
        specialty_match = True
        if specialty_lower:
            specialty_match = specialty_lower in context_text.lower()

        if keyword_match and specialty_match:
            seen_urls.add(full_url)

            # Try to determine specialty from context
            detected_specialty = 'General'
            specialty_keywords = {
                'medicine': ['medicine', 'internal medicine'],
                'pediatrics': ['pediatric', 'paediatric', 'child'],
                'surgery': ['surgery', 'surgical'],
                'obstetrics': ['obstetric', 'gynecology', 'gynaecology', 'maternal'],
                'ophthalmology': ['ophthal', 'eye'],
                'orthopedics': ['orthop', 'ortho', 'fracture'],
                'dermatology': ['dermat', 'skin'],
                'psychiatry': ['psychiatr', 'mental health'],
                'emergency': ['emergency', 'trauma', 'critical'],
                'ent': ['ent', 'ear', 'nose', 'throat']
            }

            for spec, keywords in specialty_keywords.items():
                if any(kw in context_text.lower() for kw in keywords):
                    detected_specialty = spec.title()
                    break

            # Determine document type
            doc_type = 'PDF' if href.lower().endswith('.pdf') else 'Web Page'

            results.append({
                'title': link_text[:200] if len(link_text) > 200 else link_text,
                'specialty': detected_specialty,
                'url': full_url,
                'condition': keyword_clean.title(),
                'document_type': doc_type
            })

            if len(results) >= max_results:
                break

    if not results:
        return {
            'success': True,
            'query': keyword,
            'specialty_filter': specialty_clean,
            'count': 0,
            'results': [],
            'error': 'No STG guidelines found matching the search criteria'
        }

    return {
        'success': True,
        'query': keyword,
        'specialty_filter': specialty_clean,
        'count': len(results),
        'results': results,
        'error': None
    }


@mcp.tool(
    name="get_stg_guideline",
    description="Get detailed content for a specific Standard Treatment Guideline by URL. Returns treatment protocols, diagnostic criteria, management steps, and drug recommendations."
)
async def get_stg_guideline(guideline_url: str) -> dict:
    """
    Get detailed information about a specific STG guideline.

    Args:
        guideline_url: Full URL to the guideline (PDF or web page)

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - title (str): Guideline title
            - url (str): Direct URL to the guideline
            - specialty (str): Medical specialty
            - content (str): Main treatment protocol content
            - diagnostic_criteria (str): Diagnostic criteria if available
            - management_steps (str): Management/treatment steps
            - medications (list): Key medications mentioned
            - document_type (str): Type of document (PDF or Web Page)
            - error (str|None): Error message if retrieval failed
    """
    if not guideline_url:
        return {
            'success': False,
            'title': '',
            'url': '',
            'specialty': '',
            'content': '',
            'diagnostic_criteria': '',
            'management_steps': '',
            'medications': [],
            'document_type': '',
            'error': 'No URL provided'
        }

    # Determine document type
    is_pdf = guideline_url.lower().endswith('.pdf')

    if is_pdf:
        # For PDFs, return metadata
        return {
            'success': True,
            'title': guideline_url.split('/')[-1].replace('.pdf', '').replace('_', ' ').replace('-', ' ').title(),
            'url': guideline_url,
            'specialty': 'Unknown',
            'content': 'PDF document - download required for full content',
            'diagnostic_criteria': 'Please download the PDF to view diagnostic criteria',
            'management_steps': 'Please download the PDF to view management steps',
            'medications': [],
            'document_type': 'PDF',
            'error': None
        }

    # For web pages, fetch and parse content
    html = await fetch_page(guideline_url)
    if not html:
        return {
            'success': False,
            'title': '',
            'url': guideline_url,
            'specialty': '',
            'content': '',
            'diagnostic_criteria': '',
            'management_steps': '',
            'medications': [],
            'document_type': 'Web Page',
            'error': 'Failed to fetch guideline page'
        }

    soup = BeautifulSoup(html, 'html.parser')

    # Extract title
    title = ''
    title_elem = soup.find('h1')
    if title_elem:
        title = title_elem.get_text(strip=True)
    else:
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else 'STG Guideline'

    # Extract main content
    content = ''
    main_content = soup.find(['main', 'article', 'div'], class_=re.compile(r'content|main|guideline', re.I))
    if main_content:
        paragraphs = main_content.find_all('p', limit=10)
        content = ' '.join([p.get_text(strip=True) for p in paragraphs])

    if not content:
        paragraphs = soup.find_all('p', limit=10)
        content = ' '.join([p.get_text(strip=True) for p in paragraphs])

    # Extract diagnostic criteria
    diagnostic_criteria = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['diagnos', 'criteria', 'definition', 'clinical feature']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            diagnostic_criteria = ' '.join(content_parts)
            if diagnostic_criteria:
                break

    # Extract management steps
    management_steps = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['management', 'treatment', 'protocol', 'therapy']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            management_steps = ' '.join(content_parts)
            if management_steps:
                break

    # Extract medications mentioned
    medications = []
    full_text = soup.get_text()
    # Look for common drug name patterns (simplified)
    drug_patterns = re.findall(r'\b([A-Z][a-z]+(?:cin|ol|pine|pril|sartan|ide|one|ate|ine))\b', full_text)
    medications = list(set(drug_patterns))[:10]  # Unique drugs, max 10

    # Determine specialty
    specialty = 'General'
    specialty_keywords = {
        'Medicine': ['medicine', 'internal medicine'],
        'Pediatrics': ['pediatric', 'paediatric', 'child'],
        'Surgery': ['surgery', 'surgical'],
        'Obstetrics & Gynecology': ['obstetric', 'gynecology', 'maternal'],
        'Ophthalmology': ['ophthal', 'eye'],
        'Orthopedics': ['orthop', 'fracture']
    }

    for spec, keywords in specialty_keywords.items():
        if any(kw in title.lower() for kw in keywords):
            specialty = spec
            break

    return {
        'success': True,
        'title': title,
        'url': guideline_url,
        'specialty': specialty,
        'content': content[:1500] + '...' if len(content) > 1500 else content,
        'diagnostic_criteria': diagnostic_criteria[:1000] + '...' if len(diagnostic_criteria) > 1000 else diagnostic_criteria,
        'management_steps': management_steps[:1500] + '...' if len(management_steps) > 1500 else management_steps,
        'medications': medications,
        'document_type': 'Web Page',
        'error': None
    }


@mcp.tool(
    name="list_stg_specialties",
    description="List all available medical specialties covered by NHSRC Standard Treatment Guidelines. Returns specialty names, descriptions, and common conditions covered in each specialty."
)
async def list_stg_specialties() -> dict:
    """
    List available specialties in STG guidelines.

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - specialties (list): List of specialties with name, description, common_conditions, url
            - error (str|None): Error message if retrieval failed
    """
    specialties = [
        {
            'name': 'General Medicine',
            'description': 'Treatment protocols for common medical conditions',
            'common_conditions': ['Diabetes', 'Hypertension', 'Pneumonia', 'Tuberculosis', 'Malaria', 'Dengue', 'Typhoid'],
            'url': f"{STG_URL}"
        },
        {
            'name': 'Pediatrics',
            'description': 'Treatment guidelines for infants, children, and adolescents',
            'common_conditions': ['Acute respiratory infections', 'Diarrhea', 'Malnutrition', 'Sepsis', 'Asthma'],
            'url': f"{STG_URL}"
        },
        {
            'name': 'Obstetrics & Gynecology',
            'description': 'Protocols for maternal and reproductive health',
            'common_conditions': ['Antenatal care', 'Normal delivery', 'Postpartum care', 'Abortion complications', 'Eclampsia'],
            'url': f"{STG_URL}"
        },
        {
            'name': 'Surgery',
            'description': 'Guidelines for common surgical conditions and procedures',
            'common_conditions': ['Appendicitis', 'Hernia', 'Fractures', 'Wound management', 'Burns'],
            'url': f"{STG_URL}"
        },
        {
            'name': 'Ophthalmology',
            'description': 'Eye care treatment protocols',
            'common_conditions': ['Cataract', 'Glaucoma', 'Conjunctivitis', 'Corneal ulcer', 'Refractive errors'],
            'url': f"{STG_URL}"
        },
        {
            'name': 'ENT (Ear, Nose, Throat)',
            'description': 'Treatment guidelines for ENT conditions',
            'common_conditions': ['Otitis media', 'Sinusitis', 'Tonsillitis', 'Epistaxis', 'Foreign body'],
            'url': f"{STG_URL}"
        },
        {
            'name': 'Dermatology',
            'description': 'Skin condition management protocols',
            'common_conditions': ['Scabies', 'Fungal infections', 'Eczema', 'Leprosy', 'Urticaria'],
            'url': f"{STG_URL}"
        },
        {
            'name': 'Emergency Medicine',
            'description': 'Emergency and critical care protocols',
            'common_conditions': ['Trauma', 'Shock', 'Poisoning', 'Snake bite', 'Acute abdomen'],
            'url': f"{STG_URL}"
        },
        {
            'name': 'Orthopedics',
            'description': 'Musculoskeletal condition management',
            'common_conditions': ['Fractures', 'Dislocations', 'Arthritis', 'Back pain', 'Sports injuries'],
            'url': f"{STG_URL}"
        },
        {
            'name': 'Psychiatry',
            'description': 'Mental health treatment guidelines',
            'common_conditions': ['Depression', 'Anxiety', 'Schizophrenia', 'Bipolar disorder', 'Substance abuse'],
            'url': f"{STG_URL}"
        }
    ]

    return {
        'success': True,
        'specialties': specialties,
        'error': None
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
