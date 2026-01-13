#!/usr/bin/env python
"""
Test MCP servers remotely via SSE transport.

This script tests the BMJ and Scopus MCP servers running with SSE transport.
"""

import asyncio
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client


async def test_bmj_sse():
    """Test BMJ server via SSE."""
    print("\n" + "=" * 60)
    print("Testing BMJ MCP Server (SSE Transport)")
    print("=" * 60)

    server_url = "http://localhost:8001/sse"

    try:
        async with sse_client(server_url) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the session
                await session.initialize()

                # List available tools
                tools = await session.list_tools()
                print(f"\n✓ Connected to BMJ server")
                print(f"✓ Found {len(tools.tools)} tools:")
                for tool in tools.tools:
                    print(f"  - {tool.name}: {tool.description}")

                # Test search_bmj tool
                print("\n--- Testing search_bmj tool ---")
                result = await session.call_tool(
                    "search_bmj",
                    arguments={
                        "query": "hypertension treatment",
                        "max_results": 3
                    }
                )

                print(f"✓ Search completed")
                for content in result.content:
                    if hasattr(content, 'text'):
                        import json
                        data = json.loads(content.text)
                        print(f"\nFound {data.get('count', 0)} total articles")
                        print(f"Returned {len(data.get('articles', []))} articles:")
                        for i, article in enumerate(data.get('articles', [])[:3], 1):
                            print(f"\n  {i}. {article.get('title', 'No title')}")
                            print(f"     Journal: {article.get('journal', 'Unknown')}")
                            print(f"     DOI: {article.get('doi', 'N/A')}")

                return True

    except Exception as e:
        print(f"\n✗ Error testing BMJ server: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_scopus_sse():
    """Test Scopus server via SSE."""
    print("\n" + "=" * 60)
    print("Testing Scopus MCP Server (SSE Transport)")
    print("=" * 60)

    server_url = "http://localhost:8002/sse"

    try:
        async with sse_client(server_url) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the session
                await session.initialize()

                # List available tools
                tools = await session.list_tools()
                print(f"\n✓ Connected to Scopus server")
                print(f"✓ Found {len(tools.tools)} tools:")
                for tool in tools.tools:
                    print(f"  - {tool.name}: {tool.description}")

                # Test search_scopus tool
                print("\n--- Testing search_scopus tool ---")
                result = await session.call_tool(
                    "search_scopus",
                    arguments={
                        "query": "machine learning",
                        "max_results": 3,
                        "quartile_filter": None
                    }
                )

                print(f"✓ Search completed")
                for content in result.content:
                    if hasattr(content, 'text'):
                        import json
                        try:
                            # MCP might wrap the response, try direct parsing first
                            data = json.loads(content.text)
                        except json.JSONDecodeError:
                            # If that fails, try extracting JSON from the text
                            print(f"Response text: {content.text[:200]}")
                            # Just show we got a response
                            print("Received response from server")
                            continue

                        print(f"\nFound {data.get('count', 0)} total articles")
                        print(f"Returned {len(data.get('articles', []))} articles:")
                        for i, article in enumerate(data.get('articles', [])[:3], 1):
                            print(f"\n  {i}. {article.get('title', 'No title')}")
                            print(f"     Journal: {article.get('journal', 'Unknown')}")
                            print(f"     Citations: {article.get('citation_count', 0)}")

                # Test quartile filtering
                print("\n--- Testing Q1 quartile filtering ---")
                result = await session.call_tool(
                    "search_high_impact_articles",
                    arguments={
                        "query": "diabetes",
                        "max_results": 2,
                        "include_q2": False
                    }
                )

                print(f"✓ Q1 search completed")
                for content in result.content:
                    if hasattr(content, 'text'):
                        import json
                        data = json.loads(content.text)
                        print(f"\nReturned {len(data.get('articles', []))} Q1 articles")

                return True

    except Exception as e:
        print(f"\n✗ Error testing Scopus server: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all remote MCP tests."""
    print("=" * 60)
    print("MCP Remote Server Test Suite")
    print("=" * 60)
    print("\nMake sure servers are running:")
    print("  python run_bmj_sse.py --port 8001")
    print("  python run_scopus_sse.py --port 8002")
    print()

    # Test BMJ
    bmj_success = await test_bmj_sse()

    # Test Scopus
    scopus_success = await test_scopus_sse()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary:")
    print(f"  BMJ Server:    {'✓ PASS' if bmj_success else '✗ FAIL'}")
    print(f"  Scopus Server: {'✓ PASS' if scopus_success else '✗ FAIL'}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
