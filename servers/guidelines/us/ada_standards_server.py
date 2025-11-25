#!/usr/bin/env python
"""
ADA (American Diabetes Association) Standards of Care MCP Server

This MCP server provides tools to search and access ADA Standards of Medical Care in Diabetes.
The ADA publishes comprehensive, evidence-based clinical practice recommendations for diabetes
diagnosis, treatment, and management updated annually.

Uses web scraping to retrieve published guidance from https://professional.diabetes.org/
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
    "ADA-Standards",
    instructions="Search and retrieve ADA (American Diabetes Association) Standards of Medical Care in Diabetes including diagnosis criteria, glycemic targets, medications, complications management, and screening recommendations"
)

# ADA URLs
BASE_URL = "https://professional.diabetes.org"
STANDARDS_URL = f"{BASE_URL}/content-page/practice-guidelines-resources"
CARE_URL = "https://diabetesjournals.org/care"
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
        await asyncio.sleep(0.7)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            return response.text
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return None


@mcp.tool(
    name="search_diabetes_standards",
    description="Search ADA Standards of Medical Care in Diabetes by topic. Returns recommendations for diagnosis, glycemic control, medications, complications, screening, and management across all diabetes types."
)
async def search_diabetes_standards(topic: str, max_results: int = 15) -> dict:
    """
    Search ADA Standards of Care by topic or section.

    Args:
        topic: Search term (e.g., "glycemic targets", "metformin", "retinopathy", "type 1 diabetes")
        max_results: Maximum number of results to return (default: 15, max: 30)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - query (str): The search term used
            - count (int): Number of results found
            - results (list): List of matching sections with:
                - section (str): Section number and title
                - url (str): Full URL to the section
                - year (str): Standards year
                - summary (str): Brief summary of content
                - category (str): Topic category
            - error (str|None): Error message if search failed
    """
    max_results = min(max_results, 30)

    # Clean topic
    topic_clean = " ".join(topic.split())

    # Try to access standards page
    html = await fetch_page(STANDARDS_URL)
    if not html:
        return {
            'success': False,
            'query': topic,
            'count': 0,
            'results': [],
            'error': 'Failed to connect to ADA website'
        }

    soup = BeautifulSoup(html, 'html.parser')
    results = []

    # Find standards sections
    standard_items = soup.find_all(['div', 'article', 'section'], class_=re.compile(r'standard|guideline|section'))

    # Also look for links to standards
    if not standard_items:
        links = soup.find_all('a', href=re.compile(r'standard|guideline|care'))
        standard_items = [link.parent for link in links if link.parent]

    for item in standard_items:
        # Extract title and link
        title_elem = item.find(['h2', 'h3', 'h4', 'a'])
        if not title_elem:
            continue

        title = title_elem.get_text(strip=True)

        # Filter by topic
        if topic_clean.lower() not in title.lower():
            # Check if topic is in nearby text
            item_text = item.get_text(strip=True).lower()
            if topic_clean.lower() not in item_text:
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
            link = f"{BASE_URL}{link}" if link.startswith('/') else link

        # Extract year
        year = str(datetime.now().year)
        year_match = re.search(r'\b(20\d{2})\b', title)
        if year_match:
            year = year_match.group(1)

        # Extract summary
        summary = ''
        summary_elem = item.find(['p', 'div'], class_=re.compile(r'summary|description|excerpt'))
        if summary_elem:
            summary = summary_elem.get_text(strip=True)[:300]

        # Categorize based on title keywords
        category = 'Diabetes Care'
        title_lower = title.lower()
        if any(term in title_lower for term in ['diagnosis', 'screening', 'criteria']):
            category = 'Diagnosis and Screening'
        elif any(term in title_lower for term in ['glycemic', 'glucose', 'a1c', 'target']):
            category = 'Glycemic Management'
        elif any(term in title_lower for term in ['medication', 'drug', 'insulin', 'metformin']):
            category = 'Pharmacologic Therapy'
        elif any(term in title_lower for term in ['cardiovascular', 'heart', 'cvd']):
            category = 'Cardiovascular Disease'
        elif any(term in title_lower for term in ['kidney', 'nephropathy', 'renal', 'ckd']):
            category = 'Kidney Disease'
        elif any(term in title_lower for term in ['retinopathy', 'eye', 'vision']):
            category = 'Retinopathy'
        elif any(term in title_lower for term in ['neuropathy', 'nerve', 'foot']):
            category = 'Neuropathy'
        elif any(term in title_lower for term in ['type 1', 't1d']):
            category = 'Type 1 Diabetes'
        elif any(term in title_lower for term in ['type 2', 't2d']):
            category = 'Type 2 Diabetes'
        elif any(term in title_lower for term in ['pregnancy', 'gestational', 'gdm']):
            category = 'Diabetes in Pregnancy'

        if title and link:
            results.append({
                'section': title,
                'url': link,
                'year': year,
                'summary': summary,
                'category': category
            })

        if len(results) >= max_results:
            break

    # If no results, try alternative search
    if not results:
        # Try searching Diabetes Care journal site
        search_url = f"{CARE_URL}/search?q={quote(topic_clean)}"
        html = await fetch_page(search_url)

        if html:
            soup = BeautifulSoup(html, 'html.parser')
            search_items = soup.find_all(['div', 'article'], class_=re.compile(r'result|search|article'))

            for item in search_items[:max_results]:
                title_elem = item.find(['h2', 'h3', 'a'])
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)

                # Only include Standards of Care articles
                if 'standards of' not in title.lower() and 'standards of care' not in title.lower():
                    continue

                link = ''
                if title_elem.name == 'a':
                    link = title_elem.get('href', '')
                else:
                    link_elem = item.find('a', href=True)
                    if link_elem:
                        link = link_elem.get('href', '')

                if link and not link.startswith('http'):
                    link = f"{CARE_URL}{link}" if link.startswith('/') else link

                results.append({
                    'section': title,
                    'url': link,
                    'year': str(datetime.now().year),
                    'summary': '',
                    'category': 'Diabetes Care'
                })

    if not results:
        return {
            'success': True,
            'query': topic,
            'count': 0,
            'results': [],
            'error': 'No standards found matching the search term'
        }

    return {
        'success': True,
        'query': topic,
        'count': len(results),
        'results': results,
        'error': None
    }


@mcp.tool(
    name="get_standards_section",
    description="Get detailed content from a specific ADA Standards section including recommendations, evidence levels, and clinical guidance."
)
async def get_standards_section(identifier: str) -> dict:
    """
    Get detailed information from a specific Standards section.

    Args:
        identifier: Section URL, title, or number

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - section (str): Section title
            - url (str): Direct URL to the section
            - year (str): Standards year
            - summary (str): Section summary
            - recommendations (list): Key recommendations with evidence grades
            - subsections (list): Subsection content
            - tables_figures (list): Important tables and figures
            - error (str|None): Error message if retrieval failed
    """
    # Determine URL
    if identifier.startswith('http'):
        url = identifier
    else:
        # Try to search for it
        search_result = await search_diabetes_standards(identifier, max_results=1)
        if search_result['success'] and search_result['count'] > 0:
            url = search_result['results'][0]['url']
        else:
            return {
                'success': False,
                'section': '',
                'url': '',
                'error': 'Could not find standards section with that identifier'
            }

    html = await fetch_page(url)
    if not html:
        return {
            'success': False,
            'section': '',
            'url': url,
            'error': 'Failed to retrieve standards page'
        }

    soup = BeautifulSoup(html, 'html.parser')

    # Extract section title
    section = ''
    title_elem = soup.find('h1')
    if title_elem:
        section = title_elem.get_text(strip=True)

    # Extract year
    year = str(datetime.now().year)
    year_match = re.search(r'\b(20\d{2})\b', section)
    if year_match:
        year = year_match.group(1)

    # Extract summary
    summary = ''
    summary_elem = soup.find(['div', 'section'], class_=re.compile(r'abstract|summary|overview|key-points'))
    if summary_elem:
        paragraphs = summary_elem.find_all('p', limit=3)
        summary = ' '.join([p.get_text(strip=True) for p in paragraphs])

    if not summary:
        # Get first paragraphs from main content
        main_content = soup.find(['main', 'article', 'div'], class_=re.compile(r'content|body|main'))
        if main_content:
            paragraphs = main_content.find_all('p', limit=3)
            summary = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

    # Extract recommendations
    recommendations = []

    # Look for numbered recommendations
    rec_items = soup.find_all(['p', 'div'], class_=re.compile(r'recommendation'))
    for item in rec_items[:20]:
        text = item.get_text(strip=True)
        if text and len(text) > 20:
            # Try to extract evidence grade (A, B, C, E)
            grade_match = re.search(r'\[([ABCE])\]|\bGrade ([ABCE])\b', text)
            grade = grade_match.group(1) if grade_match else 'Not specified'

            recommendations.append({
                'text': text[:600],
                'evidence_grade': grade
            })

    # Also look for bold statements (often recommendations)
    if not recommendations:
        strong_elems = soup.find_all(['strong', 'b'])
        for elem in strong_elems[:15]:
            text = elem.get_text(strip=True)
            if len(text) > 30 and len(text) < 500:
                recommendations.append({
                    'text': text,
                    'evidence_grade': 'Not specified'
                })

    # Extract subsections
    subsections = []
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
                subsections.append({
                    'heading': heading_text,
                    'content': ' '.join(content)[:800]
                })

    # Extract tables and figures
    tables_figures = []
    tables = soup.find_all('table', limit=5)
    for idx, table in enumerate(tables, 1):
        caption = table.find('caption')
        caption_text = caption.get_text(strip=True) if caption else f'Table {idx}'
        tables_figures.append({
            'type': 'table',
            'caption': caption_text,
            'note': 'Table content available in full document'
        })

    figures = soup.find_all(['figure', 'img'], limit=5)
    for idx, fig in enumerate(figures, 1):
        caption = fig.find(['figcaption', 'alt'])
        caption_text = caption.get_text(strip=True) if caption else fig.get('alt', f'Figure {idx}')
        tables_figures.append({
            'type': 'figure',
            'caption': caption_text,
            'note': 'Figure available in full document'
        })

    return {
        'success': True,
        'section': section,
        'url': url,
        'year': year,
        'summary': summary[:1000] if summary else 'Not available',
        'recommendations': recommendations,
        'subsections': subsections,
        'tables_figures': tables_figures[:10],
        'error': None
    }


@mcp.tool(
    name="list_standards_sections",
    description="List all sections of the ADA Standards of Medical Care in Diabetes organized by topic including diagnosis, glycemic targets, medications, complications, and special populations."
)
async def list_standards_sections() -> dict:
    """
    List all major sections of the ADA Standards of Care.

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - year (str): Current standards year
            - sections (list): List of standard sections with:
                - number (str): Section number
                - title (str): Section title
                - description (str): Brief description of content
                - topics (list): Key topics covered
            - error (str|None): Error message if retrieval failed
    """
    current_year = str(datetime.now().year)

    sections = [
        {
            'number': '1',
            'title': 'Improving Care and Promoting Health in Populations',
            'description': 'Strategies for improving diabetes care quality and population health',
            'topics': ['Quality improvement', 'Care delivery systems', 'Population health']
        },
        {
            'number': '2',
            'title': 'Diagnosis and Classification of Diabetes',
            'description': 'Diagnostic criteria for diabetes and prediabetes, diabetes classification',
            'topics': ['Diagnostic criteria', 'A1C thresholds', 'Type 1 vs Type 2', 'Prediabetes', 'Screening']
        },
        {
            'number': '3',
            'title': 'Prevention or Delay of Type 2 Diabetes and Associated Comorbidities',
            'description': 'Strategies to prevent or delay type 2 diabetes in at-risk individuals',
            'topics': ['Lifestyle modification', 'Metformin for prevention', 'Risk assessment']
        },
        {
            'number': '4',
            'title': 'Comprehensive Medical Evaluation and Assessment of Comorbidities',
            'description': 'Initial and ongoing evaluation of patients with diabetes',
            'topics': ['Medical history', 'Physical examination', 'Laboratory testing', 'Comorbidity screening']
        },
        {
            'number': '5',
            'title': 'Facilitating Positive Health Behaviors and Well-being',
            'description': 'Diabetes self-management education and support',
            'topics': ['DSMES', 'Nutrition therapy', 'Physical activity', 'Psychosocial care']
        },
        {
            'number': '6',
            'title': 'Glycemic Goals and Hypoglycemia',
            'description': 'Glycemic targets for different populations and hypoglycemia management',
            'topics': ['A1C targets', 'Glucose targets', 'Hypoglycemia prevention', 'Individualized goals']
        },
        {
            'number': '7',
            'title': 'Diabetes Technology',
            'description': 'Continuous glucose monitors, insulin pumps, and automated insulin delivery',
            'topics': ['CGM', 'Insulin pumps', 'Automated insulin delivery', 'Smart pens']
        },
        {
            'number': '8',
            'title': 'Obesity and Weight Management',
            'description': 'Approaches to obesity treatment in diabetes including medications and surgery',
            'topics': ['Weight loss medications', 'Bariatric surgery', 'Lifestyle interventions']
        },
        {
            'number': '9',
            'title': 'Pharmacologic Approaches to Glycemic Treatment',
            'description': 'Medication options for type 1 and type 2 diabetes management',
            'topics': ['Metformin', 'GLP-1 agonists', 'SGLT2 inhibitors', 'Insulin therapy', 'Drug selection']
        },
        {
            'number': '10',
            'title': 'Cardiovascular Disease and Risk Management',
            'description': 'Prevention and treatment of cardiovascular complications',
            'topics': ['Blood pressure management', 'Lipid management', 'Antiplatelet therapy', 'CVD screening']
        },
        {
            'number': '11',
            'title': 'Chronic Kidney Disease and Risk Management',
            'description': 'Screening, prevention, and treatment of diabetic kidney disease',
            'topics': ['CKD screening', 'SGLT2 inhibitors', 'GLP-1 agonists', 'Finerenone', 'Nephrology referral']
        },
        {
            'number': '12',
            'title': 'Retinopathy, Neuropathy, and Foot Care',
            'description': 'Screening and management of microvascular complications',
            'topics': ['Retinopathy screening', 'Neuropathy assessment', 'Foot care', 'Peripheral artery disease']
        },
        {
            'number': '13',
            'title': 'Older Adults',
            'description': 'Diabetes management in older adults with emphasis on individualization',
            'topics': ['Simplified regimens', 'Hypoglycemia avoidance', 'Functional assessment', 'End-of-life care']
        },
        {
            'number': '14',
            'title': 'Children and Adolescents',
            'description': 'Type 1 and type 2 diabetes management in pediatric populations',
            'topics': ['Pediatric A1C targets', 'Growth monitoring', 'Transition to adult care', 'School management']
        },
        {
            'number': '15',
            'title': 'Management of Diabetes in Pregnancy',
            'description': 'Preconception care, gestational diabetes, and diabetes in pregnancy',
            'topics': ['Gestational diabetes screening', 'Glucose targets in pregnancy', 'Medication safety', 'Postpartum care']
        },
        {
            'number': '16',
            'title': 'Diabetes Care in the Hospital',
            'description': 'Inpatient glucose management and transition to outpatient care',
            'topics': ['Hospital glucose targets', 'Insulin protocols', 'Perioperative management', 'Discharge planning']
        }
    ]

    return {
        'success': True,
        'year': current_year,
        'sections': sections,
        'error': None
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
