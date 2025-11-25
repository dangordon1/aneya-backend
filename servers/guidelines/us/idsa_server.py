#!/usr/bin/env python
"""
IDSA (Infectious Diseases Society of America) Guidelines MCP Server

This MCP server provides tools to search and access IDSA clinical practice guidelines
for infectious diseases. IDSA publishes evidence-based guidelines developed by expert
panels on the diagnosis and treatment of various infectious diseases.

Uses web scraping to retrieve published guidance from https://www.idsociety.org/
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
    "IDSA-Guidelines",
    instructions="Search and retrieve IDSA (Infectious Diseases Society of America) clinical practice guidelines for infectious disease diagnosis, treatment, and antimicrobial therapy including pneumonia, sepsis, UTI, endocarditis, and more"
)

# IDSA URLs
BASE_URL = "https://www.idsociety.org"
GUIDELINES_URL = f"{BASE_URL}/practice-guideline/practice-guidelines"
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
        # Add rate limiting
        await asyncio.sleep(0.5)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            return response.text
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return None


@mcp.tool(
    name="search_idsa_guidelines",
    description="Search IDSA clinical practice guidelines by disease, infection type, or treatment topic. Returns infectious disease guidelines for bacterial, viral, fungal, and parasitic infections including antimicrobial therapy recommendations."
)
async def search_idsa_guidelines(keyword: str, max_results: int = 20) -> dict:
    """
    Search IDSA guidelines by keyword or topic.

    Args:
        keyword: Search term (e.g., "pneumonia", "sepsis", "UTI", "endocarditis", "candidiasis")
        max_results: Maximum number of results to return (default: 20, max: 50)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - query (str): The search keyword used
            - count (int): Number of results found
            - results (list): List of matching guidelines with:
                - title (str): Guideline title
                - url (str): Full URL to the guideline
                - year (str): Publication year
                - category (str): Disease category
                - summary (str): Brief summary if available
            - error (str|None): Error message if search failed
    """
    max_results = min(max_results, 50)

    # Clean keyword
    keyword_clean = " ".join(keyword.split())

    # Try guidelines listing page first
    html = await fetch_page(GUIDELINES_URL)
    if not html:
        return {
            'success': False,
            'query': keyword,
            'count': 0,
            'results': [],
            'error': 'Failed to connect to IDSA website'
        }

    soup = BeautifulSoup(html, 'html.parser')
    results = []

    # Find guideline items
    guideline_items = soup.find_all(['article', 'div', 'li'], class_=re.compile(r'guideline|publication|resource'))

    # If no specific items found, look for all links in main content
    if not guideline_items:
        main_content = soup.find(['main', 'div'], class_=re.compile(r'content|main|body'))
        if main_content:
            guideline_items = main_content.find_all(['div', 'li'])

    for item in guideline_items:
        # Extract title and link
        title_elem = item.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'title|heading|name'))
        if not title_elem:
            title_elem = item.find('a', href=re.compile(r'guideline|practice|publication'))

        if not title_elem:
            continue

        title = title_elem.get_text(strip=True)

        # Filter by keyword
        if keyword_clean.lower() not in title.lower():
            continue

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

        # Extract year
        year = 'Not available'
        year_match = re.search(r'\b(20\d{2})\b', title)
        if year_match:
            year = year_match.group(1)
        else:
            year_elem = item.find(['span', 'time'], class_=re.compile(r'year|date'))
            if year_elem:
                year_text = year_elem.get_text(strip=True)
                year_match = re.search(r'\b(20\d{2})\b', year_text)
                if year_match:
                    year = year_match.group(1)

        # Extract category
        category = 'Infectious Diseases'
        # Try to categorize based on title keywords
        title_lower = title.lower()
        if any(term in title_lower for term in ['respiratory', 'pneumonia', 'influenza']):
            category = 'Respiratory Infections'
        elif any(term in title_lower for term in ['uti', 'urinary', 'pyelonephritis', 'cystitis']):
            category = 'Urinary Tract Infections'
        elif any(term in title_lower for term in ['bloodstream', 'sepsis', 'bacteremia', 'endocarditis']):
            category = 'Bloodstream Infections'
        elif any(term in title_lower for term in ['skin', 'soft tissue', 'abscess', 'cellulitis']):
            category = 'Skin and Soft Tissue Infections'
        elif any(term in title_lower for term in ['cns', 'meningitis', 'encephalitis', 'brain']):
            category = 'CNS Infections'
        elif any(term in title_lower for term in ['fungal', 'candida', 'aspergillus']):
            category = 'Fungal Infections'
        elif any(term in title_lower for term in ['hiv', 'opportunistic']):
            category = 'HIV and Opportunistic Infections'
        elif any(term in title_lower for term in ['antimicrobial', 'antibiotic', 'stewardship']):
            category = 'Antimicrobial Stewardship'

        # Extract summary
        summary = ''
        summary_elem = item.find(['p', 'div'], class_=re.compile(r'summary|abstract|description'))
        if summary_elem:
            summary = summary_elem.get_text(strip=True)[:300]

        if title and link:
            results.append({
                'title': title,
                'url': link,
                'year': year,
                'category': category,
                'summary': summary
            })

        if len(results) >= max_results:
            break

    # If no results from browsing, try search
    if not results:
        search_url = f"{BASE_URL}/search?search_api_fulltext={quote(keyword_clean)}"
        html = await fetch_page(search_url)

        if html:
            soup = BeautifulSoup(html, 'html.parser')
            search_results = soup.find_all(['div', 'article'], class_=re.compile(r'search-result|result-item'))

            for item in search_results[:max_results]:
                title_elem = item.find(['h2', 'h3', 'a'])
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

                if link and not link.startswith('http'):
                    link = f"{BASE_URL}{link}" if link.startswith('/') else link

                # Only include if it appears to be a guideline
                if 'guideline' in title.lower() or 'practice' in title.lower():
                    results.append({
                        'title': title,
                        'url': link,
                        'year': 'Not available',
                        'category': 'Infectious Diseases',
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
    name="get_guideline_detail",
    description="Get detailed information about a specific IDSA guideline including recommendations, diagnostic criteria, treatment protocols, and antimicrobial therapy guidance."
)
async def get_guideline_detail(identifier: str) -> dict:
    """
    Get detailed information about a specific IDSA guideline.

    Args:
        identifier: Guideline URL, title, or identifier

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - title (str): Guideline title
            - url (str): Direct URL to the guideline
            - year (str): Publication year
            - authors (str): Guideline authors/panel
            - summary (str): Executive summary
            - recommendations (list): Key recommendations
            - sections (list): Guideline sections with content
            - related_guidelines (list): Related IDSA guidelines
            - error (str|None): Error message if retrieval failed
    """
    # Determine URL
    if identifier.startswith('http'):
        url = identifier
    else:
        # Try to search for it
        search_result = await search_idsa_guidelines(identifier, max_results=1)
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

    # Extract year
    year = 'Not available'
    year_match = re.search(r'\b(20\d{2})\b', title)
    if year_match:
        year = year_match.group(1)
    else:
        date_elem = soup.find(['time', 'span'], class_=re.compile(r'date|year|published'))
        if date_elem:
            date_text = date_elem.get_text(strip=True)
            year_match = re.search(r'\b(20\d{2})\b', date_text)
            if year_match:
                year = year_match.group(1)

    # Extract authors
    authors = 'Not specified'
    author_elem = soup.find(['div', 'section', 'p'], class_=re.compile(r'author|contributor|panel'))
    if author_elem:
        authors = author_elem.get_text(strip=True)[:300]

    # Extract summary
    summary = ''
    summary_elem = soup.find(['div', 'section'], class_=re.compile(r'summary|abstract|executive|overview'))
    if summary_elem:
        paragraphs = summary_elem.find_all('p', limit=3)
        summary = ' '.join([p.get_text(strip=True) for p in paragraphs])

    if not summary:
        # Get first few paragraphs from main content
        main_content = soup.find(['main', 'article', 'div'], class_=re.compile(r'content|body|main'))
        if main_content:
            paragraphs = main_content.find_all('p', limit=3)
            summary = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

    # Extract recommendations
    recommendations = []
    rec_section = soup.find(['div', 'section'], class_=re.compile(r'recommendation|key-point'))
    if rec_section:
        # Look for numbered or bulleted lists
        rec_items = rec_section.find_all(['li', 'p'])
        for item in rec_items[:15]:
            text = item.get_text(strip=True)
            if text and len(text) > 20:
                recommendations.append(text[:500])

    # If no recommendations found, look for strong/bold statements
    if not recommendations:
        strong_statements = soup.find_all(['strong', 'b'])
        for statement in strong_statements[:10]:
            text = statement.get_text(strip=True)
            if len(text) > 30 and len(text) < 500:
                recommendations.append(text)

    # Extract sections
    sections = []
    headings = soup.find_all(['h2', 'h3'], limit=20)
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
                    'content': ' '.join(content)[:700]
                })

            if len(sections) >= 10:
                break

    # Extract related guidelines
    related = []
    related_section = soup.find(['div', 'aside', 'section'], class_=re.compile(r'related|see-also|additional'))
    if related_section:
        for link in related_section.find_all('a', href=True)[:5]:
            title = link.get_text(strip=True)
            if title and len(title) > 10:
                related.append({
                    'title': title,
                    'url': f"{BASE_URL}{link.get('href')}" if link.get('href', '').startswith('/') else link.get('href')
                })

    return {
        'success': True,
        'title': title,
        'url': url,
        'year': year,
        'authors': authors,
        'summary': summary[:1000] if summary else 'Not available',
        'recommendations': recommendations,
        'sections': sections,
        'related_guidelines': related,
        'error': None
    }


@mcp.tool(
    name="list_idsa_categories",
    description="List IDSA guideline categories organized by infection site, organism type, and special populations. Includes respiratory, bloodstream, CNS, fungal, antimicrobial stewardship, and more."
)
async def list_idsa_categories() -> dict:
    """
    List available IDSA guideline categories and topics.

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - categories (list): List of guideline categories with:
                - name (str): Category name
                - description (str): Category description
                - example_topics (list): Example guideline topics in this category
            - error (str|None): Error message if retrieval failed
    """
    categories = [
        {
            'name': 'Respiratory Tract Infections',
            'description': 'Guidelines for pneumonia, influenza, and other respiratory infections',
            'example_topics': [
                'Community-Acquired Pneumonia',
                'Healthcare-Associated Pneumonia',
                'Influenza',
                'Aspergillosis',
                'COVID-19'
            ]
        },
        {
            'name': 'Bloodstream and Cardiovascular Infections',
            'description': 'Guidelines for bacteremia, sepsis, endocarditis, and vascular infections',
            'example_topics': [
                'Sepsis and Septic Shock',
                'Infective Endocarditis',
                'Intravascular Catheter-Related Infections',
                'Bloodstream Infections'
            ]
        },
        {
            'name': 'Urinary Tract Infections',
            'description': 'Guidelines for cystitis, pyelonephritis, and catheter-associated UTIs',
            'example_topics': [
                'Acute Uncomplicated Cystitis',
                'Pyelonephritis',
                'Catheter-Associated UTI',
                'Recurrent UTI'
            ]
        },
        {
            'name': 'Central Nervous System Infections',
            'description': 'Guidelines for meningitis, encephalitis, and brain abscesses',
            'example_topics': [
                'Bacterial Meningitis',
                'Healthcare-Associated Ventriculitis and Meningitis',
                'Encephalitis',
                'Brain Abscess'
            ]
        },
        {
            'name': 'Skin and Soft Tissue Infections',
            'description': 'Guidelines for cellulitis, abscesses, and surgical site infections',
            'example_topics': [
                'Skin and Soft Tissue Infections',
                'Diabetic Foot Infections',
                'Necrotizing Fasciitis',
                'Surgical Site Infections'
            ]
        },
        {
            'name': 'Intra-Abdominal Infections',
            'description': 'Guidelines for peritonitis, appendicitis, and abdominal abscesses',
            'example_topics': [
                'Complicated Intra-Abdominal Infections',
                'Clostridium difficile Infection',
                'Peritonitis'
            ]
        },
        {
            'name': 'Fungal Infections',
            'description': 'Guidelines for candidiasis, aspergillosis, and other mycoses',
            'example_topics': [
                'Candidiasis',
                'Aspergillosis',
                'Cryptococcosis',
                'Endemic Mycoses'
            ]
        },
        {
            'name': 'HIV and Opportunistic Infections',
            'description': 'Guidelines for HIV-related infections and prophylaxis',
            'example_topics': [
                'Opportunistic Infections in HIV',
                'HIV Prevention',
                'Antiretroviral Therapy'
            ]
        },
        {
            'name': 'Antimicrobial Stewardship',
            'description': 'Guidelines for appropriate antimicrobial use and resistance prevention',
            'example_topics': [
                'Antimicrobial Stewardship Programs',
                'Appropriate Antibiotic Use',
                'Multidrug-Resistant Organisms',
                'Outpatient Antibiotic Prescribing'
            ]
        },
        {
            'name': 'Sexually Transmitted Infections',
            'description': 'Guidelines for diagnosis and treatment of STIs in collaboration with CDC',
            'example_topics': [
                'Syphilis',
                'Genital Herpes',
                'Pelvic Inflammatory Disease'
            ]
        },
        {
            'name': 'Bone and Joint Infections',
            'description': 'Guidelines for osteomyelitis, septic arthritis, and prosthetic joint infections',
            'example_topics': [
                'Osteomyelitis',
                'Septic Arthritis',
                'Prosthetic Joint Infection'
            ]
        },
        {
            'name': 'Immunocompromised Host',
            'description': 'Guidelines for infections in transplant recipients and neutropenic patients',
            'example_topics': [
                'Febrile Neutropenia',
                'Solid Organ Transplant Infections',
                'Hematopoietic Cell Transplant Infections'
            ]
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
