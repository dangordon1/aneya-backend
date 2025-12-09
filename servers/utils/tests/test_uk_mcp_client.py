"""
Tests for the UK MCP Client.

This module tests the UKMCPClient class which connects to UK-specific
clinical guideline servers (NICE, BNF) plus patient info management.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from mcp import types
from mcp_clients_country import UKMCPClient


class TestUKMCPClientInitialization:
    """Tests for UK MCP client initialization."""

    def test_init_creates_correct_servers(self):
        """Test that UK client initializes with correct server configurations."""
        client = UKMCPClient(verbose=False)

        assert "nice" in client._servers
        assert "bnf" in client._servers
        assert "patient_info" in client._servers
        assert len(client._servers) == 3

    def test_init_server_commands_use_python(self):
        """Test that all servers use 'python' command as per global instruction."""
        client = UKMCPClient(verbose=False)

        for server_name, config in client._servers.items():
            assert config["command"] == "python", f"Server {server_name} should use 'python' command"

    def test_init_server_paths_are_absolute(self):
        """Test that server paths are absolute."""
        client = UKMCPClient(verbose=False)

        for server_name, config in client._servers.items():
            path = config["args"][0]
            assert Path(path).is_absolute(), f"Server {server_name} path should be absolute"

    def test_init_nice_server_path(self):
        """Test NICE server path points to correct location."""
        client = UKMCPClient(verbose=False)

        nice_path = client._servers["nice"]["args"][0]
        assert "nice_guidelines_server.py" in nice_path
        assert "guidelines/uk" in nice_path

    def test_init_bnf_server_path(self):
        """Test BNF server path points to correct location."""
        client = UKMCPClient(verbose=False)

        bnf_path = client._servers["bnf"]["args"][0]
        assert "bnf_server.py" in bnf_path
        assert "guidelines/uk" in bnf_path

    def test_init_patient_info_server_path(self):
        """Test patient info server path points to correct location."""
        client = UKMCPClient(verbose=False)

        patient_path = client._servers["patient_info"]["args"][0]
        assert "patient_info_server.py" in patient_path


class TestUKMCPClientConnection:
    """Tests for UK client connection functionality."""

    @pytest.mark.asyncio
    async def test_connect_all_uk_servers(self, mock_stdio_transport):
        """Test connecting to all UK servers (NICE, BNF, patient_info)."""
        client = UKMCPClient(verbose=False)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                await client.connect()

                assert len(client._sessions) == 3
                assert "nice" in client._sessions
                assert "bnf" in client._sessions
                assert "patient_info" in client._sessions

    @pytest.mark.asyncio
    async def test_connect_verbose_output(self, mock_stdio_transport, capsys):
        """Test verbose output during connection."""
        client = UKMCPClient(verbose=True)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                await client.connect()

                captured = capsys.readouterr()
                assert "Connecting to 3 MCP servers" in captured.out
                assert "Connected to nice" in captured.out
                assert "Connected to bnf" in captured.out


class TestUKMCPClientTools:
    """Tests for UK client tool availability and routing."""

    @pytest.mark.asyncio
    async def test_nice_tools_available(self, mock_server_tools):
        """Test that NICE guideline search tools are available."""
        client = UKMCPClient(verbose=False)

        nice_session = AsyncMock()
        nice_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=mock_server_tools["nice"])
        )

        client._sessions = {"nice": nice_session}
        await client._build_tool_mapping()

        assert "search_nice_guidelines" in client._tool_to_server
        assert "search_cks_topics" in client._tool_to_server
        assert client._tool_to_server["search_nice_guidelines"] == "nice"

    @pytest.mark.asyncio
    async def test_bnf_tools_available(self, mock_server_tools):
        """Test that BNF drug search tools are available."""
        client = UKMCPClient(verbose=False)

        bnf_session = AsyncMock()
        bnf_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=mock_server_tools["bnf"])
        )

        client._sessions = {"bnf": bnf_session}
        await client._build_tool_mapping()

        assert "search_bnf_drug" in client._tool_to_server
        assert client._tool_to_server["search_bnf_drug"] == "bnf"

    @pytest.mark.asyncio
    async def test_patient_info_tools_available(self, mock_server_tools):
        """Test that patient info tools are available."""
        client = UKMCPClient(verbose=False)

        patient_session = AsyncMock()
        patient_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=mock_server_tools["patient_info"])
        )

        client._sessions = {"patient_info": patient_session}
        await client._build_tool_mapping()

        assert "get_patient_info" in client._tool_to_server
        assert client._tool_to_server["get_patient_info"] == "patient_info"


class TestUKMCPClientNICEGuidelines:
    """Tests for NICE guidelines functionality."""

    @pytest.mark.asyncio
    async def test_search_nice_guidelines(self, mock_nice_guideline_response):
        """Test searching NICE guidelines for clinical conditions."""
        client = UKMCPClient(verbose=False)

        nice_session = AsyncMock()
        nice_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=str(mock_nice_guideline_response)
            )]
        ))

        client._sessions = {"nice": nice_session}
        client._tool_to_server = {"search_nice_guidelines": "nice"}

        result = await client.call_tool(
            "search_nice_guidelines",
            {"query": "type 2 diabetes"}
        )

        assert result is not None
        nice_session.call_tool.assert_called_once_with(
            "search_nice_guidelines",
            {"query": "type 2 diabetes"}
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,expected_in_query", [
        ("diabetes", "diabetes"),
        ("hypertension", "hypertension"),
        ("asthma", "asthma"),
        ("heart failure", "heart failure")
    ])
    async def test_search_nice_guidelines_various_conditions(
        self, query, expected_in_query
    ):
        """Test NICE guideline search with various clinical conditions."""
        client = UKMCPClient(verbose=False)

        nice_session = AsyncMock()
        nice_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true}')]
        ))

        client._sessions = {"nice": nice_session}
        client._tool_to_server = {"search_nice_guidelines": "nice"}

        await client.call_tool("search_nice_guidelines", {"query": query})

        call_args = nice_session.call_tool.call_args[0]
        assert expected_in_query in call_args[1]["query"]

    @pytest.mark.asyncio
    async def test_search_cks_topics(self):
        """Test searching Clinical Knowledge Summaries."""
        client = UKMCPClient(verbose=False)

        nice_session = AsyncMock()
        nice_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true}')]
        ))

        client._sessions = {"nice": nice_session}
        client._tool_to_server = {"search_cks_topics": "nice"}

        result = await client.call_tool(
            "search_cks_topics",
            {"query": "urinary tract infection"}
        )

        assert result is not None
        nice_session.call_tool.assert_called_once()


class TestUKMCPClientBNF:
    """Tests for BNF drug information functionality."""

    @pytest.mark.asyncio
    async def test_search_bnf_drug(self, mock_bnf_drug_response):
        """Test searching BNF for drug information."""
        client = UKMCPClient(verbose=False)

        bnf_session = AsyncMock()
        bnf_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=str(mock_bnf_drug_response)
            )]
        ))

        client._sessions = {"bnf": bnf_session}
        client._tool_to_server = {"search_bnf_drug": "bnf"}

        result = await client.call_tool(
            "search_bnf_drug",
            {"drug_name": "metformin"}
        )

        assert result is not None
        bnf_session.call_tool.assert_called_once_with(
            "search_bnf_drug",
            {"drug_name": "metformin"}
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("drug_name", [
        "metformin",
        "ramipril",
        "atorvastatin",
        "amoxicillin",
        "salbutamol"
    ])
    async def test_search_bnf_common_drugs(self, drug_name):
        """Test BNF search with common UK medications."""
        client = UKMCPClient(verbose=False)

        bnf_session = AsyncMock()
        bnf_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true}')]
        ))

        client._sessions = {"bnf": bnf_session}
        client._tool_to_server = {"search_bnf_drug": "bnf"}

        await client.call_tool("search_bnf_drug", {"drug_name": drug_name})

        call_args = bnf_session.call_tool.call_args[0]
        assert call_args[1]["drug_name"] == drug_name


class TestUKMCPClientPatientInfo:
    """Tests for patient information management."""

    @pytest.mark.asyncio
    async def test_get_patient_info(self, mock_patient_info_response):
        """Test retrieving patient information."""
        client = UKMCPClient(verbose=False)

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
            {"patient_id": "TEST123"}
        )

        assert result is not None
        patient_session.call_tool.assert_called_once()


class TestUKMCPClientErrorHandling:
    """Tests for UK client error handling."""

    @pytest.mark.asyncio
    async def test_nice_connection_failure(self):
        """Test handling of NICE server connection failure."""
        client = UKMCPClient(verbose=False)

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            mock_stdio.side_effect = Exception("NICE server unavailable")

            with pytest.raises(Exception):
                await client.connect()

    @pytest.mark.asyncio
    async def test_bnf_tool_call_failure(self):
        """Test handling of BNF tool call failure."""
        client = UKMCPClient(verbose=False)

        bnf_session = AsyncMock()
        bnf_session.call_tool = AsyncMock(
            side_effect=Exception("BNF search failed")
        )

        client._sessions = {"bnf": bnf_session}
        client._tool_to_server = {"search_bnf_drug": "bnf"}

        with pytest.raises(Exception, match="BNF search failed"):
            await client.call_tool("search_bnf_drug", {"drug_name": "test"})

    @pytest.mark.asyncio
    async def test_tool_not_available(self):
        """Test calling a tool that's not available in UK client."""
        client = UKMCPClient(verbose=False)
        client._tool_to_server = {}

        with pytest.raises(ValueError, match="Tool 'unknown_tool' not found"):
            await client.call_tool("unknown_tool", {})


