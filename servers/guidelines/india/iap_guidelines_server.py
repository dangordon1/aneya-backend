#!/usr/bin/env python
"""
IAP Guidelines MCP Server

This MCP server provides tools to search and access IAP (Indian Academy of
Pediatrics) clinical practice guidelines. IAP is India's premier pediatric
organization providing evidence-based guidelines for child health, infant care,
immunization, nutrition, and common pediatric conditions specific to Indian
children and healthcare settings.

Uses web scraping to retrieve published guidelines from iapindia.org.
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
    "IAP-Guidelines",
    instructions="""Search and retrieve Indian Academy of Pediatrics (IAP) clinical practice
    guidelines with comprehensive child health management protocols specific to Indian children.
    Covers newborn care, infant nutrition, immunization schedules, common pediatric infections,
    growth monitoring, developmental assessment, and pediatric emergencies adapted for Indian
    healthcare settings and disease patterns."""
)

# IAP URLs
BASE_URL = "https://iapindia.org"
GUIDELINES_URL = f"{BASE_URL}/publication-recommendations-and-guidelines/"
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
    name="search_pediatric_guidelines",
    description="Search IAP pediatric clinical practice guidelines by topic or age group. Returns guidelines for newborn care, immunization, nutrition, growth, development, infections (diarrhea, pneumonia, dengue), asthma, anemia, and other pediatric conditions."
)
async def search_pediatric_guidelines(keyword: str, age_group: Optional[str] = None, max_results: int = 20) -> dict:
    """
    Search IAP pediatric guidelines by keyword or topic.

    Args:
        keyword: Search term or condition (e.g., "immunization", "diarrhea", "asthma", "nutrition", "growth")
        age_group: Optional age filter (e.g., "newborn", "infant", "toddler", "school-age", "adolescent")
        max_results: Maximum number of results to return (default: 20, max: 50)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - query (str): The search keyword used
            - age_group_filter (str|None): Age group filter applied
            - count (int): Number of results found
            - results (list): List of matching guidelines with title, category, url, year, age_group, document_type
            - error (str|None): Error message if search failed
    """
    max_results = min(max_results, 50)
    keyword_clean = " ".join(keyword.split())
    age_group_clean = " ".join(age_group.split()) if age_group else None

    results = []

    # Fetch the guidelines page
    html = await fetch_page(GUIDELINES_URL)
    if not html:
        return {
            'success': False,
            'query': keyword,
            'age_group_filter': age_group_clean,
            'count': 0,
            'results': [],
            'error': 'Failed to fetch IAP guidelines page'
        }

    soup = BeautifulSoup(html, 'html.parser')

    # Look for guideline links
    guideline_links = soup.find_all('a', href=True)

    seen_urls = set()
    keyword_lower = keyword_clean.lower()
    age_group_lower = age_group_clean.lower() if age_group_clean else None

    for link in guideline_links:
        href = link.get('href', '')
        if not href:
            continue

        link_text = link.get_text(strip=True)

        # Skip short links
        if len(link_text) < 10:
            continue

        # Build full URL
        full_url = urljoin(BASE_URL, href)

        # Skip duplicates
        if full_url in seen_urls:
            continue

        # Get parent context
        parent = link.find_parent(['li', 'tr', 'div', 'p', 'section', 'article'])
        context_text = parent.get_text(strip=True) if parent else link_text

        # Check if keyword matches
        keyword_match = keyword_lower in context_text.lower() or keyword_lower in link_text.lower()

        # Check age group filter if provided
        age_match = True
        if age_group_lower:
            age_match = age_group_lower in context_text.lower()

        if keyword_match and age_match:
            seen_urls.add(full_url)

            # Extract year
            year_match = re.search(r'\b(20\d{2})\b', context_text)
            year = year_match.group(1) if year_match else 'Not specified'

            # Determine age group
            detected_age_group = 'All ages'
            age_keywords = {
                'Newborn (0-28 days)': ['newborn', 'neonatal', 'neonate'],
                'Infant (1-12 months)': ['infant', 'infancy'],
                'Toddler (1-3 years)': ['toddler'],
                'Preschool (3-5 years)': ['preschool', 'pre-school'],
                'School age (5-12 years)': ['school age', 'school-age', 'children'],
                'Adolescent (12-18 years)': ['adolescent', 'teenager', 'teen']
            }

            for age_name, keywords in age_keywords.items():
                if any(kw in context_text.lower() for kw in keywords):
                    detected_age_group = age_name
                    break

            # Determine category
            category = 'General Pediatrics'
            category_keywords = {
                'Immunization': ['immunization', 'vaccination', 'vaccine'],
                'Nutrition': ['nutrition', 'feeding', 'breastfeeding', 'complementary'],
                'Growth & Development': ['growth', 'development', 'developmental'],
                'Infectious Diseases': ['infection', 'diarrhea', 'pneumonia', 'dengue', 'malaria', 'measles'],
                'Respiratory': ['asthma', 'bronchiolitis', 'cough', 'respiratory'],
                'Newborn Care': ['newborn', 'neonatal'],
                'Anemia & Nutrition': ['anemia', 'iron', 'malnutrition'],
                'Neurodevelopment': ['neurodevelopment', 'autism', 'adhd', 'cerebral palsy'],
                'Emergency Care': ['emergency', 'resuscitation', 'shock', 'seizure']
            }

            for cat_name, keywords in category_keywords.items():
                if any(kw in context_text.lower() for kw in keywords):
                    category = cat_name
                    break

            # Determine document type
            doc_type = 'PDF' if href.lower().endswith('.pdf') else 'Web Page'

            results.append({
                'title': link_text[:200] if len(link_text) > 200 else link_text,
                'category': category,
                'url': full_url,
                'year': year,
                'age_group': detected_age_group,
                'document_type': doc_type
            })

            if len(results) >= max_results:
                break

    if not results:
        return {
            'success': True,
            'query': keyword,
            'age_group_filter': age_group_clean,
            'count': 0,
            'results': [],
            'error': 'No IAP pediatric guidelines found matching the search criteria'
        }

    return {
        'success': True,
        'query': keyword,
        'age_group_filter': age_group_clean,
        'count': len(results),
        'results': results,
        'error': None
    }


@mcp.tool(
    name="get_guideline_content",
    description="Get detailed content for a specific IAP pediatric guideline by URL. Returns age-specific management protocols, dosing recommendations, Indian immunization schedules, growth charts, and developmental milestones."
)
async def get_guideline_content(guideline_url: str) -> dict:
    """
    Get detailed information about a specific IAP guideline.

    Args:
        guideline_url: Full URL to the guideline (PDF or web page)

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - title (str): Guideline title
            - url (str): Direct URL to the guideline
            - category (str): Guideline category
            - age_group (str): Target age group
            - content (str): Main guideline content/summary
            - recommendations (str): Key clinical recommendations
            - dosing_information (str): Medication dosing if applicable
            - preventive_measures (str): Prevention strategies
            - india_specific (str): India-specific considerations
            - document_type (str): Type of document
            - error (str|None): Error message if retrieval failed
    """
    if not guideline_url:
        return {
            'success': False,
            'title': '',
            'url': '',
            'category': '',
            'age_group': '',
            'content': '',
            'recommendations': '',
            'dosing_information': '',
            'preventive_measures': '',
            'india_specific': '',
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
            'category': 'Pediatrics',
            'age_group': 'Children',
            'content': 'PDF document - download required for full content. This IAP guideline contains India-specific pediatric care recommendations.',
            'recommendations': 'Please download the PDF to view clinical recommendations',
            'dosing_information': 'Please download the PDF to view dosing information',
            'preventive_measures': 'Please download the PDF to view preventive strategies',
            'india_specific': 'Indian context and immunization schedule available in PDF',
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
            'category': '',
            'age_group': '',
            'content': '',
            'recommendations': '',
            'dosing_information': '',
            'preventive_measures': '',
            'india_specific': '',
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
        title = title_tag.get_text(strip=True) if title_tag else 'IAP Guideline'

    # Extract main content
    content = ''
    main_content = soup.find(['main', 'article', 'div'], class_=re.compile(r'content|main|guideline', re.I))
    if main_content:
        paragraphs = main_content.find_all('p', limit=10)
        content = ' '.join([p.get_text(strip=True) for p in paragraphs])

    if not content:
        paragraphs = soup.find_all('p', limit=10)
        content = ' '.join([p.get_text(strip=True) for p in paragraphs])

    # Extract recommendations
    recommendations = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['recommendation', 'key point', 'summary', 'guideline']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            recommendations = ' '.join(content_parts)
            if recommendations:
                break

    # Extract dosing information
    dosing_information = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['dos', 'medication', 'drug', 'treatment']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            dosing_information = ' '.join(content_parts)
            if dosing_information:
                break

    # Extract preventive measures
    preventive_measures = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['prevention', 'preventive', 'prophylaxis', 'immunization']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            preventive_measures = ' '.join(content_parts)
            if preventive_measures:
                break

    # Extract India-specific information
    india_specific = ''
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text(strip=True).lower()
        if any(word in heading_text for word in ['indian', 'india', 'iap', 'national']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name in ['p', 'li', 'ul', 'ol']:
                    content_parts.append(sibling.get_text(strip=True))
            india_specific = ' '.join(content_parts)
            if india_specific:
                break

    # Determine category
    category = 'General Pediatrics'
    if 'immunization' in title.lower() or 'vaccine' in title.lower():
        category = 'Immunization'
    elif 'nutrition' in title.lower() or 'feeding' in title.lower():
        category = 'Nutrition'
    elif 'growth' in title.lower() or 'development' in title.lower():
        category = 'Growth & Development'
    elif any(word in title.lower() for word in ['infection', 'diarrhea', 'pneumonia']):
        category = 'Infectious Diseases'
    elif 'newborn' in title.lower() or 'neonatal' in title.lower():
        category = 'Newborn Care'

    # Determine age group
    age_group = 'All ages'
    if 'newborn' in title.lower() or 'neonatal' in title.lower():
        age_group = 'Newborn (0-28 days)'
    elif 'infant' in title.lower():
        age_group = 'Infant (1-12 months)'
    elif 'toddler' in title.lower():
        age_group = 'Toddler (1-3 years)'
    elif 'adolescent' in title.lower():
        age_group = 'Adolescent (12-18 years)'

    return {
        'success': True,
        'title': title,
        'url': guideline_url,
        'category': category,
        'age_group': age_group,
        'content': content[:1500] + '...' if len(content) > 1500 else content,
        'recommendations': recommendations[:1200] + '...' if len(recommendations) > 1200 else recommendations,
        'dosing_information': dosing_information[:1000] + '...' if len(dosing_information) > 1000 else dosing_information,
        'preventive_measures': preventive_measures[:1000] + '...' if len(preventive_measures) > 1000 else preventive_measures,
        'india_specific': india_specific[:800] + '...' if len(india_specific) > 800 else india_specific or 'IAP guidelines adapted for Indian children',
        'document_type': 'Web Page',
        'error': None
    }


@mcp.tool(
    name="list_pediatric_categories",
    description="List all pediatric guideline categories covered by IAP including immunization, nutrition, growth monitoring, infectious diseases, newborn care, developmental assessment, and emergency pediatrics."
)
async def list_pediatric_categories() -> dict:
    """
    List available pediatric guideline categories.

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - categories (list): List of categories with name, description, key_topics, age_groups, url
            - error (str|None): Error message if retrieval failed
    """
    categories = [
        {
            'name': 'Immunization',
            'description': 'IAP immunization schedule and vaccine guidelines for Indian children',
            'key_topics': ['IAP immunization timetable', 'Vaccine dosing', 'Catch-up immunization', 'Special situations', 'Adverse events'],
            'age_groups': ['Newborn to 18 years'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Infant & Young Child Nutrition',
            'description': 'Feeding practices, breastfeeding, and complementary feeding',
            'key_topics': ['Exclusive breastfeeding', 'Complementary feeding', 'Formula feeding', 'Micronutrient supplementation'],
            'age_groups': ['0-3 years'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Growth Monitoring',
            'description': 'Growth assessment using WHO and IAP growth charts',
            'key_topics': ['Weight monitoring', 'Height/length measurement', 'Head circumference', 'Growth faltering', 'Obesity'],
            'age_groups': ['0-18 years'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Developmental Assessment',
            'description': 'Monitoring neurodevelopmental milestones',
            'key_topics': ['Developmental milestones', 'Developmental delay', 'Autism screening', 'Early intervention'],
            'age_groups': ['0-6 years'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Acute Diarrhea',
            'description': 'Management of acute diarrhea and dehydration',
            'key_topics': ['ORS therapy', 'Zinc supplementation', 'Feeding during diarrhea', 'Antibiotic use'],
            'age_groups': ['All pediatric ages'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Acute Respiratory Infections',
            'description': 'Pneumonia, bronchiolitis, and upper respiratory infections',
            'key_topics': ['Pneumonia diagnosis', 'Antibiotic selection', 'Oxygen therapy', 'Bronchodilators'],
            'age_groups': ['All pediatric ages'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Childhood Asthma',
            'description': 'Diagnosis and management of pediatric asthma',
            'key_topics': ['Asthma diagnosis', 'Inhaler therapy', 'Controller medications', 'Acute exacerbation'],
            'age_groups': ['1-18 years'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Newborn Care',
            'description': 'Essential newborn care and common neonatal problems',
            'key_topics': ['Immediate newborn care', 'Breastfeeding initiation', 'Jaundice', 'Sepsis', 'Resuscitation'],
            'age_groups': ['0-28 days'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Anemia & Iron Deficiency',
            'description': 'Prevention and treatment of childhood anemia',
            'key_topics': ['Iron supplementation', 'Dietary iron', 'Anemia screening', 'Treatment protocols'],
            'age_groups': ['6 months to 18 years'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Dengue in Children',
            'description': 'Recognition and management of dengue fever',
            'key_topics': ['Warning signs', 'Fluid management', 'Platelet monitoring', 'Severe dengue'],
            'age_groups': ['All pediatric ages'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Childhood Tuberculosis',
            'description': 'TB diagnosis and treatment in children',
            'key_topics': ['TB screening', 'Contact tracing', 'Drug therapy', 'DOTS', 'Drug-resistant TB'],
            'age_groups': ['All pediatric ages'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Adolescent Health',
            'description': 'Health issues specific to adolescents',
            'key_topics': ['Puberty', 'Menstrual health', 'Mental health', 'Substance abuse', 'Sexual health'],
            'age_groups': ['10-18 years'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Pediatric Emergency Care',
            'description': 'Management of pediatric emergencies',
            'key_topics': ['Resuscitation', 'Shock', 'Seizures', 'Poisoning', 'Trauma'],
            'age_groups': ['All pediatric ages'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Neurodevelopmental Disorders',
            'description': 'Autism, ADHD, cerebral palsy, and learning disabilities',
            'key_topics': ['Early detection', 'Developmental screening', 'Therapy referrals', 'School support'],
            'age_groups': ['0-18 years'],
            'url': GUIDELINES_URL
        },
        {
            'name': 'Malnutrition',
            'description': 'Severe acute malnutrition and undernutrition',
            'key_topics': ['SAM diagnosis', 'Therapeutic feeding', 'Medical complications', 'Rehabilitation'],
            'age_groups': ['6 months to 5 years'],
            'url': GUIDELINES_URL
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
