#!/usr/bin/env python
"""
MCP Server Utilities

Shared utilities for all MCP servers to ensure proper JSON-RPC compliance.
"""

import sys


def print_stderr(*args, **kwargs):
    """
    Print to stderr to avoid contaminating MCP stdout.

    CRITICAL: MCP servers use stdio for JSON-RPC communication.
    ALL logging and debug output MUST go to stderr, never stdout.
    Only JSON-RPC messages should be written to stdout.

    Usage:
        from mcp_utils import print_stderr
        print_stderr("Debug message")  # Goes to stderr
        print_stderr(f"Value: {x}")    # Formatted strings work too
    """
    print(*args, file=sys.stderr, **kwargs)
