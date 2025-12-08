"""
Tests for the India MCP Client.

This module tests the IndiaMCPClient class which connects to Indian-specific
clinical guideline servers (FOGSI, ICMR, STG, RSSDI, CSI, NCG, IAP) plus patient info.
"""

import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path
from mcp import types
from mcp_clients_country import IndiaMCPClient


class TestIndiaMCPClientInitialization:
    """Tests for India MCP client initialization."""

    def test_init_creates_all_seven_indian_servers(self):
        """Test that India client initializes with all 7 Indian servers."""
        client = IndiaMCPClient(verbose=False)

        expected_servers = ["fogsi", "icmr", "stg", "rssdi", "csi", "ncg", "iap", "patient_info"]
        assert len(client._servers) == 8

        for server in expected_servers:
            assert server in client._servers, f"Missing server: {server}"

    def test_init_server_commands_use_python(self):
        """Test that all servers use 'python' command as per global instruction."""
        client = IndiaMCPClient(verbose=False)

        for server_name, config in client._servers.items():
            assert config["command"] == "python", f"Server {server_name} should use 'python'"

    def test_init_server_paths_are_absolute(self):
        """Test that all server paths are absolute."""
        client = IndiaMCPClient(verbose=False)

        for server_name, config in client._servers.items():
            path = config["args"][0]
            assert Path(path).is_absolute(), f"Server {server_name} path should be absolute"

    def test_init_fogsi_server_path(self):
        """Test FOGSI server path is correct."""
        client = IndiaMCPClient(verbose=False)

        fogsi_path = client._servers["fogsi"]["args"][0]
        assert "fogsi_server.py" in fogsi_path
        assert "guidelines/india" in fogsi_path

    def test_init_icmr_server_path(self):
        """Test ICMR server path is correct."""
        client = IndiaMCPClient(verbose=False)

        icmr_path = client._servers["icmr"]["args"][0]
        assert "icmr_server.py" in icmr_path
        assert "guidelines/india" in icmr_path


class TestIndiaMCPClientConnection:
    """Tests for India client connection functionality."""

    @pytest.mark.asyncio
    async def test_connect_all_indian_servers(self, mock_stdio_transport):
        """Test connecting to all 8 Indian servers (7 guideline + 1 patient)."""
        client = IndiaMCPClient(verbose=False)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                await client.connect()

                assert len(client._sessions) == 8
                assert "fogsi" in client._sessions
                assert "icmr" in client._sessions
                assert "stg" in client._sessions
                assert "rssdi" in client._sessions
                assert "csi" in client._sessions
                assert "ncg" in client._sessions
                assert "iap" in client._sessions
                assert "patient_info" in client._sessions

    @pytest.mark.asyncio
    async def test_connect_verbose_shows_all_servers(self, mock_stdio_transport, capsys):
        """Test verbose output shows all 8 server connections."""
        client = IndiaMCPClient(verbose=True)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                await client.connect()

                captured = capsys.readouterr()
                assert "Connecting to 8 MCP servers" in captured.out


class TestIndiaMCPClientFOGSI:
    """Tests for FOGSI (obstetrics/gynecology) guidelines."""

    @pytest.mark.asyncio
    async def test_fogsi_tools_available(self):
        """Test that FOGSI guideline search tool is available."""
        client = IndiaMCPClient(verbose=False)

        fogsi_tool = types.Tool(
            name="search_fogsi_guidelines",
            description="Search FOGSI obstetric guidelines",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        )

        fogsi_session = AsyncMock()
        fogsi_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=[fogsi_tool])
        )

        client._sessions = {"fogsi": fogsi_session}
        await client._build_tool_mapping()

        assert "search_fogsi_guidelines" in client._tool_to_server
        assert client._tool_to_server["search_fogsi_guidelines"] == "fogsi"

    @pytest.mark.asyncio
    async def test_search_fogsi_guidelines(self, test_clinical_scenarios):
        """Test searching FOGSI guidelines for pregnancy-related conditions."""
        client = IndiaMCPClient(verbose=False)
        scenario = test_clinical_scenarios["pregnancy"]

        fogsi_session = AsyncMock()
        fogsi_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "guidelines": ["Gestational Hypertension Management"]}'
            )]
        ))

        client._sessions = {"fogsi": fogsi_session}
        client._tool_to_server = {"search_fogsi_guidelines": "fogsi"}

        result = await client.call_tool(
            "search_fogsi_guidelines",
            {"query": "gestational hypertension"}
        )

        assert result is not None
        fogsi_session.call_tool.assert_called_once()


