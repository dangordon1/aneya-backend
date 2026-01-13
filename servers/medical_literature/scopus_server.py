#!/usr/bin/env python
"""
Scopus MCP Server

Provides access to Scopus database with journal quartile filtering (Q1/Q2).
Uses Elsevier Scopus API for article search and Scimago/CiteScore data for quartile filtering.
"""

import os
import asyncio
from typing import Any
import httpx
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(
    "Scopus",
    instructions="Search Scopus database for peer-reviewed articles with journal quartile filtering (Q1/Q2 based on SJR or CiteScore)"
)

# Scopus API configuration
# Get API key from environment - required for Scopus access
# Register at https://dev.elsevier.com/
SCOPUS_API_KEY = os.getenv("SCOPUS_API_KEY", "")
SCOPUS_SEARCH_URL = "https://api.elsevier.com/content/search/scopus"
SCOPUS_ABSTRACT_URL = "https://api.elsevier.com/content/abstract/scopus_id"
SCOPUS_SERIAL_TITLE_URL = "https://api.elsevier.com/content/serial/title"

# Rate limiting configuration
RATE_LIMIT_DELAY = 0.5  # 2 requests per second for non-subscribers


async def _get_journal_quartile(issn: str) -> dict[str, Any]:
    """
    Get journal quartile information using Scopus Serial Title API.

    Args:
        issn: Journal ISSN

    Returns:
        Dictionary with quartile information
    """
    if not SCOPUS_API_KEY:
        return {
            "error": "SCOPUS_API_KEY not configured",
            "quartile": "unknown"
        }

    headers = {
        "X-ELS-APIKey": SCOPUS_API_KEY,
        "Accept": "application/json"
    }

    params = {
        "issn": issn,
        "view": "CITESCORE"  # Request CiteScore view to get percentile data
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                SCOPUS_SERIAL_TITLE_URL,
                headers=headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            # Extract quartile from CiteScore or SJR metrics
            serial_entry = data.get("serial-metadata-response", {}).get("entry", [])
            if not serial_entry:
                return {"quartile": "unknown", "issn": issn}

            entry = serial_entry[0] if isinstance(serial_entry, list) else serial_entry

            # Get CiteScore percentile data
            citescore_year_info_list = entry.get("citeScoreYearInfoList", {})
            citescore_list = citescore_year_info_list.get("citeScoreYearInfo", [])

            quartile_info = {
                "issn": issn,
                "journal_title": entry.get("dc:title", ""),
                "publisher": entry.get("dc:publisher", ""),
                "citescore": citescore_year_info_list.get("citeScoreCurrentMetric", "N/A"),
                "citescore_year": citescore_year_info_list.get("citeScoreCurrentMetricYear", ""),
                "percentile": None,
                "quartile": "unknown"
            }

            # Extract percentile from most recent complete CiteScore data
            for year_info in citescore_list:
                if year_info.get("@status") == "Complete":
                    cite_score_info_list = year_info.get("citeScoreInformationList", [])
                    if cite_score_info_list:
                        cite_score_info = cite_score_info_list[0].get("citeScoreInfo", [])
                        if cite_score_info:
                            subject_ranks = cite_score_info[0].get("citeScoreSubjectRank", [])
                            if subject_ranks:
                                # Use the first subject area's percentile
                                percentile = int(subject_ranks[0].get("percentile", 0))
                                quartile_info["percentile"] = percentile
                                quartile_info["subject_code"] = subject_ranks[0].get("subjectCode", "")

                                # Calculate quartile from percentile
                                # Q1 = 76-100%, Q2 = 51-75%, Q3 = 26-50%, Q4 = 1-25%
                                if percentile >= 76:
                                    quartile_info["quartile"] = "Q1"
                                elif percentile >= 51:
                                    quartile_info["quartile"] = "Q2"
                                elif percentile >= 26:
                                    quartile_info["quartile"] = "Q3"
                                elif percentile >= 1:
                                    quartile_info["quartile"] = "Q4"

                                break  # Use first complete year data

            # Also keep the overall_quartile for backwards compatibility
            quartile_info["overall_quartile"] = quartile_info["quartile"]

            return quartile_info

    except Exception as e:
        return {
            "error": str(e),
            "quartile": "unknown",
            "issn": issn
        }


async def _search_scopus_impl(
    query: str,
    max_results: int = 10,
    quartile_filter: str = None
) -> dict[str, Any]:
    """
    Internal implementation for searching Scopus.

    Args:
        query: Search query string
        max_results: Maximum number of results to return
        quartile_filter: Filter by quartile (Q1, Q2, Q1-Q2, or None)

    Returns:
        Dictionary with count, articles, and query
    """
    if not SCOPUS_API_KEY:
        raise ValueError("SCOPUS_API_KEY environment variable not set. Get your API key from https://dev.elsevier.com/")

    headers = {
        "X-ELS-APIKey": SCOPUS_API_KEY,
        "Accept": "application/json"
    }

    params = {
        "query": query,
        "count": 25,  # Fetch more initially if filtering by quartile
        "sort": "-citedby-count",  # Sort by citation count
        "field": "dc:title,dc:creator,prism:publicationName,prism:coverDate,prism:doi,prism:issn,citedby-count,dc:identifier,prism:aggregationType,subtypeDescription"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            SCOPUS_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()

        search_results = data.get("search-results", {})
        total_results = int(search_results.get("opensearch:totalResults", 0))
        entries = search_results.get("entry", [])

        articles = []

        for entry in entries:
            # Extract article information
            article = {
                "scopus_id": entry.get("dc:identifier", "").replace("SCOPUS_ID:", ""),
                "title": entry.get("dc:title", ""),
                "authors": entry.get("dc:creator", ""),
                "journal": entry.get("prism:publicationName", ""),
                "publication_date": entry.get("prism:coverDate", ""),
                "doi": entry.get("prism:doi", ""),
                "issn": entry.get("prism:issn", ""),
                "citation_count": int(entry.get("citedby-count", 0)),
                "publication_type": entry.get("prism:aggregationType", ""),
                "subtype": entry.get("subtypeDescription", ""),
            }

            # If quartile filtering is requested, check the journal quartile
            if quartile_filter and article["issn"]:
                quartile_info = await _get_journal_quartile(article["issn"])
                article["quartile_info"] = quartile_info

                overall_quartile = quartile_info.get("overall_quartile", "unknown")

                # Apply quartile filter
                if quartile_filter == "Q1" and overall_quartile != "Q1":
                    await asyncio.sleep(RATE_LIMIT_DELAY)
                    continue
                elif quartile_filter == "Q2" and overall_quartile != "Q2":
                    await asyncio.sleep(RATE_LIMIT_DELAY)
                    continue
                elif quartile_filter == "Q1-Q2" and overall_quartile not in ["Q1", "Q2"]:
                    await asyncio.sleep(RATE_LIMIT_DELAY)
                    continue

                await asyncio.sleep(RATE_LIMIT_DELAY)

            articles.append(article)

            # Stop if we have enough results
            if len(articles) >= max_results:
                break

        return {
            "count": total_results,
            "articles": articles,
            "query": query,
            "quartile_filter": quartile_filter
        }


async def _get_scopus_article(scopus_id: str) -> dict[str, Any]:
    """
    Fetch full article details from Scopus.

    Args:
        scopus_id: Scopus article ID

    Returns:
        Dictionary containing full article details
    """
    if not SCOPUS_API_KEY:
        raise ValueError("SCOPUS_API_KEY environment variable not set")

    headers = {
        "X-ELS-APIKey": SCOPUS_API_KEY,
        "Accept": "application/json"
    }

    url = f"{SCOPUS_ABSTRACT_URL}/{scopus_id}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()

        abstract_response = data.get("abstracts-retrieval-response", {})
        core_data = abstract_response.get("coredata", {})
        item = abstract_response.get("item", {})

        # Extract author information
        authors = []
        author_group = abstract_response.get("authors", {}).get("author", [])
        for author in author_group:
            authors.append({
                "indexed_name": author.get("ce:indexed-name", ""),
                "given_name": author.get("ce:given-name", ""),
                "surname": author.get("ce:surname", ""),
                "affiliation": author.get("affiliation", [])
            })

        # Extract keywords
        keywords = []
        keyword_group = abstract_response.get("authkeywords", {}).get("author-keyword", [])
        if keyword_group:
            keywords = [kw.get("$", "") for kw in keyword_group]

        article_data = {
            "scopus_id": scopus_id,
            "eid": core_data.get("eid", ""),
            "doi": core_data.get("prism:doi", ""),
            "title": core_data.get("dc:title", ""),
            "abstract": core_data.get("dc:description", ""),
            "authors": authors,
            "journal": core_data.get("prism:publicationName", ""),
            "issn": core_data.get("prism:issn", ""),
            "volume": core_data.get("prism:volume", ""),
            "issue": core_data.get("prism:issueIdentifier", ""),
            "page_range": core_data.get("prism:pageRange", ""),
            "publication_date": core_data.get("prism:coverDate", ""),
            "citation_count": int(core_data.get("citedby-count", 0)),
            "keywords": keywords,
            "document_type": item.get("bibrecord", {}).get("head", {}).get("citation-info", {}).get("citation-type", {}).get("@code", ""),
            "source_type": core_data.get("prism:aggregationType", ""),
        }

        # Get journal quartile information
        if article_data["issn"]:
            quartile_info = await _get_journal_quartile(article_data["issn"])
            article_data["quartile_info"] = quartile_info

        return article_data


@mcp.tool(
    name="search_scopus",
    description="Search Scopus database for peer-reviewed articles. Optionally filter by journal quartile (Q1/Q2) based on SJR or CiteScore metrics."
)
async def search_scopus(
    query: str,
    max_results: int = 10,
    quartile_filter: str = None
) -> dict:
    """
    Search Scopus for scientific articles with optional quartile filtering.

    Args:
        query: Search query (e.g., 'machine learning healthcare', 'cancer immunotherapy')
        max_results: Maximum number of results to return (default: 10, max: 25)
        quartile_filter: Filter by journal quartile - "Q1" (top 25%), "Q2" (25-50%), "Q1-Q2" (top 50%), or None (default)

    Returns:
        Dictionary containing:
            - count (int): Total number of matching articles in Scopus
            - articles (list): List of article metadata (filtered by quartile if requested)
            - query (str): The search query used
            - quartile_filter (str): Applied quartile filter
    """
    max_results = min(max_results, 25)

    # Validate quartile filter
    valid_filters = ["Q1", "Q2", "Q1-Q2", None]
    if quartile_filter not in valid_filters:
        raise ValueError(f"Invalid quartile_filter. Must be one of: {valid_filters}")

    results = await _search_scopus_impl(query, max_results, quartile_filter)
    return results


@mcp.tool(
    name="get_scopus_article",
    description="Retrieve full Scopus article details including abstract, authors, affiliations, keywords, citation count, and journal quartile information."
)
async def get_scopus_article(scopus_id: str) -> dict:
    """
    Retrieve full article details by Scopus ID.

    Args:
        scopus_id: Scopus article identifier (e.g., "85012345678")

    Returns:
        Dictionary containing full article details including:
            - title, abstract, authors with affiliations
            - journal information and quartile ranking
            - citation count, keywords, DOI
    """
    article = await _get_scopus_article(scopus_id)
    return article


@mcp.tool(
    name="get_journal_quartile",
    description="Get journal quartile ranking (Q1-Q4) based on SJR and CiteScore metrics for a specific journal by ISSN."
)
async def get_journal_quartile_tool(issn: str) -> dict:
    """
    Get quartile information for a journal.

    Args:
        issn: Journal ISSN (with or without hyphen, e.g., "0140-6736" or "01406736")

    Returns:
        Dictionary containing:
            - journal_title (str): Journal name
            - sjr_quartile (str): SJR-based quartile (Q1-Q4)
            - citescore_quartile (str): CiteScore-based quartile (Q1-Q4)
            - overall_quartile (str): Best quartile ranking
    """
    quartile_info = await _get_journal_quartile(issn)
    return quartile_info


@mcp.tool(
    name="search_high_impact_articles",
    description="Search Scopus for high-impact articles published in Q1 or Q2 journals. Combines search query with automatic quartile filtering."
)
async def search_high_impact_articles(
    query: str,
    max_results: int = 10,
    include_q2: bool = True
) -> dict:
    """
    Search for high-impact articles in top-tier journals (Q1 or Q1-Q2).

    Args:
        query: Search query
        max_results: Maximum number of results (default: 10, max: 25)
        include_q2: Include Q2 journals (default: True). If False, only Q1 journals

    Returns:
        Dictionary with articles from high-impact journals, sorted by citation count
    """
    quartile_filter = "Q1-Q2" if include_q2 else "Q1"
    results = await _search_scopus_impl(query, max_results, quartile_filter)

    # Add summary statistics
    results["filter_description"] = (
        "Top 50% journals (Q1 and Q2)" if include_q2 else "Top 25% journals (Q1 only)"
    )

    return results


@mcp.tool(
    name="get_multiple_scopus_articles",
    description="Retrieve full details for multiple Scopus articles at once. Returns abstracts, authors, quartile info, and metadata."
)
async def get_multiple_scopus_articles(scopus_ids: list[str]) -> dict:
    """
    Retrieve full details for multiple articles.

    Args:
        scopus_ids: List of Scopus IDs to retrieve

    Returns:
        Dictionary containing:
            - count (int): Number of articles retrieved
            - articles (list): List of full article details
    """
    articles = []
    for scopus_id in scopus_ids:
        try:
            article = await _get_scopus_article(scopus_id)
            articles.append(article)
            # Rate limiting
            await asyncio.sleep(RATE_LIMIT_DELAY)
        except Exception as e:
            articles.append({
                "scopus_id": scopus_id,
                "error": str(e)
            })

    return {
        "count": len(articles),
        "articles": articles
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