class TestUKMCPClientIntegration:
    """Integration tests for UK client (may be marked as slow/integration)."""

    @pytest.mark.asyncio
    async def test_full_workflow_diabetes_case(
        self,
        test_clinical_scenarios,
        mock_nice_guideline_response,
        mock_bnf_drug_response
    ):
        """Test complete workflow for diabetes case using UK guidelines."""
        scenario = test_clinical_scenarios["diabetes_management"]
        client = UKMCPClient(verbose=False)

        # Mock all sessions
        nice_session = AsyncMock()
        nice_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text=str(mock_nice_guideline_response))]
        ))

        bnf_session = AsyncMock()
        bnf_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text=str(mock_bnf_drug_response))]
        ))

        client._sessions = {"nice": nice_session, "bnf": bnf_session}
        client._tool_to_server = {
            "search_nice_guidelines": "nice",
            "search_bnf_drug": "bnf"
        }

        # Search guidelines
        nice_result = await client.call_tool(
            "search_nice_guidelines",
            {"query": "type 2 diabetes"}
        )
        assert nice_result is not None

        # Search medication
        bnf_result = await client.call_tool(
            "search_bnf_drug",
            {"drug_name": "metformin"}
        )
        assert bnf_result is not None

    @pytest.mark.asyncio
    async def test_parallel_tool_calls(self):
        """Test making parallel calls to different UK servers."""
        client = UKMCPClient(verbose=False)

        nice_session = AsyncMock()
        nice_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true, "source": "nice"}')]
        ))

        bnf_session = AsyncMock()
        bnf_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true, "source": "bnf"}')]
        ))

        client._sessions = {"nice": nice_session, "bnf": bnf_session}
        client._tool_to_server = {
            "search_nice_guidelines": "nice",
            "search_bnf_drug": "bnf"
        }

        # Make parallel calls
        import asyncio
        results = await asyncio.gather(
            client.call_tool("search_nice_guidelines", {"query": "diabetes"}),
            client.call_tool("search_bnf_drug", {"drug_name": "metformin"})
        )

        assert len(results) == 2
        assert all(r is not None for r in results)


class TestUKMCPClientContextManager:
    """Tests for using UK client as async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_usage(self, mock_stdio_transport):
        """Test UK client as async context manager."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                async with UKMCPClient(verbose=False) as client:
                    assert len(client._sessions) == 3
                    assert "nice" in client.get_connected_servers()

                # After exit, sessions should be cleaned up
                assert len(client._sessions) == 0