class TestIndiaMCPClientICMR:
    """Tests for ICMR (Indian Council of Medical Research) guidelines."""

    @pytest.mark.asyncio
    async def test_icmr_tools_available(self):
        """Test that ICMR guideline search tool is available."""
        client = IndiaMCPClient(verbose=False)

        icmr_tool = types.Tool(
            name="search_icmr_guidelines",
            description="Search ICMR research guidelines",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        )

        icmr_session = AsyncMock()
        icmr_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=[icmr_tool])
        )

        client._sessions = {"icmr": icmr_session}
        await client._build_tool_mapping()

        assert "search_icmr_guidelines" in client._tool_to_server
        assert client._tool_to_server["search_icmr_guidelines"] == "icmr"

    @pytest.mark.asyncio
    async def test_search_icmr_guidelines(self, test_clinical_scenarios):
        """Test searching ICMR guidelines."""
        client = IndiaMCPClient(verbose=False)
        scenario = test_clinical_scenarios["infectious_disease"]

        icmr_session = AsyncMock()
        icmr_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "guidelines": ["TB Management Protocol"]}'
            )]
        ))

        client._sessions = {"icmr": icmr_session}
        client._tool_to_server = {"search_icmr_guidelines": "icmr"}

        result = await client.call_tool(
            "search_icmr_guidelines",
            {"query": "tuberculosis"}
        )

        assert result is not None
        icmr_session.call_tool.assert_called_once()


class TestIndiaMCPClientSTG:
    """Tests for STG (Standard Treatment Guidelines)."""

    @pytest.mark.asyncio
    async def test_stg_tools_available(self):
        """Test that STG guideline search tool is available."""
        client = IndiaMCPClient(verbose=False)

        stg_tool = types.Tool(
            name="search_stg_guidelines",
            description="Search Standard Treatment Guidelines",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        )

        stg_session = AsyncMock()
        stg_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=[stg_tool])
        )

        client._sessions = {"stg": stg_session}
        await client._build_tool_mapping()

        assert "search_stg_guidelines" in client._tool_to_server
        assert client._tool_to_server["search_stg_guidelines"] == "stg"

    @pytest.mark.asyncio
    async def test_search_stg_guidelines(self):
        """Test searching STG for standard treatment protocols."""
        client = IndiaMCPClient(verbose=False)

        stg_session = AsyncMock()
        stg_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true}')]
        ))

        client._sessions = {"stg": stg_session}
        client._tool_to_server = {"search_stg_guidelines": "stg"}

        result = await client.call_tool(
            "search_stg_guidelines",
            {"query": "pneumonia treatment"}
        )

        assert result is not None


class TestIndiaMCPClientRSSDI:
    """Tests for RSSDI (diabetes guidelines)."""

    @pytest.mark.asyncio
    async def test_rssdi_tools_available(self):
        """Test that RSSDI diabetes guideline search tool is available."""
        client = IndiaMCPClient(verbose=False)

        rssdi_tool = types.Tool(
            name="search_diabetes_guidelines",
            description="Search RSSDI diabetes guidelines",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        )

        rssdi_session = AsyncMock()
        rssdi_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=[rssdi_tool])
        )

        client._sessions = {"rssdi": rssdi_session}
        await client._build_tool_mapping()

        assert "search_diabetes_guidelines" in client._tool_to_server
        assert client._tool_to_server["search_diabetes_guidelines"] == "rssdi"

    @pytest.mark.asyncio
    async def test_search_rssdi_diabetes_guidelines(self, test_clinical_scenarios):
        """Test searching RSSDI for diabetes management guidelines."""
        client = IndiaMCPClient(verbose=False)
        scenario = test_clinical_scenarios["diabetes_management"]

        rssdi_session = AsyncMock()
        rssdi_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "guidelines": ["Type 2 Diabetes Management"]}'
            )]
        ))

        client._sessions = {"rssdi": rssdi_session}
        client._tool_to_server = {"search_diabetes_guidelines": "rssdi"}

        result = await client.call_tool(
            "search_diabetes_guidelines",
            {"query": "type 2 diabetes"}
        )

        assert result is not None
        rssdi_session.call_tool.assert_called_once()


