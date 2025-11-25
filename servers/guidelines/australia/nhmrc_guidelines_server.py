#!/usr/bin/env python
"""
MCP Server for NHMRC Guidelines.

Provides tools to search and access Australian National Health and Medical Research Council (NHMRC)
approved clinical guidelines. Scrapes data from the NHMRC website to provide information about
evidence-based health guidelines used across Australia.
"""

import requests
from bs4 import BeautifulSoup
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin
from fastmcp import FastMCP
from mcp_utils import print_stderr

# Initialize FastMCP server with proper name and instructions
mcp = FastMCP(
    "NHMRC_Guidelines"
)

# Base URL for NHMRC website
BASE_URL = "https://www.nhmrc.gov.au"
GUIDELINES_URL = f"{BASE_URL}/guidelinesforguidelines/nhmrc-approval/nhmrc-approved-guidelines"

# Request headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}


def fetch_guidelines_page(retries: int = 3) -> Optional[BeautifulSoup]:
    """
    Fetch and parse the NHMRC approved guidelines page with retry logic.

    Args:
        retries: Number of retry attempts if request fails

    Returns:
        BeautifulSoup object of the page or None if failed
    """
    for attempt in range(retries):
        try:
            response = requests.get(GUIDELINES_URL, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'lxml')
        except requests.Timeout:
            if attempt < retries - 1:
                print_stderr(f"Timeout on attempt {attempt + 1}, retrying...")
                continue
            else:
                print_stderr(f"Error fetching guidelines page: Timeout after {retries} attempts")
                return None
        except requests.RequestException as e:
            print_stderr(f"Error fetching guidelines page: {e}")
            return None
    return None


