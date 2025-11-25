#!/usr/bin/env python
"""
AAP (American Academy of Pediatrics) Guidelines MCP Server

This MCP server provides tools to search and access AAP clinical practice guidelines
and policy statements. The AAP publishes evidence-based recommendations for pediatric
care covering preventive health, acute and chronic conditions, and child development.

Uses web scraping to retrieve published guidance from https://www.aap.org/
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
    "AAP-Guidelines",
    instructions="Search and retrieve AAP (American Academy of Pediatrics) clinical practice guidelines covering preventive pediatric care, immunizations, developmental screening, acute and chronic pediatric conditions, and child health policy"
)

# AAP URLs
BASE_URL = "https://www.aap.org"
GUIDELINES_URL = f"{BASE_URL}/en/practice-management/clinical-practice-guidelines"
POLICY_URL = f"{BASE_URL}/en/advocacy/child-and-adolescent-health-policy"
PEDIATRICS_URL = "https://publications.aap.org/pediatrics"
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
        await asyncio.sleep(0.8)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            return response.text
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return None


@mcp.tool(
    name="search_pediatric_guidelines",
    description="Search AAP clinical practice guidelines and policy statements by topic. Returns pediatric recommendations for preventive care, immunizations, developmental screening, and management of acute and chronic pediatric conditions."
)
async def search_pediatric_guidelines(topic: str, max_results: int = 20) -> dict:
    """
    Search AAP guidelines and policy statements by topic.

    Args:
        topic: Search term (e.g., "asthma", "ADHD", "immunization", "well child", "fever")
        max_results: Maximum number of results to return (default: 20, max: 50)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - query (str): The search term used
            - count (int): Number of results found
            - results (list): List of matching guidelines with:
                - title (str): Guideline or policy title
                - url (str): Full URL to the document
                - year (str): Publication year
                - type (str): Document type (Clinical Practice Guideline, Policy Statement, etc.)
                - category (str): Pediatric category
                - summary (str): Brief summary if available
            - error (str|None): Error message if search failed
    """
    max_results = min(max_results, 50)

    # Clean topic
    topic_clean = " ".join(topic.split())

    results = []

    # Try guidelines page
    html = await fetch_page(GUIDELINES_URL)
    if html:
        soup = BeautifulSoup(html, 'html.parser')

        # Find guideline items
        guideline_items = soup.find_all(['article', 'div', 'li'], class_=re.compile(r'guideline|policy|publication|card'))

        for item in guideline_items:
            # Extract title and link
            title_elem = item.find(['h2', 'h3', 'h4', 'a'])
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)

            # Filter by topic
            if topic_clean.lower() not in title.lower():
                # Check item text
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
            year = 'Not available'
            year_match = re.search(r'\b(20\d{2})\b', title)
            if year_match:
                year = year_match.group(1)
            else:
                year_elem = item.find(['time', 'span'], class_=re.compile(r'year|date|published'))
                if year_elem:
                    year_text = year_elem.get_text(strip=True)
                    year_match = re.search(r'\b(20\d{2})\b', year_text)
                    if year_match:
                        year = year_match.group(1)

            # Determine document type
            doc_type = 'Clinical Practice Guideline'
            if 'policy statement' in title.lower():
                doc_type = 'Policy Statement'
            elif 'technical report' in title.lower():
                doc_type = 'Technical Report'
            elif 'clinical report' in title.lower():
                doc_type = 'Clinical Report'

            # Extract summary
            summary = ''
            summary_elem = item.find(['p', 'div'], class_=re.compile(r'summary|description|excerpt|abstract'))
            if summary_elem:
                summary = summary_elem.get_text(strip=True)[:300]

            # Categorize based on title keywords
            category = 'Pediatric Care'
            title_lower = title.lower()
            if any(term in title_lower for term in ['immunization', 'vaccine', 'vaccination']):
                category = 'Immunizations'
            elif any(term in title_lower for term in ['developmental', 'autism', 'adhd', 'learning', 'behavioral']):
                category = 'Developmental and Behavioral Health'
            elif any(term in title_lower for term in ['well child', 'preventive', 'screening', 'bright futures']):
                category = 'Preventive Care'
            elif any(term in title_lower for term in ['newborn', 'neonatal', 'infant']):
                category = 'Newborn and Infant Care'
            elif any(term in title_lower for term in ['adolescent', 'teen', 'puberty']):
                category = 'Adolescent Health'
            elif any(term in title_lower for term in ['respiratory', 'asthma', 'pneumonia', 'bronchiolitis']):
                category = 'Respiratory Conditions'
            elif any(term in title_lower for term in ['infection', 'fever', 'uti', 'meningitis']):
                category = 'Infectious Diseases'
            elif any(term in title_lower for term in ['injury', 'safety', 'prevention', 'car seat']):
                category = 'Injury Prevention and Safety'
            elif any(term in title_lower for term in ['nutrition', 'breastfeeding', 'feeding', 'obesity']):
                category = 'Nutrition and Feeding'
            elif any(term in title_lower for term in ['mental health', 'depression', 'anxiety', 'suicide']):
                category = 'Mental Health'

            if title and link:
                results.append({
                    'title': title,
                    'url': link,
                    'year': year,
                    'type': doc_type,
                    'category': category,
                    'summary': summary
                })

            if len(results) >= max_results:
                break

    # If not enough results, try search
    if len(results) < max_results:
        search_url = f"{BASE_URL}/en/search?q={quote(topic_clean)}"
        html = await fetch_page(search_url)

        if html:
            soup = BeautifulSoup(html, 'html.parser')
            search_items = soup.find_all(['div', 'article'], class_=re.compile(r'search-result|result'))

            for item in search_items:
                if len(results) >= max_results:
                    break

                title_elem = item.find(['h2', 'h3', 'a'])
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)

                # Only include if appears to be a guideline or policy
                if not any(term in title.lower() for term in ['guideline', 'policy', 'statement', 'recommendation']):
                    continue

                link = ''
                if title_elem.name == 'a':
                    link = title_elem.get('href', '')
                else:
                    link_elem = item.find('a', href=True)
                    if link_elem:
                        link = link_elem.get('href', '')

                if link and not link.startswith('http'):
                    link = f"{BASE_URL}{link}" if link.startswith('/') else link

                # Check if already in results
                if any(r['url'] == link for r in results):
                    continue

                # Extract year
                year = 'Not available'
                year_match = re.search(r'\b(20\d{2})\b', title)
                if year_match:
                    year = year_match.group(1)

                results.append({
                    'title': title,
                    'url': link,
                    'year': year,
                    'type': 'AAP Document',
                    'category': 'Pediatric Care',
                    'summary': ''
                })

    if not results:
        return {
            'success': True,
            'query': topic,
            'count': 0,
            'results': [],
            'error': 'No guidelines found matching the search term'
        }

    return {
        'success': True,
        'query': topic,
        'count': len(results),
        'results': results,
        'error': None
    }


@mcp.tool(
    name="get_guideline_content",
    description="Get detailed content from a specific AAP guideline or policy statement including recommendations, evidence quality, and implementation guidance."
)
async def get_guideline_content(identifier: str) -> dict:
    """
    Get detailed information about a specific AAP guideline or policy.

    Args:
        identifier: Guideline URL, title, or identifier

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - title (str): Document title
            - url (str): Direct URL to the document
            - year (str): Publication year
            - type (str): Document type
            - abstract (str): Abstract or summary
            - recommendations (list): Key recommendations with evidence quality
            - sections (list): Document sections with content
            - related_documents (list): Related AAP publications
            - error (str|None): Error message if retrieval failed
    """
    # Determine URL
    if identifier.startswith('http'):
        url = identifier
    else:
        # Try to search for it
        search_result = await search_pediatric_guidelines(identifier, max_results=1)
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

    # Determine document type
    doc_type = 'Clinical Practice Guideline'
    if 'policy statement' in title.lower():
        doc_type = 'Policy Statement'
    elif 'technical report' in title.lower():
        doc_type = 'Technical Report'
    elif 'clinical report' in title.lower():
        doc_type = 'Clinical Report'

    # Extract abstract/summary
    abstract = ''
    abstract_elem = soup.find(['div', 'section'], class_=re.compile(r'abstract|summary|overview|key-points'))
    if abstract_elem:
        paragraphs = abstract_elem.find_all('p', limit=3)
        abstract = ' '.join([p.get_text(strip=True) for p in paragraphs])

    if not abstract:
        # Try meta description
        meta_elem = soup.find('meta', attrs={'name': 'description'})
        if meta_elem:
            abstract = meta_elem.get('content', '')

    if not abstract:
        # Get first paragraphs from main content
        main_content = soup.find(['main', 'article', 'div'], class_=re.compile(r'content|body|main'))
        if main_content:
            paragraphs = main_content.find_all('p', limit=3)
            abstract = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

    # Extract recommendations
    recommendations = []

    # Look for recommendation sections
    rec_section = soup.find(['div', 'section'], class_=re.compile(r'recommendation|key-action'))
    if rec_section:
        rec_items = rec_section.find_all(['li', 'p'])
        for item in rec_items[:20]:
            text = item.get_text(strip=True)
            if text and len(text) > 20:
                # Try to extract evidence quality (Strong, Moderate, Weak, etc.)
                quality_match = re.search(r'\b(Strong|Moderate|Weak|Grade [A-C]|Level [1-3])\b', text, re.IGNORECASE)
                quality = quality_match.group(1) if quality_match else 'Not specified'

                recommendations.append({
                    'text': text[:600],
                    'evidence_quality': quality
                })

    # If no recommendations found, look for numbered or bulleted lists
    if not recommendations:
        lists = soup.find_all(['ol', 'ul'])
        for lst in lists:
            items = lst.find_all('li', limit=15)
            for item in items:
                text = item.get_text(strip=True)
                if len(text) > 40 and len(text) < 700:
                    # Check if it looks like a recommendation
                    if any(keyword in text.lower() for keyword in ['recommend', 'should', 'consider', 'advise', 'encourage']):
                        recommendations.append({
                            'text': text,
                            'evidence_quality': 'Not specified'
                        })

            if len(recommendations) >= 15:
                break

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
                    'content': ' '.join(content)[:700]
                })

    # Extract related documents
    related = []
    related_section = soup.find(['div', 'aside', 'section'], class_=re.compile(r'related|see-also|additional'))
    if related_section:
        for link in related_section.find_all('a', href=True)[:5]:
            title = link.get_text(strip=True)
            if title and len(title) > 10:
                href = link.get('href', '')
                if href and not href.startswith('http'):
                    href = f"{BASE_URL}{href}" if href.startswith('/') else href
                related.append({
                    'title': title,
                    'url': href
                })

    return {
        'success': True,
        'title': title,
        'url': url,
        'year': year,
        'type': doc_type,
        'abstract': abstract[:1000] if abstract else 'Not available',
        'recommendations': recommendations,
        'sections': sections,
        'related_documents': related,
        'error': None
    }


@mcp.tool(
    name="list_pediatric_topics",
    description="List major AAP guideline topics organized by pediatric care category including preventive care, immunizations, developmental health, acute and chronic conditions, and safety."
)
async def list_pediatric_topics() -> dict:
    """
    List available AAP guideline topics and categories.

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - topics (list): List of major pediatric topics with:
                - category (str): Topic category
                - description (str): Category description
                - example_guidelines (list): Example guidelines in category
            - error (str|None): Error message if retrieval failed
    """
    topics = [
        {
            'category': 'Preventive Pediatric Health Care',
            'description': 'Bright Futures guidelines, well-child care, and screening recommendations',
            'example_guidelines': [
                'Bright Futures Preventive Care Guidelines',
                'Periodicity Schedule for Well-Child Care',
                'Universal Screening Recommendations',
                'Oral Health Screening'
            ]
        },
        {
            'category': 'Immunizations',
            'description': 'Vaccine schedules, contraindications, and immunization practices',
            'example_guidelines': [
                'Recommended Immunization Schedules',
                'Contraindications and Precautions to Vaccination',
                'Vaccine Administration',
                'Immunizations for Special Populations'
            ]
        },
        {
            'category': 'Developmental and Behavioral Health',
            'description': 'Developmental screening, autism, ADHD, learning disorders, and behavioral concerns',
            'example_guidelines': [
                'Autism Spectrum Disorder Identification and Evaluation',
                'ADHD Diagnosis and Management',
                'Developmental Surveillance and Screening',
                'School Readiness'
            ]
        },
        {
            'category': 'Newborn and Infant Care',
            'description': 'Newborn screening, jaundice, feeding, SIDS prevention, and early infant care',
            'example_guidelines': [
                'Newborn Screening',
                'Hyperbilirubinemia Management',
                'SIDS and Safe Sleep Environment',
                'Breastfeeding Support',
                'Vitamin D Supplementation'
            ]
        },
        {
            'category': 'Respiratory Conditions',
            'description': 'Asthma, bronchiolitis, pneumonia, and other respiratory illnesses',
            'example_guidelines': [
                'Asthma Diagnosis and Management',
                'Bronchiolitis Management',
                'Community-Acquired Pneumonia',
                'Croup Management'
            ]
        },
        {
            'category': 'Infectious Diseases',
            'description': 'Fever evaluation, UTI, otitis media, and other pediatric infections',
            'example_guidelines': [
                'Febrile Infants Evaluation',
                'Urinary Tract Infection Diagnosis and Management',
                'Acute Otitis Media',
                'Influenza Management'
            ]
        },
        {
            'category': 'Adolescent Health',
            'description': 'Adolescent preventive care, mental health, substance use, and reproductive health',
            'example_guidelines': [
                'Adolescent Preventive Services',
                'Confidentiality in Adolescent Health Care',
                'Substance Use Screening and Intervention',
                'Contraception for Adolescents'
            ]
        },
        {
            'category': 'Mental and Behavioral Health',
            'description': 'Depression screening, anxiety, suicide prevention, and behavioral disorders',
            'example_guidelines': [
                'Depression Screening in Adolescents',
                'Suicide Prevention',
                'Anxiety Disorders in Children',
                'Attention and Behavior Problems'
            ]
        },
        {
            'category': 'Nutrition and Feeding',
            'description': 'Infant feeding, childhood obesity, food allergies, and nutritional support',
            'example_guidelines': [
                'Breastfeeding and Human Milk',
                'Prevention and Management of Childhood Obesity',
                'Food Allergies',
                'Failure to Thrive'
            ]
        },
        {
            'category': 'Injury Prevention and Safety',
            'description': 'Car seat safety, injury prevention, sports safety, and poison prevention',
            'example_guidelines': [
                'Child Passenger Safety',
                'Sports-Related Concussion',
                'Trampoline Safety',
                'Firearm-Related Injuries Prevention'
            ]
        },
        {
            'category': 'Chronic Conditions',
            'description': 'Diabetes, chronic kidney disease, sickle cell disease, and other chronic pediatric conditions',
            'example_guidelines': [
                'Type 1 Diabetes in Children',
                'Sickle Cell Disease Management',
                'Chronic Kidney Disease',
                'Inflammatory Bowel Disease'
            ]
        },
        {
            'category': 'Special Health Care Needs',
            'description': 'Children with disabilities, complex medical needs, and care coordination',
            'example_guidelines': [
                'Care Coordination for Children with Special Health Care Needs',
                'Medical Home',
                'Transition to Adult Care'
            ]
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
