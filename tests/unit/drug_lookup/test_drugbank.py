#!/usr/bin/env python3
"""
DrugBank Server Tests

Unit tests for the DrugBank MCP server.

Usage:
    python -m pytest tests/unit/drug_lookup/test_drugbank.py -v

Or run directly:
    python tests/unit/drug_lookup/test_drugbank.py
"""

import asyncio
import json
import sys
from pathlib import Path
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Server path
DRUGBANK_SERVER = Path(__file__).parent.parent.parent.parent / "servers" / "drug_lookup" / "drugbank_server.py"


async def run_all_tests():
    """Run all DrugBank tests."""
    print("\n" + "="*70)
    print("🧪 DRUGBANK SERVER TEST SUITE")
    print("="*70)
    print(f"Server: {DRUGBANK_SERVER}")

    if not DRUGBANK_SERVER.exists():
        print(f"❌ Server not found: {DRUGBANK_SERVER}")
        return False

    server_params = StdioServerParameters(
        command="python",
        args=[str(DRUGBANK_SERVER)],
        env=None
    )

    results = {}

    async with AsyncExitStack() as stack:
        read, write = await stack.enter_async_context(stdio_client(server_params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        # Test 1: List tools
        print("\n" + "-"*70)
        print("TEST 1: Server Connection & Tools")
        print("-"*70)

        tools = await session.list_tools()
        print(f"✅ Connected to DrugBank server")
        print(f"📦 Available tools: {len(tools.tools)}")
        for tool in tools.tools:
            print(f"   • {tool.name}")

        results['connection'] = len(tools.tools) > 0

        # Test 2: Search for a drug
        print("\n" + "-"*70)
        print("TEST 2: Drug Search")
        print("-"*70)

        try:
            result = await session.call_tool(
                "search_drugbank",
                {"query": "amoxicillin"}
            )
            data = json.loads(result.content[0].text)
            print(f"   Success: {data.get('success')}")
            print(f"   Results: {len(data.get('results', []))}")

            if data.get('results'):
                drug = data['results'][0]
                print(f"   First result: {drug.get('name')} ({drug.get('drugbank_id')})")

            results['search'] = data.get('success', False)
        except Exception as e:
            print(f"   ❌ Search failed: {e}")
            results['search'] = False

        # Test 3: Get drug info (if search succeeded)
        print("\n" + "-"*70)
        print("TEST 3: Drug Info Retrieval")
        print("-"*70)

        try:
            result = await session.call_tool(
                "get_drugbank_info",
                {"drug_id": "DB01060"}  # Amoxicillin
            )
            data = json.loads(result.content[0].text)
            print(f"   Success: {data.get('success')}")
            print(f"   Drug: {data.get('name')}")

            # Check structure
            fields = ['description', 'indication', 'mechanism_of_action']
            for field in fields:
                value = data.get(field, '')
                has_value = len(str(value)) > 0 if value else False
                print(f"   {field}: {'✓' if has_value else '✗'}")

            results['info'] = data.get('success', False)
        except Exception as e:
            print(f"   ❌ Info retrieval failed: {e}")
            results['info'] = False

    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*70)

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
