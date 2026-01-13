#!/usr/bin/env python
"""
Simple test for Scopus MCP server via SSE.
"""

import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client


async def test_scopus():
    server_url = "http://localhost:8002/sse"

    print("Connecting to Scopus server at", server_url)

    async with sse_client(server_url) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()
            print("✓ Connected and initialized")

            # List tools
            tools = await session.list_tools()
            print(f"\n✓ Found {len(tools.tools)} tools:")
            for tool in tools.tools:
                print(f"  - {tool.name}")

            # Call search tool with simple query
            print("\n--- Testing search ---")
            result = await session.call_tool(
                "search_scopus",
                arguments={
                    "query": "diabetes",
                    "max_results": 2
                }
            )

            print(f"✓ Search returned {len(result.content)} content items")
            for i, content in enumerate(result.content):
                print(f"\nContent {i+1}:")
                if hasattr(content, 'text'):
                    text = content.text
                    # Just show first 300 chars
                    print(text[:300] + "..." if len(text) > 300 else text)

            print("\n✓ Scopus server test PASSED")
            return True


if __name__ == "__main__":
    try:
        asyncio.run(test_scopus())
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
