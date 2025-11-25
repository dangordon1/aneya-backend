#!/usr/bin/env python
"""
PubMed MCP Server

Provides access to PubMed's 35M+ peer-reviewed medical literature via NCBI E-utilities.
Enables evidence-based clinical decision support when guidelines are not available.
"""

import os
import asyncio
from typing import Any
import httpx
from xml.etree import ElementTree as ET
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(
    "PubMed",
    instructions="Search and retrieve peer-reviewed medical literature from PubMed (35M+ articles) for evidence-based clinical guidance"
)

# NCBI E-utilities base URLs
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# Get API key from environment (optional but recommended for higher rate limits)
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")


async def _search_pubmed_impl(query: str, max_results: int = 10) -> dict[str, Any]:
    """
    Internal implementation for searching PubMed.

    Args:
        query: Search query string
        max_results: Maximum number of results to return

    Returns:
        Dictionary with count, pmids, and query
    """
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
    }

    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    async with httpx.AsyncClient() as client:
        response = await client.get(ESEARCH_URL, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()

        if "esearchresult" not in data:
            raise ValueError(f"Unexpected API response structure: {data}")

        esearch_result = data["esearchresult"]

        if "ERROR" in esearch_result:
            raise ValueError(f"PubMed API error: {esearch_result['ERROR']}")

        count = int(esearch_result.get("count", 0))
        pmids = esearch_result.get("idlist", [])

        return {
            "count": count,
            "pmids": pmids,
            "query": query
        }


async def _get_article_summaries(pmids: list[str]) -> list[dict[str, Any]]:
    """
    Get article summaries for a list of PMIDs.

    Args:
        pmids: List of PubMed IDs

    Returns:
        List of article summaries
    """
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }

    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    async with httpx.AsyncClient() as client:
        response = await client.get(ESUMMARY_URL, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()

        if "result" not in data:
            raise ValueError(f"Unexpected API response structure: {data}")

        if "error" in data:
            raise ValueError(f"PubMed API error: {data['error']}")

        summaries = []
        for pmid in pmids:
            if pmid in data["result"]:
                article = data["result"][pmid]
                if isinstance(article, dict) and "error" in article:
                    continue
                summaries.append({
                    "pmid": pmid,
                    "title": article.get("title", ""),
                    "authors": [author.get("name", "") for author in article.get("authors", [])],
                    "journal": article.get("fulljournalname", ""),
                    "pubdate": article.get("pubdate", ""),
                    "doi": article.get("elocationid", "").replace("doi: ", ""),
                })

        return summaries


async def _fetch_article_abstract(pmid: str) -> dict[str, Any]:
    """
    Fetch full article details including abstract from PubMed.

    Args:
        pmid: PubMed ID

    Returns:
        Dictionary containing article details
    """
    params = {
        "db": "pubmed",
        "id": pmid,
        "retmode": "xml",
    }

    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    async with httpx.AsyncClient() as client:
        response = await client.get(EFETCH_URL, params=params, timeout=30.0)
        response.raise_for_status()

        root = ET.fromstring(response.text)

        article_data = {
            "pmid": pmid,
            "title": "",
            "abstract": "",
            "authors": [],
            "journal": "",
            "pubdate": "",
            "doi": "",
            "keywords": [],
        }

        article = root.find(".//PubmedArticle")
        if article is None:
            return article_data

        # Title
        title_elem = article.find(".//ArticleTitle")
        if title_elem is not None and title_elem.text:
            article_data["title"] = title_elem.text

        # Abstract
        abstract_texts = article.findall(".//AbstractText")
        if abstract_texts:
            abstract_parts = []
            for abstract_text in abstract_texts:
                label = abstract_text.get("Label", "")
                text = abstract_text.text or ""
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            article_data["abstract"] = "\n\n".join(abstract_parts)

        # Authors
        authors = article.findall(".//Author")
        for author in authors:
            last_name = author.find("LastName")
            fore_name = author.find("ForeName")
            if last_name is not None and fore_name is not None:
                article_data["authors"].append(f"{fore_name.text} {last_name.text}")

        # Journal
        journal = article.find(".//Journal/Title")
        if journal is not None and journal.text:
            article_data["journal"] = journal.text

        # Publication date
        pub_date = article.find(".//PubDate")
        if pub_date is not None:
            year = pub_date.find("Year")
            month = pub_date.find("Month")
            day = pub_date.find("Day")
            date_parts = []
            if year is not None and year.text:
                date_parts.append(year.text)
            if month is not None and month.text:
                date_parts.append(month.text)
            if day is not None and day.text:
                date_parts.append(day.text)
            article_data["pubdate"] = " ".join(date_parts)

        # DOI
        article_ids = article.findall(".//ArticleId")
        for article_id in article_ids:
            if article_id.get("IdType") == "doi":
                article_data["doi"] = article_id.text or ""

        # Keywords
        keywords = article.findall(".//Keyword")
        article_data["keywords"] = [kw.text for kw in keywords if kw.text]

        return article_data


@mcp.tool(
    name="search_pubmed",
    description="Search PubMed for peer-reviewed medical literature (35M+ articles). Returns article PMIDs, titles, authors, and basic information matching the search query."
)
async def search_pubmed(query: str, max_results: int = 10) -> dict:
    """
    Search PubMed for scientific articles.

    Args:
        query: Search query (e.g., 'croup treatment children', 'sepsis antibiotic therapy', 'postoperative infection')
        max_results: Maximum number of results to return (default: 10, max: 100)

    Returns:
        Dictionary containing:
            - count (int): Total number of matching articles
            - results (list): List of article summaries with pmid, title, authors, journal, pubdate, doi
            - query (str): The search query used
    """
    max_results = min(max_results, 100)

    # Search PubMed
    search_results = await _search_pubmed_impl(query, max_results)
    summaries = await _get_article_summaries(search_results["pmids"])

    return {
        "count": search_results["count"],
        "results": summaries,
        "query": query
    }


@mcp.tool(
    name="get_article",
    description="Retrieve full PubMed article details including title, abstract, authors, journal, publication date, DOI, and keywords for a specific article by PMID."
)
async def get_article(pmid: str) -> dict:
    """
    Retrieve full article details by PMID.

    Args:
        pmid: PubMed ID (PMID) of the article

    Returns:
        Dictionary containing:
            - pmid (str): PubMed ID
            - title (str): Article title
            - abstract (str): Full abstract
            - authors (list): List of author names
            - journal (str): Journal name
            - pubdate (str): Publication date
            - doi (str): DOI if available
            - keywords (list): Article keywords
    """
    article = await _fetch_article_abstract(pmid)
    return article


@mcp.tool(
    name="get_multiple_articles",
    description="Retrieve full details for multiple PubMed articles at once. Returns abstracts, titles, authors, and metadata for all specified PMIDs."
)
async def get_multiple_articles(pmids: list[str]) -> dict:
    """
    Retrieve full details for multiple articles.

    Args:
        pmids: List of PubMed IDs to retrieve

    Returns:
        Dictionary containing:
            - count (int): Number of articles retrieved
            - articles (list): List of article details
    """
    articles = []
    for pmid in pmids:
        article = await _fetch_article_abstract(pmid)
        articles.append(article)
        # Rate limiting (3 requests/second without API key, 10 with key)
        if not NCBI_API_KEY:
            await asyncio.sleep(0.34)
        else:
            await asyncio.sleep(0.1)

    return {
        "count": len(articles),
        "articles": articles
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
