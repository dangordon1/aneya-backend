#!/usr/bin/env python
"""
NHM Guidelines MCP Server

Provides access to clinical and operational guidelines from the National Health Mission (NHM),
Ministry of Health & Family Welfare, Government of India at https://nhm.gov.in

This server provides access to healthcare service guidelines, operational documents,
medical device specifications, and health program implementations for Indian healthcare providers.
"""

from fastmcp import FastMCP
import httpx
from bs4 import BeautifulSoup
from typing import Optional
from urllib.parse import quote, urljoin
import re
import sys
import json
from datetime import datetime

# Create MCP server instance with detailed instructions
mcp = FastMCP(
    "NHM-Guidelines",
    instructions="Search and retrieve NHM (National Health Mission) clinical and operational guidelines from India's Ministry of Health & Family Welfare. Provides comprehensive healthcare service guidelines, medical device specifications, disease control programs, facility management standards, and health program implementation documents specific to Indian public health system."
)

# Base URL for NHM
NHM_BASE_URL = "https://nhm.gov.in"
NHM_GUIDELINES_URL = f"{NHM_BASE_URL}/index1.php?lang=1&level=1&sublinkid=197&lid=136"
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
    name="search_nhm_guidelines",
    description="Search NHM (National Health Mission) clinical and operational guidelines by keyword. Returns healthcare service guidelines, medical device specifications, disease control programs, and health facility management standards specific to Indian public health system."
)
async def search_nhm_guidelines(keyword: str, max_results: int = 20) -> dict:
    """
    Search for NHM guidelines and operational documents by keyword or topic.

    NHM provides comprehensive healthcare guidelines including laboratory services,
    diagnostic services, medical devices, disease control programs, facility management,
    and community health initiatives tailored to the Indian healthcare context.

    Args:
        keyword: Search term (e.g., "laboratory", "diagnostic services", "dialysis", "medical devices", "telemedicine")
        max_results: Maximum number of results to return (default: 20, max: 50)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - query (str): The search keyword used
            - count (int): Number of results found
            - results (list): List of matching guidelines with title, url, description, category, file_size
            - error (str|None): Error message if search failed
    """
    max_results = min(max_results, 50)

    # Sanitize keyword: remove newlines and extra whitespace
    keyword_clean = " ".join(keyword.split()).lower()

    # Fetch the main guidelines page
    html = await fetch_page(NHM_GUIDELINES_URL)
    if not html:
        raise ValueError('Failed to fetch NHM guidelines page')

    soup = BeautifulSoup(html, 'lxml')
    results = []

    # Find the main content area
    content_area = soup.find(['div'], class_=re.compile(r'contentmain', re.IGNORECASE))
    if not content_area:
        content_area = soup

    # Find the table containing guidelines
    table = content_area.find('table')
    if not table:
        table = soup.find('table')

    if table:
        # Parse table rows
        rows = table.find_all('tr')

        for row in rows:
            cells = row.find_all('td')

            # Skip header rows or rows with wrong structure
            if len(cells) < 2:
                continue

            # First cell contains the title
            title_cell = cells[0]
            title = title_cell.get_text(strip=True)

            # Remove "New" indicators and extra whitespace
            title = re.sub(r'\s*New\s*', '', title, flags=re.IGNORECASE)
            title = ' '.join(title.split())

            # Skip empty titles or very short titles
            if not title or len(title) < 10:
                continue

            # Check if keyword matches the title (case-insensitive)
            if keyword_clean not in title.lower():
                continue

            # Second cell contains download link
            download_cell = cells[1] if len(cells) > 1 else cells[0]
            pdf_link = download_cell.find('a', href=True)

            if not pdf_link:
                # Try to find any link in the row
                pdf_link = row.find('a', href=re.compile(r'\.pdf', re.IGNORECASE))

            if not pdf_link:
                continue

            href = pdf_link.get('href', '')

            # Skip invalid links
            if not href or href in ['#', '/', 'javascript:void(0)']:
                continue

            # Construct full URL
            if not href.startswith('http'):
                full_url = urljoin(NHM_BASE_URL, href)
            else:
                full_url = href

            # Extract file size from download cell
            file_size = 'Unknown'
            download_text = download_cell.get_text()
            size_match = re.search(r'[\[\(]?\s*(\d+\.?\d*\s*(?:MB|KB|GB|mb|kb|gb))\s*[\]\)]?', download_text)
            if size_match:
                file_size = size_match.group(1).strip()

            # Extract category from context (look for nearest heading before this row)
            category = "NHM Guideline"
            heading = row.find_previous(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if heading:
                heading_text = heading.get_text(strip=True)
                if heading_text and len(heading_text) < 100:
                    category = heading_text

            # Create description
            description = f"{category}: {title}"

            results.append({
                'title': title,
                'url': full_url,
                'description': description[:200],
                'category': category,
                'file_size': file_size,
                'published_date': 'Not available'
            })

            if len(results) >= max_results:
                break

    if not results:
        return {
            'success': True,
            'query': keyword,
            'count': 0,
            'results': [],
            'error': 'No guidelines found matching the search term. Try broader terms like "laboratory", "diagnostic", "medical device", or "health program".'
        }

    return {
        'success': True,
        'query': keyword,
        'count': len(results),
        'results': results,
        'error': None
    }


@mcp.resource("nhm://guidelines/list")
async def list_nhm_guidelines() -> str:
    """
    List all available NHM guidelines and operational documents.

    Retrieves the complete list of available guidelines from the NHM repository,
    including laboratory services, diagnostic services, medical devices, disease
    control programs, facility management, and community health initiatives.

    Returns:
        JSON string containing:
            - success (bool): Whether the retrieval was successful
            - count (int): Number of guidelines found
            - guidelines (list): List of guidelines with title, url, category, file_size
            - error (str|None): Error message if retrieval failed
    """
    max_results = 100  # Fixed limit for resource

    # Fetch the main guidelines page
    html = await fetch_page(NHM_GUIDELINES_URL)
    if not html:
        raise ValueError('Failed to fetch NHM guidelines page')

    soup = BeautifulSoup(html, 'lxml')
    guidelines = []

    # Find the main content area
    content_area = soup.find(['div'], class_=re.compile(r'contentmain', re.IGNORECASE))
    if not content_area:
        content_area = soup

    # Find the table containing guidelines
    table = content_area.find('table')
    if not table:
        table = soup.find('table')

    if table:
        # Parse table rows
        rows = table.find_all('tr')

        for row in rows:
            cells = row.find_all('td')

            # Skip header rows or rows with wrong structure
            if len(cells) < 2:
                continue

            # First cell contains the title
            title_cell = cells[0]
            title = title_cell.get_text(strip=True)

            # Remove "New" indicators and extra whitespace
            title = re.sub(r'\s*New\s*', '', title, flags=re.IGNORECASE)
            title = ' '.join(title.split())

            # Skip empty titles, very short titles, or navigation text
            if not title or len(title) < 10:
                continue

            # Skip common navigation text
            if title.lower() in ['home', 'back', 'next', 'click here', 'download', 'read more']:
                continue

            # Second cell contains download link
            download_cell = cells[1] if len(cells) > 1 else cells[0]
            pdf_link = download_cell.find('a', href=True)

            if not pdf_link:
                # Try to find any link in the row
                pdf_link = row.find('a', href=re.compile(r'\.pdf', re.IGNORECASE))

            if not pdf_link:
                continue

            href = pdf_link.get('href', '')

            # Skip invalid links
            if not href or href in ['#', '/', 'javascript:void(0)']:
                continue

            # Construct full URL
            if not href.startswith('http'):
                full_url = urljoin(NHM_BASE_URL, href)
            else:
                full_url = href

            # Extract file size from download cell
            file_size = 'Unknown'
            download_text = download_cell.get_text()
            size_match = re.search(r'[\[\(]?\s*(\d+\.?\d*\s*(?:MB|KB|GB|mb|kb|gb))\s*[\]\)]?', download_text)
            if size_match:
                file_size = size_match.group(1).strip()

            # Extract category from context
            category = "NHM Guideline"
            heading = row.find_previous(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if heading:
                heading_text = heading.get_text(strip=True)
                if heading_text and len(heading_text) < 100:
                    category = heading_text

            guidelines.append({
                'title': title,
                'url': full_url,
                'category': category,
                'file_size': file_size
            })

            if len(guidelines) >= max_results:
                break

    # Remove duplicates based on URL
    seen_urls = set()
    unique_guidelines = []
    for guideline in guidelines:
        if guideline['url'] not in seen_urls:
            seen_urls.add(guideline['url'])
            unique_guidelines.append(guideline)

    import json

    if not unique_guidelines:
        return json.dumps({
            'success': True,
            'count': 0,
            'guidelines': [],
            'error': 'No guidelines found on the NHM page'
        })

    return json.dumps({
        'success': True,
        'count': len(unique_guidelines),
        'guidelines': unique_guidelines,
        'error': None
    })


@mcp.resource("nhm://guidelines/categories")
async def get_nhm_guideline_categories() -> str:
    """
    Get NHM guidelines organized by category.

    Returns guidelines grouped by topic areas such as:
    - Laboratory Services
    - Diagnostic Services
    - Medical Devices (Anesthesia, Cardiology, ENT, Ophthalmology, Radiotherapy)
    - Disease Control Programs (NCDs, Dialysis, Hemoglobinopathies)
    - Facility Management (Kayakalp, Mobile Medical Units)
    - Community Health (Rogi Kalyan Samities, Health Melas, Telemedicine)

    Returns:
        JSON string containing:
            - success (bool): Whether the retrieval was successful
            - categories (list): List of categories with name, description, guideline_count
            - total_guidelines (int): Total number of guidelines across all categories
            - error (str|None): Error message if retrieval failed
    """
    import json
    # Fetch the main guidelines page
    html = await fetch_page(NHM_GUIDELINES_URL)
    if not html:
        raise ValueError('Failed to fetch NHM guidelines page')

    soup = BeautifulSoup(html, 'lxml')
    categories_dict = {}

    # Find all headings and their associated links
    content_area = soup.find(['div', 'section', 'main'], id=re.compile(r'content|main', re.IGNORECASE))
    if not content_area:
        content_area = soup

    # Find all section headings
    headings = content_area.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

    for heading in headings:
        category_name = heading.get_text(strip=True)

        # Skip empty or very short headings
        if not category_name or len(category_name) < 5:
            continue

        # Find all links until the next heading
        guidelines_in_category = []
        for sibling in heading.find_next_siblings():
            if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                break

            links = sibling.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                title = link.get_text(strip=True)

                if href and title and len(title) > 5:
                    guidelines_in_category.append(title)

        # Only add category if it has guidelines
        if guidelines_in_category:
            if category_name not in categories_dict:
                categories_dict[category_name] = {
                    'name': category_name,
                    'guideline_count': len(guidelines_in_category),
                    'description': f"NHM guidelines related to {category_name.lower()}"
                }

    categories = list(categories_dict.values())
    total_guidelines = sum(cat['guideline_count'] for cat in categories)

    # If no categories found, return default categories
    if not categories:
        categories = [
            {
                'name': 'All Guidelines',
                'guideline_count': 0,
                'description': 'All NHM clinical and operational guidelines'
            }
        ]

    return json.dumps({
        'success': True,
        'categories': categories,
        'total_guidelines': total_guidelines,
        'error': None
    })


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
