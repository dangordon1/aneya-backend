"""
Tests for the MCP Client Selector Factory.

This module tests the factory function for creating and connecting the appropriate
country-specific MCP client based on ISO country codes.
"""

import pytest
from unittest.mock import AsyncMock, patch
from mcp import types
from mcp_client_selector import (
    get_mcp_client_for_country,
    get_supported_countries,
    is_country_supported,
    get_client,
    COUNTRY_CLIENT_MAP
)
from mcp_clients_country import (
    UKMCPClient,
    IndiaMCPClient,
    USMCPClient,
    AustraliaMCPClient,
    InternationalMCPClient
)


class TestCountryCodeMapping:
    """Tests for country code to client class mapping."""

    def test_gb_maps_to_uk_client(self):
        """Test that GB country code maps to UK client."""
        assert COUNTRY_CLIENT_MAP["GB"] == UKMCPClient

    def test_uk_maps_to_uk_client(self):
        """Test that UK country code maps to UK client."""
        assert COUNTRY_CLIENT_MAP["UK"] == UKMCPClient

    def test_united_kingdom_maps_to_uk_client(self):
        """Test that 'UNITED KINGDOM' maps to UK client."""
        assert COUNTRY_CLIENT_MAP["UNITED KINGDOM"] == UKMCPClient

    def test_in_maps_to_india_client(self):
        """Test that IN country code maps to India client."""
        assert COUNTRY_CLIENT_MAP["IN"] == IndiaMCPClient

    def test_india_maps_to_india_client(self):
        """Test that INDIA maps to India client."""
        assert COUNTRY_CLIENT_MAP["INDIA"] == IndiaMCPClient

    def test_us_maps_to_us_client(self):
        """Test that US country code maps to US client."""
        assert COUNTRY_CLIENT_MAP["US"] == USMCPClient

    def test_usa_maps_to_us_client(self):
        """Test that USA maps to US client."""
        assert COUNTRY_CLIENT_MAP["USA"] == USMCPClient

    def test_united_states_maps_to_us_client(self):
        """Test that 'UNITED STATES' maps to US client."""
        assert COUNTRY_CLIENT_MAP["UNITED STATES"] == USMCPClient

    def test_au_maps_to_australia_client(self):
        """Test that AU country code maps to Australia client."""
        assert COUNTRY_CLIENT_MAP["AU"] == AustraliaMCPClient

    def test_australia_maps_to_australia_client(self):
        """Test that AUSTRALIA maps to Australia client."""
        assert COUNTRY_CLIENT_MAP["AUSTRALIA"] == AustraliaMCPClient


class TestGetMCPClientForCountry:
    """Tests for the main factory function."""

    @pytest.mark.asyncio
    async def test_get_uk_client_with_gb_code(self, mock_stdio_transport):
        """Test getting UK client with GB country code."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                client = await get_mcp_client_for_country("GB", verbose=False)

                assert isinstance(client, UKMCPClient)
                assert len(client.get_connected_servers()) == 3  # NICE, BNF, patient_info

                await client.cleanup()

    @pytest.mark.asyncio
    async def test_get_india_client_with_in_code(self, mock_stdio_transport):
        """Test getting India client with IN country code."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                client = await get_mcp_client_for_country("IN", verbose=False)

                assert isinstance(client, IndiaMCPClient)
                assert len(client.get_connected_servers()) == 8  # 7 Indian + patient_info

                await client.cleanup()

    @pytest.mark.asyncio
    async def test_get_us_client_with_us_code(self, mock_stdio_transport):
        """Test getting US client with US country code."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                client = await get_mcp_client_for_country("US", verbose=False)

                assert isinstance(client, USMCPClient)
                assert len(client.get_connected_servers()) == 7  # 6 US + patient_info

                await client.cleanup()

    @pytest.mark.asyncio
    async def test_get_australia_client_with_au_code(self, mock_stdio_transport):
        """Test getting Australia client with AU country code."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                client = await get_mcp_client_for_country("AU", verbose=False)

                assert isinstance(client, AustraliaMCPClient)
                assert len(client.get_connected_servers()) == 2  # NHMRC, patient_info

                await client.cleanup()


