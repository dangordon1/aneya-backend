"""
Pytest configuration and shared fixtures for MCP client tests.

This module provides:
- Event loop configuration for async tests
- Mock server fixtures to avoid hitting real endpoints
- Sample clinical scenarios for testing
- Shared setup/teardown logic
"""

import pytest
import asyncio
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch
from mcp import types


@pytest.fixture(scope="session")
def event_loop_policy():
    """
    Set the event loop policy for the test session.

    This ensures consistent async behavior across all tests.
    """
    return asyncio.get_event_loop_policy()


@pytest.fixture
def event_loop():
    """
    Create a new event loop for each test.

    This ensures test isolation and prevents event loop reuse issues.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_stdio_transport():
    """
    Mock stdio transport for MCP server communication.

    Returns a tuple of (read_stream, write_stream) mocks.
    """
    read_stream = AsyncMock()
    write_stream = AsyncMock()
    return (read_stream, write_stream)


@pytest.fixture
def mock_client_session():
    """
    Mock MCP ClientSession with common methods.

    Returns a mock session that can be used for testing tool calls,
    listings, and other MCP operations.
    """
    session = AsyncMock()

    # Mock initialize
    session.initialize = AsyncMock()

    # Mock list_tools
    session.list_tools = AsyncMock(return_value=types.ListToolsResult(
        tools=[
            types.Tool(
                name="test_tool",
                description="A test tool",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    }
                }
            )
        ]
    ))

    # Mock call_tool
    session.call_tool = AsyncMock(return_value=types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text='{"success": true, "data": "test result"}'
            )
        ]
    ))

    # Mock list_prompts
    session.list_prompts = AsyncMock(return_value=types.ListPromptsResult(
        prompts=[]
    ))

    return session


@pytest.fixture
def mock_server_config():
    """
    Mock server configuration for testing.

    Returns a basic server configuration dict.
    """
    return {
        "test_server": {
            "command": "python",
            "args": ["/path/to/test_server.py"]
        }
    }


@pytest.fixture
def test_clinical_scenarios():
    """
    Sample clinical scenarios for testing guideline searches.

    Returns a dictionary of clinical cases commonly used in testing.
    """
    return {
        "pediatric_fever": {
            "consultation": "3-year-old with fever 39°C for 2 days, cough, no rash",
            "patient_age": "3",
            "expected_conditions": ["fever", "respiratory infection", "pneumonia"]
        },
        "diabetes_management": {
            "consultation": "45-year-old with newly diagnosed type 2 diabetes, HbA1c 8.5%",
            "patient_age": "45",
            "expected_conditions": ["type 2 diabetes", "hyperglycemia"]
        },
        "hypertension": {
            "consultation": "60-year-old with BP 160/95, no previous treatment",
            "patient_age": "60",
            "expected_conditions": ["hypertension", "high blood pressure"]
        },
        "pregnancy": {
            "consultation": "28-year-old pregnant woman, 32 weeks gestation, elevated BP",
            "patient_age": "28",
            "expected_conditions": ["pregnancy", "preeclampsia", "gestational hypertension"]
        },
        "cardiac": {
            "consultation": "55-year-old with chest pain on exertion, smoker",
            "patient_age": "55",
            "expected_conditions": ["angina", "coronary artery disease", "chest pain"]
        },
        "infectious_disease": {
            "consultation": "35-year-old with persistent cough, night sweats, weight loss",
            "patient_age": "35",
            "expected_conditions": ["tuberculosis", "respiratory infection"]
        }
    }


@pytest.fixture
def mock_nice_guideline_response():
    """
    Mock NICE guideline search response.

    Returns a typical successful response from NICE guidelines search.
    """
    return {
        "success": True,
        "results": [
            {
                "title": "Type 2 diabetes in adults: management",
                "url": "https://www.nice.org.uk/guidance/ng28",
                "summary": "This guideline covers care and management of type 2 diabetes in adults.",
                "published": "2015-12-02",
                "guidance_type": "NICE guideline"
            }
        ],
        "count": 1
    }


@pytest.fixture
def mock_bnf_drug_response():
    """
    Mock BNF drug search response.

    Returns a typical successful response from BNF drug search.
    """
    return {
        "success": True,
        "drug_name": "metformin",
        "indications": "Type 2 diabetes mellitus",
        "dosage": "Initially 500 mg once daily, increased if necessary",
        "contraindications": "Ketoacidosis",
        "side_effects": "Gastrointestinal disturbances, lactic acidosis",
        "url": "https://bnf.nice.org.uk/drug/metformin.html"
    }


@pytest.fixture
def mock_pubmed_response():
    """
    Mock PubMed search response.

    Returns a typical successful response from PubMed search.
    """
    return {
        "success": True,
        "articles": [
            {
                "pmid": "12345678",
                "title": "Management of Type 2 Diabetes",
                "authors": "Smith J, Jones A",
                "journal": "Lancet",
                "year": "2023",
                "abstract": "This study examines the management of type 2 diabetes..."
            }
        ],
        "count": 1
    }


@pytest.fixture
def mock_patient_info_response():
    """
    Mock patient info response.

    Returns a typical successful response from patient info operations.
    """
    return {
        "success": True,
        "patient_id": "TEST123",
        "data": {
            "age": "45",
            "allergies": "penicillin",
            "conditions": ["type 2 diabetes"]
        }
    }


@pytest.fixture
async def cleanup_clients():
    """
    Fixture to track and cleanup MCP clients after tests.

    Usage:
        async def test_something(cleanup_clients):
            client = await get_client("GB")
            cleanup_clients.append(client)
            # Test code...
            # Client will be cleaned up automatically
    """
    clients = []
    yield clients

    # Cleanup all clients
    for client in clients:
        try:
            await client.cleanup()
        except Exception:
            pass  # Ignore cleanup errors in tests


@pytest.fixture
def mock_server_tools():
    """
    Mock tool definitions for different server types.

    Returns a dictionary mapping server names to their tool lists.
    """
    return {
        "nice": [
            types.Tool(
                name="search_nice_guidelines",
                description="Search NICE clinical guidelines",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            ),
            types.Tool(
                name="search_cks_topics",
                description="Search Clinical Knowledge Summaries",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            )
        ],
        "bnf": [
            types.Tool(
                name="search_bnf_drug",
                description="Search British National Formulary for drug information",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "drug_name": {"type": "string", "description": "Drug name"}
                    },
                    "required": ["drug_name"]
                }
            )
        ],
        "fogsi": [
            types.Tool(
                name="search_fogsi_guidelines",
                description="Search FOGSI obstetric guidelines",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            )
        ],
        "uspstf": [
            types.Tool(
                name="search_preventive_recommendations",
                description="Search USPSTF preventive care recommendations",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            )
        ],
        "nhmrc": [
            types.Tool(
                name="search_nhmrc_guidelines",
                description="Search NHMRC clinical guidelines",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            )
        ],
        "pubmed": [
            types.Tool(
                name="search_pubmed",
                description="Search PubMed medical literature",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            )
        ],
        "patient_info": [
            types.Tool(
                name="get_patient_info",
                description="Get patient information",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "patient_id": {"type": "string", "description": "Patient ID"}
                    },
                    "required": ["patient_id"]
                }
            )
        ]
    }


# Marker for integration tests that hit real servers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may hit real servers)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
