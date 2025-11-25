"""
Tests for the base MCPClient class.

This module tests the core functionality of the MCPClient base class including:
- Connection management to multiple servers
- Tool routing and execution
- Tool listing and discovery
- Error handling
- Cleanup and resource management
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from pathlib import Path
from mcp import types
from mcp_client_base import MCPClient


class TestMCPClientInitialization:
    """Tests for MCPClient initialization."""

    def test_init_with_servers(self):
        """Test client initialization with server configurations."""
        servers = {
            "test_server": {
                "command": "python",
                "args": ["/path/to/server.py"]
            }
        }

        client = MCPClient(servers=servers, verbose=False)

        assert client._servers == servers
        assert client._verbose is False
        assert client._sessions == {}
        assert client._tool_to_server == {}

    def test_init_verbose_mode(self):
        """Test client initialization with verbose mode enabled."""
        servers = {"test": {"command": "python", "args": ["test.py"]}}
        client = MCPClient(servers=servers, verbose=True)

        assert client._verbose is True

    def test_init_empty_servers(self):
        """Test client initialization with no servers."""
        client = MCPClient(servers={}, verbose=False)

        assert client._servers == {}
        assert len(client._sessions) == 0


class TestMCPClientConnection:
    """Tests for client connection functionality."""

    @pytest.mark.asyncio
    async def test_connect_single_server_success(self, mock_stdio_transport, mock_client_session):
        """Test successful connection to a single server."""
        servers = {
            "test_server": {
                "command": "python",
                "args": ["/path/to/test_server.py"]
            }
        }

        client = MCPClient(servers=servers, verbose=False)

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_client_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                await client._connect_single_server("test_server", servers["test_server"])

                assert "test_server" in client._sessions
                assert client._sessions["test_server"] == mock_client_session
                mock_client_session.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_single_server_failure(self):
        """Test handling of failed server connection."""
        servers = {
            "failing_server": {
                "command": "python",
                "args": ["/path/to/failing_server.py"]
            }
        }

        client = MCPClient(servers=servers, verbose=False)

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            mock_stdio.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Connection failed"):
                await client._connect_single_server("failing_server", servers["failing_server"])

    @pytest.mark.asyncio
    async def test_connect_multiple_servers_parallel(self, mock_stdio_transport, mock_client_session):
        """Test parallel connection to multiple servers."""
        servers = {
            "server1": {"command": "python", "args": ["server1.py"]},
            "server2": {"command": "python", "args": ["server2.py"]},
            "server3": {"command": "python", "args": ["server3.py"]}
        }

        client = MCPClient(servers=servers, verbose=False)

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_client_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                await client.connect()

                assert len(client._sessions) == 3
                assert "server1" in client._sessions
                assert "server2" in client._sessions
                assert "server3" in client._sessions

    @pytest.mark.asyncio
    async def test_connect_with_verbose_output(self, mock_stdio_transport, mock_client_session, capsys):
        """Test that verbose mode prints connection progress."""
        servers = {"test": {"command": "python", "args": ["test.py"]}}
        client = MCPClient(servers=servers, verbose=True)

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_client_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                await client.connect()

                captured = capsys.readouterr()
                assert "Connecting to" in captured.out
                assert "Connected to all servers" in captured.out


class TestMCPClientToolMapping:
    """Tests for tool discovery and mapping."""

    @pytest.mark.asyncio
    async def test_build_tool_mapping_success(self, mock_client_session):
        """Test building tool-to-server mapping."""
        tool1 = types.Tool(name="tool1", description="Test tool 1", inputSchema={})
        tool2 = types.Tool(name="tool2", description="Test tool 2", inputSchema={})

        mock_client_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=[tool1, tool2])
        )

        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"test_server": mock_client_session}

        await client._build_tool_mapping()

        assert client._tool_to_server["tool1"] == "test_server"
        assert client._tool_to_server["tool2"] == "test_server"

    @pytest.mark.asyncio
    async def test_build_tool_mapping_multiple_servers(self):
        """Test tool mapping with multiple servers."""
        session1 = AsyncMock()
        session1.list_tools = AsyncMock(return_value=types.ListToolsResult(
            tools=[types.Tool(name="tool1", description="Tool 1", inputSchema={})]
        ))

        session2 = AsyncMock()
        session2.list_tools = AsyncMock(return_value=types.ListToolsResult(
            tools=[types.Tool(name="tool2", description="Tool 2", inputSchema={})]
        ))

        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"server1": session1, "server2": session2}

        await client._build_tool_mapping()

        assert client._tool_to_server["tool1"] == "server1"
        assert client._tool_to_server["tool2"] == "server2"

    @pytest.mark.asyncio
    async def test_build_tool_mapping_with_error(self, mock_client_session):
        """Test tool mapping handles errors gracefully."""
        mock_client_session.list_tools = AsyncMock(side_effect=Exception("List tools failed"))

        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"failing_server": mock_client_session}

        # Should not raise, just skip the failing server
        await client._build_tool_mapping()

        assert len(client._tool_to_server) == 0


class TestMCPClientToolCalls:
    """Tests for tool calling functionality."""

    @pytest.mark.asyncio
    async def test_call_tool_with_explicit_server(self, mock_client_session):
        """Test calling a tool with explicit server name."""
        result = types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true}')]
        )
        mock_client_session.call_tool = AsyncMock(return_value=result)

        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"test_server": mock_client_session}

        response = await client.call_tool(
            tool_name="test_tool",
            tool_input={"query": "test"},
            server_name="test_server"
        )

        assert response == result
        mock_client_session.call_tool.assert_called_once_with(
            "test_tool",
            {"query": "test"}
        )

    @pytest.mark.asyncio
    async def test_call_tool_with_routing(self, mock_client_session):
        """Test automatic tool routing without explicit server."""
        result = types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true}')]
        )
        mock_client_session.call_tool = AsyncMock(return_value=result)

        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"auto_server": mock_client_session}
        client._tool_to_server = {"routed_tool": "auto_server"}

        response = await client.call_tool(
            tool_name="routed_tool",
            tool_input={"param": "value"}
        )

        assert response == result
        mock_client_session.call_tool.assert_called_once_with(
            "routed_tool",
            {"param": "value"}
        )

    @pytest.mark.asyncio
    async def test_call_tool_not_found(self):
        """Test calling a tool that doesn't exist."""
        client = MCPClient(servers={}, verbose=False)
        client._tool_to_server = {"existing_tool": "server1"}

        with pytest.raises(ValueError, match="Tool 'missing_tool' not found"):
            await client.call_tool("missing_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_server_not_connected(self):
        """Test calling a tool when server is not connected."""
        client = MCPClient(servers={}, verbose=False)

        with pytest.raises(ConnectionError, match="Server 'missing_server' not connected"):
            await client.call_tool(
                tool_name="test_tool",
                tool_input={},
                server_name="missing_server"
            )


class TestMCPClientToolListing:
    """Tests for tool listing functionality."""

    @pytest.mark.asyncio
    async def test_list_tools_all_servers(self):
        """Test listing tools from all servers."""
        session1 = AsyncMock()
        session1.list_tools = AsyncMock(return_value=types.ListToolsResult(
            tools=[types.Tool(name="tool1", description="Tool 1", inputSchema={})]
        ))

        session2 = AsyncMock()
        session2.list_tools = AsyncMock(return_value=types.ListToolsResult(
            tools=[types.Tool(name="tool2", description="Tool 2", inputSchema={})]
        ))

        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"server1": session1, "server2": session2}

        tools = await client.list_tools()

        assert len(tools) == 2
        assert tools[0].name == "tool1"
        assert tools[1].name == "tool2"

    @pytest.mark.asyncio
    async def test_list_tools_specific_server(self, mock_client_session):
        """Test listing tools from a specific server."""
        tools = [
            types.Tool(name="tool1", description="Tool 1", inputSchema={}),
            types.Tool(name="tool2", description="Tool 2", inputSchema={})
        ]
        mock_client_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=tools)
        )

        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"specific_server": mock_client_session}

        result = await client.list_tools(server_name="specific_server")

        assert len(result) == 2
        assert result == tools


