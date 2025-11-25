"""
Tests for the US MCP Client.

This module tests the USMCPClient class which connects to US-specific
clinical guideline servers (USPSTF, CDC, IDSA, ADA, AHA/ACC, AAP) plus patient info.
"""

import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path
from mcp import types
from mcp_clients_country import USMCPClient


class TestUSMCPClientInitialization:
    """Tests for US MCP client initialization."""

    def test_init_creates_all_six_us_servers(self):
        """Test that US client initializes with all 6 US servers."""
        client = USMCPClient(verbose=False)

        expected_servers = ["uspstf", "cdc", "idsa", "ada", "aha_acc", "aap", "patient_info"]
        assert len(client._servers) == 7

        for server in expected_servers:
            assert server in client._servers, f"Missing server: {server}"

    def test_init_server_commands_use_python(self):
        """Test that all servers use 'python' command."""
        client = USMCPClient(verbose=False)

        for server_name, config in client._servers.items():
            assert config["command"] == "python", f"Server {server_name} should use 'python'"

    def test_init_server_paths_are_absolute(self):
        """Test that all server paths are absolute."""
        client = USMCPClient(verbose=False)

        for server_name, config in client._servers.items():
            path = config["args"][0]
            assert Path(path).is_absolute(), f"Server {server_name} path should be absolute"

    def test_init_uspstf_server_path(self):
        """Test USPSTF server path is correct."""
        client = USMCPClient(verbose=False)

        uspstf_path = client._servers["uspstf"]["args"][0]
        assert "uspstf_server.py" in uspstf_path
        assert "guidelines/us" in uspstf_path

    def test_init_cdc_server_path(self):
        """Test CDC server path is correct."""
        client = USMCPClient(verbose=False)

        cdc_path = client._servers["cdc"]["args"][0]
        assert "cdc_guidelines_server.py" in cdc_path
        assert "guidelines/us" in cdc_path


class TestUSMCPClientConnection:
    """Tests for US client connection functionality."""

    @pytest.mark.asyncio
    async def test_connect_all_us_servers(self, mock_stdio_transport):
        """Test connecting to all 7 US servers (6 guideline + 1 patient)."""
        client = USMCPClient(verbose=False)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                await client.connect()

                assert len(client._sessions) == 7
                assert "uspstf" in client._sessions
                assert "cdc" in client._sessions
                assert "idsa" in client._sessions
                assert "ada" in client._sessions
                assert "aha_acc" in client._sessions
                assert "aap" in client._sessions
                assert "patient_info" in client._sessions

    @pytest.mark.asyncio
    async def test_connect_verbose_shows_all_servers(self, mock_stdio_transport, capsys):
        """Test verbose output shows all 7 server connections."""
        client = USMCPClient(verbose=True)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                await client.connect()

                captured = capsys.readouterr()
                assert "Connecting to 7 MCP servers" in captured.out


class TestUSMCPClientUSPSTF:
    """Tests for USPSTF (preventive services) guidelines."""

    @pytest.mark.asyncio
    async def test_uspstf_tools_available(self):
        """Test that USPSTF preventive recommendation tool is available."""
        client = USMCPClient(verbose=False)

        uspstf_tool = types.Tool(
            name="search_preventive_recommendations",
            description="Search USPSTF preventive care recommendations",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        )

        uspstf_session = AsyncMock()
        uspstf_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=[uspstf_tool])
        )

        client._sessions = {"uspstf": uspstf_session}
        await client._build_tool_mapping()

        assert "search_preventive_recommendations" in client._tool_to_server
        assert client._tool_to_server["search_preventive_recommendations"] == "uspstf"

    @pytest.mark.asyncio
    async def test_search_uspstf_preventive_recommendations(self):
        """Test searching USPSTF for preventive care recommendations."""
        client = USMCPClient(verbose=False)

        uspstf_session = AsyncMock()
        uspstf_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "recommendations": ["Colorectal Cancer Screening"]}'
            )]
        ))

        client._sessions = {"uspstf": uspstf_session}
        client._tool_to_server = {"search_preventive_recommendations": "uspstf"}

        result = await client.call_tool(
            "search_preventive_recommendations",
            {"query": "colorectal cancer screening"}
        )

        assert result is not None
        uspstf_session.call_tool.assert_called_once()


