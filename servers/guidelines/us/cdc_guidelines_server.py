#!/usr/bin/env python
"""
CDC (Centers for Disease Control and Prevention) Guidelines MCP Server

This MCP server provides tools to search and access CDC clinical guidelines and
recommendations. The CDC publishes evidence-based guidelines on infectious diseases,
immunizations, STI treatment, TB, HIV, and infection control.

Uses web scraping to retrieve published guidance from https://www.cdc.gov/
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
    "CDC-Guidelines",
    instructions="Search and retrieve CDC (Centers for Disease Control and Prevention) clinical guidelines including STI treatment, TB, HIV, immunization schedules, infection control, and disease-specific recommendations"
)

# CDC URLs
BASE_URL = "https://www.cdc.gov"
GUIDELINES_URL = f"{BASE_URL}/guidelines"
STI_URL = f"{BASE_URL}/std"
TB_URL = f"{BASE_URL}/tb"
HIV_URL = f"{BASE_URL}/hiv"
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
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            return response.text
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return None


@mcp.tool(
    name="search_cdc_guidelines",
    description="Search CDC clinical guidelines by topic, disease, or condition. Returns guidelines for infectious diseases, STIs, immunizations, TB, HIV, infection control, and other public health topics."
)
async def search_cdc_guidelines(keyword: str, max_results: int = 20) -> dict:
    """
    Search CDC guidelines by keyword or topic.

    Args:
        keyword: Search term (e.g., "STI treatment", "tuberculosis", "COVID-19", "immunization")
        max_results: Maximum number of results to return (default: 20, max: 50)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - query (str): The search keyword used
            - count (int): Number of results found
            - results (list): List of matching guidelines with:
                - title (str): Guideline title
                - url (str): Full URL to the guideline
                - category (str): Guideline category/topic area
                - date (str): Publication or update date
                - summary (str): Brief summary or excerpt
            - error (str|None): Error message if search failed
    """
    max_results = min(max_results, 50)

    # Clean keyword
    keyword_clean = " ".join(keyword.split())

    # Construct search URL
    search_url = f"{BASE_URL}/search/?query={quote(keyword_clean)}"

    html = await fetch_page(search_url)
    if not html:
        return {
            'success': False,
            'query': keyword,
            'count': 0,
            'results': [],
            'error': 'Failed to connect to CDC website'
        }

    soup = BeautifulSoup(html, 'html.parser')
    results = []

    # Find search result items
    result_items = soup.find_all(['div', 'li', 'article'], class_=re.compile(r'result|search-result|card'))

    for item in result_items[:max_results]:
        # Extract title and link
        title_elem = item.find(['h2', 'h3', 'a'], class_=re.compile(r'title|heading'))
        if not title_elem:
            title_elem = item.find('a')

        if not title_elem:
            continue

        title = title_elem.get_text(strip=True)
        link = ''

        if title_elem.name == 'a':
            link = title_elem.get('href', '')
        else:
            link_elem = item.find('a', href=True)
            if link_elem:
                link = link_elem.get('href', '')

        # Make URL absolute
        if link and not link.startswith('http'):
            link = f"{BASE_URL}{link}" if link.startswith('/') else f"{BASE_URL}/{link}"

        # Extract category
        category = 'CDC Guidelines'
        if '/std/' in link or '/sti/' in link:
            category = 'STI/STD Guidelines'
        elif '/tb/' in link:
            category = 'Tuberculosis Guidelines'
        elif '/hiv/' in link:
            category = 'HIV Guidelines'
        elif '/vaccines/' in link or '/immunization/' in link:
            category = 'Immunization Guidelines'
        elif '/infectioncontrol/' in link or '/hai/' in link:
            category = 'Infection Control Guidelines'

        # Extract date
        date = 'Not available'
        date_elem = item.find(['time', 'span'], class_=re.compile(r'date|published|updated'))
        if date_elem:
            date = date_elem.get_text(strip=True)

        # Extract summary
        summary = ''
        summary_elem = item.find(['p', 'div'], class_=re.compile(r'summary|description|excerpt|snippet'))
        if summary_elem:
            summary = summary_elem.get_text(strip=True)[:300]

        if title and link:
            results.append({
                'title': title,
                'url': link,
                'category': category,
                'date': date,
                'summary': summary
            })

    # If no results from search, try category-specific searches
    if not results:
        # Try disease-specific URLs based on keyword
        specific_searches = []
        keyword_lower = keyword.lower()

        if any(term in keyword_lower for term in ['sti', 'std', 'sexually transmitted', 'gonorrhea', 'chlamydia', 'syphilis']):
            specific_searches.append((f"{STI_URL}/treatment-guidelines", 'STI Treatment Guidelines'))
        if any(term in keyword_lower for term in ['tb', 'tuberculosis']):
            specific_searches.append((f"{TB_URL}/publications/guidelines", 'TB Guidelines'))
        if any(term in keyword_lower for term in ['hiv', 'aids']):
            specific_searches.append((f"{HIV_URL}/guidelines", 'HIV Guidelines'))

        for specific_url, category in specific_searches:
            html = await fetch_page(specific_url)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                links = soup.find_all('a', href=True)

                for link in links[:5]:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')

                    if title and len(title) > 10 and keyword_lower in title.lower():
                        full_url = f"{BASE_URL}{href}" if href.startswith('/') else href
                        results.append({
                            'title': title,
                            'url': full_url,
                            'category': category,
                            'date': 'Not available',
                            'summary': ''
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
    name="get_guideline_content",
    description="Get detailed content from a specific CDC guideline including recommendations, treatment protocols, prevention strategies, and implementation guidance."
)
async def get_guideline_content(identifier: str) -> dict:
    """
    Get detailed information about a specific CDC guideline.

    Args:
        identifier: Guideline URL, title, or identifier

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - title (str): Guideline title
            - url (str): Direct URL to the guideline
            - category (str): Guideline category
            - date (str): Publication/update date
            - summary (str): Executive summary or overview
            - recommendations (list): Key recommendations
            - sections (list): Available sections with content
            - related_resources (list): Related CDC resources
            - error (str|None): Error message if retrieval failed
    """
    # Determine URL
    if identifier.startswith('http'):
        url = identifier
    else:
        # Try to construct URL or search for it
        search_result = await search_cdc_guidelines(identifier, max_results=1)
        if search_result['success'] and search_result['count'] > 0:
            url = search_result['results'][0]['url']
        else:
            return {
                'success': False,
                'title': '',
                'url': '',
                'error': 'Could not find guideline with that identifier'
            }

    html = await fetch_page(url)
    if not html:
        return {
            'success': False,
            'title': '',
            'url': url,
            'error': 'Failed to retrieve guideline page'
        }

    soup = BeautifulSoup(html, 'html.parser')

    # Extract title
    title = ''
    title_elem = soup.find('h1')
    if title_elem:
        title = title_elem.get_text(strip=True)

    # Extract category
    category = 'CDC Guidelines'
    breadcrumb = soup.find(['nav', 'ol'], class_=re.compile(r'breadcrumb'))
    if breadcrumb:
        category_elem = breadcrumb.find_all('a')
        if category_elem:
            category = category_elem[-1].get_text(strip=True) if category_elem else category

    # Extract date
    date = 'Not available'
    date_elem = soup.find(['time', 'div', 'span'], class_=re.compile(r'date|published|updated|reviewed'))
    if date_elem:
        date = date_elem.get_text(strip=True)

    # Extract summary
    summary = ''
    summary_elem = soup.find(['div', 'section'], class_=re.compile(r'summary|synopsis|key-points|highlights'))
    if summary_elem:
        paragraphs = summary_elem.find_all('p', limit=3)
        summary = ' '.join([p.get_text(strip=True) for p in paragraphs])

    if not summary:
        # Try to get first few paragraphs
        main_content = soup.find(['main', 'article', 'div'], class_=re.compile(r'content|body'))
        if main_content:
            paragraphs = main_content.find_all('p', limit=3)
            summary = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

    # Extract recommendations
    recommendations = []
    rec_section = soup.find(['div', 'section'], class_=re.compile(r'recommendation|guidance'))
    if rec_section:
        rec_items = rec_section.find_all(['li', 'p'])
        for item in rec_items[:10]:
            text = item.get_text(strip=True)
            if text and len(text) > 20:
                recommendations.append(text)

    # Extract sections
    sections = []
    headings = soup.find_all(['h2', 'h3'], limit=15)
    for heading in headings:
        heading_text = heading.get_text(strip=True)
        if heading_text and len(heading_text) < 200:
            # Get content following heading
            content = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3']:
                    break
                if sibling.name in ['p', 'li']:
                    text = sibling.get_text(strip=True)
                    if text:
                        content.append(text)

            if content:
                sections.append({
                    'heading': heading_text,
                    'content': ' '.join(content)[:500]
                })

    # Extract related resources
    related = []
    related_section = soup.find(['div', 'aside', 'section'], class_=re.compile(r'related|additional|see-also'))
    if related_section:
        for link in related_section.find_all('a', href=True)[:5]:
            related.append({
                'title': link.get_text(strip=True),
                'url': f"{BASE_URL}{link.get('href')}" if link.get('href', '').startswith('/') else link.get('href')
            })

    return {
        'success': True,
        'title': title,
        'url': url,
        'category': category,
        'date': date,
        'summary': summary[:1000] if summary else 'Not available',
        'recommendations': recommendations,
        'sections': sections,
        'related_resources': related,
        'error': None
    }


@mcp.tool(
    name="list_cdc_topics",
    description="List major CDC guideline topics and categories including STI treatment, tuberculosis, HIV, immunizations, infection control, and other infectious diseases."
)
async def list_cdc_topics() -> dict:
    """
    List available CDC guideline topics and categories.

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - topics (list): List of major CDC guideline topics with:
                - name (str): Topic name
                - description (str): Topic description
                - url (str): Link to topic page
                - focus_areas (list): Key focus areas within topic
            - error (str|None): Error message if retrieval failed
    """
    topics = [
        {
            'name': 'STI Treatment Guidelines',
            'description': 'Clinical guidelines for diagnosis and treatment of sexually transmitted infections including gonorrhea, chlamydia, syphilis, genital herpes, and HPV',
            'url': f"{STI_URL}/treatment-guidelines",
            'focus_areas': ['Gonorrhea', 'Chlamydia', 'Syphilis', 'Genital Herpes', 'HPV', 'Trichomoniasis', 'PID']
        },
        {
            'name': 'Tuberculosis Guidelines',
            'description': 'Guidelines for TB diagnosis, treatment, and prevention including latent TB infection (LTBI) and drug-resistant TB',
            'url': f"{TB_URL}/publications/guidelines",
            'focus_areas': ['Active TB', 'Latent TB', 'Drug-Resistant TB', 'TB Screening', 'TB Prevention']
        },
        {
            'name': 'HIV Guidelines',
            'description': 'Guidelines for HIV testing, prevention, treatment, and care including PrEP and PEP recommendations',
            'url': f"{HIV_URL}/guidelines",
            'focus_areas': ['HIV Testing', 'PrEP', 'PEP', 'Antiretroviral Therapy', 'HIV Prevention']
        },
        {
            'name': 'Immunization Guidelines',
            'description': 'ACIP recommendations for vaccines including childhood immunization schedule, adult immunization, and special populations',
            'url': f"{BASE_URL}/vaccines/hcp/acip-recs",
            'focus_areas': ['Childhood Vaccines', 'Adult Vaccines', 'Travel Vaccines', 'Immunocompromised Patients']
        },
        {
            'name': 'Infection Control Guidelines',
            'description': 'Guidelines for infection prevention in healthcare settings including hand hygiene, PPE, isolation precautions, and HAI prevention',
            'url': f"{BASE_URL}/infectioncontrol/guidelines",
            'focus_areas': ['Hand Hygiene', 'PPE', 'Isolation Precautions', 'HAI Prevention', 'Environmental Cleaning']
        },
        {
            'name': 'COVID-19 Guidelines',
            'description': 'Guidelines for COVID-19 prevention, testing, treatment, and infection control',
            'url': f"{BASE_URL}/coronavirus/2019-ncov/hcp/clinical-guidance",
            'focus_areas': ['Clinical Management', 'Testing', 'Vaccination', 'Infection Control', 'Post-COVID Conditions']
        },
        {
            'name': 'Viral Hepatitis Guidelines',
            'description': 'Guidelines for hepatitis A, B, and C prevention, testing, and treatment',
            'url': f"{BASE_URL}/hepatitis/hcp",
            'focus_areas': ['Hepatitis A', 'Hepatitis B', 'Hepatitis C', 'Testing', 'Vaccination']
        },
        {
            'name': 'Antibiotic Resistance and Stewardship',
            'description': 'Guidelines for appropriate antibiotic use, antibiotic stewardship programs, and combating resistance',
            'url': f"{BASE_URL}/antibiotic-use/core-elements",
            'focus_areas': ['Antibiotic Stewardship', 'Appropriate Use', 'Resistance Prevention', 'Prescribing Guidelines']
        }
    ]

    return {
        'success': True,
        'topics': topics,
        'error': None
    }


if __name__ == "__main__":
    # Run the MCP server
    # Add rate limiting delay
    import time
    await_time = 0.5  # 500ms between requests

    mcp.run()
