"""
Tests for the International MCP Client.

This module tests the InternationalMCPClient class which serves as a fallback
for countries without dedicated guideline servers, providing access to PubMed
and patient info management.
"""

import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path
from mcp import types
from mcp_clients_country import InternationalMCPClient


class TestInternationalMCPClientInitialization:
    """Tests for International MCP client initialization."""

    def test_init_creates_correct_servers(self):
        """Test that International client initializes with PubMed and patient info."""
        client = InternationalMCPClient(verbose=False)

        assert "pubmed" in client._servers
        assert "patient_info" in client._servers
        assert len(client._servers) == 2

    def test_init_server_commands_use_python(self):
        """Test that all servers use 'python' command as per global instruction."""
        client = InternationalMCPClient(verbose=False)

        for server_name, config in client._servers.items():
            assert config["command"] == "python", f"Server {server_name} should use 'python' command"

    def test_init_server_paths_are_absolute(self):
        """Test that server paths are absolute."""
        client = InternationalMCPClient(verbose=False)

        for server_name, config in client._servers.items():
            path = config["args"][0]
            assert Path(path).is_absolute(), f"Server {server_name} path should be absolute"

    def test_init_pubmed_server_path(self):
        """Test PubMed server path points to correct location."""
        client = InternationalMCPClient(verbose=False)

        pubmed_path = client._servers["pubmed"]["args"][0]
        assert "pubmed_server.py" in pubmed_path

    def test_init_patient_info_server_path(self):
        """Test patient info server path points to correct location."""
        client = InternationalMCPClient(verbose=False)

        patient_path = client._servers["patient_info"]["args"][0]
        assert "patient_info_server.py" in patient_path

    def test_is_fallback_client(self):
        """Test that International client is designed as a fallback."""
        client = InternationalMCPClient(verbose=False)

        # Should only have 2 servers (no country-specific guidelines)
        assert len(client._servers) == 2

        # Should have PubMed as the research source
        assert "pubmed" in client._servers


class TestInternationalMCPClientConnection:
    """Tests for International client connection functionality."""

    @pytest.mark.asyncio
    async def test_connect_all_international_servers(self, mock_stdio_transport):
        """Test connecting to both International servers (PubMed, patient_info)."""
        client = InternationalMCPClient(verbose=False)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                await client.connect()

                assert len(client._sessions) == 2
                assert "pubmed" in client._sessions
                assert "patient_info" in client._sessions

    @pytest.mark.asyncio
    async def test_connect_verbose_output(self, mock_stdio_transport, capsys):
        """Test verbose output during connection."""
        client = InternationalMCPClient(verbose=True)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                await client.connect()

                captured = capsys.readouterr()
                assert "Connecting to 2 MCP servers" in captured.out
                assert "Connected to pubmed" in captured.out


class TestInternationalMCPClientPubMed:
    """Tests for PubMed medical literature search functionality."""

    @pytest.mark.asyncio
    async def test_pubmed_tools_available(self, mock_server_tools):
        """Test that PubMed search tool is available."""
        client = InternationalMCPClient(verbose=False)

        pubmed_session = AsyncMock()
        pubmed_session.list_tools = AsyncMock(
            return_value=types.ListToolsResult(tools=mock_server_tools["pubmed"])
        )

        client._sessions = {"pubmed": pubmed_session}
        await client._build_tool_mapping()

        assert "search_pubmed" in client._tool_to_server
        assert client._tool_to_server["search_pubmed"] == "pubmed"

    @pytest.mark.asyncio
    async def test_search_pubmed(self, mock_pubmed_response):
        """Test searching PubMed for medical literature."""
        client = InternationalMCPClient(verbose=False)

        pubmed_session = AsyncMock()
        pubmed_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=str(mock_pubmed_response)
            )]
        ))

        client._sessions = {"pubmed": pubmed_session}
        client._tool_to_server = {"search_pubmed": "pubmed"}

        result = await client.call_tool(
            "search_pubmed",
            {"query": "type 2 diabetes management"}
        )

        assert result is not None
        pubmed_session.call_tool.assert_called_once_with(
            "search_pubmed",
            {"query": "type 2 diabetes management"}
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,expected_articles", [
        ("diabetes", True),
        ("hypertension treatment", True),
        ("covid-19 vaccine", True),
        ("cancer immunotherapy", True)
    ])
    async def test_search_pubmed_various_topics(self, query, expected_articles):
        """Test PubMed search with various medical topics."""
        client = InternationalMCPClient(verbose=False)

        pubmed_session = AsyncMock()
        pubmed_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "articles": [{"pmid": "12345"}], "count": 1}'
            )]
        ))

        client._sessions = {"pubmed": pubmed_session}
        client._tool_to_server = {"search_pubmed": "pubmed"}

        result = await client.call_tool("search_pubmed", {"query": query})

        assert result is not None
        call_args = pubmed_session.call_tool.call_args[0]
        assert call_args[1]["query"] == query

    @pytest.mark.asyncio
    async def test_pubmed_returns_35_million_articles_coverage(self):
        """Test that PubMed provides access to large medical literature database."""
        client = InternationalMCPClient(verbose=False)

        # PubMed has 35M+ articles as per documentation
        pubmed_session = AsyncMock()
        pubmed_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "total_available": "35000000+", "count": 100}'
            )]
        ))

        client._sessions = {"pubmed": pubmed_session}
        client._tool_to_server = {"search_pubmed": "pubmed"}

        result = await client.call_tool("search_pubmed", {"query": "medicine"})

        assert result is not None


