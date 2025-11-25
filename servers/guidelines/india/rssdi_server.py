#!/usr/bin/env python
"""
RSSDI Guidelines MCP Server

This MCP server provides tools to search and access RSSDI (Research Society for
the Study of Diabetes in India) clinical guidelines. RSSDI is the premier Indian
organization for diabetes research and care, providing India-specific guidelines
for diabetes management, complications, screening, and co-morbidities.

Uses web scraping to retrieve published guidelines from www.rssdi.in.
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
    "RSSDI-Guidelines",
    instructions="""Search and retrieve RSSDI (Research Society for the Study of Diabetes in India)
    clinical guidelines with comprehensive diabetes management protocols, screening recommendations,
    and treatment algorithms specific to the Indian population. Covers type 1 and type 2 diabetes,
    gestational diabetes, diabetic complications (retinopathy, nephropathy, neuropathy, foot care),
    and co-morbidities (cardiovascular disease, hypertension, dyslipidemia)."""
)

# RSSDI URLs
BASE_URL = "https://www.rssdi.in"
GUIDELINES_URL = f"{BASE_URL}/newwebsite/page.php?id=114"  # Clinical practice recommendations
TIMEOUT = 30.0
RATE_LIMIT_DELAY = 1.0  # 1 second delay between requests


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
        'Referer': BASE_URL
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
    name="search_diabetes_guidelines",
    description="Search RSSDI diabetes management guidelines by topic or keyword. Returns matching guidelines for diabetes screening, diagnosis, treatment, complications (retinopathy, nephropathy, neuropathy, foot), gestational diabetes, pediatric diabetes, and co-morbidities."
)
async def search_diabetes_guidelines(keyword: str, max_results: int = 20) -> dict:
    """
    Search RSSDI diabetes guidelines by keyword or topic.

    Args:
        keyword: Search term or topic (e.g., "type 2 diabetes", "retinopathy", "insulin", "screening", "HbA1c")
        max_results: Maximum number of results to return (default: 20, max: 50)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - query (str): The search keyword used
            - count (int): Number of results found
            - results (list): List of matching guidelines with title, topic, url, year, document_type
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
            'error': 'Failed to fetch RSSDI guidelines page'
        }

    soup = BeautifulSoup(html, 'html.parser')

    # Look for guideline links - typically PDFs or document links
    guideline_links = soup.find_all('a', href=True)

    seen_urls = set()
    keyword_lower = keyword_clean.lower()

    for link in guideline_links:
        href = link.get('href', '')
        if not href:
            continue

        link_text = link.get_text(strip=True)

        # Skip short links (navigation, etc.)
        if len(link_text) < 10:
            continue

        # Build full URL
        full_url = urljoin(BASE_URL, href)

        # Skip duplicates
        if full_url in seen_urls:
            continue

        # Get parent context
        parent = link.find_parent(['li', 'tr', 'div', 'p', 'section'])
        context_text = parent.get_text(strip=True) if parent else link_text

        # Check if keyword matches
        if keyword_lower in context_text.lower() or keyword_lower in link_text.lower():
            seen_urls.add(full_url)

            # Extract year from text
            year_match = re.search(r'\b(20\d{2})\b', context_text)
            year = year_match.group(1) if year_match else 'Not specified'

            # Determine topic from content
            topic = 'General Diabetes Management'
            topic_keywords = {
                'Type 2 Diabetes': ['type 2', 't2d', 't2dm'],
                'Type 1 Diabetes': ['type 1', 't1d', 't1dm'],
                'Gestational Diabetes': ['gestational', 'gdm', 'pregnancy'],
                'Diabetic Retinopathy': ['retinopathy', 'eye', 'vision'],
                'Diabetic Nephropathy': ['nephropathy', 'kidney', 'renal'],
                'Diabetic Neuropathy': ['neuropathy', 'nerve', 'peripheral'],
                'Diabetic Foot': ['foot', 'ulcer', 'amputation'],
                'Cardiovascular': ['cardiovascular', 'heart', 'cvd', 'cardiac'],
                'Screening': ['screening', 'diagnosis', 'detection'],
                'Insulin Therapy': ['insulin', 'basal', 'bolus'],
                'Oral Medications': ['metformin', 'sulfonylurea', 'dpp-4', 'sglt2', 'glp-1']
            }

            for topic_name, keywords in topic_keywords.items():
                if any(kw in context_text.lower() for kw in keywords):
                    topic = topic_name
                    break

            # Determine document type
            doc_type = 'PDF' if href.lower().endswith('.pdf') else 'Web Page'

            results.append({
                'title': link_text[:200] if len(link_text) > 200 else link_text,
                'topic': topic,
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
            'error': 'No RSSDI diabetes guidelines found matching the search term'
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
    description="Get detailed content for a specific RSSDI diabetes guideline by URL. Returns management protocols, screening criteria, treatment algorithms, and medication recommendations specific to Indian diabetes patients."
)
async def get_guideline_content(guideline_url: str) -> dict:
    """
    Get detailed information about a specific RSSDI guideline.

    Args:
        guideline_url: Full URL to the guideline (PDF or web page)

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - title (str): Guideline title
            - url (str): Direct URL to the guideline
            - topic (str): Main topic covered
            - content (str): Main guideline content/summary
            - key_recommendations (str): Key clinical recommendations
            - target_population (str): Target patient population
            - screening_criteria (str): Screening/diagnostic criteria if applicable
            - treatment_algorithm (str): Treatment approach
            - document_type (str): Type of document
            - error (str|None): Error message if retrieval failed
    """
    if not guideline_url:
        return {
            'success': False,
            'title': '',
            'url': '',
            'topic': '',
            'content': '',
            'key_recommendations': '',
            'target_population': '',
            'screening_criteria': '',
            'treatment_algorithm': '',
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
            'topic': 'Diabetes Management',
            'content': 'PDF document - download required for full content. This RSSDI guideline contains India-specific diabetes management recommendations.',
            'key_recommendations': 'Please download the PDF to view detailed recommendations',
            'target_population': 'Indian diabetes patients',
            'screening_criteria': 'Please download the PDF to view screening criteria',
            'treatment_algorithm': 'Please download the PDF to view treatment algorithms',
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
            'topic': '',
            'content': '',
            'key_recommendations': '',
            'target_population': '',
            'screening_criteria': '',
            'treatment_algorithm': '',
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
        title = title_tag.get_text(strip=True) if title_tag else 'RSSDI Guideline'

    # Extract main content
    content = ''
    main_content = soup.find(['main', 'article', 'div'], class_=re.compile(r'content|main|guideline', re.I))
    if main_content:
        paragraphs = main_content.find_all('p', limit=10)
        content = ' '.join([p.get_text(strip=True) for p in paragraphs])

    if not content:
        paragraphs = soup.find_all('p', limit=10)
        content = ' '.join([p.get_text(strip=True) for p in paragraphs])

    # Extract key recommendations
    key_recommendations = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['recommendation', 'key point', 'summary', 'guideline']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            key_recommendations = ' '.join(content_parts)
            if key_recommendations:
                break

    # Extract screening criteria
    screening_criteria = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['screening', 'diagnosis', 'criteria', 'detection']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            screening_criteria = ' '.join(content_parts)
            if screening_criteria:
                break

    # Extract treatment algorithm
    treatment_algorithm = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['treatment', 'management', 'therapy', 'algorithm']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            treatment_algorithm = ' '.join(content_parts)
            if treatment_algorithm:
                break

    # Determine topic
    topic = 'Diabetes Management'
    if 'type 2' in title.lower():
        topic = 'Type 2 Diabetes'
    elif 'type 1' in title.lower():
        topic = 'Type 1 Diabetes'
    elif 'gestational' in title.lower():
        topic = 'Gestational Diabetes'
    elif 'retinopathy' in title.lower():
        topic = 'Diabetic Retinopathy'
    elif 'nephropathy' in title.lower():
        topic = 'Diabetic Nephropathy'
    elif 'neuropathy' in title.lower():
        topic = 'Diabetic Neuropathy'
    elif 'foot' in title.lower():
        topic = 'Diabetic Foot Care'

    return {
        'success': True,
        'title': title,
        'url': guideline_url,
        'topic': topic,
        'content': content[:1500] + '...' if len(content) > 1500 else content,
        'key_recommendations': key_recommendations[:1000] + '...' if len(key_recommendations) > 1000 else key_recommendations,
        'target_population': 'Indian diabetes patients',
        'screening_criteria': screening_criteria[:800] + '...' if len(screening_criteria) > 800 else screening_criteria,
        'treatment_algorithm': treatment_algorithm[:1200] + '...' if len(treatment_algorithm) > 1200 else treatment_algorithm,
        'document_type': 'Web Page',
        'error': None
    }


@mcp.tool(
    name="list_guideline_topics",
    description="List available RSSDI guideline topics covering all aspects of diabetes care including screening, diagnosis, type 1 and 2 diabetes, gestational diabetes, complications, co-morbidities, and special populations."
)
async def list_guideline_topics() -> dict:
    """
    List available RSSDI diabetes guideline topics.

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - topics (list): List of guideline topics with name, description, key_areas, url
            - error (str|None): Error message if retrieval failed
    """
    topics = [
        {
            'name': 'Type 2 Diabetes Management',
            'description': 'Comprehensive management of type 2 diabetes in Indian adults',
            'key_areas': ['Lifestyle modification', 'Oral medications', 'Insulin therapy', 'Glycemic targets', 'Monitoring'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Type 1 Diabetes Management',
            'description': 'Guidelines for managing type 1 diabetes across age groups',
            'key_areas': ['Insulin regimens', 'Continuous glucose monitoring', 'Hypoglycemia management', 'Psychosocial support'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Gestational Diabetes Mellitus (GDM)',
            'description': 'Screening and management of diabetes in pregnancy',
            'key_areas': ['Screening criteria', 'Diagnostic thresholds', 'Blood glucose targets', 'Insulin in pregnancy', 'Postpartum care'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Diabetic Retinopathy',
            'description': 'Prevention, screening, and management of diabetic eye disease',
            'key_areas': ['Screening protocols', 'Laser therapy', 'Anti-VEGF therapy', 'Referral criteria'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Diabetic Nephropathy',
            'description': 'Kidney disease prevention and management in diabetes',
            'key_areas': ['Screening for albuminuria', 'Blood pressure control', 'RAAS blockade', 'CKD staging', 'Dialysis'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Diabetic Neuropathy',
            'description': 'Management of peripheral and autonomic neuropathy',
            'key_areas': ['Screening methods', 'Pain management', 'Autonomic neuropathy', 'Foot care'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Diabetic Foot Care',
            'description': 'Prevention and management of diabetic foot complications',
            'key_areas': ['Foot examination', 'Risk stratification', 'Ulcer management', 'Infection treatment', 'Amputation prevention'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Cardiovascular Disease in Diabetes',
            'description': 'Managing cardiovascular risk and disease in diabetic patients',
            'key_areas': ['Risk assessment', 'Lipid management', 'Antiplatelet therapy', 'Blood pressure targets'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Diabetes Screening and Diagnosis',
            'description': 'Criteria for screening and diagnosing diabetes in India',
            'key_areas': ['Risk factors', 'Screening tests', 'HbA1c criteria', 'OGTT interpretation', 'Prediabetes'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Hypoglycemia Management',
            'description': 'Prevention and treatment of low blood sugar',
            'key_areas': ['Risk factors', 'Symptoms', 'Treatment protocols', 'Patient education', 'Severe hypoglycemia'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Pediatric Diabetes',
            'description': 'Special considerations for children and adolescents with diabetes',
            'key_areas': ['Growth monitoring', 'School management', 'Family involvement', 'Transition to adult care'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Elderly Diabetes Care',
            'description': 'Tailored management for older adults with diabetes',
            'key_areas': ['Glycemic targets', 'Polypharmacy', 'Fall prevention', 'Cognitive assessment', 'Frailty'],
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
