#!/usr/bin/env python
"""
NCG (National Cancer Grid) MCP Server

This MCP server provides tools to search and access NCG (National Cancer Grid)
India cancer management guidelines. NCG is a collaborative network of major
cancer centers across India providing evidence-based, consensus-driven cancer
care guidelines specific to Indian resources and patient populations.

Uses web scraping to retrieve published guidelines from www.ncgindia.org.
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
    "NCG-Guidelines",
    instructions="""Search and retrieve National Cancer Grid (NCG) India cancer management guidelines
    with site-specific cancer treatment protocols adapted for Indian healthcare settings.
    Covers all major cancers including breast, lung, colorectal, cervical, oral, stomach,
    ovarian, prostate, and pediatric cancers. Guidelines are consensus-driven by India's
    leading cancer centers and designed for resource-appropriate care delivery."""
)

# NCG URLs
BASE_URL = "https://www.ncgindia.org"
GUIDELINES_URL = f"{BASE_URL}/cancer-guidelines"
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
    name="search_cancer_guidelines",
    description="Search NCG cancer management guidelines by cancer type or keyword. Returns site-specific guidelines for breast, lung, colorectal, cervical, oral, gastric, ovarian, prostate, pediatric cancers, and more with India-specific treatment protocols."
)
async def search_cancer_guidelines(keyword: str, cancer_site: Optional[str] = None, max_results: int = 20) -> dict:
    """
    Search NCG cancer guidelines by keyword or cancer type.

    Args:
        keyword: Search term or cancer type (e.g., "breast cancer", "chemotherapy", "radiation", "palliative")
        cancer_site: Optional cancer site filter (e.g., "breast", "lung", "colorectal", "cervical")
        max_results: Maximum number of results to return (default: 20, max: 50)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - query (str): The search keyword used
            - cancer_site_filter (str|None): Cancer site filter applied
            - count (int): Number of results found
            - results (list): List of matching guidelines with title, cancer_site, url, version, document_type
            - error (str|None): Error message if search failed
    """
    max_results = min(max_results, 50)
    keyword_clean = " ".join(keyword.split())
    cancer_site_clean = " ".join(cancer_site.split()) if cancer_site else None

    results = []

    # Fetch the guidelines page
    html = await fetch_page(GUIDELINES_URL)
    if not html:
        return {
            'success': False,
            'query': keyword,
            'cancer_site_filter': cancer_site_clean,
            'count': 0,
            'results': [],
            'error': 'Failed to fetch NCG guidelines page'
        }

    soup = BeautifulSoup(html, 'html.parser')

    # Look for guideline links
    guideline_links = soup.find_all('a', href=True)

    seen_urls = set()
    keyword_lower = keyword_clean.lower()
    cancer_site_lower = cancer_site_clean.lower() if cancer_site_clean else None

    for link in guideline_links:
        href = link.get('href', '')
        if not href:
            continue

        link_text = link.get_text(strip=True)

        # Skip short links
        if len(link_text) < 8:
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
        keyword_match = keyword_lower in context_text.lower() or keyword_lower in link_text.lower()

        # Check cancer site filter if provided
        site_match = True
        if cancer_site_lower:
            site_match = cancer_site_lower in context_text.lower()

        if keyword_match and site_match:
            seen_urls.add(full_url)

            # Determine cancer site
            detected_site = 'Unknown'
            site_keywords = {
                'Breast': ['breast'],
                'Lung': ['lung', 'nsclc', 'sclc'],
                'Colorectal': ['colorectal', 'colon', 'rectal', 'crc'],
                'Cervical': ['cervical', 'cervix'],
                'Oral': ['oral', 'mouth', 'tongue', 'buccal'],
                'Gastric': ['gastric', 'stomach'],
                'Ovarian': ['ovarian', 'ovary'],
                'Prostate': ['prostate'],
                'Head & Neck': ['head and neck', 'head & neck', 'laryngeal', 'pharyngeal'],
                'Liver': ['liver', 'hepatocellular', 'hcc'],
                'Pancreatic': ['pancreatic', 'pancreas'],
                'Esophageal': ['esophageal', 'esophagus', 'oesophageal'],
                'Thyroid': ['thyroid'],
                'Renal': ['renal', 'kidney'],
                'Bladder': ['bladder', 'urothelial'],
                'Pediatric': ['pediatric', 'paediatric', 'children', 'childhood'],
                'Leukemia': ['leukemia', 'leukaemia', 'aml', 'all', 'cml', 'cll'],
                'Lymphoma': ['lymphoma', 'hodgkin', 'non-hodgkin'],
                'Bone': ['bone', 'sarcoma', 'osteosarcoma'],
                'Brain': ['brain', 'glioma', 'glioblastoma', 'cns']
            }

            for site_name, keywords in site_keywords.items():
                if any(kw in context_text.lower() for kw in keywords):
                    detected_site = site_name
                    break

            # Extract version if available
            version_match = re.search(r'v(?:ersion)?\s*(\d+\.?\d*)', context_text, re.I)
            version = version_match.group(1) if version_match else 'Latest'

            # Determine document type
            doc_type = 'PDF' if href.lower().endswith('.pdf') else 'Web Page'

            results.append({
                'title': link_text[:200] if len(link_text) > 200 else link_text,
                'cancer_site': detected_site,
                'url': full_url,
                'version': version,
                'document_type': doc_type
            })

            if len(results) >= max_results:
                break

    if not results:
        return {
            'success': True,
            'query': keyword,
            'cancer_site_filter': cancer_site_clean,
            'count': 0,
            'results': [],
            'error': 'No NCG cancer guidelines found matching the search criteria'
        }

    return {
        'success': True,
        'query': keyword,
        'cancer_site_filter': cancer_site_clean,
        'count': len(results),
        'results': results,
        'error': None
    }


@mcp.tool(
    name="get_guideline_content",
    description="Get detailed content for a specific NCG cancer guideline by URL. Returns treatment protocols, staging criteria, chemotherapy regimens, radiation doses, and India-specific resource considerations."
)
async def get_guideline_content(guideline_url: str) -> dict:
    """
    Get detailed information about a specific NCG cancer guideline.

    Args:
        guideline_url: Full URL to the guideline (PDF or web page)

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - title (str): Guideline title
            - url (str): Direct URL to the guideline
            - cancer_site (str): Cancer site/type
            - content (str): Main guideline content/summary
            - staging (str): Staging information
            - treatment_protocol (str): Treatment recommendations
            - chemotherapy (str): Chemotherapy regimens if applicable
            - radiation (str): Radiation therapy protocols if applicable
            - resource_considerations (str): India-specific resource adaptations
            - document_type (str): Type of document
            - error (str|None): Error message if retrieval failed
    """
    if not guideline_url:
        return {
            'success': False,
            'title': '',
            'url': '',
            'cancer_site': '',
            'content': '',
            'staging': '',
            'treatment_protocol': '',
            'chemotherapy': '',
            'radiation': '',
            'resource_considerations': '',
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
            'cancer_site': 'Cancer',
            'content': 'PDF document - download required for full content. This NCG guideline contains comprehensive, India-specific cancer management protocols.',
            'staging': 'Please download the PDF to view staging criteria',
            'treatment_protocol': 'Please download the PDF to view treatment protocols',
            'chemotherapy': 'Please download the PDF to view chemotherapy regimens',
            'radiation': 'Please download the PDF to view radiation protocols',
            'resource_considerations': 'Resource-stratified recommendations available in PDF',
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
            'cancer_site': '',
            'content': '',
            'staging': '',
            'treatment_protocol': '',
            'chemotherapy': '',
            'radiation': '',
            'resource_considerations': '',
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
        title = title_tag.get_text(strip=True) if title_tag else 'NCG Cancer Guideline'

    # Extract main content
    content = ''
    main_content = soup.find(['main', 'article', 'div'], class_=re.compile(r'content|main|guideline', re.I))
    if main_content:
        paragraphs = main_content.find_all('p', limit=10)
        content = ' '.join([p.get_text(strip=True) for p in paragraphs])

    if not content:
        paragraphs = soup.find_all('p', limit=10)
        content = ' '.join([p.get_text(strip=True) for p in paragraphs])

    # Extract staging information
    staging = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['staging', 'stage', 'classification', 'tnm']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol', 'table']:
                    content_parts.append(sibling.get_text(strip=True))
            staging = ' '.join(content_parts)
            if staging:
                break

    # Extract treatment protocol
    treatment_protocol = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['treatment', 'management', 'protocol', 'algorithm']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            treatment_protocol = ' '.join(content_parts)
            if treatment_protocol:
                break

    # Extract chemotherapy information
    chemotherapy = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['chemotherapy', 'chemo', 'systemic therapy', 'regimen']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            chemotherapy = ' '.join(content_parts)
            if chemotherapy:
                break

    # Extract radiation therapy information
    radiation = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['radiation', 'radiotherapy', 'rt ']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            radiation = ' '.join(content_parts)
            if radiation:
                break

    # Extract resource considerations
    resource_considerations = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['resource', 'indian', 'setting', 'adaptation']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            resource_considerations = ' '.join(content_parts)
            if resource_considerations:
                break

    # Determine cancer site
    cancer_site = 'Cancer'
    site_keywords = {
        'Breast Cancer': ['breast'],
        'Lung Cancer': ['lung'],
        'Colorectal Cancer': ['colorectal', 'colon', 'rectal'],
        'Cervical Cancer': ['cervical'],
        'Oral Cancer': ['oral'],
        'Gastric Cancer': ['gastric', 'stomach']
    }

    for site_name, keywords in site_keywords.items():
        if any(kw in title.lower() for kw in keywords):
            cancer_site = site_name
            break

    return {
        'success': True,
        'title': title,
        'url': guideline_url,
        'cancer_site': cancer_site,
        'content': content[:1500] + '...' if len(content) > 1500 else content,
        'staging': staging[:1000] + '...' if len(staging) > 1000 else staging,
        'treatment_protocol': treatment_protocol[:1500] + '...' if len(treatment_protocol) > 1500 else treatment_protocol,
        'chemotherapy': chemotherapy[:1000] + '...' if len(chemotherapy) > 1000 else chemotherapy,
        'radiation': radiation[:800] + '...' if len(radiation) > 800 else radiation,
        'resource_considerations': resource_considerations[:800] + '...' if len(resource_considerations) > 800 else resource_considerations or 'Guidelines adapted for Indian healthcare settings',
        'document_type': 'Web Page',
        'error': None
    }


@mcp.tool(
    name="list_cancer_types",
    description="List all cancer types covered by NCG guidelines including common solid tumors (breast, lung, colorectal, cervical, oral, gastric, etc.), hematological malignancies, and pediatric cancers with site-specific treatment protocols."
)
async def list_cancer_types() -> dict:
    """
    List available cancer types in NCG guidelines.

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - cancer_types (list): List of cancer types with name, description, key_topics, prevalence_in_india, url
            - error (str|None): Error message if retrieval failed
    """
    cancer_types = [
        {
            'name': 'Breast Cancer',
            'description': 'Comprehensive management of breast cancer',
            'key_topics': ['Screening', 'Surgery', 'Chemotherapy', 'Hormone therapy', 'HER2-targeted therapy', 'Radiation'],
            'prevalence_in_india': 'Most common cancer in Indian women',
            'url': GUIDELINES_URL
        },
        {
            'name': 'Lung Cancer',
            'description': 'NSCLC and SCLC management protocols',
            'key_topics': ['Staging', 'Molecular testing', 'Targeted therapy', 'Immunotherapy', 'Radiation', 'Palliative care'],
            'prevalence_in_india': 'Leading cause of cancer deaths in men',
            'url': GUIDELINES_URL
        },
        {
            'name': 'Colorectal Cancer',
            'description': 'Colon and rectal cancer treatment guidelines',
            'key_topics': ['Screening', 'Surgery', 'Chemotherapy', 'Targeted therapy', 'Radiation for rectal cancer'],
            'prevalence_in_india': 'Increasing incidence in urban India',
            'url': GUIDELINES_URL
        },
        {
            'name': 'Cervical Cancer',
            'description': 'Prevention and treatment of cervical cancer',
            'key_topics': ['HPV vaccination', 'Screening', 'Surgery', 'Chemoradiation', 'Brachytherapy'],
            'prevalence_in_india': 'Second most common cancer in Indian women',
            'url': GUIDELINES_URL
        },
        {
            'name': 'Oral Cancer',
            'description': 'Head and neck squamous cell carcinoma management',
            'key_topics': ['Tobacco cessation', 'Surgery', 'Radiation', 'Chemotherapy', 'Reconstruction'],
            'prevalence_in_india': 'Very high incidence due to tobacco/betel nut use',
            'url': GUIDELINES_URL
        },
        {
            'name': 'Gastric Cancer',
            'description': 'Stomach cancer treatment protocols',
            'key_topics': ['Endoscopy', 'Surgery', 'Perioperative chemotherapy', 'Palliative care'],
            'prevalence_in_india': 'Common in certain regions of India',
            'url': GUIDELINES_URL
        },
        {
            'name': 'Ovarian Cancer',
            'description': 'Epithelial ovarian cancer management',
            'key_topics': ['Surgery', 'Chemotherapy', 'Maintenance therapy', 'PARP inhibitors', 'Recurrence'],
            'prevalence_in_india': 'Third most common gynecological cancer',
            'url': GUIDELINES_URL
        },
        {
            'name': 'Prostate Cancer',
            'description': 'Prostate cancer screening and treatment',
            'key_topics': ['PSA screening', 'Active surveillance', 'Surgery', 'Radiation', 'Hormone therapy'],
            'prevalence_in_india': 'Increasing detection in urban areas',
            'url': GUIDELINES_URL
        },
        {
            'name': 'Liver Cancer',
            'description': 'Hepatocellular carcinoma management',
            'key_topics': ['Surveillance', 'Resection', 'Transplantation', 'Ablation', 'Systemic therapy'],
            'prevalence_in_india': 'Associated with hepatitis B and C',
            'url': GUIDELINES_URL
        },
        {
            'name': 'Esophageal Cancer',
            'description': 'Esophageal cancer treatment guidelines',
            'key_topics': ['Staging', 'Neoadjuvant therapy', 'Surgery', 'Chemoradiation', 'Palliation'],
            'prevalence_in_india': 'Higher incidence in certain regions',
            'url': GUIDELINES_URL
        },
        {
            'name': 'Pancreatic Cancer',
            'description': 'Pancreatic adenocarcinoma management',
            'key_topics': ['Resectability', 'Surgery', 'Chemotherapy', 'Palliative care', 'Pain management'],
            'prevalence_in_india': 'Increasing incidence',
            'url': GUIDELINES_URL
        },
        {
            'name': 'Thyroid Cancer',
            'description': 'Differentiated and medullary thyroid cancer',
            'key_topics': ['Surgery', 'Radioiodine therapy', 'TSH suppression', 'Targeted therapy'],
            'prevalence_in_india': 'More common in women',
            'url': GUIDELINES_URL
        },
        {
            'name': 'Pediatric Cancers',
            'description': 'Childhood malignancies management',
            'key_topics': ['Leukemia', 'Brain tumors', 'Neuroblastoma', 'Wilms tumor', 'Retinoblastoma'],
            'prevalence_in_india': 'Distinct treatment protocols for children',
            'url': GUIDELINES_URL
        },
        {
            'name': 'Leukemia',
            'description': 'Acute and chronic leukemia protocols',
            'key_topics': ['AML', 'ALL', 'CML', 'CLL', 'Stem cell transplant', 'Targeted therapy'],
            'prevalence_in_india': 'Common hematological malignancy',
            'url': GUIDELINES_URL
        },
        {
            'name': 'Lymphoma',
            'description': 'Hodgkin and non-Hodgkin lymphoma',
            'key_topics': ['Staging', 'Chemotherapy', 'Radiation', 'Immunotherapy', 'CAR-T therapy'],
            'prevalence_in_india': 'Variable subtypes',
            'url': GUIDELINES_URL
        },
        {
            'name': 'Bone Sarcoma',
            'description': 'Osteosarcoma and Ewing sarcoma',
            'key_topics': ['Surgery', 'Chemotherapy', 'Limb salvage', 'Rehabilitation'],
            'prevalence_in_india': 'More common in younger patients',
            'url': GUIDELINES_URL
        }
    ]

    return {
        'success': True,
        'cancer_types': cancer_types,
        'error': None
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
