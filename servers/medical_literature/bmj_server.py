#!/usr/bin/env python
"""
BMJ (British Medical Journal) MCP Server

Provides access to BMJ's medical literature database for evidence-based clinical guidance.
Uses BMJ Best Practice and BMJ Case Reports APIs where available.
"""

import os
import asyncio
from typing import Any
import httpx
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(
    "BMJ",
    instructions="Search and retrieve peer-reviewed medical literature from BMJ (British Medical Journal) for evidence-based clinical guidance"
)

# BMJ API configuration
# Note: BMJ provides both open access content and subscription-only content
# For full access, an API key from BMJ is required
BMJ_API_KEY = os.getenv("BMJ_API_KEY", "")
BMJ_SEARCH_URL = "https://www.bmj.com/search/advanced/"
BMJ_API_BASE = "https://www.bmj.com/api/v1"

# Alternative: Use Europe PMC which indexes BMJ content
EUROPE_PMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUROPE_PMC_ARTICLE = "https://www.ebi.ac.uk/europepmc/webservices/rest/article"


async def _search_bmj_via_europepmc(query: str, max_results: int = 10) -> dict[str, Any]:
    """
    Search for BMJ articles via Europe PMC API.

    Args:
        query: Search query string
        max_results: Maximum number of results to return

    Returns:
        Dictionary with count, articles, and query
    """
    # Add BMJ journal filter to the query
    bmj_query = f'{query} AND (JOURNAL:"BMJ" OR JOURNAL:"British Medical Journal" OR JOURNAL:"BMJ Case Rep" OR JOURNAL:"BMJ Open")'

    params = {
        "query": bmj_query,
        "format": "json",
        "pageSize": min(max_results, 100),
        "resultType": "core"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(EUROPE_PMC_SEARCH, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()

        if "resultList" not in data:
            raise ValueError(f"Unexpected API response structure: {data}")

        result_list = data["resultList"]
        results = result_list.get("result", [])
        hit_count = int(data.get("hitCount", 0))

        articles = []
        for result in results:
            article = {
                "id": result.get("id", ""),
                "source": result.get("source", ""),
                "pmid": result.get("pmid", ""),
                "pmcid": result.get("pmcid", ""),
                "doi": result.get("doi", ""),
                "title": result.get("title", ""),
                "authors": [
                    {
                        "fullName": author.get("fullName", ""),
                        "firstName": author.get("firstName", ""),
                        "lastName": author.get("lastName", "")
                    }
                    for author in result.get("authorList", {}).get("author", [])
                ],
                "journal": result.get("journalTitle", ""),
                "journalVolume": result.get("journalVolume", ""),
                "journalIssue": result.get("issue", ""),
                "pubYear": result.get("pubYear", ""),
                "pubDate": result.get("firstPublicationDate", ""),
                "isOpenAccess": result.get("isOpenAccess", "N") == "Y",
                "abstractText": result.get("abstractText", ""),
            }
            articles.append(article)

        return {
            "count": hit_count,
            "articles": articles,
            "query": query
        }


async def _get_bmj_article_details(article_id: str, source: str = "MED") -> dict[str, Any]:
    """
    Fetch full article details from Europe PMC.

    Args:
        article_id: Article ID (PMID, PMCID, or DOI)
        source: Source database (MED for PubMed, PMC for PMC, DOI for DOI)

    Returns:
        Dictionary containing full article details
    """
    url = f"{EUROPE_PMC_ARTICLE}/{source}/{article_id}"
    params = {"format": "json"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()

        if "result" not in data:
            raise ValueError(f"Unexpected API response structure: {data}")

        result = data["result"]

        article_data = {
            "id": result.get("id", ""),
            "source": result.get("source", ""),
            "pmid": result.get("pmid", ""),
            "pmcid": result.get("pmcid", ""),
            "doi": result.get("doi", ""),
            "title": result.get("title", ""),
            "authors": [
                {
                    "fullName": author.get("fullName", ""),
                    "firstName": author.get("firstName", ""),
                    "lastName": author.get("lastName", ""),
                    "affiliation": author.get("affiliation", "")
                }
                for author in result.get("authorList", {}).get("author", [])
            ],
            "journal": result.get("journalInfo", {}).get("journal", {}).get("title", ""),
            "journalVolume": result.get("journalInfo", {}).get("volume", ""),
            "journalIssue": result.get("journalInfo", {}).get("issue", ""),
            "pubYear": result.get("journalInfo", {}).get("yearOfPublication", ""),
            "pubDate": result.get("firstPublicationDate", ""),
            "isOpenAccess": result.get("isOpenAccess", "N") == "Y",
            "abstractText": result.get("abstractText", ""),
            "fullTextUrl": result.get("fullTextUrlList", {}).get("fullTextUrl", []),
            "keywords": [kw.get("value", "") for kw in result.get("keywordList", {}).get("keyword", [])],
        }

        return article_data


async def _download_bmj_pdf(doi: str, pmcid: str = "") -> dict[str, Any]:
    """
    Get download information for a BMJ article.

    Args:
        doi: Article DOI
        pmcid: PubMed Central ID (if available)

    Returns:
        Dictionary with download URLs and access information
    """
    download_info = {
        "doi": doi,
        "pmcid": pmcid,
        "urls": []
    }

    # Add BMJ direct URL
    if doi:
        bmj_url = f"https://www.bmj.com/content/{doi}"
        download_info["urls"].append({
            "type": "html",
            "url": bmj_url,
            "description": "BMJ HTML version (may require subscription)"
        })

        # BMJ PDF URL pattern
        pdf_url = f"https://www.bmj.com/content/{doi}.full.pdf"
        download_info["urls"].append({
            "type": "pdf",
            "url": pdf_url,
            "description": "BMJ PDF version (may require subscription)"
        })

    # Add Europe PMC URL for open access content
    if pmcid:
        pmc_url = f"https://europepmc.org/article/PMC/{pmcid.replace('PMC', '')}"
        download_info["urls"].append({
            "type": "html",
            "url": pmc_url,
            "description": "Europe PMC version (open access if available)"
        })

    download_info["note"] = "Some BMJ content requires institutional subscription. Open access articles are freely available."

    return download_info


@mcp.tool(
    name="search_bmj",
    description="Search BMJ (British Medical Journal) publications for peer-reviewed medical literature. Returns article metadata including titles, authors, abstracts, and publication details."
)
async def search_bmj(query: str, max_results: int = 10) -> dict:
    """
    Search BMJ publications for medical articles.

    Args:
        query: Search query (e.g., 'acute myocardial infarction', 'diabetes management', 'sepsis guidelines')
        max_results: Maximum number of results to return (default: 10, max: 100)

    Returns:
        Dictionary containing:
            - count (int): Total number of matching articles
            - articles (list): List of article metadata
            - query (str): The search query used
    """
    max_results = min(max_results, 100)
    results = await _search_bmj_via_europepmc(query, max_results)
    return results


@mcp.tool(
    name="get_bmj_article",
    description="Retrieve full BMJ article details including abstract, authors, journal information, keywords, and full text URLs by article ID (PMID, PMCID, or DOI)."
)
async def get_bmj_article(article_id: str, id_type: str = "MED") -> dict:
    """
    Retrieve full article details by ID.

    Args:
        article_id: Article identifier (PMID, PMCID, or DOI)
        id_type: Type of ID - "MED" for PMID (default), "PMC" for PMCID, "DOI" for DOI

    Returns:
        Dictionary containing full article details including abstract, authors, and download URLs
    """
    article = await _get_bmj_article_details(article_id, id_type)
    return article


@mcp.tool(
    name="download_bmj_article",
    description="Get download URLs and access information for a BMJ article. Returns links to HTML and PDF versions, with notes about subscription requirements."
)
async def download_bmj_article(doi: str, pmcid: str = "") -> dict:
    """
    Get download information for a BMJ article.

    Args:
        doi: Article DOI (required)
        pmcid: PubMed Central ID (optional, for open access content)

    Returns:
        Dictionary containing:
            - doi (str): Article DOI
            - pmcid (str): Article PMCID if provided
            - urls (list): List of download URLs with type and description
            - note (str): Information about access requirements
    """
    download_info = await _download_bmj_pdf(doi, pmcid)
    return download_info


@mcp.tool(
    name="get_multiple_bmj_articles",
    description="Retrieve full details for multiple BMJ articles at once. Returns abstracts, authors, and metadata for all specified article IDs."
)
async def get_multiple_bmj_articles(article_ids: list[str], id_type: str = "MED") -> dict:
    """
    Retrieve full details for multiple BMJ articles.

    Args:
        article_ids: List of article IDs to retrieve
        id_type: Type of ID - "MED" for PMID (default), "PMC" for PMCID, "DOI" for DOI

    Returns:
        Dictionary containing:
            - count (int): Number of articles retrieved
            - articles (list): List of full article details
    """
    articles = []
    for article_id in article_ids:
        try:
            article = await _get_bmj_article_details(article_id, id_type)
            articles.append(article)
            # Rate limiting - be respectful to Europe PMC
            await asyncio.sleep(0.2)
        except Exception as e:
            # Add error entry but continue processing other articles
            articles.append({
                "id": article_id,
                "error": str(e)
            })

    return {
        "count": len(articles),
        "articles": articles
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
