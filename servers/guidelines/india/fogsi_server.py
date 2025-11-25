#!/usr/bin/env python
"""
FOGSI Guidelines MCP Server

Provides access to clinical guidelines from the Federation of Obstetric
and Gynaecological Societies of India (FOGSI) at https://www.fogsi.org

This server is specifically for Indian healthcare providers and users.
"""

from fastmcp import FastMCP
import httpx
from bs4 import BeautifulSoup
from typing import Optional
from urllib.parse import quote
import re
import sys
import json
from datetime import datetime

# Create MCP server instance with detailed instructions
mcp = FastMCP(
    "FOGSI-Guidelines",
    instructions="Search and retrieve FOGSI (Federation of Obstetric and Gynaecological Societies of India) clinical guidelines for obstetric and gynecological care. Provides evidence-based recommendations specific to Indian healthcare context.",
    dependencies=["httpx", "beautifulsoup4", "lxml"]
)

# Base URL for FOGSI
FOGSI_BASE_URL = "https://www.fogsi.org"
TIMEOUT = 30.0


async def fetch_page(url: str) -> Optional[str]:
    """
    Fetch a webpage with proper headers and error handling.

    Args:
        url: The URL to fetch

    Returns:
        HTML content as string or None if failed
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        return response.text


@mcp.tool(
    name="search_fogsi_guidelines",
    description="Search FOGSI (Federation of Obstetric and Gynaecological Societies of India) clinical guidelines by keyword. Returns evidence-based guidelines for obstetric and gynecological care specific to Indian healthcare context."
)
async def search_fogsi_guidelines(keyword: str, max_results: int = 10) -> dict:
    """
    Search for FOGSI clinical guidelines by keyword or topic.

    FOGSI provides evidence-based guidelines for obstetric and gynecological
    care tailored to the Indian healthcare context.

    Args:
        keyword: Search term (e.g., "pregnancy", "gestational diabetes", "pre-eclampsia", "postpartum hemorrhage")
        max_results: Maximum number of results to return (default: 10, max: 50)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - query (str): The search keyword used
            - count (int): Number of results found
            - results (list): List of matching guidelines with title, url, description, category, published_date
            - error (str|None): Error message if search failed
    """
    max_results = min(max_results, 50)

    # Sanitize keyword: remove newlines and extra whitespace
    keyword_clean = " ".join(keyword.split())

    # Construct search URL with proper URL encoding
    search_url = f"{FOGSI_BASE_URL}/?s={quote(keyword_clean)}"

    html = await fetch_page(search_url)
    if not html:
        raise ValueError('Failed to fetch search results from FOGSI website')

    soup = BeautifulSoup(html, 'lxml')
    results = []

    # Try to extract structured data from JSON-LD first (if available)
    script_tags = soup.find_all('script', type='application/ld+json')

    for script in script_tags:
        try:
            data = json.loads(script.string)

            # Check if this contains search results or articles
            if isinstance(data, dict) and ('itemListElement' in data or 'mainEntity' in data):
                items = data.get('itemListElement', []) or data.get('mainEntity', [])

                for item in items[:max_results]:
                    if isinstance(item, dict):
                        title = item.get('name') or item.get('headline', '')
                        url = item.get('url') or item.get('@id', '')
                        description = item.get('description', '')

                        if url and not url.startswith('http'):
                            url = FOGSI_BASE_URL + url

                        # Extract publication date if available
                        pub_date = item.get('datePublished') or item.get('dateModified', '')
                        if pub_date:
                            try:
                                dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                                pub_date = dt.strftime('%B %Y')
                            except Exception:
                                pass

                        if title and url:
                            results.append({
                                'title': title,
                                'url': url,
                                'description': description[:200] if description else "",
                                'category': 'FOGSI Guideline',
                                'published_date': pub_date if pub_date else 'Not available'
                            })

                if results:
                    break  # Found structured data, no need to check other scripts

        except (json.JSONDecodeError, KeyError):
            continue

    # Fallback: Parse HTML if JSON-LD approach didn't work
    if not results:
        articles = soup.find_all(['article', 'div'], class_=re.compile(r'post|article|result'), limit=max_results)

        for article in articles:
            # Extract title
            title_elem = article.find(['h1', 'h2', 'h3', 'h4'], class_=re.compile(r'title|heading|entry-title'))
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)

            # Extract URL
            link_elem = title_elem.find('a') or article.find('a')
            if not link_elem:
                continue

            url = link_elem.get('href', '')
            if url and not url.startswith('http'):
                url = FOGSI_BASE_URL + url

            # Extract description/excerpt
            desc_elem = article.find(['p', 'div'], class_=re.compile(r'excerpt|summary|description|entry-content'))
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # Extract category if available
            category_elem = article.find(['span', 'a'], class_=re.compile(r'category|tag'))
            category = category_elem.get_text(strip=True) if category_elem else "FOGSI Guideline"

            # Extract publication date
            date_elem = article.find(['time', 'span'], class_=re.compile(r'date|published'))
            pub_date = date_elem.get_text(strip=True) if date_elem else 'Not available'

            if title and url:
                results.append({
                    "title": title,
                    "url": url,
                    "description": description[:200] if description else "",
                    "category": category,
                    "published_date": pub_date
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
    name="get_fogsi_guideline_content",
    description="Retrieve detailed content for a specific FOGSI guideline including full text, sections, recommendations, and clinical guidance for obstetric and gynecological care."
)
async def get_fogsi_guideline_content(guideline_url: str) -> dict:
    """
    Get the full content of a specific FOGSI guideline.

    Args:
        guideline_url: Full URL to the FOGSI guideline page

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - title (str): Guideline title
            - url (str): Original URL
            - summary (str): Brief overview or summary
            - content (str): Full text content
            - sections (list): List of sections with headings and content
            - published_date (str): Publication date if available
            - error (str|None): Error message if retrieval failed
    """
    html = await fetch_page(guideline_url)
    if not html:
        raise ValueError('Failed to fetch guideline content from FOGSI website')

    soup = BeautifulSoup(html, 'lxml')

    # Extract title
    title = ''
    title_elem = soup.find(['h1', 'h2'], class_=re.compile(r'title|heading|entry-title'))
    if title_elem:
        title = title_elem.get_text(strip=True)

    # Extract summary/meta description
    summary = ''
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc:
        summary = meta_desc.get('content', '')

    if not summary:
        # Try to find introductory paragraph
        intro_elem = soup.find(['div', 'section'], class_=re.compile(r'summary|intro|abstract'))
        if intro_elem:
            paragraphs = intro_elem.find_all('p', limit=2)
            summary = ' '.join([p.get_text(strip=True) for p in paragraphs])

    # Extract publication date
    published_date = 'Not available'
    date_elem = soup.find(['time', 'span'], class_=re.compile(r'date|published'))
    if date_elem:
        published_date = date_elem.get_text(strip=True)
        # Try to format if it's an ISO date
        try:
            dt = datetime.fromisoformat(date_elem.get('datetime', published_date).replace('Z', '+00:00'))
            published_date = dt.strftime('%B %Y')
        except Exception:
            pass

    # Extract main content area
    content_elem = soup.find(['article', 'div', 'main'], class_=re.compile(r'content|post|article|entry-content'))
    if not content_elem:
        content_elem = soup.find('main') or soup.find('body')

    # Extract sections with headings and content
    sections = []
    if content_elem:
        headings = content_elem.find_all(['h1', 'h2', 'h3', 'h4', 'h5'])

        for heading in headings:
            section_title = heading.get_text(strip=True)

            # Get content until next heading
            section_content = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5']:
                    break
                if sibling.name in ['p', 'ul', 'ol', 'div', 'li']:
                    text = sibling.get_text(strip=True)
                    if text:
                        section_content.append(text)

            if section_title and section_content:
                sections.append({
                    "heading": section_title,
                    "content": "\n".join(section_content)
                })

    # Get full text content (limit to reasonable size)
    full_content = content_elem.get_text(separator="\n", strip=True) if content_elem else ""

    return {
        "success": True,
        "title": title if title else "Unknown",
        "url": guideline_url,
        "summary": summary[:500] + '...' if len(summary) > 500 else summary,
        "content": full_content[:2000] + '...' if len(full_content) > 2000 else full_content,
        "sections": sections[:15],  # Limit to first 15 sections
        "published_date": published_date,
        "error": None
    }


@mcp.tool(
    name="list_fogsi_categories",
    description="List available FOGSI guideline categories including Clinical Guidelines, Good Clinical Practice, Publications, and other obstetric/gynecological topic areas. Returns category names, URLs, and descriptions."
)
async def list_fogsi_categories() -> dict:
    """
    List available guideline categories from FOGSI.

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - categories (list): List of categories with name, url, description
            - total (int): Total number of categories found
            - error (str|None): Error message if retrieval failed
    """
    html = await fetch_page(FOGSI_BASE_URL)
    if not html:
        raise ValueError('Failed to fetch FOGSI homepage')

    soup = BeautifulSoup(html, 'lxml')
    categories = []

    # Look for navigation menu or category links
    nav_elem = soup.find(['nav', 'ul', 'div'], class_=re.compile(r'menu|nav|categories|primary'))
    if nav_elem:
        links = nav_elem.find_all('a')

        for link in links:
            category_name = link.get_text(strip=True)
            category_url = link.get('href', '')

            # Skip empty links, home links, and anchor links
            if not category_name or not category_url or category_url in ['#', '/', FOGSI_BASE_URL]:
                continue

            if category_url and not category_url.startswith('http'):
                category_url = FOGSI_BASE_URL + category_url

            # Extract description from title attribute if available
            description = link.get('title', '')

            if category_name and category_url and len(category_name) > 2:
                categories.append({
                    "name": category_name,
                    "url": category_url,
                    "description": description
                })

    # Remove duplicates based on URL
    seen_urls = set()
    unique_categories = []
    for cat in categories:
        if cat['url'] not in seen_urls:
            seen_urls.add(cat['url'])
            unique_categories.append(cat)

    # Fallback: Common FOGSI categories if none found
    if not unique_categories:
        unique_categories = [
            {
                "name": "All Guidelines",
                "url": f"{FOGSI_BASE_URL}/guidelines/",
                "description": "All FOGSI clinical guidelines and recommendations"
            },
            {
                "name": "Clinical Guidelines",
                "url": f"{FOGSI_BASE_URL}/clinical-guidelines/",
                "description": "Evidence-based clinical practice guidelines for obstetrics and gynecology"
            },
            {
                "name": "Good Clinical Practice",
                "url": f"{FOGSI_BASE_URL}/good-clinical-practice/",
                "description": "Best practices and clinical recommendations"
            },
            {
                "name": "Focus",
                "url": f"{FOGSI_BASE_URL}/focus/",
                "description": "FOGSI focus publications and special topics"
            },
            {
                "name": "Publications",
                "url": f"{FOGSI_BASE_URL}/publications/",
                "description": "Research publications and academic resources"
            }
        ]

    return {
        "success": True,
        "categories": unique_categories,
        "total": len(unique_categories),
        "error": None
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
