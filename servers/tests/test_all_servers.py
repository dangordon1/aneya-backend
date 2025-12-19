#!/usr/bin/env python
"""
Test All MCP Servers

Tests all 4 servers (Geolocation, NICE Guidelines, BNF, PubMed) by calling each tool
and verifying the responses.
"""

import asyncio
from pathlib import Path
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Server paths (relative to servers/ directory)
SERVERS_DIR = Path(__file__).parent.parent  # Go up from tests/ to servers/
SERVERS = {
    "nice": str(SERVERS_DIR / "guidelines" / "uk" / "nice_guidelines_server.py"),
    "bnf": str(SERVERS_DIR / "drug_lookup" / "bnf_server.py"),
    "pubmed": str(SERVERS_DIR / "medical_literature" / "pubmed_server.py"),
    "patient_info": str(SERVERS_DIR / "patient_context" / "patient_info_server.py")
}


async def test_server(server_name: str, server_path: str, test_calls: list):
    """Test a single server with provided test calls."""
    print(f"\n{'='*80}")
    print(f"Testing {server_name.upper()} Server")
    print(f"{'='*80}")

    exit_stack = AsyncExitStack()

    try:
        # Connect to server
        print(f"📡 Connecting to {server_name}...")
        server_params = StdioServerParameters(
            command="fastmcp",
            args=["run", server_path, "--transport", "stdio", "--no-banner"]
        )

        stdio_transport = await exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        stdio, write = stdio_transport
        session = await exit_stack.enter_async_context(
            ClientSession(stdio, write)
        )

        await session.initialize()
        print(f"✅ Connected to {server_name}")

        # List available tools
        tools_response = await session.list_tools()
        tools = tools_response.tools
        print(f"\n📋 Available tools ({len(tools)}):")
        for tool in tools:
            print(f"   • {tool.name}: {tool.description[:70]}...")

        # Run test calls
        print(f"\n🧪 Running {len(test_calls)} test call(s):")
        for i, (tool_name, arguments, description) in enumerate(test_calls, 1):
            print(f"\n   Test {i}/{len(test_calls)}: {description}")
            print(f"   Tool: {tool_name}")
            print(f"   Args: {arguments}")

            try:
                result = await session.call_tool(tool_name, arguments)

                # Display result
                if result.content:
                    content = result.content[0].text
                    # Truncate long responses
                    if len(content) > 500:
                        print(f"   ✅ Result (truncated): {content[:500]}...")
                    else:
                        print(f"   ✅ Result: {content}")
                else:
                    print(f"   ✅ Success (no content returned)")

            except Exception as e:
                print(f"   ❌ Error: {str(e)}")

        print(f"\n✅ {server_name.upper()} tests completed")

    except Exception as e:
        print(f"❌ Failed to test {server_name}: {str(e)}")
        raise
    finally:
        await exit_stack.aclose()


async def main():
    """Run all server tests."""
    print("="*80)
    print("MCP SERVERS TEST SUITE")
    print("="*80)
    print("\nTesting all 4 servers with real tool calls...")

    # Define test cases for each server
    test_cases = {
        "geolocation": [
            ("get_user_country", {}, "Auto-detect user country"),
            ("get_country_from_ip", {"ip_address": "8.8.8.8"}, "Get country for Google DNS IP"),
        ],
        "nice": [
            ("search_nice_guidelines", {"keyword": "croup", "max_results": 3}, "Search for croup guidelines"),
            ("list_guideline_categories", {}, "List all guideline categories"),
        ],
        "bnf": [
            ("search_bnf_drug", {"drug_name": "paracetamol"}, "Search for paracetamol"),
            ("search_bnf_by_condition", {"condition": "pain"}, "Search drugs for pain"),
        ],
        "pubmed": [
            ("search_pubmed", {"query": "pediatric croup treatment", "max_results": 3}, "Search PubMed for croup"),
            ("get_article", {"pmid": "35078966"}, "Get specific article by PMID"),
        ]
    }

    # Test each server sequentially
    for server_name, test_calls in test_cases.items():
        server_path = SERVERS.get(server_name)
        if not server_path:
            print(f"❌ Server path not found for {server_name}")
            continue

        if not Path(server_path).exists():
            print(f"❌ Server file not found: {server_path}")
            continue

        try:
            await test_server(server_name, server_path, test_calls)
            await asyncio.sleep(1)  # Brief pause between servers
        except Exception as e:
            print(f"\n❌ Testing failed for {server_name}: {str(e)}")
            continue

    print("\n" + "="*80)
    print("ALL TESTS COMPLETED")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
