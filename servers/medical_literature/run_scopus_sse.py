#!/usr/bin/env python
"""
Run Scopus MCP Server with SSE transport for remote access.

Usage:
    python run_scopus_sse.py [--port PORT] [--host HOST]

Requirements:
    SCOPUS_API_KEY environment variable must be set
"""

import os
import sys
import argparse
from scopus_server import mcp, SCOPUS_API_KEY

def main():
    # Check for API key
    if not SCOPUS_API_KEY:
        print("ERROR: SCOPUS_API_KEY environment variable not set!")
        print("Get your API key from https://dev.elsevier.com/")
        print("Set it with: export SCOPUS_API_KEY='your-key-here'")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Run Scopus MCP Server with SSE transport")
    parser.add_argument("--port", type=int, default=8002, help="Port to run server on (default: 8002)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    args = parser.parse_args()

    print(f"Starting Scopus MCP Server...")
    print(f"  Transport: SSE")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  URL: http://{args.host}:{args.port}")
    print(f"  API Key: {'*' * 20}{SCOPUS_API_KEY[-8:]}")
    print()

    # Run with SSE transport
    mcp.run(transport="sse", host=args.host, port=args.port)

if __name__ == "__main__":
    main()