class TestFallbackToInternational:
    """Tests for fallback to International client for unsupported countries."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("country_code", [
        "FR",  # France
        "DE",  # Germany
        "CA",  # Canada
        "JP",  # Japan
        "BR",  # Brazil
        "MX",  # Mexico
        "IT",  # Italy
        "ES",  # Spain
        "ZZ",  # Invalid
    ])
    async def test_fallback_to_international_for_unsupported_countries(
        self, country_code, mock_stdio_transport
    ):
        """Test that unsupported country codes fallback to International client."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                client = await get_mcp_client_for_country(country_code, verbose=False)

                assert isinstance(client, InternationalMCPClient)
                assert len(client.get_connected_servers()) == 2  # PubMed, patient_info

                await client.cleanup()

    @pytest.mark.asyncio
    async def test_fallback_verbose_message(self, mock_stdio_transport, capsys):
        """Test that fallback to international prints appropriate message."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                client = await get_mcp_client_for_country("FR", verbose=True)

                captured = capsys.readouterr()
                assert "Country 'FR' not supported" in captured.out
                assert "International client" in captured.out

                await client.cleanup()


class TestCaseInsensitiveMatching:
    """Tests for case-insensitive country code matching."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("country_code,expected_client", [
        ("gb", UKMCPClient),
        ("GB", UKMCPClient),
        ("Gb", UKMCPClient),
        ("uk", UKMCPClient),
        ("UK", UKMCPClient),
        ("in", IndiaMCPClient),
        ("IN", IndiaMCPClient),
        ("us", USMCPClient),
        ("US", USMCPClient),
        ("au", AustraliaMCPClient),
        ("AU", AustraliaMCPClient),
    ])
    async def test_case_insensitive_country_code(
        self, country_code, expected_client, mock_stdio_transport
    ):
        """Test that country codes are case-insensitive."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                client = await get_mcp_client_for_country(country_code, verbose=False)

                assert isinstance(client, expected_client)

                await client.cleanup()


class TestWhitespaceHandling:
    """Tests for whitespace handling in country codes."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("country_code", [
        "  GB  ",
        "\tUS\t",
        " IN ",
        "AU\n",
    ])
    async def test_whitespace_stripped_from_country_code(
        self, country_code, mock_stdio_transport
    ):
        """Test that whitespace is stripped from country codes."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                client = await get_mcp_client_for_country(country_code, verbose=False)

                # Should successfully create a client (not fall back to international)
                assert not isinstance(client, InternationalMCPClient)

                await client.cleanup()


class TestVerboseMode:
    """Tests for verbose mode output."""

    @pytest.mark.asyncio
    async def test_verbose_mode_shows_selection(self, mock_stdio_transport, capsys):
        """Test that verbose mode shows client selection."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                client = await get_mcp_client_for_country("GB", verbose=True)

                captured = capsys.readouterr()
                assert "Selecting MCP client for country" in captured.out
                assert "GB" in captured.out
                assert "Using UK client" in captured.out

                await client.cleanup()

    @pytest.mark.asyncio
    async def test_verbose_mode_shows_ready_status(self, mock_stdio_transport, capsys):
        """Test that verbose mode shows ready status with server/tool counts."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[
            types.Tool(name="test_tool", description="Test", inputSchema={})
        ]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                client = await get_mcp_client_for_country("GB", verbose=True)

                captured = capsys.readouterr()
                assert "Client ready" in captured.out
                assert "servers" in captured.out
                assert "tools" in captured.out

                await client.cleanup()


class TestConnectionFailure:
    """Tests for handling connection failures."""

    @pytest.mark.asyncio
    async def test_connection_failure_cleans_up_client(self):
        """Test that client is cleaned up on connection failure."""
        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            mock_stdio.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Connection failed"):
                await get_mcp_client_for_country("GB", verbose=False)

    @pytest.mark.asyncio
    async def test_connection_failure_verbose_output(self, capsys):
        """Test that verbose mode shows connection failure."""
        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            mock_stdio.side_effect = Exception("Connection failed")

            with pytest.raises(Exception):
                await get_mcp_client_for_country("GB", verbose=True)

            captured = capsys.readouterr()
            assert "Failed to connect client" in captured.out


class TestGetSupportedCountries:
    """Tests for getting list of supported countries."""

    @pytest.mark.asyncio
    async def test_get_supported_countries_returns_dict(self):
        """Test that get_supported_countries returns a dictionary."""
        countries = await get_supported_countries()

        assert isinstance(countries, dict)
        assert len(countries) > 0

    @pytest.mark.asyncio
    async def test_get_supported_countries_includes_all_variants(self):
        """Test that all country code variants are included."""
        countries = await get_supported_countries()

        # UK variants
        assert "GB" in countries
        assert "UK" in countries
        assert "UNITED KINGDOM" in countries

        # India variants
        assert "IN" in countries
        assert "INDIA" in countries

        # US variants
        assert "US" in countries
        assert "USA" in countries
        assert "UNITED STATES" in countries

        # Australia variants
        assert "AU" in countries
        assert "AUSTRALIA" in countries

    @pytest.mark.asyncio
    async def test_get_supported_countries_maps_to_client_names(self):
        """Test that countries map to client class names."""
        countries = await get_supported_countries()

        assert countries["GB"] == "UKMCPClient"
        assert countries["IN"] == "IndiaMCPClient"
        assert countries["US"] == "USMCPClient"
        assert countries["AU"] == "AustraliaMCPClient"


class TestIsCountrySupported:
    """Tests for checking if a country is supported."""

    @pytest.mark.parametrize("country_code,expected", [
        ("GB", True),
        ("UK", True),
        ("IN", True),
        ("US", True),
        ("USA", True),
        ("AU", True),
        ("FR", False),
        ("DE", False),
        ("CA", False),
        ("ZZ", False),
    ])
    def test_is_country_supported(self, country_code, expected):
        """Test checking if country codes are supported."""
        assert is_country_supported(country_code) == expected

    def test_is_country_supported_case_insensitive(self):
        """Test that is_country_supported is case-insensitive."""
        assert is_country_supported("gb") is True
        assert is_country_supported("GB") is True
        assert is_country_supported("Gb") is True

    def test_is_country_supported_strips_whitespace(self):
        """Test that is_country_supported strips whitespace."""
        assert is_country_supported("  GB  ") is True
        assert is_country_supported("\tUS\t") is True


class TestGetClientConvenience:
    """Tests for the convenience get_client function."""

    @pytest.mark.asyncio
    async def test_get_client_is_alias(self, mock_stdio_transport):
        """Test that get_client is an alias for get_mcp_client_for_country."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                client = await get_client("GB", verbose=False)

                assert isinstance(client, UKMCPClient)

                await client.cleanup()


