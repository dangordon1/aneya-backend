"""
Diagnosis Engine for Clinical Decision Support.

Handles clinical diagnosis analysis using guideline MCP servers (NICE, FOGSI, NHM, AIIMS, PubMed).
This class owns its own MCP server connections for guideline-related tools.
"""

import asyncio
import json
import os
from pathlib import Path
from contextlib import AsyncExitStack
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Dict, List, Any, Optional, Tuple

from .config import MCP_SERVERS, REGION_SERVERS, GUIDELINE_SERVERS
from .prompts import (
    get_clinical_validation_prompt,
    get_diagnosis_analysis_prompt,
    get_pubmed_fallback_prompt,
)


class DiagnosisEngine:
    """
    Handles clinical diagnosis analysis using guideline MCP servers.

    This class owns its own MCP server connections for:
    - patient_info: Patient context and seasonal data
    - nice: UK NICE guidelines
    - fogsi, nhm, aiims: India-specific guidelines
    - pubmed: Medical literature fallback
    """

    def __init__(self, anthropic_api_key: Optional[str] = None):
        """
        Initialize the diagnosis engine.

        Args:
            anthropic_api_key: Anthropic API key for Claude. If None, reads from env.
        """
        self.sessions: Dict[str, ClientSession] = {}
        self.tool_registry: Dict[str, str] = {}
        self.exit_stack = AsyncExitStack()
        self.current_region: Optional[str] = None

        api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.anthropic = Anthropic(api_key=api_key) if api_key else None

    async def connect_guideline_servers(self, country_code: Optional[str] = None, verbose: bool = True):
        """
        Connect to guideline MCP servers based on region.

        Args:
            country_code: ISO country code (e.g., 'GB', 'IN'). Determines which servers to connect.
            verbose: Whether to print connection status.
        """
        normalized_code = country_code.upper() if country_code else None

        # Check if we need to reconnect
        if self.sessions and self.current_region != normalized_code:
            if verbose:
                print(f"   [DiagnosisEngine] Region changed, reconnecting...")
            await self.disconnect()

        # Skip if already connected
        if self.sessions and self.current_region == normalized_code:
            if verbose:
                print(f"   [DiagnosisEngine] Already connected to {normalized_code}")
            return

        # Get region-specific servers, filtered to only guideline servers
        if country_code:
            region_servers = REGION_SERVERS.get(country_code.upper(), REGION_SERVERS.get("default", []))
            servers_to_connect = [s for s in region_servers if s in GUIDELINE_SERVERS]
        else:
            servers_to_connect = GUIDELINE_SERVERS

        # Build server dict
        servers = {
            name: MCP_SERVERS[name]
            for name in servers_to_connect
            if name in MCP_SERVERS and Path(MCP_SERVERS[name]).exists()
        }

        if verbose:
            print(f"   [DiagnosisEngine] Connecting to {len(servers)} guideline server(s): {', '.join(servers.keys())}")

        # Connect in parallel
        connection_tasks = [
            self._connect_single_server(server_name, server_path, verbose)
            for server_name, server_path in servers.items()
        ]

        await asyncio.gather(*connection_tasks, return_exceptions=True)

        # Build tool registry
        await self._discover_tools(verbose)

        self.current_region = normalized_code

    async def _connect_single_server(self, server_name: str, server_path: str, verbose: bool = True):
        """Connect to a single MCP server."""
        try:
            server_params = StdioServerParameters(
                command="fastmcp",
                args=["run", server_path, "--transport", "stdio", "--no-banner"],
                env=os.environ.copy()
            )

            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            stdio, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(stdio, write)
            )

            await session.initialize()
            self.sessions[server_name] = session

        except Exception as e:
            if verbose:
                print(f"      [DiagnosisEngine] Failed to connect {server_name}: {e}")

    async def _discover_tools(self, verbose: bool = True):
        """Build registry of tools from connected servers."""
        list_tasks = [
            (server_name, session.list_tools())
            for server_name, session in self.sessions.items()
        ]

        results = await asyncio.gather(*[task[1] for task in list_tasks])

        for (server_name, _), tools_response in zip(list_tasks, results):
            for tool in tools_response.tools:
                self.tool_registry[tool.name] = server_name

    async def disconnect(self):
        """Disconnect from all MCP servers."""
        try:
            await self.exit_stack.aclose()
        except Exception:
            pass
        self.sessions = {}
        self.tool_registry = {}
        self.exit_stack = AsyncExitStack()
        self.current_region = None

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """Route tool call to appropriate server."""
        server_name = self.tool_registry.get(tool_name)
        if not server_name:
            raise ValueError(f"Unknown tool: {tool_name}")

        session = self.sessions[server_name]
        return await session.call_tool(tool_name, arguments)

    async def get_guideline_tools(self) -> List[Dict[str, Any]]:
        """Get guideline tools for Claude API (excludes drug tools)."""
        all_tools = []
        for session in self.sessions.values():
            tools = await session.list_tools()
            all_tools.extend([{
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            } for tool in tools.tools])

        # Exclude drug and pubmed tools from initial diagnosis
        excluded_patterns = ['bnf', 'drugbank', 'mims', 'drug', 'pubmed']
        guideline_tools = [
            tool for tool in all_tools
            if not any(pattern in tool['name'].lower() for pattern in excluded_patterns)
        ]

        return guideline_tools

    async def get_pubmed_tools(self) -> List[Dict[str, Any]]:
        """Get PubMed tools for fallback."""
        all_tools = []
        for session in self.sessions.values():
            tools = await session.list_tools()
            all_tools.extend([{
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            } for tool in tools.tools])

        return [t for t in all_tools if 'pubmed' in t['name'].lower()]

    async def validate_clinical_input(
        self,
        clinical_scenario: str,
        verbose: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that input is a genuine clinical consultation.

        Args:
            clinical_scenario: The text to validate.
            verbose: Whether to print validation result.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if not self.anthropic:
            return (True, None)

        try:
            validation_prompt = get_clinical_validation_prompt(clinical_scenario)

            message = self.anthropic.messages.create(
                model="claude-haiku-4-5",
                max_tokens=200,
                messages=[{"role": "user", "content": validation_prompt}]
            )

            response_text = message.content[0].text.strip()

            # Extract JSON from response
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            if "{" in response_text and "}" in response_text:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                response_text = response_text[json_start:json_end]

            validation_result = json.loads(response_text)

            is_valid = validation_result.get('is_valid', False)
            reason = validation_result.get('reason', 'No reason provided')

            if verbose:
                status = "VALID" if is_valid else "INVALID"
                print(f"   [DiagnosisEngine] Input validation: {status} - {reason}")

            if not is_valid:
                error_message = (
                    "This system is designed to analyze clinical consultations and provide "
                    "evidence-based medical guidance. Your input does not appear to be a "
                    "clinical consultation or medical scenario.\n\n"
                    f"Reason: {reason}\n\n"
                    "Please provide information about a patient's symptoms, medical condition, "
                    "or clinical scenario requiring decision support."
                )
                return (False, error_message)

            return (True, None)

        except Exception as e:
            if verbose:
                print(f"   [DiagnosisEngine] Validation error: {e} - allowing processing")
            return (True, None)

    async def analyze_with_guidelines(
        self,
        clinical_scenario: str,
        verbose: bool = True
    ) -> Tuple[List[dict], List[dict]]:
        """
        Analyze clinical scenario using guideline tools.

        This method uses Claude with MCP guideline tools to analyze the clinical
        scenario and extract structured diagnoses.

        Args:
            clinical_scenario: Patient case description.
            verbose: Whether to print progress.

        Returns:
            Tuple of (diagnoses, tool_calls) where:
            - diagnoses: List of diagnosis dictionaries
            - tool_calls: List of tool calls made (for progress reporting)
        """
        if not self.anthropic:
            if verbose:
                print(f"   [DiagnosisEngine] ERROR: No Anthropic client!")
            return [], []

        tools = await self.get_guideline_tools()

        if verbose:
            print(f"   [DiagnosisEngine] Available tools: {len(tools)}")
            print(f"   [DiagnosisEngine] Anthropic client initialized: {self.anthropic is not None}")

        prompt = get_diagnosis_analysis_prompt(clinical_scenario)
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
                print(f"   [DiagnosisEngine] Stop reason: {response.stop_reason}")

            # Tool use loop
            while response.stop_reason == "tool_use":
                tool_results = []
                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_name = content_block.name
                        tool_input = content_block.input

                        if verbose:
                            print(f"   [DiagnosisEngine] Calling tool: {tool_name}")

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
                                break
                            except:
                                pass

            if verbose:
                print(f"   [DiagnosisEngine] Extracted {len(diagnoses)} diagnoses")

        except Exception as e:
            if verbose:
                print(f"   [DiagnosisEngine] Error: {e}")
            diagnoses = []

        return diagnoses, tool_calls

    async def pubmed_fallback(
        self,
        clinical_scenario: str,
        existing_diagnoses: List[dict],
        verbose: bool = True
    ) -> Tuple[List[dict], List[dict]]:
        """
        Search PubMed if guidelines are insufficient.

        Args:
            clinical_scenario: Patient case description.
            existing_diagnoses: Diagnoses from guideline analysis.
            verbose: Whether to print progress.

        Returns:
            Tuple of (diagnoses, tool_calls).
        """
        if not self.anthropic:
            return existing_diagnoses, []

        pubmed_tools = await self.get_pubmed_tools()
        if not pubmed_tools:
            return existing_diagnoses, []

        if verbose:
            print(f"   [DiagnosisEngine] PubMed fallback with {len(pubmed_tools)} tools")

        pubmed_prompt = get_pubmed_fallback_prompt(clinical_scenario)
        messages = [{"role": "user", "content": pubmed_prompt}]
        tool_calls = []

        try:
            response = self.anthropic.messages.create(
                model="claude-haiku-4-5",
                max_tokens=8192,
                tools=pubmed_tools,
                messages=messages
            )

            # Tool use loop
            while response.stop_reason == "tool_use":
                tool_results = []
                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_name = content_block.name
                        tool_input = content_block.input

                        if verbose:
                            print(f"   [DiagnosisEngine] PubMed tool: {tool_name}")

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
                    tools=pubmed_tools,
                    messages=messages
                )

            # Extract diagnoses from response
            for block in response.content:
                if hasattr(block, 'text'):
                    try:
                        result = json.loads(block.text)
                        new_diagnoses = result.get('diagnoses', [])
                        if new_diagnoses:
                            # Merge with existing, avoiding duplicates
                            existing_names = {d.get('diagnosis', '').lower() for d in existing_diagnoses}
                            for diag in new_diagnoses:
                                if diag.get('diagnosis', '').lower() not in existing_names:
                                    existing_diagnoses.append(diag)
                        break
                    except:
                        text = block.text
                        if '{' in text:
                            try:
                                json_start = text.index('{')
                                json_end = text.rindex('}') + 1
                                result = json.loads(text[json_start:json_end])
                                new_diagnoses = result.get('diagnoses', [])
                                if new_diagnoses:
                                    existing_names = {d.get('diagnosis', '').lower() for d in existing_diagnoses}
                                    for diag in new_diagnoses:
                                        if diag.get('diagnosis', '').lower() not in existing_names:
                                            existing_diagnoses.append(diag)
                                break
                            except:
                                pass

            if verbose:
                print(f"   [DiagnosisEngine] Total diagnoses after PubMed: {len(existing_diagnoses)}")

        except Exception as e:
            if verbose:
                print(f"   [DiagnosisEngine] PubMed error: {e}")

        return existing_diagnoses, tool_calls


__all__ = ['DiagnosisEngine']
