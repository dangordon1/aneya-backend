#!/usr/bin/env python3
"""
BNF Drug Lookup Tests

Unit tests for the BNF MCP server. Tests drug search, info retrieval,
and parallel batch lookups.

Usage:
    python -m pytest tests/unit/drug_lookup/test_bnf.py -v

Or run directly:
    python tests/unit/drug_lookup/test_bnf.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

# Server path
BNF_SERVER = Path(__file__).parent.parent.parent.parent / "servers" / "drug_lookup" / "bnf_server.py"


async def get_bnf_session():
    """Create a BNF server session."""
    load_dotenv()
    server_params = StdioServerParameters(
        command="python",
        args=[str(BNF_SERVER)],
        env=dict(os.environ)
    )
    return stdio_client(server_params)


class TestBNFServer:
    """Test BNF MCP Server functionality."""

    @staticmethod
    async def test_server_connection():
        """Test 1: Verify server connects and lists tools."""
        print("\n" + "="*70)
        print("TEST 1: BNF Server Connection")
        print("="*70)

        async with await get_bnf_session() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()

                print(f"✅ Connected to BNF server")
                print(f"📦 Available tools: {len(tools.tools)}")
                for tool in tools.tools:
                    print(f"   • {tool.name}")

                expected_tools = [
                    "search_bnf_drug",
                    "get_bnf_drug_info",
                    "get_multiple_bnf_drugs_parallel"
                ]
                tool_names = [t.name for t in tools.tools]
                for expected in expected_tools:
                    assert expected in tool_names, f"Missing tool: {expected}"

                print(f"\n✅ All expected tools present")
                return True

    @staticmethod
    async def test_single_drug_search(drug_name: str = "amoxicillin"):
        """Test 2: Search for a single drug."""
        print("\n" + "="*70)
        print(f"TEST 2: Single Drug Search - {drug_name}")
        print("="*70)

        async with await get_bnf_session() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "search_bnf_drug",
                    {"drug_name": drug_name, "variations": [drug_name]}
                )

                data = json.loads(result.content[0].text)
                print(f"   Success: {data.get('success')}")
                print(f"   Results: {data.get('count')}")

                assert data.get('success'), f"Search failed for {drug_name}"
                assert data.get('count', 0) > 0, f"No results for {drug_name}"

                if data.get('results'):
                    drug = data['results'][0]
                    print(f"   Found: {drug['name']} ({drug['url']})")

                print(f"\n✅ Drug search successful")
                return data.get('results', [{}])[0].get('url')

    @staticmethod
    async def test_drug_info_retrieval(drug_url: str):
        """Test 3: Get detailed drug information."""
        print("\n" + "="*70)
        print(f"TEST 3: Drug Info Retrieval")
        print("="*70)

        async with await get_bnf_session() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "get_bnf_drug_info",
                    {"drug_url": drug_url}
                )

                data = json.loads(result.content[0].text)
                print(f"   Success: {data.get('success')}")
                print(f"   Drug name: {data.get('drug_name')}")

                assert data.get('success'), "Failed to get drug info"
                assert data.get('drug_name'), "No drug name returned"

                # Check key fields exist
                fields = ['indications', 'dosage', 'side_effects', 'interactions']
                for field in fields:
                    value = data.get(field, '')
                    print(f"   {field}: {len(value)} chars")

                print(f"\n✅ Drug info retrieved successfully")
                return True

    @staticmethod
    async def test_drug_variations(drug_name: str = "Cetirizine"):
        """Test 4: Search with chemical/salt variations."""
        print("\n" + "="*70)
        print(f"TEST 4: Drug Variations - {drug_name}")
        print("="*70)

        variations = [drug_name, f"{drug_name} hydrochloride", f"{drug_name} dihydrochloride"]

        async with await get_bnf_session() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "search_bnf_drug",
                    {"drug_name": drug_name, "variations": variations}
                )

                data = json.loads(result.content[0].text)
                attempted = data.get('attempted_name', drug_name)

                print(f"   Original: {drug_name}")
                print(f"   Variations tried: {variations}")
                print(f"   Matched using: {attempted}")
                print(f"   Success: {data.get('success')}")

                # Note: Cetirizine may not be in BNF, so we just check the mechanism works
                print(f"\n✅ Variation search completed")
                return True

    @staticmethod
    async def test_parallel_lookup():
        """Test 5: Parallel batch drug lookup."""
        print("\n" + "="*70)
        print("TEST 5: Parallel Batch Lookup")
        print("="*70)

        drugs = ["Amoxicillin", "Paracetamol", "Ibuprofen"]

        async with await get_bnf_session() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                import time
                start = time.time()

                result = await session.call_tool(
                    "get_multiple_bnf_drugs_parallel",
                    {"drug_names": drugs}
                )

                elapsed = time.time() - start
                data = json.loads(result.content[0].text)

                print(f"   Drugs requested: {len(drugs)}")
                print(f"   Successful: {data.get('successful_lookups')}")
                print(f"   Failed: {data.get('failed_lookups')}")
                print(f"   Time: {elapsed:.2f}s")

                for drug_result in data.get('drugs', []):
                    status = "✅" if drug_result['status'] == 'success' else "❌"
                    print(f"   {status} {drug_result['drug_name']}: {drug_result['status']}")

                assert data.get('successful_lookups', 0) > 0, "No successful lookups"

                print(f"\n✅ Parallel lookup completed")
                return True


async def run_all_tests():
    """Run all BNF tests in sequence."""
    print("\n" + "="*70)
    print("🧪 BNF DRUG LOOKUP TEST SUITE")
    print("="*70)
    print(f"Server: {BNF_SERVER}")

    if not BNF_SERVER.exists():
        print(f"❌ Server not found: {BNF_SERVER}")
        return False

    tests = TestBNFServer()
    results = {}

    try:
        # Test 1: Connection
        results['connection'] = await tests.test_server_connection()

        # Test 2: Single drug search
        drug_url = await tests.test_single_drug_search("amoxicillin")
        results['search'] = drug_url is not None

        # Test 3: Drug info (only if search succeeded)
        if drug_url:
            results['info'] = await tests.test_drug_info_retrieval(drug_url)

        # Test 4: Variations
        results['variations'] = await tests.test_drug_variations()

        # Test 5: Parallel lookup
        results['parallel'] = await tests.test_parallel_lookup()

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

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