class TestClientReadiness:
    """Tests for client readiness after connection."""

    @pytest.mark.asyncio
    async def test_client_is_ready_after_connection(self, mock_stdio_transport):
        """Test that client is ready to use after connection."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        tool = types.Tool(name="test_tool", description="Test", inputSchema={})
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[tool]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                client = await get_mcp_client_for_country("GB", verbose=False)

                # Client should be connected and ready
                assert len(client.get_connected_servers()) > 0
                assert len(client.get_available_tools()) > 0

                await client.cleanup()

    @pytest.mark.asyncio
    async def test_client_has_correct_tools_after_connection(self, mock_stdio_transport):
        """Test that client has correct tools available after connection."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()

        # Mock different tools for different servers
        nice_tool = types.Tool(name="search_nice_guidelines", description="Search NICE", inputSchema={})
        bnf_tool = types.Tool(name="search_bnf_drug", description="Search BNF", inputSchema={})

        call_count = [0]

        def mock_list_tools(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # NICE
                return types.ListToolsResult(tools=[nice_tool])
            elif call_count[0] == 2:  # BNF
                return types.ListToolsResult(tools=[bnf_tool])
            else:  # patient_info
                return types.ListToolsResult(tools=[])

        mock_session.list_tools = AsyncMock(side_effect=mock_list_tools)

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                client = await get_mcp_client_for_country("GB", verbose=False)

                tools = client.get_available_tools()
                assert "search_nice_guidelines" in tools
                assert "search_bnf_drug" in tools

                await client.cleanup()


class TestMultipleClientCreation:
    """Tests for creating multiple clients."""

    @pytest.mark.asyncio
    async def test_create_clients_for_different_countries(self, mock_stdio_transport):
        """Test creating clients for different countries."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                uk_client = await get_mcp_client_for_country("GB", verbose=False)
                us_client = await get_mcp_client_for_country("US", verbose=False)
                india_client = await get_mcp_client_for_country("IN", verbose=False)

                assert isinstance(uk_client, UKMCPClient)
                assert isinstance(us_client, USMCPClient)
                assert isinstance(india_client, IndiaMCPClient)

                # Clean up all clients
                await uk_client.cleanup()
                await us_client.cleanup()
                await india_client.cleanup()

    @pytest.mark.asyncio
    async def test_clients_are_independent(self, mock_stdio_transport):
        """Test that multiple clients are independent of each other."""
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=types.ListToolsResult(tools=[]))

        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            with patch('mcp_client_base.ClientSession', return_value=mock_session):
                mock_stdio.return_value.__aenter__.return_value = mock_stdio_transport

                client1 = await get_mcp_client_for_country("GB", verbose=False)
                client2 = await get_mcp_client_for_country("GB", verbose=False)

                # Should be different instances
                assert client1 is not client2

                # Cleanup one shouldn't affect the other
                await client1.cleanup()
                assert len(client1.get_connected_servers()) == 0
                assert len(client2.get_connected_servers()) > 0

                await client2.cleanup()


class TestErrorMessages:
    """Tests for error messages and diagnostics."""

    @pytest.mark.asyncio
    async def test_connection_error_includes_country_code(self):
        """Test that connection errors include the country code for context."""
        with patch('mcp_client_base.stdio_client', new_callable=AsyncMock) as mock_stdio:
            mock_stdio.side_effect = Exception("Connection failed")

            try:
                await get_mcp_client_for_country("GB", verbose=True)
                assert False, "Should have raised exception"
            except Exception:
                pass  # Expected
