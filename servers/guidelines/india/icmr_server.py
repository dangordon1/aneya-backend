#!/usr/bin/env python
"""
ICMR Guidelines MCP Server

This MCP server provides tools to search and access ICMR (Indian Council of
Medical Research) clinical guidelines. ICMR is India's apex body for biomedical
research and provides evidence-based national treatment guidelines, ethical
guidelines, and disease management protocols for the Indian healthcare context.

Uses web scraping to retrieve published guidance documents from www.icmr.gov.in.
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
    "ICMR-Guidelines",
    instructions="""Search and retrieve Indian Council of Medical Research (ICMR) clinical guidelines
    with detailed information including national treatment protocols, ethical guidelines, and disease
    management recommendations specific to the Indian healthcare context. ICMR is India's apex body
    for biomedical research and formulates health research policy for India."""
)

# ICMR URLs
BASE_URL = "https://www.icmr.gov.in"
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
    name="search_icmr_guidelines",
    description="Search ICMR clinical guidelines by keyword or topic. Returns matching guidelines with titles, publication dates, and URLs for national treatment protocols, ethical guidelines, disease management for conditions like tuberculosis, malaria, diabetes, COVID-19, etc."
)
async def search_icmr_guidelines(keyword: str, max_results: int = 20) -> dict:
    """
    Search ICMR guidelines by keyword or topic.

    Args:
        keyword: Search term or topic to find guidelines (e.g., "tuberculosis", "diabetes", "covid-19", "ethics")
        max_results: Maximum number of results to return (default: 20, max: 50)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - query (str): The search keyword used
            - count (int): Number of results found
            - results (list): List of matching guidelines with title, url, published_date, category, document_type
            - error (str|None): Error message if search failed
    """
    max_results = min(max_results, 50)
    keyword_clean = " ".join(keyword.split())

    results = []

    # Try guidelines page
    html = await fetch_page(GUIDELINES_URL)
    if not html:
        return {
            'success': False,
            'query': keyword,
            'count': 0,
            'results': [],
            'error': 'Failed to fetch ICMR guidelines page'
        }

    soup = BeautifulSoup(html, 'html.parser')

    # Look for guideline links - ICMR typically lists guidelines as PDF links
    guideline_links = soup.find_all('a', href=re.compile(r'\.(pdf|PDF)'))

    # Also look for guideline listings in tables or lists
    guideline_containers = soup.find_all(['div', 'section', 'article', 'li', 'tr'],
                                        class_=re.compile(r'guideline|publication|document', re.I))

    seen_urls = set()
    keyword_lower = keyword_clean.lower()

    # Process PDF links
    for link in guideline_links:
        href = link.get('href', '')
        if not href:
            continue

        # Build full URL
        full_url = urljoin(BASE_URL, href)

        # Skip duplicates
        if full_url in seen_urls:
            continue

        # Get link text and surrounding context
        link_text = link.get_text(strip=True)
        parent = link.find_parent(['li', 'tr', 'div', 'p'])
        context_text = parent.get_text(strip=True) if parent else link_text

        # Check if keyword matches
        if keyword_lower in context_text.lower() or keyword_lower in link_text.lower():
            seen_urls.add(full_url)

            # Extract date if available
            date_match = re.search(r'\b(\d{4})\b', context_text)
            pub_date = date_match.group(1) if date_match else 'Not available'

            # Determine category from text
            category = 'General Guideline'
            if any(word in context_text.lower() for word in ['treatment', 'clinical', 'management']):
                category = 'Treatment Guideline'
            elif 'ethic' in context_text.lower():
                category = 'Ethical Guideline'
            elif any(word in context_text.lower() for word in ['diagnostic', 'screening']):
                category = 'Diagnostic Guideline'

            results.append({
                'title': link_text or context_text[:100],
                'url': full_url,
                'published_date': pub_date,
                'category': category,
                'document_type': 'PDF'
            })

            if len(results) >= max_results:
                break

    # If no results from PDF links, try finding guideline listings
    if not results:
        for container in guideline_containers:
            text = container.get_text(strip=True)

            if keyword_lower in text.lower():
                # Find link in container
                link = container.find('a', href=True)
                if link:
                    href = link.get('href', '')
                    full_url = urljoin(BASE_URL, href)

                    if full_url not in seen_urls:
                        seen_urls.add(full_url)

                        results.append({
                            'title': text[:200] if len(text) > 200 else text,
                            'url': full_url,
                            'published_date': 'Not available',
                            'category': 'General Guideline',
                            'document_type': 'Web Page' if not href.endswith('.pdf') else 'PDF'
                        })

                        if len(results) >= max_results:
                            break

    if not results:
        return {
            'success': True,
            'query': keyword,
            'count': 0,
            'results': [],
            'error': 'No ICMR guidelines found matching the search term'
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
    description="Get detailed information about a specific ICMR guideline by its URL. For PDF documents, returns metadata; for web pages, returns full content including recommendations and sections."
)
async def get_guideline_content(guideline_url: str) -> dict:
    """
    Get detailed information about a specific ICMR guideline.

    Args:
        guideline_url: Full URL to the guideline (PDF or web page)

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - title (str): Guideline title
            - url (str): Direct URL to the guideline
            - content (str): Main content/summary (for web pages) or metadata (for PDFs)
            - document_type (str): Type of document (PDF or Web Page)
            - sections (list): Available sections (for web pages)
            - recommendations (str): Key recommendations if extractable
            - error (str|None): Error message if retrieval failed
    """
    if not guideline_url:
        return {
            'success': False,
            'title': '',
            'url': '',
            'content': '',
            'document_type': '',
            'sections': [],
            'recommendations': '',
            'error': 'No URL provided'
        }

    # Determine document type
    is_pdf = guideline_url.lower().endswith('.pdf')

    if is_pdf:
        # For PDFs, we can't extract content directly via web scraping
        # Return metadata and inform user
        return {
            'success': True,
            'title': guideline_url.split('/')[-1].replace('.pdf', '').replace('_', ' ').title(),
            'url': guideline_url,
            'content': 'PDF document - download required for full content',
            'document_type': 'PDF',
            'sections': [],
            'recommendations': 'Please download the PDF to view recommendations',
            'error': None
        }

    # For web pages, fetch and parse content
    html = await fetch_page(guideline_url)
    if not html:
        return {
            'success': False,
            'title': '',
            'url': guideline_url,
            'content': '',
            'document_type': 'Web Page',
            'sections': [],
            'recommendations': '',
            'error': 'Failed to fetch guideline page'
        }

    soup = BeautifulSoup(html, 'html.parser')

    # Extract title
    title = ''
    title_elem = soup.find('h1')
    if title_elem:
        title = title_elem.get_text(strip=True)
    else:
        # Try from title tag
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else 'ICMR Guideline'

    # Extract main content
    content = ''
    main_content = soup.find(['main', 'article', 'div'], class_=re.compile(r'content|main|article', re.I))
    if main_content:
        paragraphs = main_content.find_all('p', limit=5)
        content = ' '.join([p.get_text(strip=True) for p in paragraphs])

    if not content:
        # Fallback to all paragraphs
        paragraphs = soup.find_all('p', limit=5)
        content = ' '.join([p.get_text(strip=True) for p in paragraphs])

    # Extract sections
    sections = []
    headings = soup.find_all(['h2', 'h3'], limit=15)
    sections = [h.get_text(strip=True) for h in headings if h.get_text(strip=True)]

    # Extract recommendations
    recommendations = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['recommendation', 'key point', 'summary', 'conclusion']):
            # Get following content
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            recommendations = ' '.join(content_parts)
            if recommendations:
                break

    return {
        'success': True,
        'title': title,
        'url': guideline_url,
        'content': content[:1000] + '...' if len(content) > 1000 else content,
        'document_type': 'Web Page',
        'sections': sections,
        'recommendations': recommendations[:1000] + '...' if len(recommendations) > 1000 else recommendations,
        'error': None
    }


@mcp.tool(
    name="list_guideline_categories",
    description="List available ICMR guideline categories including National Treatment Guidelines, Ethical Guidelines, Disease Management Protocols, Research Guidelines, etc. Returns category names, descriptions, and typical topics covered."
)
async def list_guideline_categories() -> dict:
    """
    List available ICMR guideline categories and types.

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - categories (list): List of guideline categories with name, description, typical_topics, url
            - error (str|None): Error message if retrieval failed
    """
    categories = [
        {
            'name': 'National Treatment Guidelines',
            'description': 'Evidence-based treatment protocols for major diseases in Indian context',
            'typical_topics': ['Tuberculosis', 'Malaria', 'HIV/AIDS', 'Dengue', 'COVID-19', 'Diabetes', 'Hypertension'],
            'url': f"{GUIDELINES_URL}"
        },
        {
            'name': 'Ethical Guidelines',
            'description': 'Guidelines for ethical conduct in biomedical and health research',
            'typical_topics': ['Clinical trials', 'Human participant research', 'Stem cell research', 'Data protection'],
            'url': f"{GUIDELINES_URL}"
        },
        {
            'name': 'Diagnostic Guidelines',
            'description': 'Standardized protocols for disease diagnosis and screening',
            'typical_topics': ['Laboratory diagnostics', 'Imaging protocols', 'Screening programs', 'Quality assurance'],
            'url': f"{GUIDELINES_URL}"
        },
        {
            'name': 'Disease Management Protocols',
            'description': 'Comprehensive disease management strategies for Indian healthcare settings',
            'typical_topics': ['Non-communicable diseases', 'Infectious diseases', 'Maternal health', 'Child health'],
            'url': f"{GUIDELINES_URL}"
        },
        {
            'name': 'Public Health Guidelines',
            'description': 'Guidelines for public health programs and interventions',
            'typical_topics': ['Immunization', 'Nutrition', 'Sanitation', 'Disease surveillance', 'Outbreak response'],
            'url': f"{GUIDELINES_URL}"
        },
        {
            'name': 'Research Guidelines',
            'description': 'Protocols and standards for conducting health research in India',
            'typical_topics': ['Good clinical practice', 'Laboratory standards', 'Research methodology', 'Data management'],
            'url': f"{GUIDELINES_URL}"
        }
    ]

    return {
        'success': True,
        'categories': categories,
        'error': None
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
