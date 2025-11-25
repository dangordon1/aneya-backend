#!/usr/bin/env python
"""
AHA/ACC (American Heart Association / American College of Cardiology) Guidelines MCP Server

This MCP server provides tools to search and access joint AHA/ACC cardiovascular clinical
practice guidelines. These organizations publish evidence-based recommendations for prevention,
diagnosis, and treatment of cardiovascular diseases.

Uses web scraping to retrieve published guidance from https://professional.heart.org/
and https://www.acc.org/
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
    "AHA-ACC-Guidelines",
    instructions="Search and retrieve AHA/ACC cardiovascular clinical practice guidelines including heart failure, arrhythmias, coronary artery disease, hypertension, valvular disease, and prevention recommendations"
)

# AHA/ACC URLs
AHA_BASE_URL = "https://professional.heart.org"
ACC_BASE_URL = "https://www.acc.org"
AHA_GUIDELINES_URL = f"{AHA_BASE_URL}/en/science-news/guidelines"
ACC_GUIDELINES_URL = f"{ACC_BASE_URL}/guidelines"
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
        await asyncio.sleep(0.6)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            return response.text
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return None


@mcp.tool(
    name="search_cardiovascular_guidelines",
    description="Search AHA/ACC cardiovascular guidelines by topic or condition. Returns evidence-based recommendations for heart disease, hypertension, heart failure, arrhythmias, valvular disease, and cardiovascular prevention."
)
async def search_cardiovascular_guidelines(topic: str, max_results: int = 20) -> dict:
    """
    Search AHA/ACC guidelines by topic or cardiovascular condition.

    Args:
        topic: Search term (e.g., "heart failure", "atrial fibrillation", "hypertension", "STEMI")
        max_results: Maximum number of results to return (default: 20, max: 50)

    Returns:
        Dictionary containing:
            - success (bool): Whether the search was successful
            - query (str): The search term used
            - count (int): Number of results found
            - results (list): List of matching guidelines with:
                - title (str): Guideline title
                - url (str): Full URL to the guideline
                - year (str): Publication year
                - organizations (list): Publishing organizations (AHA, ACC, other)
                - category (str): Cardiovascular category
                - summary (str): Brief summary if available
            - error (str|None): Error message if search failed
    """
    max_results = min(max_results, 50)

    # Clean topic
    topic_clean = " ".join(topic.split())

    results = []

    # Try AHA guidelines page first
    html = await fetch_page(AHA_GUIDELINES_URL)
    if html:
        soup = BeautifulSoup(html, 'html.parser')

        # Find guideline items
        guideline_items = soup.find_all(['article', 'div', 'li'], class_=re.compile(r'guideline|publication|card'))

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
                link = f"{AHA_BASE_URL}{link}" if link.startswith('/') else link

            # Extract year
            year = 'Not available'
            year_match = re.search(r'\b(20\d{2})\b', title)
            if year_match:
                year = year_match.group(1)
            else:
                year_elem = item.find(['time', 'span'], class_=re.compile(r'year|date'))
                if year_elem:
                    year_text = year_elem.get_text(strip=True)
                    year_match = re.search(r'\b(20\d{2})\b', year_text)
                    if year_match:
                        year = year_match.group(1)

            # Determine organizations
            orgs = ['AHA']
            if 'acc' in title.lower() or 'college of cardiology' in title.lower():
                orgs.append('ACC')
            if 'hrs' in title.lower() or 'heart rhythm' in title.lower():
                orgs.append('HRS')

            # Extract summary
            summary = ''
            summary_elem = item.find(['p', 'div'], class_=re.compile(r'summary|description|excerpt'))
            if summary_elem:
                summary = summary_elem.get_text(strip=True)[:300]

            # Categorize
            category = 'Cardiovascular Disease'
            title_lower = title.lower()
            if any(term in title_lower for term in ['heart failure', 'hf', 'hfref', 'hfpef']):
                category = 'Heart Failure'
            elif any(term in title_lower for term in ['atrial fibrillation', 'afib', 'af', 'arrhythmia', 'svt', 'vt']):
                category = 'Arrhythmias'
            elif any(term in title_lower for term in ['hypertension', 'blood pressure', 'bp']):
                category = 'Hypertension'
            elif any(term in title_lower for term in ['coronary', 'cad', 'acs', 'stemi', 'nstemi', 'angina']):
                category = 'Coronary Artery Disease'
            elif any(term in title_lower for term in ['valve', 'valvular', 'aortic', 'mitral', 'tricuspid']):
                category = 'Valvular Heart Disease'
            elif any(term in title_lower for term in ['prevention', 'risk assessment', 'lipid', 'cholesterol']):
                category = 'Cardiovascular Prevention'
            elif any(term in title_lower for term in ['perioperative', 'noncardiac surgery']):
                category = 'Perioperative Care'
            elif any(term in title_lower for term in ['cardiomyopathy', 'myocarditis', 'pericarditis']):
                category = 'Cardiomyopathy'

            if title and link:
                results.append({
                    'title': title,
                    'url': link,
                    'year': year,
                    'organizations': orgs,
                    'category': category,
                    'summary': summary
                })

            if len(results) >= max_results:
                break

    # If not enough results, try ACC website
    if len(results) < max_results:
        html = await fetch_page(ACC_GUIDELINES_URL)
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            guideline_items = soup.find_all(['article', 'div', 'li'], class_=re.compile(r'guideline|publication'))

            for item in guideline_items:
                if len(results) >= max_results:
                    break

                title_elem = item.find(['h2', 'h3', 'a'])
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)

                # Filter by topic
                if topic_clean.lower() not in title.lower():
                    continue

                link = ''
                if title_elem.name == 'a':
                    link = title_elem.get('href', '')
                else:
                    link_elem = item.find('a', href=True)
                    if link_elem:
                        link = link_elem.get('href', '')

                if link and not link.startswith('http'):
                    link = f"{ACC_BASE_URL}{link}" if link.startswith('/') else link

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
                    'organizations': ['ACC'],
                    'category': 'Cardiovascular Disease',
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
    description="Get detailed content from a specific AHA/ACC guideline including recommendations, evidence levels, and clinical implementation guidance."
)
async def get_guideline_content(identifier: str) -> dict:
    """
    Get detailed information about a specific AHA/ACC guideline.

    Args:
        identifier: Guideline URL, title, or identifier

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - title (str): Guideline title
            - url (str): Direct URL to the guideline
            - year (str): Publication year
            - organizations (list): Publishing organizations
            - summary (str): Executive summary
            - recommendations (list): Key recommendations with class and level
            - sections (list): Guideline sections with content
            - related_guidelines (list): Related guidelines
            - error (str|None): Error message if retrieval failed
    """
    # Determine URL
    if identifier.startswith('http'):
        url = identifier
    else:
        # Try to search for it
        search_result = await search_cardiovascular_guidelines(identifier, max_results=1)
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

    # Determine organizations
    orgs = []
    if 'aha' in title.lower() or 'american heart' in title.lower():
        orgs.append('AHA')
    if 'acc' in title.lower() or 'college of cardiology' in title.lower():
        orgs.append('ACC')
    if not orgs:
        orgs = ['AHA/ACC']

    # Extract summary
    summary = ''
    summary_elem = soup.find(['div', 'section'], class_=re.compile(r'abstract|summary|executive|overview|key-points'))
    if summary_elem:
        paragraphs = summary_elem.find_all('p', limit=3)
        summary = ' '.join([p.get_text(strip=True) for p in paragraphs])

    if not summary:
        main_content = soup.find(['main', 'article'], class_=re.compile(r'content|body'))
        if main_content:
            paragraphs = main_content.find_all('p', limit=3)
            summary = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

    # Extract recommendations
    recommendations = []

    # Look for recommendation sections
    rec_sections = soup.find_all(['div', 'section'], class_=re.compile(r'recommendation'))
    for section in rec_sections[:20]:
        text = section.get_text(strip=True)

        # Try to extract class and level of evidence
        # AHA/ACC uses format like "Class I, Level A" or "COR: I, LOE: A"
        class_match = re.search(r'\bClass\s+([I]+|IV?)\b|\bCOR:\s*([I]+|IV?)\b', text, re.IGNORECASE)
        level_match = re.search(r'\bLevel\s+([A-C])\b|\bLOE:\s*([A-C])\b', text, re.IGNORECASE)

        cor = class_match.group(1) or class_match.group(2) if class_match else 'Not specified'
        loe = level_match.group(1) or level_match.group(2) if level_match else 'Not specified'

        if len(text) > 30:
            recommendations.append({
                'text': text[:600],
                'class_of_recommendation': cor,
                'level_of_evidence': loe
            })

    # If no recommendations found, look for numbered items
    if not recommendations:
        numbered_items = soup.find_all(['li', 'p'])
        for item in numbered_items:
            text = item.get_text(strip=True)
            if re.match(r'^\d+\.', text) and len(text) > 40:
                # Try to extract class and level
                class_match = re.search(r'\bClass\s+([I]+|IV?)\b', text)
                level_match = re.search(r'\bLevel\s+([A-C])\b', text)

                recommendations.append({
                    'text': text[:600],
                    'class_of_recommendation': class_match.group(1) if class_match else 'Not specified',
                    'level_of_evidence': level_match.group(1) if level_match else 'Not specified'
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

    # Extract related guidelines
    related = []
    related_section = soup.find(['div', 'aside', 'section'], class_=re.compile(r'related|see-also'))
    if related_section:
        for link in related_section.find_all('a', href=True)[:5]:
            title = link.get_text(strip=True)
            if title and len(title) > 10:
                href = link.get('href', '')
                if href and not href.startswith('http'):
                    href = f"{AHA_BASE_URL}{href}" if href.startswith('/') else href
                related.append({
                    'title': title,
                    'url': href
                })

    return {
        'success': True,
        'title': title,
        'url': url,
        'year': year,
        'organizations': orgs,
        'summary': summary[:1000] if summary else 'Not available',
        'recommendations': recommendations,
        'sections': sections,
        'related_guidelines': related,
        'error': None
    }


@mcp.tool(
    name="list_guideline_categories",
    description="List major AHA/ACC guideline categories including heart failure, arrhythmias, coronary disease, hypertension, valvular disease, prevention, and perioperative care."
)
async def list_guideline_categories() -> dict:
    """
    List available AHA/ACC guideline categories and topics.

    Returns:
        Dictionary containing:
            - success (bool): Whether the retrieval was successful
            - categories (list): List of guideline categories with:
                - name (str): Category name
                - description (str): Category description
                - example_guidelines (list): Example guidelines in category
            - error (str|None): Error message if retrieval failed
    """
    categories = [
        {
            'name': 'Heart Failure',
            'description': 'Guidelines for diagnosis and management of heart failure including HFrEF, HFpEF, and advanced heart failure',
            'example_guidelines': [
                'Heart Failure Management',
                'Chronic Heart Failure',
                'Acute Decompensated Heart Failure',
                'Advanced Heart Failure and Cardiac Transplantation'
            ]
        },
        {
            'name': 'Arrhythmias and Electrophysiology',
            'description': 'Guidelines for atrial fibrillation, ventricular arrhythmias, and device therapy',
            'example_guidelines': [
                'Atrial Fibrillation Management',
                'Ventricular Arrhythmias and Sudden Cardiac Death',
                'Supraventricular Tachycardia',
                'Cardiac Pacing and Cardiac Resynchronization Therapy'
            ]
        },
        {
            'name': 'Coronary Artery Disease',
            'description': 'Guidelines for stable ischemic heart disease, ACS, and revascularization',
            'example_guidelines': [
                'STEMI Management',
                'NSTEMI and Unstable Angina',
                'Stable Ischemic Heart Disease',
                'Coronary Artery Revascularization'
            ]
        },
        {
            'name': 'Hypertension',
            'description': 'Guidelines for detection, evaluation, and management of high blood pressure',
            'example_guidelines': [
                'High Blood Pressure in Adults',
                'Resistant Hypertension',
                'Hypertension in Pregnancy',
                'Secondary Hypertension'
            ]
        },
        {
            'name': 'Valvular Heart Disease',
            'description': 'Guidelines for management of valvular disorders including surgical and transcatheter interventions',
            'example_guidelines': [
                'Valvular Heart Disease Management',
                'Aortic Stenosis (TAVR)',
                'Mitral Regurgitation',
                'Prosthetic Valve Management'
            ]
        },
        {
            'name': 'Cardiovascular Prevention',
            'description': 'Guidelines for primary and secondary prevention including lipid management and risk assessment',
            'example_guidelines': [
                'Cholesterol Management',
                'Primary Prevention of Cardiovascular Disease',
                'Secondary Prevention for Coronary and Other Atherosclerotic Disease',
                'Aspirin Use in Primary Prevention'
            ]
        },
        {
            'name': 'Cardiomyopathy',
            'description': 'Guidelines for hypertrophic cardiomyopathy, myocarditis, and other cardiomyopathies',
            'example_guidelines': [
                'Hypertrophic Cardiomyopathy',
                'Myocarditis',
                'Restrictive Cardiomyopathy',
                'Arrhythmogenic Right Ventricular Cardiomyopathy'
            ]
        },
        {
            'name': 'Perioperative Cardiovascular Care',
            'description': 'Guidelines for cardiovascular evaluation and management for noncardiac surgery',
            'example_guidelines': [
                'Perioperative Cardiovascular Evaluation for Noncardiac Surgery',
                'Perioperative Beta-Blocker Therapy'
            ]
        },
        {
            'name': 'Peripheral Arterial Disease',
            'description': 'Guidelines for PAD diagnosis and management',
            'example_guidelines': [
                'Lower Extremity Peripheral Artery Disease',
                'Carotid Artery Disease'
            ]
        },
        {
            'name': 'Congenital Heart Disease',
            'description': 'Guidelines for adults with congenital heart disease',
            'example_guidelines': [
                'Adults with Congenital Heart Disease'
            ]
        },
        {
            'name': 'Cardiopulmonary Resuscitation',
            'description': 'AHA guidelines for CPR and emergency cardiovascular care',
            'example_guidelines': [
                'CPR and Emergency Cardiovascular Care',
                'Advanced Cardiovascular Life Support',
                'Pediatric Advanced Life Support'
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
