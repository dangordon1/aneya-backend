#!/usr/bin/env python
"""
Run BMJ MCP Server with SSE transport for remote access.

Usage:
    python run_bmj_sse.py [--port PORT] [--host HOST]
"""

import os
import sys
import argparse
from bmj_server import mcp

def main():
    parser = argparse.ArgumentParser(description="Run BMJ MCP Server with SSE transport")
    parser.add_argument("--port", type=int, default=8001, help="Port to run server on (default: 8001)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    args = parser.parse_args()

    print(f"Starting BMJ MCP Server...")
    print(f"  Transport: SSE")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  URL: http://{args.host}:{args.port}")
    print()

    # Run with SSE transport
    mcp.run(transport="sse", host=args.host, port=args.port)

if __name__ == "__main__":
    main()