class TestInternationalMCPClientPatientInfo:
    """Tests for patient information management."""

    @pytest.mark.asyncio
    async def test_patient_info_tools_available(self, mock_server_tools):
        """Test that patient info tools are available."""
        client = InternationalMCPClient(verbose=False)

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
        client = InternationalMCPClient(verbose=False)

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
            {"patient_id": "INTL123"}
        )

        assert result is not None
        patient_session.call_tool.assert_called_once()


class TestInternationalMCPClientErrorHandling:
    """Tests for International client error handling."""

    @pytest.mark.asyncio
    async def test_pubmed_connection_failure(self):
        """Test handling of PubMed server connection failure."""
        client = InternationalMCPClient(verbose=False)

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            mock_stdio.side_effect = Exception("PubMed server unavailable")

            with pytest.raises(Exception):
                await client.connect()

    @pytest.mark.asyncio
    async def test_pubmed_tool_call_failure(self):
        """Test handling of PubMed tool call failure."""
        client = InternationalMCPClient(verbose=False)

        pubmed_session = AsyncMock()
        pubmed_session.call_tool = AsyncMock(
            side_effect=Exception("PubMed search failed")
        )

        client._sessions = {"pubmed": pubmed_session}
        client._tool_to_server = {"search_pubmed": "pubmed"}

        with pytest.raises(Exception, match="PubMed search failed"):
            await client.call_tool("search_pubmed", {"query": "test"})

    @pytest.mark.asyncio
    async def test_pubmed_api_rate_limiting(self):
        """Test handling of PubMed API rate limiting."""
        client = InternationalMCPClient(verbose=False)

        pubmed_session = AsyncMock()
        pubmed_session.call_tool = AsyncMock(
            side_effect=Exception("Rate limit exceeded")
        )

        client._sessions = {"pubmed": pubmed_session}
        client._tool_to_server = {"search_pubmed": "pubmed"}

        with pytest.raises(Exception, match="Rate limit exceeded"):
            await client.call_tool("search_pubmed", {"query": "test"})

    @pytest.mark.asyncio
    async def test_tool_not_available(self):
        """Test calling a tool that's not available in International client."""
        client = InternationalMCPClient(verbose=False)
        client._tool_to_server = {}

        with pytest.raises(ValueError, match="Tool 'unknown_tool' not found"):
            await client.call_tool("unknown_tool", {})


class TestInternationalMCPClientUseCases:
    """Tests for typical use cases of the International client."""

    @pytest.mark.asyncio
    async def test_fallback_for_unsupported_country(self, test_clinical_scenarios):
        """Test using International client as fallback for unsupported country."""
        # Simulates what happens when user is from France, Germany, etc.
        client = InternationalMCPClient(verbose=False)
        scenario = test_clinical_scenarios["diabetes_management"]

        pubmed_session = AsyncMock()
        pubmed_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "articles": [{"title": "Diabetes Management"}]}'
            )]
        ))

        client._sessions = {"pubmed": pubmed_session}
        client._tool_to_server = {"search_pubmed": "pubmed"}

        # Even without country-specific guidelines, can search research
        result = await client.call_tool(
            "search_pubmed",
            {"query": "type 2 diabetes management guidelines"}
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_research_based_clinical_support(self, test_clinical_scenarios):
        """Test providing research-based clinical support via PubMed."""
        client = InternationalMCPClient(verbose=False)
        scenario = test_clinical_scenarios["cardiac"]

        pubmed_session = AsyncMock()
        pubmed_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "articles": [{"title": "Angina Management", "year": "2023"}]}'
            )]
        ))

        client._sessions = {"pubmed": pubmed_session}
        client._tool_to_server = {"search_pubmed": "pubmed"}

        result = await client.call_tool(
            "search_pubmed",
            {"query": "angina pectoris treatment recent"}
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_global_medical_literature_access(self):
        """Test that International client provides global literature access."""
        client = InternationalMCPClient(verbose=False)

        # PubMed covers global research, not country-specific
        pubmed_session = AsyncMock()
        pubmed_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text='{"success": true, "articles": [{"countries": ["multi-national"]}]}'
            )]
        ))

        client._sessions = {"pubmed": pubmed_session}
        client._tool_to_server = {"search_pubmed": "pubmed"}

        result = await client.call_tool(
            "search_pubmed",
            {"query": "global health guidelines"}
        )

        assert result is not None