def extract_guidelines_from_soup(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Extract guideline information from the parsed HTML.

    Args:
        soup: BeautifulSoup object of the guidelines page

    Returns:
        List of dictionaries containing guideline information
    """
    guidelines = []

    # Try multiple strategies to find guidelines
    # Strategy 1: Look for table rows (common pattern for guideline lists)
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        for row in rows[1:]:  # Skip header row
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                title_cell = cells[0]

                # Extract title and link
                title_link = title_cell.find('a')
                if title_link:
                    title = title_link.get_text(strip=True)
                    link = title_link.get('href', '')
                    if link and not link.startswith('http'):
                        link = urljoin(BASE_URL, link)
                else:
                    title = title_cell.get_text(strip=True)
                    link = ""

                # Extract additional info from other cells
                info = {}
                if len(cells) > 1:
                    info['organisation'] = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                if len(cells) > 2:
                    info['date'] = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                if len(cells) > 3:
                    info['status'] = cells[3].get_text(strip=True) if len(cells) > 3 else ""

                if title:
                    guidelines.append({
                        'title': title,
                        'link': link,
                        **info
                    })

    # Strategy 2: Look for list items with links (alternative pattern)
    if not guidelines:
        content_divs = soup.find_all(['div', 'section'], class_=lambda x: x and ('content' in x.lower() or 'guideline' in x.lower()))
        for div in content_divs:
            list_items = div.find_all('li')
            for item in list_items:
                link_tag = item.find('a')
                if link_tag:
                    title = link_tag.get_text(strip=True)
                    link = link_tag.get('href', '')
                    if link and not link.startswith('http'):
                        link = urljoin(BASE_URL, link)

                    # Get any additional text in the list item
                    full_text = item.get_text(strip=True)
                    description = full_text.replace(title, '').strip()

                    guidelines.append({
                        'title': title,
                        'link': link,
                        'description': description
                    })

    # Strategy 3: Look for article or content sections
    if not guidelines:
        articles = soup.find_all(['article', 'section'])
        for article in articles:
            heading = article.find(['h2', 'h3', 'h4'])
            if heading:
                title = heading.get_text(strip=True)
                link_tag = article.find('a')
                link = ''
                if link_tag:
                    link = link_tag.get('href', '')
                    if link and not link.startswith('http'):
                        link = urljoin(BASE_URL, link)

                # Get description from paragraph
                description = ''
                p_tag = article.find('p')
                if p_tag:
                    description = p_tag.get_text(strip=True)

                guidelines.append({
                    'title': title,
                    'link': link,
                    'description': description
                })

    return guidelines


@mcp.tool(
    name="list_nhmrc_guidelines",
    description="List all NHMRC approved clinical guidelines available on the NHMRC website"
)
def list_nhmrc_guidelines() -> dict:
    """
    List all approved NHMRC clinical guidelines.

    This tool scrapes the NHMRC approved guidelines page and returns a list of all
    available clinical guidelines with their titles, links, and available metadata.

    Returns:
        Dictionary containing:
            - success (bool): Whether the operation was successful
            - guidelines (list): List of guideline dictionaries, each containing:
                - title (str): The guideline title
                - link (str): URL to the full guideline
                - organisation (str, optional): Organisation that developed it
                - date (str, optional): Publication or approval date
                - status (str, optional): Current status of the guideline
                - description (str, optional): Brief description
            - count (int): Number of guidelines found
            - error (str|None): Error message if operation failed, None otherwise

    Example:
        >>> list_nhmrc_guidelines()
        {
            "success": True,
            "guidelines": [
                {
                    "title": "Australian Guidelines for Clinical Care of People with SCI",
                    "link": "https://www.nhmrc.gov.au/...",
                    "organisation": "NHMRC",
                    "date": "2023",
                    "status": "Approved"
                },
                ...
            ],
            "count": 25,
            "error": None
        }
    """
    try:
        soup = fetch_guidelines_page()
        if not soup:
            return {
                'success': False,
                'guidelines': [],
                'count': 0,
                'error': 'Failed to fetch guidelines page'
            }

        guidelines = extract_guidelines_from_soup(soup)

        return {
            'success': True,
            'guidelines': guidelines,
            'count': len(guidelines),
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'guidelines': [],
            'count': 0,
            'error': f'Error listing guidelines: {str(e)}'
        }


@mcp.tool(
    name="search_nhmrc_guidelines",
    description="Search NHMRC approved guidelines by keyword or topic (e.g., 'diabetes', 'cancer', 'mental health')"
)
def search_nhmrc_guidelines(keyword: str) -> dict:
    """
    Search for NHMRC guidelines by keyword or topic.

    This tool searches through all approved NHMRC guidelines and returns those that
    match the search keyword in their title or description. The search is case-insensitive.

    Args:
        keyword: Search term to look for in guideline titles and descriptions
                (e.g., "diabetes", "cancer", "cardiovascular", "mental health")

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - keyword (str): The search keyword used
            - guidelines (list): List of matching guideline dictionaries
            - count (int): Number of matching guidelines found
            - error (str|None): Error message if search failed, None otherwise

    Example:
        >>> search_nhmrc_guidelines("diabetes")
        {
            "success": True,
            "keyword": "diabetes",
            "guidelines": [
                {
                    "title": "Guidelines for Type 2 Diabetes Management",
                    "link": "https://www.nhmrc.gov.au/...",
                    "organisation": "NHMRC",
                    "relevance": "Title match"
                }
            ],
            "count": 1,
            "error": None
        }
    """
    try:
        soup = fetch_guidelines_page()
        if not soup:
            return {
                'success': False,
                'keyword': keyword,
                'guidelines': [],
                'count': 0,
                'error': 'Failed to fetch guidelines page'
            }

        all_guidelines = extract_guidelines_from_soup(soup)

        # Filter guidelines based on keyword
        keyword_lower = keyword.lower()
        matching_guidelines = []

        for guideline in all_guidelines:
            title = guideline.get('title', '').lower()
            description = guideline.get('description', '').lower()
            organisation = guideline.get('organisation', '').lower()

            relevance = []
            if keyword_lower in title:
                relevance.append('Title match')
            if keyword_lower in description:
                relevance.append('Description match')
            if keyword_lower in organisation:
                relevance.append('Organisation match')

            if relevance:
                guideline_copy = guideline.copy()
                guideline_copy['relevance'] = ', '.join(relevance)
                matching_guidelines.append(guideline_copy)

        return {
            'success': True,
            'keyword': keyword,
            'guidelines': matching_guidelines,
            'count': len(matching_guidelines),
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'keyword': keyword,
            'guidelines': [],
            'count': 0,
            'error': f'Error searching guidelines: {str(e)}'
        }


@mcp.tool(
    name="get_guideline_details",
    description="Get detailed information about a specific NHMRC guideline by its URL or title"
)
def get_guideline_details(identifier: str) -> dict:
    """
    Get detailed information about a specific NHMRC guideline.

    This tool fetches and parses a specific guideline page to extract detailed information
    including the full content, sections, recommendations, and metadata. The identifier
    can be either a URL to the guideline or the exact title.

    Args:
        identifier: Either the full URL to the guideline page or the exact title
                   of the guideline to retrieve

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - title (str): The guideline title
            - url (str): URL to the guideline
            - content (str): Main content of the guideline
            - sections (list): List of section headings found in the guideline
            - metadata (dict): Additional metadata (publication date, authors, etc.)
            - error (str|None): Error message if retrieval failed, None otherwise

    Example:
        >>> get_guideline_details("https://www.nhmrc.gov.au/about-us/publications/...")
        {
            "success": True,
            "title": "Australian Guidelines for Clinical Care",
            "url": "https://www.nhmrc.gov.au/...",
            "content": "Full guideline content...",
            "sections": ["Introduction", "Methodology", "Recommendations"],
            "metadata": {
                "published": "2023",
                "authors": "NHMRC",
                "status": "Current"
            },
            "error": None
        }
    """
    try:
        # Determine if identifier is a URL or title
        url = identifier
        if not identifier.startswith('http'):
            # It's a title, need to search for it first
            search_result = search_nhmrc_guidelines(identifier)
            if not search_result['success'] or search_result['count'] == 0:
                # Try exact match from list
                list_result = list_nhmrc_guidelines()
                if list_result['success']:
                    for guideline in list_result['guidelines']:
                        if guideline['title'].lower() == identifier.lower():
                            url = guideline.get('link', '')
                            break

                if not url or not url.startswith('http'):
                    return {
                        'success': False,
                        'title': '',
                        'url': '',
                        'content': '',
                        'sections': [],
                        'metadata': {},
                        'error': f'Could not find guideline with title: {identifier}'
                    }
            else:
                url = search_result['guidelines'][0].get('link', '')

        # Fetch the guideline page
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')

        # Extract title
        title = ''
        title_tag = soup.find('h1')
        if title_tag:
            title = title_tag.get_text(strip=True)

        # Extract main content
        content = ''
        content_areas = soup.find_all(['div', 'section', 'article'],
                                      class_=lambda x: x and ('content' in x.lower() or 'main' in x.lower()))
        if content_areas:
            content = content_areas[0].get_text(separator='\n', strip=True)
        else:
            # Fallback: get all paragraphs
            paragraphs = soup.find_all('p')
            content = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

        # Extract sections
        sections = []
        for heading in soup.find_all(['h2', 'h3', 'h4']):
            section_title = heading.get_text(strip=True)
            if section_title:
                sections.append(section_title)

        # Extract metadata
        metadata = {}

        # Look for publication date
        date_patterns = soup.find_all(['time', 'span', 'div'],
                                      class_=lambda x: x and ('date' in x.lower() or 'published' in x.lower()))
        for date_elem in date_patterns:
            date_text = date_elem.get_text(strip=True)
            if date_text:
                metadata['published'] = date_text
                break

        # Look for author/organisation info
        org_patterns = soup.find_all(['span', 'div', 'p'],
                                     class_=lambda x: x and ('author' in x.lower() or 'organisation' in x.lower()))
        for org_elem in org_patterns:
            org_text = org_elem.get_text(strip=True)
            if org_text:
                metadata['organisation'] = org_text
                break

        # Look for status information
        status_patterns = soup.find_all(['span', 'div'],
                                       class_=lambda x: x and 'status' in x.lower())
        for status_elem in status_patterns:
            status_text = status_elem.get_text(strip=True)
            if status_text:
                metadata['status'] = status_text
                break

        return {
            'success': True,
            'title': title,
            'url': url,
            'content': content[:5000] if len(content) > 5000 else content,  # Limit content length
            'content_length': len(content),
            'sections': sections,
            'metadata': metadata,
            'error': None
        }

    except requests.RequestException as e:
        return {
            'success': False,
            'title': '',
            'url': url if 'url' in locals() else identifier,
            'content': '',
            'sections': [],
            'metadata': {},
            'error': f'Error fetching guideline: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'title': '',
            'url': url if 'url' in locals() else identifier,
            'content': '',
            'sections': [],
            'metadata': {},
            'error': f'Error processing guideline: {str(e)}'
        }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
