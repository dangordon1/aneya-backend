#!/usr/bin/env python
"""
USPSTF (US Preventive Services Task Force) MCP Server

This MCP server provides tools to search and access USPSTF preventive care recommendations.
The USPSTF is an independent panel of experts in primary care and prevention that systematically
reviews evidence and makes recommendations on preventive services.

Note: The USPSTF API requires approval. Contact uspstfpda@ahrq.gov for API access.
This implementation includes the structure for API integration once credentials are obtained.
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
    "USPSTF-Guidelines",
    instructions="Search and retrieve US Preventive Services Task Force (USPSTF) recommendations for preventive care services including screenings, counseling, and preventive medications with evidence grades"
)

# USPSTF URLs
BASE_URL = "https://www.uspreventiveservicestaskforce.org"
API_BASE_URL = "https://api.uspreventiveservicestaskforce.org"  # Requires API key
TIMEOUT = 30.0

# API key should be set via environment variable
import os
USPSTF_API_KEY = os.getenv('USPSTF_API_KEY')


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
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            return response.text
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return None


async def fetch_api(endpoint: str, params: Dict[str, Any] = None) -> Optional[Dict]:
    """
    Fetch data from USPSTF API (requires API key).

    Args:
        endpoint: API endpoint path
        params: Query parameters

    Returns:
        JSON response as dictionary or None if failed
    """
    if not USPSTF_API_KEY:
        return None

    headers = {
        'Authorization': f'Bearer {USPSTF_API_KEY}',
        'User-Agent': 'USPSTF-MCP-Server/1.0'
    }

    url = f"{API_BASE_URL}{endpoint}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params or {}, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"API Error: {str(e)}")
        return None


@mcp.tool(
    name="search_preventive_recommendations",
    description="Search USPSTF preventive care recommendations by topic, condition, or service type. Returns recommendations with grade ratings (A, B, C, D, I) indicating strength of evidence. Examples: cancer screening, diabetes, depression, tobacco use."
)
async def search_preventive_recommendations(topic: str, max_results: int = 20) -> dict:
    """
    Search USPSTF recommendations by topic or condition.

    Args:
        topic: Search term for preventive service (e.g., "breast cancer screening", "diabetes", "aspirin")
        max_results: Maximum number of results to return (default: 20, max: 50)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - query (str): The search term used
            - count (int): Number of results found
            - results (list): List of matching recommendations with:
                - title (str): Recommendation title
                - grade (str): USPSTF grade (A, B, C, D, I)
                - url (str): Link to full recommendation
                - date (str): Publication/update date
                - summary (str): Brief summary of recommendation
                - population (str): Target population
            - error (str|None): Error message if search failed
    """
    max_results = min(max_results, 50)

    # Try API first if available
    if USPSTF_API_KEY:
        api_data = await fetch_api('/recommendations/search', {'q': topic, 'limit': max_results})
        if api_data:
            results = []
            for item in api_data.get('results', [])[:max_results]:
                results.append({
                    'title': item.get('title', ''),
                    'grade': item.get('grade', 'Not specified'),
                    'url': item.get('url', ''),
                    'date': item.get('date', 'Not available'),
                    'summary': item.get('summary', ''),
                    'population': item.get('population', 'Not specified')
                })

            return {
                'success': True,
                'query': topic,
                'count': len(results),
                'results': results,
                'error': None
            }

    # Fallback to web scraping
    search_url = f"{BASE_URL}/uspstf/search?q={quote(topic)}"
    html = await fetch_page(search_url)

    if not html:
        return {
            'success': False,
            'query': topic,
            'count': 0,
            'results': [],
            'error': 'Failed to connect to USPSTF website. API key may be required for full access.'
        }

    soup = BeautifulSoup(html, 'html.parser')
    results = []

    # Find recommendation cards/items
    recommendation_items = soup.find_all(['article', 'div'], class_=re.compile(r'recommendation|result|card'))

    for item in recommendation_items[:max_results]:
        # Extract title and link
        title_elem = item.find(['h2', 'h3', 'a'], class_=re.compile(r'title|heading'))
        if not title_elem:
            title_elem = item.find('a')

        if not title_elem:
            continue

        title = title_elem.get_text(strip=True)
        link = title_elem.get('href', '') if title_elem.name == 'a' else ''

        if not link:
            link_elem = item.find('a', href=True)
            if link_elem:
                link = link_elem.get('href', '')

        # Make URL absolute
        if link and not link.startswith('http'):
            link = f"{BASE_URL}{link}" if link.startswith('/') else f"{BASE_URL}/{link}"

        # Extract grade
        grade = 'Not specified'
        grade_elem = item.find(['span', 'div'], class_=re.compile(r'grade|rating'))
        if grade_elem:
            grade_text = grade_elem.get_text(strip=True)
            # Extract letter grade (A, B, C, D, or I)
            grade_match = re.search(r'\b([ABCDI])\b', grade_text)
            if grade_match:
                grade = f"Grade {grade_match.group(1)}"

        # Extract date
        date = 'Not available'
        date_elem = item.find(['time', 'span', 'div'], class_=re.compile(r'date|published|updated'))
        if date_elem:
            date = date_elem.get_text(strip=True)

        # Extract summary
        summary = ''
        summary_elem = item.find(['p', 'div'], class_=re.compile(r'summary|description|excerpt'))
        if summary_elem:
            summary = summary_elem.get_text(strip=True)[:300]

        # Extract population
        population = 'Not specified'
        pop_elem = item.find(['span', 'div'], class_=re.compile(r'population|audience'))
        if pop_elem:
            population = pop_elem.get_text(strip=True)

        if title:
            results.append({
                'title': title,
                'grade': grade,
                'url': link,
                'date': date,
                'summary': summary,
                'population': population
            })

    if not results:
        return {
            'success': True,
            'query': topic,
            'count': 0,
            'results': [],
            'error': 'No recommendations found. Try different search terms or contact uspstfpda@ahrq.gov for API access.'
        }

    return {
        'success': True,
        'query': topic,
        'count': len(results),
        'results': results,
        'error': None
    }


@mcp.tool(
    name="get_uspstf_recommendation",
    description="Get detailed information about a specific USPSTF recommendation including rationale, evidence summary, clinical considerations, and implementation guidance."
)
async def get_uspstf_recommendation(identifier: str) -> dict:
    """
    Get detailed information about a specific USPSTF recommendation.

    Args:
        identifier: Recommendation identifier, title, or URL

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - title (str): Recommendation title
            - grade (str): USPSTF grade with explanation
            - url (str): Direct URL to the recommendation
            - population (str): Target population
            - date (str): Publication/update date
            - summary (str): Executive summary
            - rationale (str): Rationale for recommendation
            - clinical_considerations (str): Clinical implementation guidance
            - evidence_summary (str): Summary of supporting evidence
            - related_recommendations (list): Links to related recommendations
            - error (str|None): Error message if retrieval failed
    """
    # Determine URL
    if identifier.startswith('http'):
        url = identifier
    else:
        # Try to construct URL from identifier/title
        slug = identifier.lower().replace(' ', '-').replace('_', '-')
        url = f"{BASE_URL}/uspstf/recommendation/{slug}"

    # Try API first if available
    if USPSTF_API_KEY:
        api_data = await fetch_api(f'/recommendations/{identifier}')
        if api_data:
            return {
                'success': True,
                'title': api_data.get('title', ''),
                'grade': api_data.get('grade', '') + ' - ' + api_data.get('grade_definition', ''),
                'url': api_data.get('url', url),
                'population': api_data.get('population', 'Not specified'),
                'date': api_data.get('date', 'Not available'),
                'summary': api_data.get('summary', ''),
                'rationale': api_data.get('rationale', ''),
                'clinical_considerations': api_data.get('clinical_considerations', ''),
                'evidence_summary': api_data.get('evidence_summary', ''),
                'related_recommendations': api_data.get('related', []),
                'error': None
            }

    # Fallback to web scraping
    html = await fetch_page(url)

    if not html:
        return {
            'success': False,
            'title': '',
            'url': url,
            'error': 'Failed to retrieve recommendation. API access may be required.'
        }

    soup = BeautifulSoup(html, 'html.parser')

    # Extract title
    title = ''
    title_elem = soup.find('h1')
    if title_elem:
        title = title_elem.get_text(strip=True)

    # Extract grade
    grade = 'Not specified'
    grade_elem = soup.find(['div', 'span'], class_=re.compile(r'grade|rating'))
    if grade_elem:
        grade = grade_elem.get_text(strip=True)

    # Extract date
    date = 'Not available'
    date_elem = soup.find(['time', 'span'], class_=re.compile(r'date|published'))
    if date_elem:
        date = date_elem.get_text(strip=True)

    # Extract population
    population = 'Not specified'
    pop_elem = soup.find(['div', 'p'], class_=re.compile(r'population|audience'))
    if pop_elem:
        population = pop_elem.get_text(strip=True)

    # Helper function to extract section content
    def extract_section(section_keywords: List[str]) -> str:
        """Extract content from a section by heading keywords."""
        for heading in soup.find_all(['h2', 'h3']):
            heading_text = heading.get_text(strip=True).lower()
            if any(keyword.lower() in heading_text for keyword in section_keywords):
                content = []
                for sibling in heading.find_next_siblings():
                    if sibling.name in ['h2', 'h3']:
                        break
                    if sibling.name in ['p', 'div', 'li']:
                        text = sibling.get_text(strip=True)
                        if text:
                            content.append(text)
                return ' '.join(content)[:1000]
        return 'Not available'

    # Extract sections
    summary = extract_section(['summary', 'recommendation'])
    rationale = extract_section(['rationale', 'justification'])
    clinical_considerations = extract_section(['clinical', 'implementation', 'practice'])
    evidence_summary = extract_section(['evidence', 'supporting'])

    # Extract related recommendations
    related = []
    related_section = soup.find(['div', 'section'], class_=re.compile(r'related'))
    if related_section:
        for link in related_section.find_all('a', href=True)[:5]:
            related.append({
                'title': link.get_text(strip=True),
                'url': f"{BASE_URL}{link.get('href')}" if link.get('href', '').startswith('/') else link.get('href')
            })

    return {
        'success': True,
        'title': title,
        'grade': grade,
        'url': url,
        'population': population,
        'date': date,
        'summary': summary,
        'rationale': rationale,
        'clinical_considerations': clinical_considerations,
        'evidence_summary': evidence_summary,
        'related_recommendations': related,
        'error': None
    }


@mcp.tool(
    name="list_recommendation_topics",
    description="List available USPSTF recommendation topics and categories including cancer screening, cardiovascular prevention, behavioral counseling, and preventive medications."
)
async def list_recommendation_topics() -> dict:
    """
    List available USPSTF recommendation topics and categories.

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - categories (list): List of recommendation categories with:
                - name (str): Category name
                - description (str): Category description
                - url (str): Link to category page
                - count (int): Number of recommendations in category (if available)
            - error (str|None): Error message if retrieval failed
    """
    # Try API first
    if USPSTF_API_KEY:
        api_data = await fetch_api('/topics')
        if api_data:
            categories = []
            for topic in api_data.get('topics', []):
                categories.append({
                    'name': topic.get('name', ''),
                    'description': topic.get('description', ''),
                    'url': topic.get('url', ''),
                    'count': topic.get('count', 0)
                })

            return {
                'success': True,
                'categories': categories,
                'error': None
            }

    # Fallback to predefined categories (USPSTF standard categories)
    categories = [
        {
            'name': 'Cancer Screening',
            'description': 'Recommendations for various cancer screening tests including breast, colorectal, lung, cervical, prostate, and skin cancer',
            'url': f"{BASE_URL}/uspstf/topic_search_results?topic_status=P&searchterm=cancer+screening",
            'count': None
        },
        {
            'name': 'Cardiovascular Disease Prevention',
            'description': 'Recommendations for preventing cardiovascular disease including aspirin use, blood pressure screening, cholesterol screening, and statin use',
            'url': f"{BASE_URL}/uspstf/topic_search_results?topic_status=P&searchterm=cardiovascular",
            'count': None
        },
        {
            'name': 'Behavioral Counseling',
            'description': 'Recommendations for behavioral counseling interventions including tobacco cessation, alcohol misuse, diet, and physical activity',
            'url': f"{BASE_URL}/uspstf/topic_search_results?topic_status=P&searchterm=behavioral+counseling",
            'count': None
        },
        {
            'name': 'Preventive Medications',
            'description': 'Recommendations for preventive medication use including aspirin, statins, vitamin supplementation, and chemoprevention',
            'url': f"{BASE_URL}/uspstf/topic_search_results?topic_status=P&searchterm=preventive+medication",
            'count': None
        },
        {
            'name': 'Mental Health Screening',
            'description': 'Recommendations for screening for mental health conditions including depression, anxiety, suicide risk, and substance use disorders',
            'url': f"{BASE_URL}/uspstf/topic_search_results?topic_status=P&searchterm=mental+health",
            'count': None
        },
        {
            'name': 'Infectious Disease Prevention',
            'description': 'Recommendations for prevention and screening of infectious diseases including HIV, hepatitis, STIs, and tuberculosis',
            'url': f"{BASE_URL}/uspstf/topic_search_results?topic_status=P&searchterm=infectious+disease",
            'count': None
        },
        {
            'name': 'Pregnancy and Newborn Care',
            'description': 'Recommendations for prenatal care, newborn screening, and perinatal conditions',
            'url': f"{BASE_URL}/uspstf/topic_search_results?topic_status=P&searchterm=pregnancy",
            'count': None
        },
        {
            'name': 'Chronic Disease Screening',
            'description': 'Recommendations for screening for chronic conditions including diabetes, osteoporosis, obesity, and kidney disease',
            'url': f"{BASE_URL}/uspstf/topic_search_results?topic_status=P&searchterm=chronic+disease+screening",
            'count': None
        }
    ]

    return {
        'success': True,
        'categories': categories,
        'error': 'Showing predefined categories. For complete topic list, API access is recommended (contact uspstfpda@ahrq.gov)'
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
