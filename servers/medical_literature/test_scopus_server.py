#!/usr/bin/env python
"""
Test script for Scopus MCP Server

Note: Requires SCOPUS_API_KEY environment variable to be set.
Register at https://dev.elsevier.com/ to get your API key.
"""

import asyncio
import os
from scopus_server import (
    _search_scopus_impl,
    _get_scopus_article,
    _get_journal_quartile,
)


def check_api_key():
    """Check if Scopus API key is configured."""
    api_key = os.getenv("SCOPUS_API_KEY")
    if not api_key:
        print("\n" + "!" * 60)
        print("WARNING: SCOPUS_API_KEY not set!")
        print("Get your API key from https://dev.elsevier.com/")
        print("Set it with: export SCOPUS_API_KEY='your-key-here'")
        print("!" * 60 + "\n")
        return False
    print(f"✓ Scopus API key configured (length: {len(api_key)})")
    return True


async def test_search_scopus():
    """Test searching Scopus articles."""
    print("\n=== Testing Scopus Search (No Quartile Filter) ===")
    query = "machine learning healthcare"
    print(f"Query: {query}")

    try:
        result = await _search_scopus_impl(query, max_results=5, quartile_filter=None)
        print(f"\nTotal results in Scopus: {result['count']}")
        print(f"Returned articles: {len(result['articles'])}")

        if result['articles']:
            print("\nFirst article:")
            first = result['articles'][0]
            print(f"  Title: {first['title']}")
            print(f"  Authors: {first['authors']}")
            print(f"  Journal: {first['journal']}")
            print(f"  DOI: {first.get('doi', 'N/A')}")
            print(f"  Citations: {first.get('citation_count', 0)}")
            print(f"  Scopus ID: {first['scopus_id']}")

        return result['articles']

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return []


async def test_search_scopus_with_quartile():
    """Test searching Scopus with quartile filtering."""
    print("\n=== Testing Scopus Search with Q1-Q2 Filter ===")
    query = "diabetes treatment"
    print(f"Query: {query}")
    print(f"Quartile Filter: Q1-Q2 (top 50% journals)")

    try:
        result = await _search_scopus_impl(query, max_results=5, quartile_filter="Q1-Q2")
        print(f"\nTotal results in Scopus: {result['count']}")
        print(f"Returned Q1-Q2 articles: {len(result['articles'])}")

        for i, article in enumerate(result['articles'], 1):
            print(f"\nArticle {i}:")
            print(f"  Title: {article['title'][:70]}...")
            print(f"  Journal: {article['journal']}")
            quartile_info = article.get('quartile_info', {})
            print(f"  Quartile: {quartile_info.get('overall_quartile', 'unknown')}")
            print(f"  Citations: {article.get('citation_count', 0)}")

        return result['articles']

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return []