class TestMCPClientSessionManagement:
    """Tests for session retrieval and management."""

    def test_get_session_success(self, mock_client_session):
        """Test successful session retrieval."""
        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"test_server": mock_client_session}

        session = client.get_session("test_server")

        assert session == mock_client_session

    def test_get_session_not_connected(self):
        """Test getting session for unconnected server."""
        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"server1": MagicMock()}

        with pytest.raises(ConnectionError, match="Server 'server2' not connected"):
            client.get_session("server2")

    def test_get_connected_servers(self):
        """Test retrieving list of connected servers."""
        client = MCPClient(servers={}, verbose=False)
        client._sessions = {
            "server1": MagicMock(),
            "server2": MagicMock(),
            "server3": MagicMock()
        }

        servers = client.get_connected_servers()

        assert len(servers) == 3
        assert "server1" in servers
        assert "server2" in servers
        assert "server3" in servers

    def test_get_available_tools(self):
        """Test retrieving list of available tools."""
        client = MCPClient(servers={}, verbose=False)
        client._tool_to_server = {
            "tool1": "server1",
            "tool2": "server1",
            "tool3": "server2"
        }

        tools = client.get_available_tools()

        assert len(tools) == 3
        assert "tool1" in tools
        assert "tool2" in tools
        assert "tool3" in tools


