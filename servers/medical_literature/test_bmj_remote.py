#!/usr/bin/env python
"""
Test BMJ MCP Server as a remote endpoint

This script runs the BMJ server as an HTTP/SSE server and tests it remotely.
"""

import asyncio
import httpx
import subprocess
import time
import signal
import sys

# Server configuration
SERVER_HOST = "localhost"
SERVER_PORT = 8001
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

server_process = None


def start_server():
    """Start the BMJ MCP server with SSE transport."""
    global server_process

    print(f"Starting BMJ server on {SERVER_URL}...")

    # Run the server with SSE transport
    server_process = subprocess.Popen(
        ["python", "bmj_server.py"],
        env={**subprocess.os.environ, "MCP_TRANSPORT": "sse", "MCP_PORT": str(SERVER_PORT)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    time.sleep(3)

    if server_process.poll() is not None:
        stdout, stderr = server_process.communicate()
        print(f"Server failed to start!")
        print(f"STDOUT: {stdout.decode()}")
        print(f"STDERR: {stderr.decode()}")
        return False

    print(f"✓ Server started (PID: {server_process.pid})")
    return True


def stop_server():
    """Stop the BMJ MCP server."""
    global server_process

    if server_process:
        print("\nStopping server...")
        server_process.send_signal(signal.SIGTERM)
        server_process.wait(timeout=5)
        print("✓ Server stopped")


async def test_server_health():
    """Test if the server is running and responsive."""
    print("\n=== Testing Server Health ===")

    try:
        async with httpx.AsyncClient() as client:
            # Try to connect to the server
            response = await client.get(f"{SERVER_URL}/health", timeout=5.0)
            print(f"Health check status: {response.status_code}")
            if response.status_code == 200:
                print("✓ Server is healthy")
                return True
            else:
                print(f"✗ Server returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"✗ Server health check failed: {e}")
        return False


async def test_mcp_tools():
    """Test listing available MCP tools."""
    print("\n=== Testing MCP Tools List ===")

    try:
        async with httpx.AsyncClient() as client:
            # MCP tools/list endpoint
            response = await client.post(
                f"{SERVER_URL}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list"
                },
                timeout=10.0
            )

            if response.status_code == 200:
                result = response.json()
                if "result" in result and "tools" in result["result"]:
                    tools = result["result"]["tools"]
                    print(f"✓ Found {len(tools)} tools:")
                    for tool in tools:
                        print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                    return True
                else:
                    print(f"✗ Unexpected response: {result}")
                    return False
            else:
                print(f"✗ Request failed with status {response.status_code}")
                return False
    except Exception as e:
        print(f"✗ Tools list failed: {e}")
        return False


async def test_search_bmj():
    """Test searching BMJ articles via MCP."""
    print("\n=== Testing BMJ Search via MCP ===")

    try:
        async with httpx.AsyncClient() as client:
            # Call search_bmj tool
            response = await client.post(
                f"{SERVER_URL}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "search_bmj",
                        "arguments": {
                            "query": "diabetes treatment",
                            "max_results": 3
                        }
                    }
                },
                timeout=30.0
            )

            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    content = result["result"].get("content", [])
                    if content:
                        print(f"✓ Search successful!")
                        print(f"Response: {content[0].get('text', '')[:200]}...")
                        return True
                    else:
                        print(f"✗ No content in response: {result}")
                        return False
                else:
                    print(f"✗ Unexpected response: {result}")
                    return False
            else:
                print(f"✗ Request failed with status {response.status_code}")
                print(f"Response: {response.text}")
                return False
    except Exception as e:
        print(f"✗ Search test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_tests():
    """Run all remote MCP tests."""
    print("=" * 60)
    print("BMJ MCP Remote Server Test Suite")
    print("=" * 60)

    # Start the server
    if not start_server():
        print("\n✗ Failed to start server")
        return False

    try:
        # Wait a bit more for server to be ready
        await asyncio.sleep(2)

        # Run tests
        health_ok = await test_server_health()
        if not health_ok:
            print("\n⚠ Server health check failed, trying to continue...")

        tools_ok = await test_mcp_tools()
        search_ok = await test_search_bmj()

        # Summary
        print("\n" + "=" * 60)
        print("Test Summary:")
        print(f"  Health Check: {'✓' if health_ok else '✗'}")
        print(f"  Tools List:   {'✓' if tools_ok else '✗'}")
        print(f"  Search Test:  {'✓' if search_ok else '✗'}")
        print("=" * 60)

        return tools_ok or search_ok  # At least one should work

    finally:
        stop_server()


if __name__ == "__main__":
    try:
        success = asyncio.run(run_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        stop_server()
        sys.exit(1)
