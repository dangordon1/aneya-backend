"""
Tests for the Australia MCP Client.

This module tests the AustraliaMCPClient class which connects to Australian-specific
clinical guideline servers (NHMRC) plus patient info management.
"""

import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path
from mcp import types
from mcp_clients_country import AustraliaMCPClient


class TestAustraliaMCPClientInitialization:
    """Tests for Australia MCP client initialization."""

    def test_init_creates_correct_servers(self):
        """Test that Australia client initializes with correct server configurations."""
        client = AustraliaMCPClient(verbose=False)

        assert "nhmrc" in client._servers
        assert "patient_info" in client._servers
        assert len(client._servers) == 2

    def test_init_server_commands_use_python(self):
        """Test that all servers use 'python' command as per global instruction."""
        client = AustraliaMCPClient(verbose=False)

        for server_name, config in client._servers.items():
            assert config["command"] == "python", f"Server {server_name} should use 'python' command"

    def test_init_server_paths_are_absolute(self):
        """Test that server paths are absolute."""
        client = AustraliaMCPClient(verbose=False)

        for server_name, config in client._servers.items():
            path = config["args"][0]
            assert Path(path).is_absolute(), f"Server {server_name} path should be absolute"

    def test_init_nhmrc_server_path(self):
        """Test NHMRC server path points to correct location."""
        client = AustraliaMCPClient(verbose=False)

        nhmrc_path = client._servers["nhmrc"]["args"][0]
        assert "nhmrc_guidelines_server.py" in nhmrc_path
        assert "guidelines/australia" in nhmrc_path

    def test_init_patient_info_server_path(self):
        """Test patient info server path points to correct location."""
        client = AustraliaMCPClient(verbose=False)

        patient_path = client._servers["patient_info"]["args"][0]
        assert "patient_info_server.py" in patient_path


class TestAustraliaMCPClientConnection:
    """Tests for Australia client connection functionality."""

    @pytest.mark.asyncio
    async def test_connect_all_australian_servers(self, mock_stdio_transport):
        """Test connecting to both Australian servers (NHMRC, patient_info)."""
        client = AustraliaMCPClient(verbose=False)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                await client.connect()

                assert len(client._sessions) == 2
                assert "nhmrc" in client._sessions
                assert "patient_info" in client._sessions

    @pytest.mark.asyncio
    async def test_connect_verbose_output(self, mock_stdio_transport, capsys):
        """Test verbose output during connection."""
        client = AustraliaMCPClient(verbose=True)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                await client.connect()

                captured = capsys.readouterr()
                assert "Connecting to 2 MCP servers" in captured.out
                assert "Connected to nhmrc" in captured.out


class TestAustraliaMCPClientNHMRC:
    """Tests for NHMRC guidelines functionality."""

    @pytest.mark.asyncio
    async def test_nhmrc_tools_available(self):
        """Test that NHMRC guideline search tool is available."""
        client = AustraliaMCPClient(verbose=False)

        nhmrc_tool = types.Tool(
            name="search_nhmrc_guidelines",
            description="Search NHMRC clinical guidelines",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        )

        nhmrc_session = AsyncMock()
        nhmrc_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=[nhmrc_tool])
        )

        client._sessions = {"nhmrc": nhmrc_session}
        await client._build_tool_mapping()

        assert "search_nhmrc_guidelines" in client._tool_to_server
        assert client._tool_to_server["search_nhmrc_guidelines"] == "nhmrc"

    @pytest.mark.asyncio
    async def test_search_nhmrc_guidelines(self):
        """Test searching NHMRC guidelines for clinical conditions."""
        client = AustraliaMCPClient(verbose=False)

        nhmrc_session = AsyncMock()
        nhmrc_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "guidelines": ["Clinical Practice Guidelines"]}'
            )]
        ))

        client._sessions = {"nhmrc": nhmrc_session}
        client._tool_to_server = {"search_nhmrc_guidelines": "nhmrc"}

        result = await client.call_tool(
            "search_nhmrc_guidelines",
            {"query": "diabetes"}
        )

        assert result is not None
        nhmrc_session.call_tool.assert_called_once_with(
            "search_nhmrc_guidelines",
            {"query": "diabetes"}
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,expected_in_query", [
        ("diabetes", "diabetes"),
        ("hypertension", "hypertension"),
        ("asthma", "asthma"),
        ("cancer screening", "cancer screening")
    ])
    async def test_search_nhmrc_various_conditions(self, query, expected_in_query):
        """Test NHMRC guideline search with various clinical conditions."""
        client = AustraliaMCPClient(verbose=False)

        nhmrc_session = AsyncMock()
        nhmrc_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true}')]
        ))

        client._sessions = {"nhmrc": nhmrc_session}
        client._tool_to_server = {"search_nhmrc_guidelines": "nhmrc"}

        await client.call_tool("search_nhmrc_guidelines", {"query": query})

        call_args = nhmrc_session.call_tool.call_args[0]
        assert expected_in_query in call_args[1]["query"]