class TestUSMCPClientCDC:
    """Tests for CDC guidelines."""

    @pytest.mark.asyncio
    async def test_cdc_tools_available(self):
        """Test that CDC guideline search tool is available."""
        client = USMCPClient(verbose=False)

        cdc_tool = types.Tool(
            name="search_cdc_guidelines",
            description="Search CDC clinical guidelines",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        )

        cdc_session = AsyncMock()
        cdc_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=[cdc_tool])
        )

        client._sessions = {"cdc": cdc_session}
        await client._build_tool_mapping()

        assert "search_cdc_guidelines" in client._tool_to_server
        assert client._tool_to_server["search_cdc_guidelines"] == "cdc"

    @pytest.mark.asyncio
    async def test_search_cdc_guidelines(self):
        """Test searching CDC for public health guidelines."""
        client = USMCPClient(verbose=False)

        cdc_session = AsyncMock()
        cdc_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "guidelines": ["COVID-19 Vaccination Guidelines"]}'
            )]
        ))

        client._sessions = {"cdc": cdc_session}
        client._tool_to_server = {"search_cdc_guidelines": "cdc"}

        result = await client.call_tool(
            "search_cdc_guidelines",
            {"query": "vaccination"}
        )

        assert result is not None
        cdc_session.call_tool.assert_called_once()


class TestUSMCPClientIDSA:
    """Tests for IDSA (Infectious Diseases Society of America)."""

    @pytest.mark.asyncio
    async def test_idsa_tools_available(self):
        """Test that IDSA guideline search tool is available."""
        client = USMCPClient(verbose=False)

        idsa_tool = types.Tool(
            name="search_idsa_guidelines",
            description="Search IDSA infectious disease guidelines",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        )

        idsa_session = AsyncMock()
        idsa_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=[idsa_tool])
        )

        client._sessions = {"idsa": idsa_session}
        await client._build_tool_mapping()

        assert "search_idsa_guidelines" in client._tool_to_server
        assert client._tool_to_server["search_idsa_guidelines"] == "idsa"

    @pytest.mark.asyncio
    async def test_search_idsa_guidelines(self, test_clinical_scenarios):
        """Test searching IDSA for infectious disease guidelines."""
        client = USMCPClient(verbose=False)
        scenario = test_clinical_scenarios["infectious_disease"]

        idsa_session = AsyncMock()
        idsa_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "guidelines": ["Pneumonia Management"]}'
            )]
        ))

        client._sessions = {"idsa": idsa_session}
        client._tool_to_server = {"search_idsa_guidelines": "idsa"}

        result = await client.call_tool(
            "search_idsa_guidelines",
            {"query": "pneumonia"}
        )

        assert result is not None
        idsa_session.call_tool.assert_called_once()


class TestUSMCPClientADA:
    """Tests for ADA (American Diabetes Association)."""

    @pytest.mark.asyncio
    async def test_ada_tools_available(self):
        """Test that ADA standards search tool is available."""
        client = USMCPClient(verbose=False)

        ada_tool = types.Tool(
            name="search_diabetes_standards",
            description="Search ADA diabetes standards",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        )

        ada_session = AsyncMock()
        ada_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=[ada_tool])
        )

        client._sessions = {"ada": ada_session}
        await client._build_tool_mapping()

        assert "search_diabetes_standards" in client._tool_to_server
        assert client._tool_to_server["search_diabetes_standards"] == "ada"

    @pytest.mark.asyncio
    async def test_search_ada_diabetes_standards(self, test_clinical_scenarios):
        """Test searching ADA for diabetes management standards."""
        client = USMCPClient(verbose=False)
        scenario = test_clinical_scenarios["diabetes_management"]

        ada_session = AsyncMock()
        ada_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "standards": ["Standards of Medical Care 2024"]}'
            )]
        ))

        client._sessions = {"ada": ada_session}
        client._tool_to_server = {"search_diabetes_standards": "ada"}

        result = await client.call_tool(
            "search_diabetes_standards",
            {"query": "type 2 diabetes"}
        )

        assert result is not None
        ada_session.call_tool.assert_called_once()