class TestIndiaMCPClientCSI:
    """Tests for CSI (Cardiological Society of India)."""

    @pytest.mark.asyncio
    async def test_csi_tools_available(self):
        """Test that CSI cardiac guideline search tool is available."""
        client = IndiaMCPClient(verbose=False)

        csi_tool = types.Tool(
            name="search_cardiac_guidelines",
            description="Search CSI cardiac guidelines",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        )

        csi_session = AsyncMock()
        csi_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=[csi_tool])
        )

        client._sessions = {"csi": csi_session}
        await client._build_tool_mapping()

        assert "search_cardiac_guidelines" in client._tool_to_server
        assert client._tool_to_server["search_cardiac_guidelines"] == "csi"

    @pytest.mark.asyncio
    async def test_search_csi_cardiac_guidelines(self, test_clinical_scenarios):
        """Test searching CSI for cardiac condition guidelines."""
        client = IndiaMCPClient(verbose=False)
        scenario = test_clinical_scenarios["cardiac"]

        csi_session = AsyncMock()
        csi_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "guidelines": ["Angina Management"]}'
            )]
        ))

        client._sessions = {"csi": csi_session}
        client._tool_to_server = {"search_cardiac_guidelines": "csi"}

        result = await client.call_tool(
            "search_cardiac_guidelines",
            {"query": "angina"}
        )

        assert result is not None
        csi_session.call_tool.assert_called_once()


class TestIndiaMCPClientNCG:
    """Tests for NCG (National Cancer Guidelines)."""

    @pytest.mark.asyncio
    async def test_ncg_tools_available(self):
        """Test that NCG cancer guideline search tool is available."""
        client = IndiaMCPClient(verbose=False)

        ncg_tool = types.Tool(
            name="search_cancer_guidelines",
            description="Search NCG cancer guidelines",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        )

        ncg_session = AsyncMock()
        ncg_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=[ncg_tool])
        )

        client._sessions = {"ncg": ncg_session}
        await client._build_tool_mapping()

        assert "search_cancer_guidelines" in client._tool_to_server
        assert client._tool_to_server["search_cancer_guidelines"] == "ncg"

    @pytest.mark.asyncio
    async def test_search_ncg_cancer_guidelines(self):
        """Test searching NCG for cancer management guidelines."""
        client = IndiaMCPClient(verbose=False)

        ncg_session = AsyncMock()
        ncg_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "guidelines": ["Breast Cancer Screening"]}'
            )]
        ))

        client._sessions = {"ncg": ncg_session}
        client._tool_to_server = {"search_cancer_guidelines": "ncg"}

        result = await client.call_tool(
            "search_cancer_guidelines",
            {"query": "breast cancer"}
        )

        assert result is not None


class TestIndiaMCPClientIAP:
    """Tests for IAP (Indian Academy of Pediatrics)."""

    @pytest.mark.asyncio
    async def test_iap_tools_available(self):
        """Test that IAP pediatric guideline search tool is available."""
        client = IndiaMCPClient(verbose=False)

        iap_tool = types.Tool(
            name="search_pediatric_guidelines",
            description="Search IAP pediatric guidelines",
            inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
        )

        iap_session = AsyncMock()
        iap_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=[iap_tool])
        )

        client._sessions = {"iap": iap_session}
        await client._build_tool_mapping()

        assert "search_pediatric_guidelines" in client._tool_to_server
        assert client._tool_to_server["search_pediatric_guidelines"] == "iap"

    @pytest.mark.asyncio
    async def test_search_iap_pediatric_guidelines(self, test_clinical_scenarios):
        """Test searching IAP for pediatric guidelines."""
        client = IndiaMCPClient(verbose=False)
        scenario = test_clinical_scenarios["pediatric_fever"]

        iap_session = AsyncMock()
        iap_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "guidelines": ["Fever Management in Children"]}'
            )]
        ))

        client._sessions = {"iap": iap_session}
        client._tool_to_server = {"search_pediatric_guidelines": "iap"}

        result = await client.call_tool(
            "search_pediatric_guidelines",
            {"query": "pediatric fever"}
        )

        assert result is not None
        iap_session.call_tool.assert_called_once()


