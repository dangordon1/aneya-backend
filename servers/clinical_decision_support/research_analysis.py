"""
Research Analysis Engine for Clinical Decision Support.

Handles clinical analysis using research paper MCP servers (PubMed, BMJ, Scopus).
Focuses on recent, high-quality research (last 5 years, Q1/Q2 journals).
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from contextlib import AsyncExitStack
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Dict, List, Any, Optional, Tuple

from .config import MCP_SERVERS, RESEARCH_SERVERS


class ResearchAnalysisEngine:
    """
    Handles clinical analysis using research paper MCP servers.

    This class connects to:
    - pubmed: PubMed medical literature (35M+ articles)
    - bmj: BMJ publications via Europe PMC
    - scopus: Scopus with quartile filtering (Q1/Q2)

    Focuses on recent, high-quality research:
    - Date filter: Last 5 years
    - Quality filter: Q1/Q2 journals only
    """

    def __init__(self, anthropic_api_key: Optional[str] = None):
        """
        Initialize the research analysis engine.

        Args:
            anthropic_api_key: Anthropic API key for Claude. If None, reads from env.
        """
        self.sessions: Dict[str, ClientSession] = {}
        self.tool_registry: Dict[str, str] = {}
        self.exit_stack = AsyncExitStack()

        api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.anthropic = Anthropic(api_key=api_key) if api_key else None

    async def connect_research_servers(self, verbose: bool = True):
        """
        Connect to research MCP servers (PubMed, BMJ, Scopus).

        Args:
            verbose: Whether to print connection status.
        """
        if self.sessions:
            if verbose:
                print(f"   [ResearchEngine] Already connected to {len(self.sessions)} servers")
            return

        if verbose:
            print(f"   [ResearchEngine] Connecting to research servers: {RESEARCH_SERVERS}")

        for server_name in RESEARCH_SERVERS:
            if server_name not in MCP_SERVERS:
                if verbose:
                    print(f"   [ResearchEngine] WARNING: Server '{server_name}' not found in MCP_SERVERS")
                continue

            server_path = MCP_SERVERS[server_name]
            server_params = StdioServerParameters(
                command="python",
                args=[server_path],
                env={**os.environ}
            )

            try:
                if verbose:
                    print(f"   [ResearchEngine] Connecting to {server_name}...")

                stdio_transport = await self.exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                stdio, write = stdio_transport
                session = await self.exit_stack.enter_async_context(
                    ClientSession(stdio, write)
                )
                await session.initialize()

                self.sessions[server_name] = session

                # Register all tools from this server
                tools = await session.list_tools()
                for tool in tools.tools:
                    self.tool_registry[tool.name] = server_name
                    if verbose:
                        print(f"   [ResearchEngine]   ✓ Registered tool: {tool.name}")

            except Exception as e:
                if verbose:
                    print(f"   [ResearchEngine]   ✗ Failed to connect to {server_name}: {e}")

        if verbose:
            print(f"   [ResearchEngine] Connected to {len(self.sessions)} servers with {len(self.tool_registry)} tools")

    async def disconnect(self, verbose: bool = True):
        """Disconnect from all MCP servers."""
        if verbose:
            print(f"   [ResearchEngine] Disconnecting from {len(self.sessions)} servers...")

        await self.exit_stack.aclose()
        self.sessions.clear()
        self.tool_registry.clear()

        if verbose:
            print(f"   [ResearchEngine] Disconnected")

    async def get_research_tools(self, exclude: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get all available research paper tools from connected servers.

        Args:
            exclude: List of tool names to exclude.

        Returns:
            List of tool definitions for Claude API.
        """
        exclude = exclude or []
        tools = []

        for session in self.sessions.values():
            server_tools = await session.list_tools()
            for tool in server_tools.tools:
                if tool.name not in exclude:
                    tools.append({
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.inputSchema
                    })

        return tools

    async def call_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Call a research tool by name.

        Args:
            tool_name: Name of the tool to call.
            tool_input: Input parameters for the tool.

        Returns:
            Tool result.
        """
        server_name = self.tool_registry.get(tool_name)
        if not server_name or server_name not in self.sessions:
            raise ValueError(f"Tool {tool_name} not found or server not connected")

        session = self.sessions[server_name]
        return await session.call_tool(tool_name, tool_input)

    def get_date_filter(self, years_back: int = 5) -> str:
        """
        Calculate date filter for research papers.

        Args:
            years_back: Number of years to look back (default: 5).

        Returns:
            Minimum date string in format "YYYY" or "YYYY/MM/DD".
        """
        current_year = datetime.now().year
        min_year = current_year - years_back
        return str(min_year)

    async def analyze_with_research_papers(
        self,
        clinical_scenario: str,
        date_filter: int = 5,
        quartile_filter: str = "Q1-Q2",
        verbose: bool = True
    ) -> Tuple[List[dict], List[dict]]:
        """
        Analyze clinical scenario using recent, high-quality research papers.

        Evidence cascade:
        1. BMJ articles (last 5 years, peer-reviewed)
        2. Scopus Q1/Q2 articles (last 5 years, high-impact)
        3. PubMed articles (last 5 years, fallback)

        Args:
            clinical_scenario: Patient case description.
            date_filter: Years to look back (default: 5).
            quartile_filter: Journal quality filter (default: "Q1-Q2").
            verbose: Whether to print progress.

        Returns:
            Tuple of (diagnoses, tool_calls) where:
            - diagnoses: List of diagnosis dictionaries with research citations
            - tool_calls: List of tool calls made (for progress reporting)
        """
        if not self.anthropic:
            if verbose:
                print(f"   [ResearchEngine] ERROR: No Anthropic client!")
            return [], []

        tools = await self.get_research_tools()
        min_date = self.get_date_filter(date_filter)

        if verbose:
            print(f"   [ResearchEngine] Available research tools: {len(tools)}")
            print(f"   [ResearchEngine] Date filter: Papers from {min_date} onwards")
            print(f"   [ResearchEngine] Quartile filter: {quartile_filter}")

        # Import the research prompt function
        from .prompts.diagnosis_prompts import get_research_analysis_prompt

        prompt = get_research_analysis_prompt(clinical_scenario, min_date, quartile_filter)
        messages = [{"role": "user", "content": prompt}]
        diagnoses = []
        tool_calls = []

        try:
            response = self.anthropic.messages.create(
                model="claude-haiku-4-5",
                max_tokens=8192,
                tools=tools,
                messages=messages
            )

            if verbose:
                print(f"   [ResearchEngine] Stop reason: {response.stop_reason}")

            # Tool use loop
            while response.stop_reason == "tool_use":
                tool_results = []
                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_name = content_block.name
                        tool_input = content_block.input

                        if verbose:
                            print(f"   [ResearchEngine] Calling tool: {tool_name}")

                        # Track tool call for progress reporting
                        tool_calls.append({
                            "tool_name": tool_name,
                            "tool_input": tool_input
                        })

                        result = await self.call_tool(tool_name, tool_input)
                        result_text = result.content[0].text

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": result_text
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

                response = self.anthropic.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=8192,
                    tools=tools,
                    messages=messages
                )

            # Extract final JSON response
            for block in response.content:
                if hasattr(block, 'text'):
                    try:
                        result = json.loads(block.text)
                        diagnoses = result.get('diagnoses', [])

                        # Tag all diagnoses with source_type for UI differentiation
                        for diagnosis in diagnoses:
                            diagnosis['source_type'] = 'research'

                        break
                    except:
                        # Try to find JSON in text
                        text = block.text
                        if '{' in text:
                            json_start = text.index('{')
                            json_end = text.rindex('}') + 1
                            try:
                                result = json.loads(text[json_start:json_end])
                                diagnoses = result.get('diagnoses', [])

                                # Tag all diagnoses with source_type
                                for diagnosis in diagnoses:
                                    diagnosis['source_type'] = 'research'

                                break
                            except:
                                pass

            if verbose:
                print(f"   [ResearchEngine] Extracted {len(diagnoses)} research-based diagnoses")

        except Exception as e:
            if verbose:
                print(f"   [ResearchEngine] Error: {e}")
            diagnoses = []

        return diagnoses, tool_calls