class TestAustraliaMCPClientPatientInfo:
    """Tests for patient information management."""

    @pytest.mark.asyncio
    async def test_patient_info_tools_available(self, mock_server_tools):
        """Test that patient info tools are available."""
        client = AustraliaMCPClient(verbose=False)

        patient_session = AsyncMock()
        patient_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=mock_server_tools["patient_info"])
        )

        client._sessions = {"patient_info": patient_session}
        await client._build_tool_mapping()

        assert "get_patient_info" in client._tool_to_server
        assert client._tool_to_server["get_patient_info"] == "patient_info"

    @pytest.mark.asyncio
    async def test_get_patient_info(self, mock_patient_info_response):
        """Test retrieving patient information."""
        client = AustraliaMCPClient(verbose=False)

        patient_session = AsyncMock()
        patient_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=str(mock_patient_info_response)
            )]
        ))

        client._sessions = {"patient_info": patient_session}
        client._tool_to_server = {"get_patient_info": "patient_info"}

        result = await client.call_tool(
            "get_patient_info",
            {"patient_id": "AU123"}
        )

        assert result is not None
        patient_session.call_tool.assert_called_once()


class TestAustraliaMCPClientErrorHandling:
    """Tests for Australia client error handling."""

    @pytest.mark.asyncio
    async def test_nhmrc_connection_failure(self):
        """Test handling of NHMRC server connection failure."""
        client = AustraliaMCPClient(verbose=False)

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            mock_stdio.side_effect = Exception("NHMRC server unavailable")

            with pytest.raises(Exception):
                await client.connect()

    @pytest.mark.asyncio
    async def test_nhmrc_tool_call_failure(self):
        """Test handling of NHMRC tool call failure."""
        client = AustraliaMCPClient(verbose=False)

        nhmrc_session = AsyncMock()
        nhmrc_session.call_tool = AsyncMock(
            side_effect=Exception("NHMRC search failed")
        )

        client._sessions = {"nhmrc": nhmrc_session}
        client._tool_to_server = {"search_nhmrc_guidelines": "nhmrc"}

        with pytest.raises(Exception, match="NHMRC search failed"):
            await client.call_tool("search_nhmrc_guidelines", {"query": "test"})

    @pytest.mark.asyncio
    async def test_tool_not_available(self):
        """Test calling a tool that's not available in Australia client."""
        client = AustraliaMCPClient(verbose=False)
        client._tool_to_server = {}

        with pytest.raises(ValueError, match="Tool 'unknown_tool' not found"):
            await client.call_tool("unknown_tool", {})

    @pytest.mark.asyncio
    async def test_nhmrc_timeout_handling(self):
        """Test handling of NHMRC timeout (known issue per documentation)."""
        client = AustraliaMCPClient(verbose=False)

        nhmrc_session = AsyncMock()
        nhmrc_session.call_tool = AsyncMock(
            side_effect=asyncio.TimeoutError("NHMRC timeout")
        )

        client._sessions = {"nhmrc": nhmrc_session}
        client._tool_to_server = {"search_nhmrc_guidelines": "nhmrc"}

        with pytest.raises(asyncio.TimeoutError):
            await client.call_tool("search_nhmrc_guidelines", {"query": "test"})


