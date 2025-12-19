#!/usr/bin/env python3
"""
India Guidelines Server Tests

Unit tests for FOGSI, NHM, and AIIMS MCP servers.

Usage:
    python -m pytest tests/unit/guidelines/test_india.py -v

Or run directly:
    python tests/unit/guidelines/test_india.py
"""

import asyncio
import json
import sys
from pathlib import Path
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Server paths
SERVERS_DIR = Path(__file__).parent.parent.parent.parent / "servers" / "guidelines" / "india"
FOGSI_SERVER = SERVERS_DIR / "fogsi_server.py"
NHM_SERVER = SERVERS_DIR / "nhm_guidelines_server.py"
AIIMS_SERVER = SERVERS_DIR / "aiims_server.py"


async def test_server(name: str, server_path: Path, test_tool: str, test_args: dict):
    """Test a single guidelines server."""
    print(f"\n{'─'*70}")
    print(f"Testing: {name}")
    print(f"Server: {server_path}")
    print(f"{'─'*70}")

    if not server_path.exists():
        print(f"❌ Server not found")
        return False

    server_params = StdioServerParameters(
        command="python",
        args=[str(server_path)],
        env=None
    )

    try:
        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(stdio_client(server_params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await asyncio.wait_for(session.initialize(), timeout=30)

            # List tools
            tools = await session.list_tools()
            print(f"✅ Connected - {len(tools.tools)} tools available")
            for tool in tools.tools:
                print(f"   • {tool.name}")

            # Test search
            print(f"\n   Testing {test_tool}...")
            result = await session.call_tool(test_tool, test_args)
            data = json.loads(result.content[0].text)

            success = data.get('success', False)
            results = data.get('results', [])
            print(f"   Success: {success}")
            print(f"   Results: {len(results)}")

            if results:
                for r in results[:3]:
                    title = r.get('title', r.get('name', 'Unknown'))[:60]
                    print(f"   • {title}...")

            print(f"\n✅ {name} test completed")
            return True

    except asyncio.TimeoutError:
        print(f"❌ Connection timeout")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def run_all_tests():
    """Run all India guidelines tests."""
    print("\n" + "="*70)
    print("🧪 INDIA GUIDELINES TEST SUITE")
    print("="*70)

    results = {}

    # Test FOGSI
    results['FOGSI'] = await test_server(
        "FOGSI Guidelines",
        FOGSI_SERVER,
        "search_fogsi_guidelines",
        {"keyword": "pregnancy", "max_results": 5}
    )

    # Test NHM
    results['NHM'] = await test_server(
        "NHM Guidelines",
        NHM_SERVER,
        "search_nhm_guidelines",
        {"keyword": "maternal health", "max_results": 5}
    )

    # Test AIIMS
    results['AIIMS'] = await test_server(
        "AIIMS Guidelines",
        AIIMS_SERVER,
        "search_aiims_guidelines",
        {"keyword": "emergency", "max_results": 5}
    )

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
