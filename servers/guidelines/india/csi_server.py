#!/usr/bin/env python
"""
CSI Guidelines MCP Server

This MCP server provides tools to search and access CSI (Cardiological Society of
India) clinical guidelines. CSI is India's premier cardiac care organization
providing evidence-based guidelines for cardiovascular disease management with
specific recommendations for the Indian population and healthcare system.

Uses web scraping to retrieve published guidelines from www.csi.org.in.
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
    "CSI-Guidelines",
    instructions="""Search and retrieve Cardiological Society of India (CSI) clinical guidelines
    with comprehensive cardiovascular disease management protocols specific to Indian patients.
    Covers coronary artery disease, heart failure, arrhythmias, valvular heart disease,
    hypertension, dyslipidemia, acute coronary syndromes, interventional cardiology, and
    preventive cardiology tailored for the Indian healthcare context."""
)

# CSI URLs
BASE_URL = "https://www.csi.org.in"
GUIDELINES_URL = f"{BASE_URL}/guidelines"
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
    name="search_cardiac_guidelines",
    description="Search CSI cardiac guidelines by condition or topic. Returns matching guidelines for coronary artery disease, heart failure, arrhythmias, hypertension, acute MI, valvular disease, preventive cardiology, interventional procedures, etc."
)
async def search_cardiac_guidelines(keyword: str, max_results: int = 20) -> dict:
    """
    Search CSI cardiac guidelines by keyword or topic.

    Args:
        keyword: Search term or condition (e.g., "heart failure", "atrial fibrillation", "STEMI", "hypertension")
        max_results: Maximum number of results to return (default: 20, max: 50)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - query (str): The search keyword used
            - count (int): Number of results found
            - results (list): List of matching guidelines with title, category, url, year, document_type
            - error (str|None): Error message if search failed
    """
    max_results = min(max_results, 50)
    keyword_clean = " ".join(keyword.split())

    results = []

    # Fetch the guidelines page
    html = await fetch_page(GUIDELINES_URL)
    if not html:
        return {
            'success': False,
            'query': keyword,
            'count': 0,
            'results': [],
            'error': 'Failed to fetch CSI guidelines page'
        }

    soup = BeautifulSoup(html, 'html.parser')

    # Look for guideline links
    guideline_links = soup.find_all('a', href=True)

    seen_urls = set()
    keyword_lower = keyword_clean.lower()

    for link in guideline_links:
        href = link.get('href', '')
        if not href:
            continue

        link_text = link.get_text(strip=True)

        # Skip short links
        if len(link_text) < 10:
            continue

        # Build full URL
        full_url = urljoin(BASE_URL, href)

        # Skip duplicates
        if full_url in seen_urls:
            continue

        # Get parent context
        parent = link.find_parent(['li', 'tr', 'div', 'p', 'section', 'article'])
        context_text = parent.get_text(strip=True) if parent else link_text

        # Check if keyword matches
        if keyword_lower in context_text.lower() or keyword_lower in link_text.lower():
            seen_urls.add(full_url)

            # Extract year
            year_match = re.search(r'\b(20\d{2})\b', context_text)
            year = year_match.group(1) if year_match else 'Not specified'

            # Determine category
            category = 'General Cardiology'
            category_keywords = {
                'Coronary Artery Disease': ['coronary', 'cad', 'ischemic', 'angina'],
                'Acute Coronary Syndrome': ['acs', 'stemi', 'nstemi', 'myocardial infarction', 'mi'],
                'Heart Failure': ['heart failure', 'hfref', 'hfpef', 'cardiac failure'],
                'Arrhythmias': ['arrhythmia', 'atrial fibrillation', 'af', 'ventricular tachycardia', 'vt'],
                'Hypertension': ['hypertension', 'blood pressure', 'bp'],
                'Valvular Heart Disease': ['valvular', 'mitral', 'aortic', 'valve'],
                'Interventional Cardiology': ['pci', 'angioplasty', 'stent', 'intervention'],
                'Preventive Cardiology': ['prevention', 'risk factor', 'lipid', 'cholesterol'],
                'Cardiac Imaging': ['echo', 'echocardiography', 'ct', 'mri', 'imaging'],
                'Electrophysiology': ['electrophysiology', 'ep', 'ablation', 'pacemaker', 'icd']
            }

            for cat_name, keywords in category_keywords.items():
                if any(kw in context_text.lower() for kw in keywords):
                    category = cat_name
                    break

            # Determine document type
            doc_type = 'PDF' if href.lower().endswith('.pdf') else 'Web Page'

            results.append({
                'title': link_text[:200] if len(link_text) > 200 else link_text,
                'category': category,
                'url': full_url,
                'year': year,
                'document_type': doc_type
            })

            if len(results) >= max_results:
                break

    if not results:
        return {
            'success': True,
            'query': keyword,
            'count': 0,
            'results': [],
            'error': 'No CSI cardiac guidelines found matching the search term'
        }

    return {
        'success': True,
        'query': keyword,
        'count': len(results),
        'results': results,
        'error': None
    }


@mcp.tool(
    name="get_guideline_content",
    description="Get detailed content for a specific CSI cardiac guideline by URL. Returns management protocols, diagnostic criteria, treatment algorithms, and medication recommendations for cardiovascular conditions in Indian patients."
)
async def get_guideline_content(guideline_url: str) -> dict:
    """
    Get detailed information about a specific CSI guideline.

    Args:
        guideline_url: Full URL to the guideline (PDF or web page)

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - title (str): Guideline title
            - url (str): Direct URL to the guideline
            - category (str): Cardiac category
            - content (str): Main guideline content/summary
            - diagnostic_approach (str): Diagnostic recommendations
            - treatment_protocol (str): Treatment recommendations
            - medications (str): Key medications and dosing
            - special_considerations (str): India-specific considerations
            - document_type (str): Type of document
            - error (str|None): Error message if retrieval failed
    """
    if not guideline_url:
        return {
            'success': False,
            'title': '',
            'url': '',
            'category': '',
            'content': '',
            'diagnostic_approach': '',
            'treatment_protocol': '',
            'medications': '',
            'special_considerations': '',
            'document_type': '',
            'error': 'No URL provided'
        }

    # Determine document type
    is_pdf = guideline_url.lower().endswith('.pdf')

    if is_pdf:
        # For PDFs, return metadata
        title = guideline_url.split('/')[-1].replace('.pdf', '').replace('_', ' ').replace('-', ' ').title()
        return {
            'success': True,
            'title': title,
            'url': guideline_url,
            'category': 'Cardiology',
            'content': 'PDF document - download required for full content. This CSI guideline contains India-specific cardiac care recommendations.',
            'diagnostic_approach': 'Please download the PDF to view diagnostic protocols',
            'treatment_protocol': 'Please download the PDF to view treatment protocols',
            'medications': 'Please download the PDF to view medication recommendations',
            'special_considerations': 'Indian population-specific recommendations available in PDF',
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
            'category': '',
            'content': '',
            'diagnostic_approach': '',
            'treatment_protocol': '',
            'medications': '',
            'special_considerations': '',
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
        title = title_tag.get_text(strip=True) if title_tag else 'CSI Guideline'

    # Extract main content
    content = ''
    main_content = soup.find(['main', 'article', 'div'], class_=re.compile(r'content|main|guideline', re.I))
    if main_content:
        paragraphs = main_content.find_all('p', limit=10)
        content = ' '.join([p.get_text(strip=True) for p in paragraphs])

    if not content:
        paragraphs = soup.find_all('p', limit=10)
        content = ' '.join([p.get_text(strip=True) for p in paragraphs])

    # Extract diagnostic approach
    diagnostic_approach = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['diagnos', 'investigation', 'evaluation', 'assessment']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            diagnostic_approach = ' '.join(content_parts)
            if diagnostic_approach:
                break

    # Extract treatment protocol
    treatment_protocol = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['treatment', 'management', 'therapy', 'protocol']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            treatment_protocol = ' '.join(content_parts)
            if treatment_protocol:
                break

    # Extract medication information
    medications = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['medication', 'drug', 'pharmacological', 'pharmacotherapy']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            medications = ' '.join(content_parts)
            if medications:
                break

    # Extract special considerations
    special_considerations = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['indian', 'special', 'consideration', 'local']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            special_considerations = ' '.join(content_parts)
            if special_considerations:
                break

    # Determine category
    category = 'General Cardiology'
    if 'coronary' in title.lower() or 'cad' in title.lower():
        category = 'Coronary Artery Disease'
    elif 'stemi' in title.lower() or 'nstemi' in title.lower() or 'acs' in title.lower():
        category = 'Acute Coronary Syndrome'
    elif 'heart failure' in title.lower():
        category = 'Heart Failure'
    elif 'arrhythmia' in title.lower() or 'fibrillation' in title.lower():
        category = 'Arrhythmias'
    elif 'hypertension' in title.lower():
        category = 'Hypertension'
    elif 'valve' in title.lower() or 'valvular' in title.lower():
        category = 'Valvular Heart Disease'

    return {
        'success': True,
        'title': title,
        'url': guideline_url,
        'category': category,
        'content': content[:1500] + '...' if len(content) > 1500 else content,
        'diagnostic_approach': diagnostic_approach[:1000] + '...' if len(diagnostic_approach) > 1000 else diagnostic_approach,
        'treatment_protocol': treatment_protocol[:1500] + '...' if len(treatment_protocol) > 1500 else treatment_protocol,
        'medications': medications[:1000] + '...' if len(medications) > 1000 else medications,
        'special_considerations': special_considerations[:800] + '...' if len(special_considerations) > 800 else special_considerations or 'India-specific recommendations included',
        'document_type': 'Web Page',
        'error': None
    }


@mcp.tool(
    name="list_cardiac_topics",
    description="List all cardiac topics covered by CSI guidelines including coronary disease, heart failure, arrhythmias, valvular disease, hypertension, preventive cardiology, interventional procedures, and more."
)
async def list_cardiac_topics() -> dict:
    """
    List available cardiac topics in CSI guidelines.

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - topics (list): List of cardiac topics with name, description, key_areas, url
            - error (str|None): Error message if retrieval failed
    """
    topics = [
        {
            'name': 'Coronary Artery Disease (CAD)',
            'description': 'Diagnosis and management of stable coronary artery disease',
            'key_areas': ['Risk stratification', 'Medical therapy', 'Revascularization', 'Secondary prevention'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Acute Coronary Syndrome (ACS)',
            'description': 'Management of STEMI, NSTEMI, and unstable angina',
            'key_areas': ['Early recognition', 'Reperfusion therapy', 'Antiplatelet therapy', 'Post-MI care'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Heart Failure',
            'description': 'Diagnosis and management of acute and chronic heart failure',
            'key_areas': ['HFrEF management', 'HFpEF management', 'Device therapy', 'Advanced heart failure'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Atrial Fibrillation',
            'description': 'Management of atrial fibrillation and flutter',
            'key_areas': ['Rate vs rhythm control', 'Anticoagulation', 'Catheter ablation', 'Stroke prevention'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Ventricular Arrhythmias',
            'description': 'Management of ventricular tachycardia and fibrillation',
            'key_areas': ['Risk stratification', 'ICD therapy', 'Antiarrhythmic drugs', 'Ablation'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Hypertension',
            'description': 'Diagnosis and treatment of high blood pressure',
            'key_areas': ['Blood pressure targets', 'First-line medications', 'Resistant hypertension', 'Hypertensive emergencies'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Dyslipidemia',
            'description': 'Management of cholesterol and triglycerides',
            'key_areas': ['LDL targets', 'Statin therapy', 'PCSK9 inhibitors', 'Familial hypercholesterolemia'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Valvular Heart Disease',
            'description': 'Management of heart valve disorders',
            'key_areas': ['Aortic stenosis', 'Mitral regurgitation', 'TAVR', 'Surgical indications'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Rheumatic Heart Disease',
            'description': 'Prevention and management of rheumatic heart disease',
            'key_areas': ['Primary prevention', 'Secondary prophylaxis', 'Valve intervention', 'Indian context'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Interventional Cardiology',
            'description': 'PCI and other interventional procedures',
            'key_areas': ['Stent selection', 'DAPT duration', 'Complex PCI', 'Radiation safety'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Preventive Cardiology',
            'description': 'Cardiovascular disease prevention strategies',
            'key_areas': ['Risk assessment', 'Lifestyle modification', 'Aspirin prophylaxis', 'Smoking cessation'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Cardiac Imaging',
            'description': 'Appropriate use of cardiac imaging modalities',
            'key_areas': ['Echocardiography', 'Cardiac CT', 'Cardiac MRI', 'Nuclear imaging'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Perioperative Cardiac Care',
            'description': 'Cardiac risk assessment for non-cardiac surgery',
            'key_areas': ['Risk stratification', 'Preoperative testing', 'Beta-blockers', 'Postoperative monitoring'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Cardiogenic Shock',
            'description': 'Management of cardiogenic shock',
            'key_areas': ['Hemodynamic support', 'Mechanical circulatory support', 'Revascularization', 'ICU care'],
            'url': GUIDELINES_URL
        }
    ]

    return {
        'success': True,
        'topics': topics,
        'error': None
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