class TestUSMCPClientAHAACC:
    """Tests for AHA/ACC (American Heart Association / American College of Cardiology)."""

    @pytest.mark.asyncio
    async def test_aha_acc_tools_available(self):
        """Test that AHA/ACC cardiovascular guideline tool is available."""
        client = USMCPClient(verbose=False)

        aha_acc_tool = types.Tool(
            name="search_cardiovascular_guidelines",
            description="Search AHA/ACC cardiovascular guidelines",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        )

        aha_acc_session = AsyncMock()
        aha_acc_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=[aha_acc_tool])
        )

        client._sessions = {"aha_acc": aha_acc_session}
        await client._build_tool_mapping()

        assert "search_cardiovascular_guidelines" in client._tool_to_server
        assert client._tool_to_server["search_cardiovascular_guidelines"] == "aha_acc"

    @pytest.mark.asyncio
    async def test_search_aha_acc_cardiovascular_guidelines(self, test_clinical_scenarios):
        """Test searching AHA/ACC for cardiovascular guidelines."""
        client = USMCPClient(verbose=False)
        scenario = test_clinical_scenarios["cardiac"]

        aha_acc_session = AsyncMock()
        aha_acc_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "guidelines": ["Heart Failure Management"]}'
            )]
        ))

        client._sessions = {"aha_acc": aha_acc_session}
        client._tool_to_server = {"search_cardiovascular_guidelines": "aha_acc"}

        result = await client.call_tool(
            "search_cardiovascular_guidelines",
            {"query": "heart failure"}
        )

        assert result is not None
        aha_acc_session.call_tool.assert_called_once()


class TestUSMCPClientAAP:
    """Tests for AAP (American Academy of Pediatrics)."""

    @pytest.mark.asyncio
    async def test_aap_tools_available(self):
        """Test that AAP pediatric guideline tool is available."""
        client = USMCPClient(verbose=False)

        aap_tool = types.Tool(
            name="search_pediatric_guidelines",
            description="Search AAP pediatric guidelines",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        )

        aap_session = AsyncMock()
        aap_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=[aap_tool])
        )

        client._sessions = {"aap": aap_session}
        await client._build_tool_mapping()

        assert "search_pediatric_guidelines" in client._tool_to_server
        assert client._tool_to_server["search_pediatric_guidelines"] == "aap"

    @pytest.mark.asyncio
    async def test_search_aap_pediatric_guidelines(self, test_clinical_scenarios):
        """Test searching AAP for pediatric guidelines."""
        client = USMCPClient(verbose=False)
        scenario = test_clinical_scenarios["pediatric_fever"]

        aap_session = AsyncMock()
        aap_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "guidelines": ["Fever and Antipyretic Use"]}'
            )]
        ))

        client._sessions = {"aap": aap_session}
        client._tool_to_server = {"search_pediatric_guidelines": "aap"}

        result = await client.call_tool(
            "search_pediatric_guidelines",
            {"query": "pediatric fever"}
        )

        assert result is not None
        aap_session.call_tool.assert_called_once()


