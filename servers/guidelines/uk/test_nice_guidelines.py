#!/usr/bin/env python
"""
Test script for NICE Guidelines MCP Server

This script tests the core functionality of the NICE guidelines scraper
without running the full MCP server.
"""

import asyncio
import sys
sys.path.insert(0, '/Users/dgordon/python/hackathons/heidi/servers')

from nice_guidelines_server import (
    search_nice_guidelines_impl,
    get_guideline_details_impl,
    list_guideline_categories_impl
)


async def test_search():
    """Test searching for guidelines."""
    print("\n=== Testing Search ===")
    print("Searching for 'diabetes'...")

    result = await search_nice_guidelines_impl("diabetes", max_results=5)

    print(f"Success: {result['success']}")
    print(f"Query: {result['query']}")
    print(f"Count: {result['count']}")

    if result['results']:
        print(f"\nFirst result:")
        first = result['results'][0]
        print(f"  Reference: {first['reference']}")
        print(f"  Title: {first['title']}")
        print(f"  URL: {first['url']}")
    else:
        print(f"Error: {result.get('error', 'No results found')}")


async def test_guideline_details():
    """Test getting guideline details."""
    print("\n=== Testing Guideline Details ===")
    print("Getting details for 'NG235'...")

    result = await get_guideline_details_impl("NG235")

    print(f"Success: {result['success']}")
    print(f"Reference: {result['reference']}")
    print(f"Title: {result['title']}")
    print(f"URL: {result['url']}")
    print(f"Published: {result['published_date']}")
    print(f"Last Updated: {result['last_updated']}")
    print(f"Type: {result['guideline_type']}")

    if result['overview']:
        print(f"\nOverview (first 200 chars):")
        print(f"  {result['overview'][:200]}...")

    if result['sections']:
        print(f"\nSections ({len(result['sections'])}):")
        for section in result['sections'][:5]:
            print(f"  - {section}")

    if result['error']:
        print(f"\nError: {result['error']}")


async def test_categories():
    """Test listing categories."""
    print("\n=== Testing Categories ===")
    print("Listing guideline categories...")

    result = await list_guideline_categories_impl()

    print(f"Success: {result['success']}")
    print(f"\nCategories ({len(result['categories'])}):")

    for category in result['categories']:
        print(f"\n  {category['code']}: {category['name']}")
        print(f"    {category['description']}")
        print(f"    URL: {category['url']}")

    if result['error']:
        print(f"\nError: {result['error']}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("NICE Guidelines MCP Server - Test Suite")
    print("=" * 60)

    try:
        await test_search()
        await test_guideline_details()
        await test_categories()

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
