#!/usr/bin/env python
"""
Base MCP Client

Generic MCP client that can connect to multiple servers and route tool calls.
Based on the architecture from cli_project_COMPLETE.

Each country-specific client inherits from this base class.
"""

import sys
import asyncio
from typing import Optional, Any, Dict, List
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from pathlib import Path
import json
from pydantic import AnyUrl


class MCPClient:
    """
    Base MCP client that connects to multiple MCP servers via stdio.

    Each server runs as a separate process and this client manages the connections,
    routing tool calls to the appropriate server.
    """

    def __init__(
        self,
        servers: Dict[str, Dict[str, Any]],
        verbose: bool = False
    ):
        """
        Initialize the MCP client with server configurations.

        Args:
            servers: Dict mapping server names to their configurations
                    Each config should have 'command', 'args', and optional 'env'
            verbose: Whether to print connection progress
        """
        self._servers = servers
        self._verbose = verbose
        self._sessions: Dict[str, ClientSession] = {}
        self._exit_stack: AsyncExitStack = AsyncExitStack()
        self._tool_to_server: Dict[str, str] = {}  # Maps tool names to server names

    async def connect(self):
        """
        Connect to all configured MCP servers in parallel.
        """
        if self._verbose:
            print(f"\n🔌 Connecting to {len(self._servers)} MCP servers...")

        # Connect to all servers in parallel
        connection_tasks = [
            self._connect_single_server(name, config)
            for name, config in self._servers.items()
        ]

        await asyncio.gather(*connection_tasks)

        # Build tool-to-server mapping
        await self._build_tool_mapping()

        if self._verbose:
            print(f"✓ Connected to all servers ({len(self._sessions)} sessions)")
            print(f"✓ Available tools: {len(self._tool_to_server)}")

    async def _connect_single_server(
        self,
        server_name: str,
        config: Dict[str, Any]
    ):
        """
        Connect to a single MCP server.

        Args:
            server_name: Name identifier for the server
            config: Server configuration with command, args, env
        """
        try:
            server_params = StdioServerParameters(
                command=config['command'],
                args=config['args'],
                env=config.get('env')
            )

            stdio_transport = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )

            _stdio, _write = stdio_transport
            session = await self._exit_stack.enter_async_context(
                ClientSession(_stdio, _write)
            )

            await session.initialize()
            self._sessions[server_name] = session

            if self._verbose:
                print(f"  ✓ Connected to {server_name}")

        except Exception as e:
            if self._verbose:
                print(f"  ✗ Failed to connect to {server_name}: {e}")
            raise

    async def _build_tool_mapping(self):
        """
        Build a mapping of tool names to their server names.

        This allows routing tool calls to the correct server.
        """
        for server_name, session in self._sessions.items():
            try:
                result = await session.list_tools()
                for tool in result.tools:
                    self._tool_to_server[tool.name] = server_name
            except Exception as e:
                if self._verbose:
                    print(f"  ⚠️  Could not list tools for {server_name}: {e}")

    def get_session(self, server_name: str) -> ClientSession:
        """
        Get a session for a specific server.

        Args:
            server_name: Name of the server

        Returns:
            ClientSession for the server

        Raises:
            ConnectionError: If server is not connected
        """
        if server_name not in self._sessions:
            raise ConnectionError(
                f"Server '{server_name}' not connected. "
                f"Available servers: {list(self._sessions.keys())}"
            )
        return self._sessions[server_name]

    async def list_tools(self, server_name: Optional[str] = None) -> List[types.Tool]:
        """
        List available tools from one or all servers.

        Args:
            server_name: Optional server name. If None, lists tools from all servers.

        Returns:
            List of available tools
        """
        if server_name:
            result = await self.get_session(server_name).list_tools()
            return result.tools

        # List tools from all servers
        all_tools = []
        for session in self._sessions.values():
            result = await session.list_tools()
            all_tools.extend(result.tools)
        return all_tools

    async def call_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        server_name: Optional[str] = None
    ) -> types.CallToolResult:
        """
        Call a tool on the appropriate server.

        Args:
            tool_name: Name of the tool to call
            tool_input: Input parameters for the tool
            server_name: Optional explicit server name. If None, routes automatically.

        Returns:
            Tool result

        Raises:
            ValueError: If tool is not found
        """
        # Determine which server to use
        if server_name is None:
            if tool_name not in self._tool_to_server:
                raise ValueError(
                    f"Tool '{tool_name}' not found. Available tools: "
                    f"{list(self._tool_to_server.keys())}"
                )
            server_name = self._tool_to_server[tool_name]

        # Call the tool
        session = self.get_session(server_name)
        return await session.call_tool(tool_name, tool_input)

    async def list_prompts(self, server_name: Optional[str] = None) -> List[types.Prompt]:
        """
        List available prompts from one or all servers.

        Args:
            server_name: Optional server name. If None, lists prompts from all servers.

        Returns:
            List of available prompts
        """
        if server_name:
            result = await self.get_session(server_name).list_prompts()
            return result.prompts

        # List prompts from all servers
        all_prompts = []
        for session in self._sessions.values():
            result = await session.list_prompts()
            all_prompts.extend(result.prompts)
        return all_prompts

    async def get_prompt(
        self,
        prompt_name: str,
        args: Dict[str, str],
        server_name: Optional[str] = None
    ):
        """
        Get a prompt from a server.

        Args:
            prompt_name: Name of the prompt
            args: Arguments for the prompt
            server_name: Optional server name (required if prompt exists on multiple servers)

        Returns:
            Prompt messages
        """
        if server_name:
            session = self.get_session(server_name)
        else:
            # Use first session (could be enhanced to search for prompt)
            session = next(iter(self._sessions.values()))

        result = await session.get_prompt(prompt_name, args)
        return result.messages

    async def read_resource(
        self,
        uri: str,
        server_name: Optional[str] = None
    ) -> Any:
        """
        Read a resource from a server.

        Args:
            uri: Resource URI
            server_name: Optional server name

        Returns:
            Resource content (parsed if JSON)
        """
        if server_name:
            session = self.get_session(server_name)
        else:
            # Use first session (could be enhanced)
            session = next(iter(self._sessions.values()))

        result = await session.read_resource(AnyUrl(uri))
        resource = result.contents[0]

        if isinstance(resource, types.TextResourceContents):
            if resource.mimeType == "application/json":
                return json.loads(resource.text)
            return resource.text

        return resource

    async def cleanup(self):
        """
        Clean up all server connections.
        """
        await self._exit_stack.aclose()
        self._sessions.clear()
        self._tool_to_server.clear()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

    def get_connected_servers(self) -> List[str]:
        """Get list of connected server names."""
        return list(self._sessions.keys())

    def get_available_tools(self) -> List[str]:
        """Get list of all available tool names."""
        return list(self._tool_to_server.keys())