async def test_get_scopus_article(scopus_id: str = None):
    """Test retrieving a specific Scopus article."""
    print("\n=== Testing Get Scopus Article ===")

    # Use a provided ID or try to get one from a search
    if not scopus_id:
        print("No Scopus ID provided, searching for one...")
        result = await _search_scopus_impl("medical imaging", max_results=1, quartile_filter=None)
        if result['articles']:
            scopus_id = result['articles'][0]['scopus_id']
        else:
            print("Could not find a test article")
            return None

    print(f"Scopus ID: {scopus_id}")

    try:
        article = await _get_scopus_article(scopus_id)
        print(f"\nTitle: {article['title']}")
        print(f"Journal: {article['journal']}")
        print(f"DOI: {article.get('doi', 'N/A')}")
        print(f"Publication Date: {article['publication_date']}")
        print(f"Citations: {article['citation_count']}")
        print(f"Abstract length: {len(article.get('abstract', ''))} characters")
        print(f"Number of authors: {len(article.get('authors', []))}")
        print(f"Keywords: {', '.join(article.get('keywords', [])[:5])}")

        if 'quartile_info' in article:
            q_info = article['quartile_info']
            print(f"\nJournal Quartile Info:")
            print(f"  Overall Quartile: {q_info.get('overall_quartile', 'unknown')}")
            print(f"  SJR Quartile: {q_info.get('sjr_quartile', 'unknown')}")
            print(f"  CiteScore Quartile: {q_info.get('citescore_quartile', 'unknown')}")

        return article

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_get_journal_quartile():
    """Test getting journal quartile information."""
    print("\n=== Testing Get Journal Quartile ===")

    # Test with The Lancet ISSN
    issn = "0140-6736"
    print(f"Journal ISSN: {issn} (The Lancet)")

    try:
        quartile_info = await _get_journal_quartile(issn)
        print(f"\nJournal: {quartile_info.get('journal_title', 'N/A')}")
        print(f"Publisher: {quartile_info.get('publisher', 'N/A')}")
        print(f"Overall Quartile: {quartile_info.get('overall_quartile', 'unknown')}")
        print(f"SJR Quartile: {quartile_info.get('sjr_quartile', 'unknown')}")
        print(f"CiteScore Quartile: {quartile_info.get('citescore_quartile', 'unknown')}")

        return quartile_info

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_search_high_impact():
    """Test searching for high-impact articles."""
    print("\n=== Testing High-Impact Article Search ===")
    query = "cancer immunotherapy"
    print(f"Query: {query}")
    print(f"Filter: Q1 journals only")

    try:
        result = await _search_scopus_impl(query, max_results=5, quartile_filter="Q1")
        print(f"\nTotal results in Scopus: {result['count']}")
        print(f"Returned Q1 articles: {len(result['articles'])}")
        print(f"Filter description: Top 25% journals (Q1 only)")

        for i, article in enumerate(result['articles'][:3], 1):
            print(f"\nArticle {i}:")
            print(f"  Title: {article['title'][:70]}...")
            print(f"  Journal: {article['journal']}")
            quartile_info = article.get('quartile_info', {})
            print(f"  Quartile: {quartile_info.get('overall_quartile', 'unknown')}")
            print(f"  Citations: {article.get('citation_count', 0)}")

        return result

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_get_multiple_scopus_articles():
    """Test retrieving multiple Scopus articles."""
    print("\n=== Testing Get Multiple Scopus Articles ===")

    # First, search for some article IDs
    print("Searching for test articles...")
    result = await _search_scopus_impl("clinical trial", max_results=3, quartile_filter=None)

    if not result['articles']:
        print("Could not find test articles")
        return None

    scopus_ids = [article['scopus_id'] for article in result['articles']]
    print(f"Retrieving {len(scopus_ids)} articles...")

    try:
        articles = []
        for scopus_id in scopus_ids:
            try:
                article = await _get_scopus_article(scopus_id)
                articles.append(article)
                await asyncio.sleep(0.5)
            except Exception as e:
                articles.append({
                    "scopus_id": scopus_id,
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
                print(f"  Title: {article['title'][:60]}...")
                print(f"  Journal: {article['journal']}")
                print(f"  Citations: {article.get('citation_count', 0)}")

        return result

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def run_all_tests():
    """Run all Scopus server tests."""
    print("=" * 60)
    print("Scopus MCP Server Test Suite")
    print("=" * 60)

    # Check API key
    if not check_api_key():
        print("\nSkipping tests due to missing API key.")
        return

    # Test 1: Basic search
    articles = await test_search_scopus()

    # Test 2: Search with quartile filter
    await test_search_scopus_with_quartile()

    # Test 3: Get specific article
    if articles:
        await test_get_scopus_article(articles[0]['scopus_id'])
    else:
        await test_get_scopus_article()

    # Test 4: Get journal quartile
    await test_get_journal_quartile()

    # Test 5: High-impact search
    await test_search_high_impact()

    # Test 6: Get multiple articles
    await test_get_multiple_scopus_articles()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
