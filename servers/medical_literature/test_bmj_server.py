#!/usr/bin/env python
"""
Test script for BMJ MCP Server
"""

import asyncio
from bmj_server import (
    _search_bmj_via_europepmc,
    _get_bmj_article_details,
    _download_bmj_pdf,
)


async def test_search_bmj():
    """Test searching BMJ articles."""
    print("\n=== Testing BMJ Search ===")
    query = "acute myocardial infarction"
    print(f"Query: {query}")

    try:
        result = await _search_bmj_via_europepmc(query, max_results=5)
        print(f"\nTotal results: {result['count']}")
        print(f"Returned articles: {len(result['articles'])}")

        if result['articles']:
            print("\nFirst article:")
            first = result['articles'][0]
            print(f"  Title: {first['title']}")
            print(f"  Journal: {first['journal']}")
            print(f"  DOI: {first.get('doi', 'N/A')}")
            print(f"  PMID: {first.get('pmid', 'N/A')}")
            print(f"  Open Access: {first.get('isOpenAccess', False)}")

        return result['articles'][0] if result['articles'] else None

    except Exception as e:
        print(f"Error: {e}")
        return None


async def test_get_bmj_article(article_id: str = None):
    """Test retrieving a specific BMJ article."""
    print("\n=== Testing Get BMJ Article ===")

    # Use a known BMJ article PMID if none provided
    test_id = article_id or "33526403"  # A BMJ article
    print(f"Article ID: {test_id}")

    try:
        article = await _get_bmj_article_details(test_id, source="MED")
        print(f"\nTitle: {article['title']}")
        print(f"Journal: {article['journal']}")
        print(f"Authors: {', '.join(article['authors'][:3])}...")
        print(f"Publication Date: {article['pubDate']}")
        print(f"DOI: {article.get('doi', 'N/A')}")
        print(f"Abstract length: {len(article.get('abstractText', ''))} characters")
        print(f"Keywords: {', '.join(article.get('keywords', [])[:5])}")

        return article

    except Exception as e:
        print(f"Error: {e}")
        return None


async def test_download_bmj_article(doi: str = None):
    """Test getting download URLs for a BMJ article."""
    print("\n=== Testing BMJ Article Download ===")

    test_doi = doi or "10.1136/bmj.n71"
    print(f"DOI: {test_doi}")

    try:
        download_info = await _download_bmj_pdf(test_doi)
        print(f"\nDOI: {download_info['doi']}")
        print(f"Available URLs: {len(download_info['urls'])}")

        for url_info in download_info['urls']:
            print(f"\n  Type: {url_info['type']}")
            print(f"  URL: {url_info['url']}")
            print(f"  Description: {url_info['description']}")

        print(f"\nNote: {download_info['note']}")

        return download_info

    except Exception as e:
        print(f"Error: {e}")
        return None


async def test_get_multiple_bmj_articles():
    """Test retrieving multiple BMJ articles."""
    print("\n=== Testing Get Multiple BMJ Articles ===")

    # Known BMJ article PMIDs
    test_ids = ["33526403", "33028618", "32843355"]
    print(f"Retrieving {len(test_ids)} articles...")

    try:
        articles = []
        for article_id in test_ids:
            try:
                article = await _get_bmj_article_details(article_id, source="MED")
                articles.append(article)
                await asyncio.sleep(0.2)
            except Exception as e:
                articles.append({
                    "id": article_id,
                    "error": str(e)
                })

        result = {
            "count": len(articles),
            "articles": articles
        }

        print(f"\nSuccessfully retrieved: {result['count']} articles")

        for i, article in enumerate(result['articles'], 1):
            if 'error' in article:
                print(f"\nArticle {i}: ERROR - {article['error']}")
            else:
                print(f"\nArticle {i}:")
                print(f"  Title: {article['title'][:80]}...")
                print(f"  Journal: {article['journal']}")

        return result

    except Exception as e:
        print(f"Error: {e}")
        return None


async def run_all_tests():
    """Run all BMJ server tests."""
    print("=" * 60)
    print("BMJ MCP Server Test Suite")
    print("=" * 60)

    # Test 1: Search
    first_article = await test_search_bmj()

    # Test 2: Get specific article
    await test_get_bmj_article()

    # Test 3: Download article info
    if first_article and first_article.get('doi'):
        await test_download_bmj_article(first_article['doi'])
    else:
        await test_download_bmj_article()

    # Test 4: Get multiple articles
    await test_get_multiple_bmj_articles()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