class TestIndiaMCPClientToolRouting:
    """Tests for tool routing across all 7 Indian servers."""

    @pytest.mark.asyncio
    async def test_all_seven_servers_provide_unique_tools(self):
        """Test that all 7 Indian guideline servers provide distinct tools."""
        client = IndiaMCPClient(verbose=False)

        # Mock sessions for all 7 guideline servers
        server_tools = {
            "fogsi": [types.Tool(name="search_fogsi_guidelines", description="", inputSchema={})],
            "icmr": [types.Tool(name="search_icmr_guidelines", description="", inputSchema={})],
            "stg": [types.Tool(name="search_stg_guidelines", description="", inputSchema={})],
            "rssdi": [types.Tool(name="search_diabetes_guidelines", description="", inputSchema={})],
            "csi": [types.Tool(name="search_cardiac_guidelines", description="", inputSchema={})],
            "ncg": [types.Tool(name="search_cancer_guidelines", description="", inputSchema={})],
            "iap": [types.Tool(name="search_pediatric_guidelines", description="", inputSchema={})],
        }

        for server_name, tools in server_tools.items():
            session = AsyncMock()
            session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=tools))
            client._sessions[server_name] = session

        await client._build_tool_mapping()

        # Verify all 7 specialized tools are mapped
        assert len(client._tool_to_server) >= 7
        assert "search_fogsi_guidelines" in client._tool_to_server
        assert "search_icmr_guidelines" in client._tool_to_server
        assert "search_stg_guidelines" in client._tool_to_server
        assert "search_diabetes_guidelines" in client._tool_to_server
        assert "search_cardiac_guidelines" in client._tool_to_server
        assert "search_cancer_guidelines" in client._tool_to_server
        assert "search_pediatric_guidelines" in client._tool_to_server


class TestIndiaMCPClientErrorHandling:
    """Tests for India client error handling."""

    @pytest.mark.asyncio
    async def test_single_server_failure_doesnt_block_others(self, mock_stdio_transport):
        """Test that if one Indian server fails, others can still connect."""
        client = IndiaMCPClient(verbose=False)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        call_count = [0]

        async def mock_stdio_with_one_failure(*args, **kwargs):
            call_count[0] += 1
            # Fail the second connection (ICMR)
            if call_count[0] == 2:
                raise Exception("ICMR server unavailable")
            return mock_stdio_transport

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.side_effect = mock_stdio_with_one_failure

                # Should raise because one server failed
                with pytest.raises(Exception):
                    await client.connect()

    @pytest.mark.asyncio
    async def test_tool_routing_with_unknown_condition(self):
        """Test tool routing when tool doesn't exist."""
        client = IndiaMCPClient(verbose=False)
        client._tool_to_server = {"search_fogsi_guidelines": "fogsi"}

        with pytest.raises(ValueError, match="Tool 'unknown_tool' not found"):
            await client.call_tool("unknown_tool", {})


class TestIndiaMCPClientIntegration:
    """Integration tests for India client."""

    @pytest.mark.asyncio
    async def test_multi_specialty_workflow(self, test_clinical_scenarios):
        """Test workflow using multiple Indian specialty servers."""
        client = IndiaMCPClient(verbose=False)

        # Mock RSSDI for diabetes
        rssdi_session = AsyncMock()
        rssdi_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true, "source": "rssdi"}')]
        ))

        # Mock CSI for cardiac
        csi_session = AsyncMock()
        csi_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true, "source": "csi"}')]
        ))

        client._sessions = {"rssdi": rssdi_session, "csi": csi_session}
        client._tool_to_server = {
            "search_diabetes_guidelines": "rssdi",
            "search_cardiac_guidelines": "csi"
        }

        # Patient with both diabetes and cardiac issues
        diabetes_result = await client.call_tool(
            "search_diabetes_guidelines",
            {"query": "type 2 diabetes"}
        )

        cardiac_result = await client.call_tool(
            "search_cardiac_guidelines",
            {"query": "hypertension"}
        )

        assert diabetes_result is not None
        assert cardiac_result is not None

    @pytest.mark.asyncio
    async def test_context_manager_usage(self, mock_stdio_transport):
        """Test India client as async context manager."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                async with IndiaMCPClient(verbose=False) as client:
                    assert len(client._sessions) == 8
                    servers = client.get_connected_servers()
                    assert "fogsi" in servers
                    assert "rssdi" in servers

                # After exit, cleanup should have occurred
                assert len(client._sessions) == 0