class TestMCPClientCleanup:
    """Tests for cleanup and resource management."""

    @pytest.mark.asyncio
    async def test_cleanup_clears_sessions(self):
        """Test that cleanup clears all sessions and mappings."""
        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"server1": MagicMock()}
        client._tool_to_server = {"tool1": "server1"}

        mock_exit_stack = AsyncMock()
        client._exit_stack = mock_exit_stack

        await client.cleanup()

        mock_exit_stack.aclose.assert_called_once()
        assert len(client._sessions) == 0
        assert len(client._tool_to_server) == 0

    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_stdio_transport, mock_client_session):
        """Test using client as async context manager."""
        servers = {"test": {"command": "python", "args": ["test.py"]}}

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_client_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                async with MCPClient(servers=servers, verbose=False) as client:
                    assert len(client._sessions) == 1
                    assert "test" in client._sessions

                # After exit, sessions should be cleaned up
                assert len(client._sessions) == 0


class TestMCPClientPrompts:
    """Tests for prompt-related functionality."""

    @pytest.mark.asyncio
    async def test_list_prompts_all_servers(self):
        """Test listing prompts from all servers."""
        session1 = AsyncMock()
        session1.list_prompts = AsyncMock(return_value=types.ListPromptsResult(
            prompts=[types.Prompt(name="prompt1", description="Prompt 1", arguments=[])]
        ))

        session2 = AsyncMock()
        session2.list_prompts = AsyncMock(return_value=types.ListPromptsResult(
            prompts=[types.Prompt(name="prompt2", description="Prompt 2", arguments=[])]
        ))

        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"server1": session1, "server2": session2}

        prompts = await client.list_prompts()

        assert len(prompts) == 2
        assert prompts[0].name == "prompt1"
        assert prompts[1].name == "prompt2"

    @pytest.mark.asyncio
    async def test_list_prompts_specific_server(self):
        """Test listing prompts from specific server."""
        prompt = types.Prompt(name="test_prompt", description="Test", arguments=[])
        session = AsyncMock()
        session.list_prompts = AsyncMock(
            return_value=types.ListPromptsResult(prompts=[prompt])
        )

        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"test_server": session}

        prompts = await client.list_prompts(server_name="test_server")

        assert len(prompts) == 1
        assert prompts[0].name == "test_prompt"

    @pytest.mark.asyncio
    async def test_get_prompt(self):
        """Test getting a prompt from a server."""
        messages = [{"role": "user", "content": "Test message"}]
        session = AsyncMock()
        session.get_prompt = AsyncMock(
            return_value=types.GetPromptResult(messages=messages)
        )

        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"test_server": session}

        result = await client.get_prompt(
            prompt_name="test_prompt",
            args={"arg1": "value1"},
            server_name="test_server"
        )

        assert result == messages
        session.get_prompt.assert_called_once_with("test_prompt", {"arg1": "value1"})


class TestMCPClientResources:
    """Tests for resource reading functionality."""

    @pytest.mark.asyncio
    async def test_read_resource_json(self):
        """Test reading a JSON resource."""
        json_data = '{"key": "value"}'
        resource = types.TextResourceContents(
            uri="test://resource",
            mimeType="application/json",
            text=json_data
        )
        session = AsyncMock()
        session.read_resource = AsyncMock(
            return_value=types.ReadResourceResult(contents=[resource])
        )

        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"test_server": session}

        result = await client.read_resource("test://resource", server_name="test_server")

        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_read_resource_text(self):
        """Test reading a text resource."""
        resource = types.TextResourceContents(
            uri="test://resource",
            mimeType="text/plain",
            text="plain text content"
        )
        session = AsyncMock()
        session.read_resource = AsyncMock(
            return_value=types.ReadResourceResult(contents=[resource])
        )

        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"test_server": session}

        result = await client.read_resource("test://resource", server_name="test_server")

        assert result == "plain text content"


class TestMCPClientErrorHandling:
    """Tests for error handling across various operations."""

    @pytest.mark.asyncio
    async def test_connection_timeout_handling(self):
        """Test handling of connection timeouts."""
        servers = {"slow_server": {"command": "python", "args": ["slow.py"]}}
        client = MCPClient(servers=servers, verbose=False)

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            mock_stdio.side_effect = asyncio.TimeoutError("Connection timeout")

            with pytest.raises(asyncio.TimeoutError):
                await client._connect_single_server("slow_server", servers["slow_server"])

    @pytest.mark.asyncio
    async def test_tool_call_exception_propagation(self, mock_client_session):
        """Test that tool call exceptions are propagated."""
        mock_client_session.call_tool = AsyncMock(
            side_effect=Exception("Tool execution failed")
        )

        client = MCPClient(servers={}, verbose=False)
        client._sessions = {"test_server": mock_client_session}
        client._tool_to_server = {"failing_tool": "test_server"}

        with pytest.raises(Exception, match="Tool execution failed"):
            await client.call_tool("failing_tool", {})