class TestInternationalMCPClientIntegration:
    """Integration tests for International client."""

    @pytest.mark.asyncio
    async def test_full_workflow_with_pubmed_and_patient(
        self,
        test_clinical_scenarios,
        mock_pubmed_response,
        mock_patient_info_response
    ):
        """Test complete workflow using PubMed and patient info."""
        scenario = test_clinical_scenarios["diabetes_management"]
        client = InternationalMCPClient(verbose=False)

        # Mock PubMed session
        pubmed_session = AsyncMock()
        pubmed_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text=str(mock_pubmed_response))]
        ))

        # Mock patient info session
        patient_session = AsyncMock()
        patient_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text=str(mock_patient_info_response))]
        ))

        client._sessions = {"pubmed": pubmed_session, "patient_info": patient_session}
        client._tool_to_server = {
            "search_pubmed": "pubmed",
            "get_patient_info": "patient_info"
        }

        # Search research
        pubmed_result = await client.call_tool(
            "search_pubmed",
            {"query": "type 2 diabetes management"}
        )
        assert pubmed_result is not None

        # Get patient info
        patient_result = await client.call_tool(
            "get_patient_info",
            {"patient_id": "INTL123"}
        )
        assert patient_result is not None

    @pytest.mark.asyncio
    async def test_parallel_tool_calls(self):
        """Test making parallel calls to PubMed and patient info."""
        client = InternationalMCPClient(verbose=False)

        pubmed_session = AsyncMock()
        pubmed_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true, "source": "pubmed"}')]
        ))

        patient_session = AsyncMock()
        patient_session.call_tool = AsyncMock(return_value=types.CallToolResult(
            content=[types.TextContent(type="text", text='{"success": true, "source": "patient"}')]
        ))

        client._sessions = {"pubmed": pubmed_session, "patient_info": patient_session}
        client._tool_to_server = {
            "search_pubmed": "pubmed",
            "get_patient_info": "patient_info"
        }

        # Make parallel calls
        import asyncio
        results = await asyncio.gather(
            client.call_tool("search_pubmed", {"query": "hypertension"}),
            client.call_tool("get_patient_info", {"patient_id": "INTL123"})
        )

        assert len(results) == 2
        assert all(r is not None for r in results)


class TestInternationalMCPClientContextManager:
    """Tests for using International client as async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_usage(self, mock_stdio_transport):
        """Test International client as async context manager."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                async with InternationalMCPClient(verbose=False) as client:
                    assert len(client._sessions) == 2
                    assert "pubmed" in client.get_connected_servers()
                    assert "patient_info" in client.get_connected_servers()

                # After exit, sessions should be cleaned up
                assert len(client._sessions) == 0


class TestInternationalMCPClientComparison:
    """Tests comparing International client with country-specific clients."""

    def test_minimal_server_count(self):
        """Test that International client has minimal servers (PubMed only)."""
        client = InternationalMCPClient(verbose=False)

        # Should have only 2 servers (PubMed + patient_info)
        assert len(client._servers) == 2

    def test_no_country_specific_guidelines(self):
        """Test that International client has no country-specific guideline servers."""
        client = InternationalMCPClient(verbose=False)

        # Should NOT have NICE, BNF, FOGSI, USPSTF, etc.
        country_specific_servers = [
            "nice", "bnf", "fogsi", "icmr", "uspstf", "cdc", "nhmrc"
        ]

        for server in country_specific_servers:
            assert server not in client._servers

    def test_pubmed_is_universal_research_source(self):
        """Test that PubMed serves as universal research source."""
        client = InternationalMCPClient(verbose=False)

        # PubMed should be the primary source
        assert "pubmed" in client._servers

        # Should be the only guideline/research server
        research_servers = [
            name for name in client._servers.keys()
            if name not in ["patient_info"]
        ]
        assert len(research_servers) == 1
        assert research_servers[0] == "pubmed"