class TestUSMCPClientToolRouting:
    """Tests for tool routing across all 6 US servers."""

    @pytest.mark.asyncio
    async def test_all_six_servers_provide_unique_tools(self):
        """Test that all 6 US guideline servers provide distinct tools."""
        client = USMCPClient(verbose=False)

        server_tools = {
            "uspstf": [types.Tool(name="search_preventive_recommendations", description="", inputSchema={})],
            "cdc": [types.Tool(name="search_cdc_guidelines", description="", inputSchema={})],
            "idsa": [types.Tool(name="search_idsa_guidelines", description="", inputSchema={})],
            "ada": [types.Tool(name="search_diabetes_standards", description="", inputSchema={})],
            "aha_acc": [types.Tool(name="search_cardiovascular_guidelines", description="", inputSchema={})],
            "aap": [types.Tool(name="search_pediatric_guidelines", description="", inputSchema={})],
        }

        for server_name, tools in server_tools.items():
            session = AsyncMock()
            session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=tools))
            client._sessions[server_name] = session

        await client._build_tool_mapping()

        # Verify all 6 specialized tools are mapped
        assert len(client._tool_to_server) >= 6
        assert "search_preventive_recommendations" in client._tool_to_server
        assert "search_cdc_guidelines" in client._tool_to_server
        assert "search_idsa_guidelines" in client._tool_to_server
        assert "search_diabetes_standards" in client._tool_to_server
        assert "search_cardiovascular_guidelines" in client._tool_to_server
        assert "search_pediatric_guidelines" in client._tool_to_server


class TestUSMCPClientErrorHandling:
    """Tests for US client error handling."""

    @pytest.mark.asyncio
    async def test_server_connection_failure(self):
        """Test handling of server connection failure."""
        client = USMCPClient(verbose=False)

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            mock_stdio.side_effect = Exception("Server unavailable")

            with pytest.raises(Exception):
                await client.connect()

    @pytest.mark.asyncio
    async def test_tool_routing_with_unknown_tool(self):
        """Test tool routing when tool doesn't exist."""
        client = USMCPClient(verbose=False)
        client._tool_to_server = {"search_cdc_guidelines": "cdc"}

        with pytest.raises(ValueError, match="Tool 'unknown_tool' not found"):
            await client.call_tool("unknown_tool", {})


class TestUSMCPClientIntegration:
    """Integration tests for US client."""

    @pytest.mark.asyncio
    async def test_multi_specialty_workflow(self, test_clinical_scenarios):
        """Test workflow using multiple US specialty servers."""
        client = USMCPClient(verbose=False)

        # Mock ADA for diabetes
        ada_session = AsyncMock()
        ada_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true, "source": "ada"}')]
        ))

        # Mock AHA/ACC for cardiac
        aha_acc_session = AsyncMock()
        aha_acc_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true, "source": "aha_acc"}')]
        ))

        client._sessions = {"ada": ada_session, "aha_acc": aha_acc_session}
        client._tool_to_server = {
            "search_diabetes_standards": "ada",
            "search_cardiovascular_guidelines": "aha_acc"
        }

        # Patient with diabetes and hypertension
        diabetes_result = await client.call_tool(
            "search_diabetes_standards",
            {"query": "type 2 diabetes"}
        )

        cardiac_result = await client.call_tool(
            "search_cardiovascular_guidelines",
            {"query": "hypertension"}
        )

        assert diabetes_result is not None
        assert cardiac_result is not None

    @pytest.mark.asyncio
    async def test_parallel_server_calls(self):
        """Test making parallel calls to different US servers."""
        client = USMCPClient(verbose=False)

        uspstf_session = AsyncMock()
        uspstf_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true}')]
        ))

        cdc_session = AsyncMock()
        cdc_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true}')]
        ))

        client._sessions = {"uspstf": uspstf_session, "cdc": cdc_session}
        client._tool_to_server = {
            "search_preventive_recommendations": "uspstf",
            "search_cdc_guidelines": "cdc"
        }

        import asyncio
        results = await asyncio.gather(
            client.call_tool("search_preventive_recommendations", {"query": "screening"}),
            client.call_tool("search_cdc_guidelines", {"query": "vaccination"})
        )

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_context_manager_usage(self, mock_stdio_transport):
        """Test US client as async context manager."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                async with USMCPClient(verbose=False) as client:
                    assert len(client._sessions) == 7
                    servers = client.get_connected_servers()
                    assert "uspstf" in servers
                    assert "ada" in servers

                # After exit, cleanup should have occurred
                assert len(client._sessions) == 0