class TestAustraliaMCPClientIntegration:
    """Integration tests for Australia client."""

    @pytest.mark.asyncio
    async def test_full_workflow_clinical_case(
        self,
        test_clinical_scenarios,
        mock_patient_info_response
    ):
        """Test complete workflow for clinical case using Australian guidelines."""
        scenario = test_clinical_scenarios["diabetes_management"]
        client = AustraliaMCPClient(verbose=False)

        # Mock NHMRC session
        nhmrc_session = AsyncMock()
        nhmrc_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "guidelines": ["Type 2 Diabetes Guidelines"]}'
            )]
        ))

        # Mock patient info session
        patient_session = AsyncMock()
        patient_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text=str(mock_patient_info_response))]
        ))

        client._sessions = {"nhmrc": nhmrc_session, "patient_info": patient_session}
        client._tool_to_server = {
            "search_nhmrc_guidelines": "nhmrc",
            "get_patient_info": "patient_info"
        }

        # Search guidelines
        nhmrc_result = await client.call_tool(
            "search_nhmrc_guidelines",
            {"query": "type 2 diabetes"}
        )
        assert nhmrc_result is not None

        # Get patient info
        patient_result = await client.call_tool(
            "get_patient_info",
            {"patient_id": "AU123"}
        )
        assert patient_result is not None

    @pytest.mark.asyncio
    async def test_parallel_tool_calls(self):
        """Test making parallel calls to different Australian servers."""
        client = AustraliaMCPClient(verbose=False)

        nhmrc_session = AsyncMock()
        nhmrc_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true, "source": "nhmrc"}')]
        ))

        patient_session = AsyncMock()
        patient_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true, "source": "patient"}')]
        ))

        client._sessions = {"nhmrc": nhmrc_session, "patient_info": patient_session}
        client._tool_to_server = {
            "search_nhmrc_guidelines": "nhmrc",
            "get_patient_info": "patient_info"
        }

        # Make parallel calls
        import asyncio
        results = await asyncio.gather(
            client.call_tool("search_nhmrc_guidelines", {"query": "diabetes"}),
            client.call_tool("get_patient_info", {"patient_id": "AU123"})
        )

        assert len(results) == 2
        assert all(r is not None for r in results)


class TestAustraliaMCPClientContextManager:
    """Tests for using Australia client as async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_usage(self, mock_stdio_transport):
        """Test Australia client as async context manager."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                async with AustraliaMCPClient(verbose=False) as client:
                    assert len(client._sessions) == 2
                    assert "nhmrc" in client.get_connected_servers()
                    assert "patient_info" in client.get_connected_servers()

                # After exit, sessions should be cleaned up
                assert len(client._sessions) == 0

    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self, mock_stdio_transport):
        """Test that context manager properly cleans up even on exception."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                client = None
                try:
                    async with AustraliaMCPClient(verbose=False) as client:
                        assert len(client._sessions) == 2
                        raise ValueError("Test exception")
                except ValueError:
                    pass

                # After exception, sessions should still be cleaned up
                assert len(client._sessions) == 0


class TestAustraliaMCPClientComparison:
    """Tests comparing Australia client with other country clients."""

    def test_server_count_smaller_than_india_us(self):
        """Test that Australia has fewer servers than India/US (expected)."""
        au_client = AustraliaMCPClient(verbose=False)

        # Australia should have 2 servers (NHMRC + patient_info)
        assert len(au_client._servers) == 2

    def test_nhmrc_is_primary_guideline_source(self):
        """Test that NHMRC is the primary guideline source for Australia."""
        client = AustraliaMCPClient(verbose=False)

        # NHMRC should be configured
        assert "nhmrc" in client._servers

        # Should be the only guideline server (patient_info is auxiliary)
        guideline_servers = [
            name for name in client._servers.keys()
            if name not in ["patient_info"]
        ]
        assert len(guideline_servers) == 1
        assert guideline_servers[0] == "nhmrc"
