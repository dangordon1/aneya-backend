#!/usr/bin/env python
"""
NICE Guidelines MCP Server

This MCP server provides tools to search and access NICE (National Institute for
Health and Care Excellence) clinical guidelines from the UK. Uses web scraping
to retrieve published guidance documents and their details.
"""

import asyncio
from typing import Any, Optional, List, Dict
from urllib.parse import quote
import httpx
from bs4 import BeautifulSoup
import re
from datetime import datetime
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(
    "NICE-Guidelines",
    instructions="Search and retrieve UK NICE clinical guidelines with detailed information including indications, recommendations, and evidence"
)

# NICE URLs
BASE_URL = "https://www.nice.org.uk"
GUIDANCE_URL = f"{BASE_URL}/guidance"
CKS_BASE_URL = "https://cks.nice.org.uk"
TIMEOUT = 30.0


async def fetch_page(url: str) -> Optional[str]:
    """
    Fetch a webpage and return its HTML content.

    Args:
        url: The URL to fetch

    Returns:
        HTML content as string or None if failed
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        return response.text


@mcp.tool(
    name="search_nice_guidelines",
    description="Search NICE clinical guidelines by keyword or topic. Returns matching guidelines with reference numbers, titles, publication dates, and URLs for conditions like diabetes, pregnancy, croup, sepsis, etc."
)
async def search_nice_guidelines(keyword: str, max_results: int = 20) -> dict:
    """
    Search NICE guidelines by keyword or topic.

    Args:
        keyword: Search term or topic to find guidelines (e.g., "diabetes", "pregnancy", "ng235")
        max_results: Maximum number of results to return (default: 20, max: 100)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - query (str): The search keyword used
            - count (int): Number of results found
            - results (list): List of matching guidelines with reference, title, url, published_date
            - error (str|None): Error message if search failed
    """
    max_results = min(max_results, 100)

    # Sanitize keyword: remove newlines and extra whitespace
    keyword_clean = " ".join(keyword.split())

    # Construct search URL with proper URL encoding
    page_size = min(max_results, 50)  # NICE allows max 50 per page
    search_url = f"{GUIDANCE_URL}/published?q={quote(keyword_clean)}&ps={page_size}"

    html = await fetch_page(search_url)
    if not html:
        raise ValueError('Failed to fetch search results page')

    soup = BeautifulSoup(html, 'html.parser')
    results = []

    # Find JSON-LD script tag containing structured data
    script_tags = soup.find_all('script', type='application/ld+json')

    for script in script_tags:
        try:
            import json
            data = json.loads(script.string)

            # Check if this is the search results data
            if isinstance(data, dict) and 'documents' in data:
                documents = data['documents']

                for doc in documents[:max_results]:
                    # Extract guideline reference
                    ref = doc.get('guidanceRef', '')

                    # Extract title (prefer plain text version)
                    title = doc.get('titleNoHtml') or doc.get('title', '')
                    # Remove HTML tags if still present
                    title = re.sub(r'<[^>]+>', '', title)

                    # Extract URL
                    url = doc.get('url', '')
                    if url and not url.startswith('http'):
                        url = f"{BASE_URL}{url}"

                    # Extract dates
                    pub_date = doc.get('publicationDate', 'Not available')
                    if pub_date and pub_date != 'Not available':
                        # Convert ISO date to readable format
                        try:
                            dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                            pub_date = dt.strftime('%B %Y')
                        except Exception:
                            pass

                    last_updated = doc.get('lastUpdated', 'Not available')
                    if last_updated and last_updated != 'Not available':
                        try:
                            dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                            last_updated = dt.strftime('%B %Y')
                        except Exception:
                            pass

                    # Extract guideline type
                    guideline_types = doc.get('niceGuidanceType', [])
                    guideline_type = guideline_types[0] if guideline_types else 'NICE guidance'

                    results.append({
                        'reference': ref,
                        'title': title,
                        'url': url,
                        'published_date': pub_date,
                        'last_updated': last_updated,
                        'guideline_type': guideline_type
                    })

                break  # Found the results, no need to check other scripts

        except (json.JSONDecodeError, KeyError):
            continue

    # Fallback: try parsing HTML if JSON approach didn't work
    if not results:
        links = soup.find_all('a', href=re.compile(r'/guidance/[a-z]{2,3}\d+'))
        seen_refs = set()

        for link in links[:max_results]:
            href = link.get('href', '')
            match = re.search(r'/guidance/([a-z]{2,3}\d+)', href)
            if match:
                ref = match.group(1).upper()
                if ref not in seen_refs:
                    seen_refs.add(ref)
                    title = link.get_text(strip=True)
                    if title and len(title) > 5:
                        results.append({
                            'reference': ref,
                            'title': title,
                            'url': f"{BASE_URL}{href}" if href.startswith('/') else href,
                            'published_date': 'Not available',
                            'last_updated': 'Not available',
                            'guideline_type': 'NICE guidance'
                        })

    if not results:
        return {
            'success': True,
            'query': keyword,
            'count': 0,
            'results': [],
            'error': 'No guidelines found matching the search term'
        }

    return {
        'success': True,
        'query': keyword,
        'count': len(results),
        'results': results,
        'error': None
    }


@mcp.tool(
    name="get_guideline_details",
    description="Get detailed information about a specific NICE guideline by its reference number (e.g., NG235, TA456) or URL. Returns title, overview, publication dates, sections, and related guidance."
)
async def get_guideline_details(identifier: str) -> dict:
    """
    Get detailed information about a specific NICE guideline.

    Args:
        identifier: Guideline reference number (e.g., "NG235", "TA1109") or full URL

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - reference (str): Guideline reference number
            - title (str): Full title of the guideline
            - url (str): Direct URL to the guideline
            - overview (str): Summary/overview of the guideline
            - published_date (str): Publication date
            - last_updated (str): Last update date
            - guideline_type (str): Type of guidance
            - sections (list): Available sections/chapters in the guideline
            - related_guidance (list): Links to related NICE guidelines
            - error (str|None): Error message if retrieval failed
    """
    # Determine if identifier is a URL or reference number
    if identifier.startswith('http'):
        url = identifier
        match = re.search(r'/guidance/([a-z]{2,3}\d+)', identifier, re.IGNORECASE)
        reference = match.group(1).upper() if match else 'Unknown'
    else:
        reference = identifier.strip().upper()
        url = f"{GUIDANCE_URL}/{reference.lower()}"

    html = await fetch_page(url)
    if not html:
        raise ValueError('Failed to fetch guideline page')

    soup = BeautifulSoup(html, 'html.parser')

    # Extract title
    title = ''
    title_elem = soup.find('h1')
    if title_elem:
        title = title_elem.get_text(strip=True)

    # Extract overview/summary
    overview = ''
    overview_elem = soup.find(['div', 'section'], class_=re.compile(r'overview|summary|introduction'))
    if overview_elem:
        paragraphs = overview_elem.find_all('p', limit=3)
        overview = ' '.join([p.get_text(strip=True) for p in paragraphs])

    if not overview:
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            overview = meta_desc.get('content', '')

    # Extract dates
    published_date = 'Not available'
    last_updated = 'Not available'

    date_container = soup.find(['div', 'dl'], class_=re.compile(r'date|publish|metadata'))
    if date_container:
        date_items = date_container.find_all(['time', 'dd', 'span'])
        if len(date_items) >= 1:
            published_date = date_items[0].get_text(strip=True)
        if len(date_items) >= 2:
            last_updated = date_items[1].get_text(strip=True)

    # Extract guideline type
    guideline_type = 'NICE guidance'
    type_elem = soup.find(['span', 'div'], class_=re.compile(r'type|category'))
    if type_elem:
        guideline_type = type_elem.get_text(strip=True)

    # Extract available sections
    sections = []
    nav_elem = soup.find(['nav', 'ul'], class_=re.compile(r'section|chapter|navigation|toc'))
    if nav_elem:
        section_links = nav_elem.find_all('a')
        sections = [link.get_text(strip=True) for link in section_links if link.get_text(strip=True)]

    if not sections:
        section_headings = soup.find_all(['h2', 'h3'], limit=10)
        sections = [h.get_text(strip=True) for h in section_headings if h.get_text(strip=True)]

    # Extract related guidance
    related_guidance = []
    related_section = soup.find(['div', 'section'], class_=re.compile(r'related|see-also'))
    if related_section:
        related_links = related_section.find_all('a', href=re.compile(r'/guidance/'))
        for link in related_links[:5]:
            related_guidance.append({
                'title': link.get_text(strip=True),
                'url': f"{BASE_URL}{link.get('href', '')}" if link.get('href', '').startswith('/') else link.get('href', '')
            })

    return {
        'success': True,
        'reference': reference,
        'title': title,
        'url': url,
        'overview': overview[:500] + '...' if len(overview) > 500 else overview,
        'published_date': published_date,
        'last_updated': last_updated,
        'guideline_type': guideline_type,
        'sections': sections[:15],
        'related_guidance': related_guidance,
        'error': None
    }


@mcp.tool(
    name="list_guideline_categories",
    description="List available NICE guideline categories and types including Clinical guidelines (NG), Technology appraisals (TA), Quality standards (QS), etc. Returns category names, codes, descriptions, and URLs."
)
async def list_guideline_categories() -> dict:
    """
    List available NICE guideline categories and types.

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - categories (list): List of guideline categories with name, code, count, description, url
            - error (str|None): Error message if retrieval failed
    """
    # Define known NICE guideline types
    categories = [
        {
            'name': 'All published guidance',
            'code': 'ALL',
            'count': None,
            'description': 'All published NICE guidance across all categories',
            'url': f"{GUIDANCE_URL}/published"
        },
        {
            'name': 'Clinical guidelines',
            'code': 'NG',
            'count': None,
            'description': 'Evidence-based recommendations for managing specific conditions and improving health',
            'url': f"{GUIDANCE_URL}/published?type=cg"
        },
        {
            'name': 'Technology appraisal guidance',
            'code': 'TA',
            'count': None,
            'description': 'Guidance on new and existing medicines, treatments and procedures',
            'url': f"{GUIDANCE_URL}/published?type=ta"
        },
        {
            'name': 'Interventional procedures guidance',
            'code': 'IPG',
            'count': None,
            'description': 'Guidance on whether interventional procedures are safe and work well enough',
            'url': f"{GUIDANCE_URL}/published?type=ipg"
        },
        {
            'name': 'Medical technologies guidance',
            'code': 'MTG',
            'count': None,
            'description': 'Guidance on medical devices and diagnostics',
            'url': f"{GUIDANCE_URL}/published?type=mtg"
        },
        {
            'name': 'Diagnostics guidance',
            'code': 'DG',
            'count': None,
            'description': 'Guidance on using diagnostic tests for specific conditions',
            'url': f"{GUIDANCE_URL}/published?type=dg"
        },
        {
            'name': 'Quality standards',
            'code': 'QS',
            'count': None,
            'description': 'Concise sets of prioritised statements for quality improvement',
            'url': f"{GUIDANCE_URL}/published?type=qs"
        },
        {
            'name': 'Public health guidelines',
            'code': 'PH',
            'count': None,
            'description': 'Recommendations on activities to promote health and prevent disease',
            'url': f"{GUIDANCE_URL}/published?type=ph"
        },
        {
            'name': 'Social care guidelines',
            'code': 'SC',
            'count': None,
            'description': 'Recommendations for social care and public health',
            'url': f"{GUIDANCE_URL}/published?type=sc"
        }
    ]

    return {
        'success': True,
        'categories': categories,
        'error': None
    }


@mcp.tool(
    name="search_cks_topics",
    description="Search NICE Clinical Knowledge Summaries (CKS) for primary care topics like croup, asthma, UTI, etc. CKS contains 375+ topics focused on common primary care presentations. Note: CKS may be geo-restricted to UK IPs."
)
async def search_cks_topics(topic: str, max_results: int = 5) -> dict:
    """
    Search NICE Clinical Knowledge Summaries by topic name.

    Args:
        topic: Topic to search for (e.g., "croup", "asthma", "urinary tract infection")
        max_results: Maximum number of results to return (default: 5)

    Returns:
        Dictionary containing:
            - success (bool): Whether search succeeded
            - query (str): Search term used
            - count (int): Number of results found
            - results (list): List of matching topics with title, url, summary
            - error (str|None): Error message if search failed
    """
    # Try direct topic URL first (most reliable method)
    topic_slug = topic.lower().replace(' ', '-').replace('_', '-')
    direct_url = f"{CKS_BASE_URL}/topics/{topic_slug}"

    results = []

    try:
        html = await fetch_page(direct_url)

        if html and 'Page not found' not in html and 'Error 404' not in html:
            # Direct match found
            soup = BeautifulSoup(html, 'html.parser')

            # Extract title
            title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else topic.title()

            # Extract summary
            summary = ''
            summary_elem = soup.find(['div', 'section'], class_=re.compile(r'summary|intro|overview'))
            if summary_elem:
                paragraphs = summary_elem.find_all('p', limit=2)
                summary = ' '.join([p.get_text(strip=True) for p in paragraphs])

            if not summary:
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc:
                    summary = meta_desc.get('content', '')

            results.append({
                'title': title,
                'url': direct_url,
                'summary': summary[:300] + '...' if len(summary) > 300 else summary,
                'type': 'Clinical Knowledge Summary'
            })
    except Exception:
        # Topic not found (404) or other error - return empty results gracefully
        pass

    return {
        'success': True,
        'query': topic,
        'count': len(results),
        'results': results,
        'error': 'Topic not found - CKS may be geo-restricted to UK IPs or topic does not exist' if not results else None
    }


@mcp.tool(
    name="get_cks_topic",
    description="Retrieve detailed content for a specific NICE Clinical Knowledge Summary topic including management guidance, prescribing information, and patient advice. Note: CKS may be geo-restricted to UK IPs."
)
async def get_cks_topic(topic: str) -> dict:
    """
    Get full content for a specific CKS topic.

    Args:
        topic: Topic name or slug (e.g., "croup", "asthma")

    Returns:
        Dictionary containing:
            - success (bool): Whether retrieval succeeded
            - title (str): Topic title
            - url (str): Topic URL
            - summary (str): Brief summary
            - sections (list): Available sections/chapters
            - management (str): Management guidance
            - prescribing (str): Prescribing information
            - error (str|None): Error message if failed
    """
    topic_slug = topic.lower().replace(' ', '-').replace('_', '-')
    url = f"{CKS_BASE_URL}/topics/{topic_slug}"

    html = await fetch_page(url)

    if not html or 'Page not found' in html or 'Error 404' in html:
        return {
            'success': False,
            'title': '',
            'url': url,
            'summary': '',
            'sections': [],
            'management': '',
            'prescribing': '',
            'error': 'Topic not found - CKS may be geo-restricted to UK IPs or topic does not exist'
        }

    soup = BeautifulSoup(html, 'html.parser')

    # Extract title
    title_elem = soup.find('h1')
    title = title_elem.get_text(strip=True) if title_elem else topic.title()

    # Extract summary
    summary = ''
    summary_elem = soup.find(['div', 'section'], class_=re.compile(r'summary|intro|overview'))
    if summary_elem:
        paragraphs = summary_elem.find_all('p', limit=3)
        summary = ' '.join([p.get_text(strip=True) for p in paragraphs])

    # Extract sections
    sections = []
    nav_elem = soup.find(['nav', 'div'], class_=re.compile(r'navigation|toc|contents'))
    if nav_elem:
        links = nav_elem.find_all('a')
        sections = [link.get_text(strip=True) for link in links if link.get_text(strip=True)]

    # Extract all content text (since CKS uses dynamic class names)
    # Get all text from the main content area
    full_text = ''
    main_content = soup.find('main') or soup.find('body')
    if main_content:
        # Get all paragraphs and list items
        content_elements = main_content.find_all(['p', 'li'])
        full_text = ' '.join([elem.get_text(strip=True) for elem in content_elements])

    # Extract management-related content
    management = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['management', 'treatment', 'scenario']):
            # Get following paragraphs until next heading
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li']:
                    content_parts.append(sibling.get_text(strip=True))
            management = ' '.join(content_parts)
            if management:
                break

    # Extract prescribing-related content
    prescribing = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['prescrib', 'medication', 'drug', 'corticosteroid']):
            # Get following paragraphs until next heading
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li']:
                    content_parts.append(sibling.get_text(strip=True))
            prescribing = ' '.join(content_parts)
            if prescribing:
                break

    # If specific sections not found, use full text
    if not management:
        management = full_text

    if not prescribing:
        prescribing = full_text

    return {
        'success': True,
        'title': title,
        'url': url,
        'summary': summary[:500] + '...' if len(summary) > 500 else summary,
        'sections': sections[:10],  # Limit to first 10 sections
        'management': management[:1000] + '...' if len(management) > 1000 else management,
        'prescribing': prescribing[:1000] + '...' if len(prescribing) > 1000 else prescribing,
        'error': None
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
