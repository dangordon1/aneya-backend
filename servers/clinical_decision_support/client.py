"""
Client module for Clinical Decision Support system.

Contains the main ClinicalDecisionSupportClient class with MCP server connection
management, tool routing, and complete clinical workflow functionality.
"""

import asyncio
import json
from pathlib import Path
from contextlib import AsyncExitStack
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Dict, List, Any, Optional, Tuple
import os
import httpx

from .config import MCP_SERVERS, REGION_SERVERS
from .regional_search import RegionalSearchService


class ClinicalDecisionSupportClient:
    """
    Multi-server MCP client for clinical decision support.

    Orchestrates geolocation, NICE guidelines, and BNF servers to provide
    evidence-based clinical recommendations using parallel execution where possible.
    """

    def __init__(self, anthropic_api_key: Optional[str] = None):
        """
        Initialize the clinical decision support client.

        Args:
            anthropic_api_key: Anthropic API key for Claude. If None, reads from ANTHROPIC_API_KEY env var.
                              Can be None if not using Claude-based features.
        """
        self.sessions: Dict[str, ClientSession] = {}  # server_name -> ClientSession
        self.tool_registry: Dict[str, str] = {}  # tool_name -> server_name
        self.exit_stack = AsyncExitStack()

        api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.anthropic = Anthropic(api_key=api_key) if api_key else None

        # Initialize regional search service
        self.regional_search = RegionalSearchService(self)

    async def get_location_from_ip(self, user_ip: Optional[str] = None) -> dict:
        """
        Get location information from IP address using direct HTTP call (no MCP).

        This is called BEFORE connecting to MCP servers to determine which
        region-specific servers to load.

        Args:
            user_ip: Optional IP address. If None, will auto-detect.

        Returns:
            Dictionary with:
            - country: Country name
            - country_code: ISO country code (e.g., 'GB', 'IN', 'US')
            - ip: IP address used for lookup
        """
        try:
            # Use ip-api.com for geolocation (free, no API key required)
            if user_ip:
                url = f"http://ip-api.com/json/{user_ip}?fields=status,message,country,countryCode"
            else:
                # Auto-detect by not specifying IP
                url = "http://ip-api.com/json/?fields=status,message,country,countryCode"

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                if data.get('status') == 'fail':
                    print(f"⚠️  Geolocation failed: {data.get('message', 'Unknown error')}")
                    return {
                        'country': 'Unknown',
                        'country_code': 'XX',
                        'ip': user_ip or 'unknown'
                    }

                return {
                    'country': data.get('country', 'Unknown'),
                    'country_code': data.get('countryCode', 'XX'),
                    'ip': user_ip or 'auto-detected'
                }
        except Exception as e:
            print(f"⚠️  Geolocation error: {str(e)}")
            return {
                'country': 'Unknown',
                'country_code': 'XX',
                'ip': user_ip or 'unknown'
            }

    async def connect_to_servers(self, country_code: Optional[str] = None, server_paths: Optional[Dict[str, str]] = None, verbose: bool = True):
        """
        Connect to region-specific MCP servers in parallel.

        Args:
            country_code: ISO country code (e.g., 'GB', 'IN', 'US'). If provided,
                         only connects to servers relevant for that region.
            server_paths: Optional dict of server_name -> server_path. Uses defaults if None.
            verbose: Whether to print connection status
        """
        # Filter servers based on country code
        if country_code and not server_paths:
            # Get region-specific server list
            server_names = REGION_SERVERS.get(country_code.upper(), REGION_SERVERS["default"])

            if verbose:
                print(f"🌍 Region: {country_code.upper()} - Loading region-specific servers")

            # Build filtered server dict
            servers = {
                name: MCP_SERVERS[name]
                for name in server_names
                if name in MCP_SERVERS and Path(MCP_SERVERS[name]).exists()
            }
        else:
            servers = server_paths or MCP_SERVERS

        if verbose:
            print(f"🔄 Connecting to {len(servers)} server(s) in parallel...")
            if country_code:
                print(f"   Region-specific servers for {country_code}: {', '.join(servers.keys())}")

        # Validate all servers exist
        for server_name, server_path in servers.items():
            if not Path(server_path).exists():
                print(f"   ⚠️  Skipping {server_name} - file not found: {server_path}")
                continue

        # Connect to all servers in parallel using asyncio.gather
        connection_tasks = [
            self._connect_single_server(server_name, server_path, verbose)
            for server_name, server_path in servers.items()
            if Path(server_path).exists()
        ]

        await asyncio.gather(*connection_tasks, return_exceptions=True)

        # Build tool registry by listing tools from all servers in parallel
        await self._discover_tools(verbose)

    async def _connect_single_server(self, server_name: str, server_path: str, verbose: bool = True):
        """Connect to a single MCP server."""
        try:
            if verbose:
                print(f"  ⏳ Connecting to {server_name}...")

            server_params = StdioServerParameters(
                command="fastmcp",
                args=["run", server_path, "--transport", "stdio", "--no-banner"],
                env=os.environ.copy()  # Pass environment variables to subprocess
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

            if verbose:
                print(f"  ✅ {server_name} connected")

        except Exception as e:
            print(f"  ❌ Failed to connect to {server_name}: {str(e)}")
            raise

    async def _discover_tools(self, verbose: bool = True):
        """Build registry of which tool belongs to which server (parallel execution)."""
        if verbose:
            print(f"\n📋 Discovering tools from {len(self.sessions)} servers...")

        # List tools from all servers in parallel
        list_tasks = [
            (server_name, session.list_tools())
            for server_name, session in self.sessions.items()
        ]

        results = await asyncio.gather(*[task[1] for task in list_tasks])

        total_tools = 0
        for (server_name, _), tools_response in zip(list_tasks, results):
            server_tool_count = len(tools_response.tools)
            total_tools += server_tool_count

            for tool in tools_response.tools:
                self.tool_registry[tool.name] = server_name

            if verbose:
                tool_names = [tool.name for tool in tools_response.tools]
                print(f"  📦 {server_name}: {server_tool_count} tools")
                for tool_name in tool_names:
                    print(f"      • {tool_name}")

        if verbose:
            print(f"\n✅ Total: {total_tools} tools discovered")

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """
        Route tool call to appropriate server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result
        """
        server_name = self.tool_registry.get(tool_name)
        if not server_name:
            raise ValueError(f"Unknown tool: {tool_name}")

        session = self.sessions[server_name]
        return await session.call_tool(tool_name, arguments)

    async def get_all_tools_for_claude(self) -> List[Dict[str, Any]]:
        """Aggregate tools from all servers for Claude API."""
        all_tools = []
        for session in self.sessions.values():
            tools = await session.list_tools()
            all_tools.extend([{
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            } for tool in tools.tools])
        return all_tools

    async def _get_patient_info_and_season(
        self,
        patient_id: Optional[str],
        patient_age: Optional[str],
        allergies: Optional[str],
        verbose: bool = True
    ) -> tuple[Optional[dict], Optional[dict], Optional[str], Optional[str]]:
        """
        Retrieve patient information and seasonal context.

        Returns:
            Tuple of (patient_info, seasonal_context, patient_age, allergies)
        """
        patient_info = None
        seasonal_context = None

        if patient_id:
            if verbose:
                print("\n👤 Step 0: Retrieving patient information...")

            # Get patient info and seasonal context in parallel
            patient_result, season_result = await asyncio.gather(
                self.call_tool("get_patient_info", {"patient_id": patient_id}),
                self.call_tool("get_current_season", {}),
                return_exceptions=True
            )

            if not isinstance(patient_result, Exception):
                patient_info = json.loads(patient_result.content[0].text)
                if patient_info.get('success'):
                    if verbose:
                        print(f"   Patient: {patient_info.get('gender')}, {patient_info.get('age')}")
                        print(f"   Weight: {patient_info.get('weight_kg')}kg, BMI: {patient_info.get('bmi')}")
                        if patient_info.get('current_medications'):
                            print(f"   Current medications: {', '.join(patient_info['current_medications'])}")
                        if patient_info.get('existing_conditions'):
                            print(f"   Existing conditions: {', '.join(patient_info['existing_conditions'])}")
                        if patient_info.get('allergies'):
                            print(f"   Allergies: {', '.join(patient_info['allergies'])}")

                    # Override with patient_info if not explicitly provided
                    if not patient_age:
                        patient_age = patient_info.get('age')
                    if not allergies and patient_info.get('allergies'):
                        allergies = ', '.join(patient_info['allergies'])

            if not isinstance(season_result, Exception):
                seasonal_context = json.loads(season_result.content[0].text)
                if verbose:
                    print(f"   Season: {seasonal_context.get('season')} ({seasonal_context.get('month')})")
                    print(f"   {seasonal_context.get('seasonal_notes')}")
        else:
            # Get seasonal context even without patient ID
            try:
                season_result = await self.call_tool("get_current_season", {})
                seasonal_context = json.loads(season_result.content[0].text)
                if verbose:
                    print(f"\n📅 Current season: {seasonal_context.get('season')} - {seasonal_context.get('seasonal_notes')}")
            except:
                pass

        return patient_info, seasonal_context, patient_age, allergies

    async def _extract_search_terms(
        self,
        clinical_scenario: str,
        verbose: bool = True
    ) -> str:
        """
        Extract key medical conditions from consultation text for focused guideline searching.

        Args:
            clinical_scenario: Raw consultation text
            verbose: Whether to print progress

        Returns:
            Simplified search terms (e.g., "throat infection" instead of "prescribe amoxicillin for throat infection")
        """
        if verbose:
            print("\n🔍 Extracting key medical conditions for guideline search...")

        try:
            prompt = f"""Extract the PRIMARY medical condition or symptom from this clinical consultation for searching medical guidelines.

Consultation: "{clinical_scenario}"

Return ONLY 1-3 words describing the core medical condition (e.g., "throat infection", "pneumonia", "asthma exacerbation").
Do NOT include:
- Medication names
- Dosages
- Instructions like "prescribe" or "treat"
- Patient details

Examples:
- "prescribe amoxicillin 500mg for bacterial throat infection" → "throat infection"
- "3-year-old with croup and stridor" → "croup"
- "patient with pneumonia needs antibiotics" → "pneumonia"

Medical condition:"""

            message = self.anthropic.messages.create(
                model="claude-haiku-4-5",  # Use latest Haiku 4.5 model (Oct 2025)
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}]
            )

            search_terms = message.content[0].text.strip().strip('"').strip("'")

            if verbose:
                print(f"   📝 Search terms: \"{search_terms}\" (from: \"{clinical_scenario[:60]}...\")")

            return search_terms

        except Exception as e:
            if verbose:
                print(f"   ⚠️  Failed to extract search terms: {e}")
                print(f"   Using original text...")
            return clinical_scenario

    async def _determine_location(
        self,
        location_override: Optional[str],
        verbose: bool = True
    ) -> dict:
        """
        Determine user location (using direct geolocation or override).

        Returns:
            Location info dictionary with country_code, country, and ip
        """
        if verbose:
            print("\n📍 Step 1: Determining location...")

        if location_override:
            location_info = {
                'country_code': location_override.upper(),
                'country': 'User specified',
                'ip': 'override'
            }
            if verbose:
                print(f"   Location: {location_override} (user override)")
        else:
            # This should be passed in from the API layer after calling get_location_from_ip
            # Fallback to direct geolocation if not provided
            location_info = await self.get_location_from_ip()
            if verbose:
                print(f"   Auto-detected: {location_info['country']} ({location_info['country_code']})")

        return location_info

    async def _search_uk_resources(
        self,
        clinical_scenario: str,
        verbose: bool = True
    ) -> tuple[List[dict], List[dict], List[dict]]:
        """
        Search UK-specific resources (NICE guidelines, CKS, BNF).

        Returns:
            Tuple of (guidelines, cks_topics, bnf_summaries)
        """
        if verbose:
            print(f"\n📚 Step 2: Searching NICE and BNF resources...")

        guidelines = []
        cks_topics = []
        bnf_summaries = []

        # Extract key medical terms from scenario for better search
        scenario_lower = clinical_scenario.lower()
        search_terms = []

        # Common conditions to extract
        conditions = ['croup', 'bronchiolitis', 'asthma', 'pneumonia', 'sepsis',
                     'fever', 'cough', 'uti', 'infection', 'pain']
        for condition in conditions:
            if condition in scenario_lower:
                search_terms.append(condition)

        # Add broader search terms for BNF treatment summaries AT THE BEGINNING
        broader_terms = []
        if any(term in scenario_lower for term in ['pneumonia', 'respiratory', 'cap ', ' cap,', 'cap)', 'cap-']):
            if 'respiratory' not in search_terms:
                broader_terms.append('respiratory')
            if 'pneumonia' not in search_terms:
                broader_terms.append('pneumonia')
        if 'sepsis' in scenario_lower or 'septic' in scenario_lower:
            if 'sepsis' not in search_terms:
                broader_terms.append('sepsis')

        # Prepend broader terms so they're searched first
        search_terms = broader_terms + search_terms

        # If no specific condition found, use full scenario
        if not search_terms:
            search_terms = [clinical_scenario]

        # PARALLELIZED: Search NICE Guidelines, CKS, and BNF in parallel
        async def search_nice_guideline(term):
            try:
                result = await self.call_tool("search_nice_guidelines", {
                    "keyword": term,
                    "max_results": 3
                })
                guidelines_data = json.loads(result.content[0].text)
                return ('nice', guidelines_data.get('results', []))
            except Exception as e:
                return ('nice', [])

        async def search_cks_topic(term):
            try:
                result = await self.call_tool("search_cks_topics", {
                    "topic": term
                })
                cks_data = json.loads(result.content[0].text)
                if cks_data.get('success') and cks_data.get('results'):
                    return ('cks', cks_data['results'])
                return ('cks', [])
            except:
                return ('cks', [])

        async def search_bnf_summary(term):
            try:
                result = await self.call_tool("search_bnf_treatment_summaries", {
                    "condition": term,
                    "max_results": 3
                })
                bnf_data = json.loads(result.content[0].text)
                if bnf_data.get('success') and bnf_data.get('results'):
                    return ('bnf', bnf_data['results'])
                return ('bnf', [])
            except:
                return ('bnf', [])

        # Build all search tasks
        search_tasks = []
        for term in search_terms[:2]:
            search_tasks.append(search_nice_guideline(term))
            search_tasks.append(search_cks_topic(term))
            search_tasks.append(search_bnf_summary(term))

        # Execute all searches in parallel
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Process results
        for result in search_results:
            if isinstance(result, Exception):
                continue
            search_type, data = result
            if search_type == 'nice':
                guidelines.extend(data)
            elif search_type == 'cks':
                cks_topics.extend(data)
            elif search_type == 'bnf':
                bnf_summaries.extend(data)

        # Remove duplicates from guidelines
        seen_refs = set()
        unique_guidelines = []
        for g in guidelines:
            ref = g.get('reference', g.get('url'))
            if ref not in seen_refs:
                seen_refs.add(ref)
                unique_guidelines.append(g)
        guidelines = unique_guidelines[:5]

        # Remove duplicates from BNF summaries
        seen_bnf_urls = set()
        unique_bnf = []
        for b in bnf_summaries:
            if b['url'] not in seen_bnf_urls:
                seen_bnf_urls.add(b['url'])
                unique_bnf.append(b)
        bnf_summaries = unique_bnf[:3]

        if verbose:
            print(f"   Found {len(guidelines)} guideline(s), {len(cks_topics)} CKS topic(s), and {len(bnf_summaries)} BNF treatment summar{'y' if len(bnf_summaries) == 1 else 'ies'}")
            for g in guidelines[:3]:
                if 'reference' in g:
                    print(f"      • Guideline {g['reference']}: {g['title'][:50]}...")
                else:
                    print(f"      • {g['title'][:60]}...")
            for topic in cks_topics[:3]:
                print(f"      • CKS: {topic['title'][:50]}...")
            for bnf in bnf_summaries[:3]:
                print(f"      • BNF: {bnf['title'][:50]}...")

        return guidelines, cks_topics, bnf_summaries

    async def _search_india_resources(
        self,
        clinical_scenario: str,
        verbose: bool = True
    ) -> List[dict]:
        """
        Search India-specific resources (FOGSI guidelines).

        Returns:
            List of FOGSI guidelines
        """
        if verbose:
            print(f"\n📚 Step 2: Searching FOGSI guidelines for India...")

        # Extract key medical terms from scenario
        scenario_lower = clinical_scenario.lower()
        search_terms = []

        # Common OB/GYN and general medical conditions
        conditions = ['pregnancy', 'preeclampsia', 'gestational', 'labor', 'delivery', 'cesarean',
                     'postpartum', 'antenatal', 'prenatal', 'diabetes', 'hypertension', 'fever',
                     'infection', 'bleeding', 'pain']
        for condition in conditions:
            if condition in scenario_lower:
                search_terms.append(condition)

        # If no specific condition found, use full scenario
        if not search_terms:
            search_terms = [clinical_scenario]

        # Search FOGSI guidelines
        fogsi_guidelines = []
        for term in search_terms[:2]:
            try:
                result = await self.call_tool("search_fogsi_guidelines", {
                    "keyword": term,
                    "max_results": 3
                })
                fogsi_data = json.loads(result.content[0].text)
                if fogsi_data.get('success'):
                    fogsi_guidelines.extend(fogsi_data.get('results', []))
            except Exception as e:
                if verbose:
                    print(f"   ⚠️  FOGSI search failed for '{term}': {str(e)}")

        if verbose:
            print(f"   Found {len(fogsi_guidelines)} FOGSI guideline(s)")
            if fogsi_guidelines:
                for guideline in fogsi_guidelines[:3]:
                    print(f"      • {guideline['title'][:60]}...")

        return fogsi_guidelines

    async def _search_international_resources(
        self,
        clinical_scenario: str,
        verbose: bool = True
    ) -> List[dict]:
        """
        Search international resources (PubMed).

        Returns:
            List of PubMed articles
        """
        if verbose:
            print(f"\n📰 Step 2b: Searching PubMed for evidence...")

        result = await self.call_tool("search_pubmed", {
            "query": clinical_scenario,
            "max_results": 5
        })
        pubmed_data = json.loads(result.content[0].text)
        pubmed_articles = pubmed_data.get('results', [])

        if verbose:
            print(f"   Found {pubmed_data.get('count', 0)} PubMed articles")
            for article in pubmed_articles[:3]:
                print(f"      • PMID {article['pmid']}: {article['title'][:60]}...")

        return pubmed_articles

    async def _search_guidelines_by_region(
        self,
        location_info: dict,
        clinical_scenario: str,
        verbose: bool = True
    ) -> tuple[List[dict], List[dict], List[dict], List[dict]]:
        """
        Route guideline search based on region using configuration-driven service.

        Returns:
            Tuple of (guidelines, cks_topics, bnf_summaries, pubmed_articles)
        """
        return await self.regional_search.search_by_region(
            location_info['country_code'],
            clinical_scenario,
            verbose
        )

    async def _fetch_guideline_details(
        self,
        guidelines: List[dict],
        cks_topics: List[dict],
        bnf_summaries: List[dict],
        verbose: bool = True
    ) -> tuple[List[dict], List[dict], List[dict]]:
        """
        Fetch detailed content for guidelines, CKS topics, and BNF summaries in parallel.

        Returns:
            Tuple of (guideline_contents, cks_contents, bnf_summary_contents)
        """
        guideline_contents = []
        cks_contents = []
        bnf_summary_contents = []

        # Helper functions for fetching details
        async def fetch_guideline_detail(guideline):
            try:
                result = await self.call_tool("get_guideline_details", {
                    "identifier": guideline['reference']
                })
                guideline_detail = json.loads(result.content[0].text)

                if guideline_detail.get('success'):
                    return ('guideline', {
                        'title': guideline['title'],
                        'reference': guideline['reference'],
                        'url': guideline['url'],
                        'overview': guideline_detail.get('overview', ''),
                        'sections': guideline_detail.get('sections', []),
                        'published_date': guideline_detail.get('published_date', '')
                    }, guideline['reference'], True, None)
                else:
                    error_msg = guideline_detail.get('error', 'Unknown error')
                    return ('guideline', None, guideline['reference'], False, error_msg)
            except Exception as e:
                return ('guideline', None, guideline.get('reference', 'guideline'), False, str(e))

        async def fetch_fogsi_guideline_detail(guideline):
            """Fetch FOGSI guideline content using URL instead of reference"""
            try:
                result = await self.call_tool("get_fogsi_guideline_content", {
                    "guideline_url": guideline['url']
                })
                guideline_detail = json.loads(result.content[0].text)

                if guideline_detail.get('success'):
                    return ('guideline', {
                        'title': guideline['title'],
                        'url': guideline['url'],
                        'overview': guideline.get('description', ''),
                        'sections': guideline_detail.get('sections', []),
                        'content': guideline_detail.get('content', ''),
                        'category': guideline.get('category', 'General')
                    }, guideline['title'], True, None)
                else:
                    error_msg = guideline_detail.get('error', 'Unknown error')
                    return ('guideline', None, guideline['title'], False, error_msg)
            except Exception as e:
                return ('guideline', None, guideline.get('title', 'guideline'), False, str(e))

        async def fetch_cks_detail(topic):
            try:
                result = await self.call_tool("get_cks_topic", {
                    "topic": topic['title'].lower().replace(' ', '-')
                })
                cks_content = json.loads(result.content[0].text)

                if cks_content.get('success'):
                    return ('cks', {
                        'title': topic['title'],
                        'url': topic['url'],
                        'summary': topic.get('summary', ''),
                        'management': cks_content.get('management', ''),
                        'prescribing': cks_content.get('prescribing', ''),
                        'full_text': cks_content.get('full_text', '')
                    }, topic['title'], True, None)
                else:
                    return ('cks', None, topic['title'], False, 'Failed')
            except Exception as e:
                return ('cks', None, topic.get('title', 'topic'), False, str(e))

        async def fetch_bnf_summary_detail(bnf):
            try:
                result = await self.call_tool("get_bnf_treatment_summary", {
                    "url": bnf['url']
                })
                bnf_content = json.loads(result.content[0].text)

                if bnf_content.get('success'):
                    return ('bnf', {
                        'title': bnf['title'],
                        'url': bnf['url'],
                        'summary': bnf_content.get('summary', ''),
                        'sections': bnf_content.get('sections', [])
                    }, bnf['title'], True, None)
                else:
                    return ('bnf', None, bnf['title'], False, 'Failed')
            except Exception as e:
                return ('bnf', None, bnf.get('title', 'BNF summary'), False, str(e))

        # Build all detail fetch tasks
        detail_tasks = []

        if guidelines:
            if verbose:
                print(f"   Retrieving full guideline content for {len(guidelines[:3])} guideline(s) (parallel)...")
            for guideline in guidelines[:3]:
                # Check if this is a FOGSI guideline (no 'reference' field) or NICE guideline
                if 'reference' in guideline:
                    detail_tasks.append(fetch_guideline_detail(guideline))
                else:
                    detail_tasks.append(fetch_fogsi_guideline_detail(guideline))

        if cks_topics:
            if verbose:
                print(f"   Retrieving full CKS content for {len(cks_topics[:3])} topic(s) (parallel)...")
            for topic in cks_topics[:3]:
                detail_tasks.append(fetch_cks_detail(topic))

        if bnf_summaries:
            if verbose:
                print(f"   Retrieving full BNF treatment summar{'y' if len(bnf_summaries[:3]) == 1 else 'ies'} for {len(bnf_summaries[:3])} resource(s) (parallel)...")
            for bnf in bnf_summaries[:3]:
                detail_tasks.append(fetch_bnf_summary_detail(bnf))

        # Execute all detail fetches in parallel
        if detail_tasks:
            detail_results = await asyncio.gather(*detail_tasks, return_exceptions=True)

            # Process results
            for result in detail_results:
                if isinstance(result, Exception):
                    continue

                content_type, content_data, identifier, success, error = result

                if success and content_data:
                    if content_type == 'guideline':
                        guideline_contents.append(content_data)
                        if verbose:
                            print(f"      ✓ Retrieved: {identifier}")
                    elif content_type == 'cks':
                        cks_contents.append(content_data)
                        if verbose:
                            print(f"      ✓ Retrieved: {identifier}")
                    elif content_type == 'bnf':
                        bnf_summary_contents.append(content_data)
                        if verbose:
                            print(f"      ✓ Retrieved: {identifier}")
                else:
                    if verbose:
                        print(f"      ✗ Failed to retrieve {identifier}: {error}")

        return guideline_contents, cks_contents, bnf_summary_contents

    async def _generate_summary(
        self,
        patient_info: Optional[dict],
        patient_age: Optional[str],
        allergies: Optional[str],
        seasonal_context: Optional[dict],
        location_info: dict,
        guidelines: List[dict],
        cks_topics: List[dict],
        bnf_summaries: List[dict],
        pubmed_articles: List[dict],
        diagnoses: List[dict],
        bnf_prescribing_guidance: List[dict],
        drug_interactions: List[dict],
        verbose: bool = True
    ) -> str:
        """
        Generate comprehensive summary report.

        Returns:
            Summary string
        """
        if verbose:
            print(f"\n📝 Step 5: Generating recommendations...")

        summary_parts = []

        # Patient demographics
        if patient_info and patient_info.get('success'):
            summary_parts.append(f"👤 PATIENT INFORMATION")
            summary_parts.append(f"   ID: {patient_info.get('patient_id')}")
            summary_parts.append(f"   Age: {patient_info.get('age')}, Gender: {patient_info.get('gender')}")
            summary_parts.append(f"   Weight: {patient_info.get('weight_kg')}kg, Height: {patient_info.get('height_cm')}cm, BMI: {patient_info.get('bmi')}")
            if patient_info.get('ethnicity'):
                summary_parts.append(f"   Ethnicity: {patient_info.get('ethnicity')}")
            if patient_info.get('existing_conditions'):
                summary_parts.append(f"   Existing conditions: {', '.join(patient_info['existing_conditions'])}")
            if patient_info.get('current_medications'):
                summary_parts.append(f"   Current medications: {', '.join(patient_info['current_medications'])}")
            if patient_info.get('allergies'):
                summary_parts.append(f"   ⚠️  Allergies: {', '.join(patient_info['allergies'])}")
        elif patient_age:
            summary_parts.append(f"👤 Patient age: {patient_age}")
            if allergies:
                summary_parts.append(f"⚠️  Known allergies: {allergies}")

        # Seasonal context
        if seasonal_context:
            summary_parts.append(f"\n📅 SEASONAL CONTEXT")
            summary_parts.append(f"   {seasonal_context.get('season')} ({seasonal_context.get('month')})")
            summary_parts.append(f"   {seasonal_context.get('seasonal_notes')}")

        summary_parts.append(f"\n📍 Location: {location_info.get('country', 'Unknown')} ({location_info.get('country_code', 'XX')})")

        if guidelines:
            # Check if these are NICE or FOGSI guidelines
            guideline_type = "NICE" if guidelines and 'reference' in guidelines[0] else "FOGSI"
            summary_parts.append(f"\n📚 Found {len(guidelines)} relevant {guideline_type} guideline(s):")
            for g in guidelines[:3]:
                if 'reference' in g:
                    # NICE guideline
                    summary_parts.append(f"   • {g['reference']}: {g['title']}")
                else:
                    # FOGSI guideline
                    summary_parts.append(f"   • {g['title']}")
                summary_parts.append(f"     {g['url']}")

        if cks_topics:
            summary_parts.append(f"\n📖 Found {len(cks_topics)} relevant NICE CKS topic(s):")
            for topic in cks_topics[:3]:
                summary_parts.append(f"   • {topic['title']}")
                summary_parts.append(f"     {topic['url']}")
                if topic.get('summary'):
                    summary_parts.append(f"     {topic['summary'][:100]}...")

        if bnf_summaries:
            summary_parts.append(f"\n💊 Found {len(bnf_summaries)} relevant BNF treatment summar{'y' if len(bnf_summaries) == 1 else 'ies'}:")
            for bnf in bnf_summaries[:3]:
                summary_parts.append(f"   • {bnf['title']}")
                summary_parts.append(f"     {bnf['url']}")
                if bnf.get('description'):
                    summary_parts.append(f"     {bnf['description'][:100]}...")

        if not guidelines and not cks_topics and not bnf_summaries:
            summary_parts.append("\n📚 No NICE guidelines, CKS topics, or BNF treatment summaries found")

        if pubmed_articles:
            summary_parts.append(f"\n📰 Found {len(pubmed_articles)} relevant PubMed article(s):")
            for article in pubmed_articles[:3]:
                summary_parts.append(f"   • {article['title']}")
                summary_parts.append(f"     PMID: {article['pmid']}")
                if article.get('doi'):
                    summary_parts.append(f"     DOI: {article['doi']}")
                summary_parts.append(f"     {article['journal']} ({article['pubdate']})")

        # New diagnosis-based output with treatment options and medications
        if diagnoses:
            summary_parts.append(f"\n🔍 CLINICAL DIAGNOSES AND TREATMENT OPTIONS ({len(diagnoses)}):")
            for idx, diagnosis in enumerate(diagnoses, 1):
                summary_parts.append(f"\n{'='*70}")
                summary_parts.append(f"DIAGNOSIS {idx}: {diagnosis['diagnosis']}")
                summary_parts.append(f"{'='*70}")
                summary_parts.append(f"Source: {diagnosis['source']}")
                summary_parts.append(f"Guideline URL: {diagnosis['url']}")
                if diagnosis.get('summary'):
                    summary_parts.append(f"Summary: {diagnosis['summary'][:150]}...")

                summary_parts.append(f"\nTREATMENT OPTIONS:")
                for tidx, treatment in enumerate(diagnosis['treatments'], 1):
                    summary_parts.append(f"\n  {tidx}. {treatment['treatment_name']}")

                    if treatment.get('description'):
                        summary_parts.append(f"     {treatment['description']}")

                    if treatment.get('medications_detailed'):
                        summary_parts.append(f"     \n     💊 MEDICATIONS:")
                        for drug in treatment['medications_detailed']:
                            summary_parts.append(f"\n     • {drug['drug_name']}")
                            summary_parts.append(f"       BNF URL: {drug['url']}")

                            if drug.get('indications') and drug['indications'] != 'Not specified':
                                indications = drug['indications'][:150]
                                summary_parts.append(f"       Indications: {indications}...")

                            if drug.get('dosage') and drug['dosage'] != 'Not specified':
                                dosage = drug['dosage'][:150]
                                summary_parts.append(f"       Dosage: {dosage}...")

                            if drug.get('contraindications') and drug['contraindications'] != 'Not specified':
                                contraindications = drug['contraindications'][:120]
                                summary_parts.append(f"       ⚠️  Contraindications: {contraindications}...")

                            # Check for allergy warnings
                            if allergies:
                                allergy_lower = allergies.lower()
                                drug_name_lower = drug['drug_name'].lower()
                                contraind_lower = drug.get('contraindications', '').lower()

                                # Check for allergy matches
                                if ('penicillin' in allergy_lower and
                                    any(x in drug_name_lower for x in ['penicillin', 'amoxicillin', 'ampicillin'])):
                                    summary_parts.append(f"       🚨 ALLERGY WARNING: Patient allergic to penicillin - DO NOT PRESCRIBE")
                                elif ('nsaid' in allergy_lower and
                                      any(x in drug_name_lower for x in ['ibuprofen', 'aspirin', 'diclofenac'])):
                                    summary_parts.append(f"       🚨 ALLERGY WARNING: Patient allergic to NSAIDs - DO NOT PRESCRIBE")
                                elif allergy_lower in contraind_lower:
                                    summary_parts.append(f"       🚨 ALLERGY WARNING: Check contraindications for {allergies}")
        else:
            summary_parts.append(f"\n🔍 No structured diagnoses and treatment options identified")

        # BNF Prescribing Guidance
        if bnf_prescribing_guidance:
            summary_parts.append(f"\n💊 BNF PRESCRIBING GUIDANCE ({len(bnf_prescribing_guidance)}):")
            for idx, guidance in enumerate(bnf_prescribing_guidance, 1):
                summary_parts.append(f"\n{'='*70}")
                summary_parts.append(f"CONDITION {idx}: {guidance['condition']}")
                summary_parts.append(f"{'='*70}")
                summary_parts.append(f"Source: {guidance['source']}")
                summary_parts.append(f"BNF URL: {guidance['source_url']}")
                if guidance.get('severity_assessment'):
                    summary_parts.append(f"Severity Assessment: {guidance['severity_assessment']}")

                if guidance.get('first_line_treatments'):
                    summary_parts.append(f"\nFIRST-LINE TREATMENTS:")
                    for treatment in guidance['first_line_treatments']:
                        summary_parts.append(f"\n  • {treatment['medication']}")
                        summary_parts.append(f"    Dose: {treatment.get('dose', 'Not specified')}")
                        summary_parts.append(f"    Route: {treatment.get('route', 'Not specified')}")
                        summary_parts.append(f"    Duration: {treatment.get('duration', 'Not specified')}")
                        if treatment.get('notes'):
                            summary_parts.append(f"    Notes: {treatment['notes']}")

                if guidance.get('alternative_treatments'):
                    summary_parts.append(f"\nALTERNATIVE TREATMENTS:")
                    for alt in guidance['alternative_treatments']:
                        summary_parts.append(f"\n  • {alt['medication']} ({alt.get('indication', 'Alternative option')})")
                        summary_parts.append(f"    Dose: {alt.get('dose', 'Not specified')}")
                        summary_parts.append(f"    Route: {alt.get('route', 'Not specified')}")
                        summary_parts.append(f"    Duration: {alt.get('duration', 'Not specified')}")
                        if alt.get('notes'):
                            summary_parts.append(f"    Notes: {alt['notes']}")

                if guidance.get('special_considerations'):
                    spec = guidance['special_considerations']
                    summary_parts.append(f"\nSPECIAL CONSIDERATIONS:")
                    if spec.get('renal_impairment'):
                        summary_parts.append(f"  Renal: {spec['renal_impairment']}")
                    if spec.get('elderly'):
                        summary_parts.append(f"  Elderly: {spec['elderly']}")
                    if spec.get('pregnancy'):
                        summary_parts.append(f"  Pregnancy: {spec['pregnancy']}")
                    if spec.get('drug_interactions'):
                        summary_parts.append(f"  Interactions: {spec['drug_interactions']}")

        # Drug-drug interaction warnings
        if drug_interactions:
            summary_parts.append(f"\n🚨 DRUG-DRUG INTERACTIONS DETECTED ({len(drug_interactions)}):")
            for interaction in drug_interactions:
                summary_parts.append(f"   • {interaction['new_drug']} ↔ {interaction['current_med']}")
                summary_parts.append(f"     {interaction['description']}")
            summary_parts.append("\n⚠️  CRITICAL: Review interactions before prescribing. Consider alternative medications or dosage adjustments.")

        summary_parts.append("\n⚕️  Recommendation: Review full guideline content and BNF medication details for evidence-based prescribing.")

        if allergies:
            summary_parts.append("⚠️  IMPORTANT: Always verify no contraindications related to patient allergies before prescribing.")

        if patient_info and patient_info.get('weight_kg'):
            summary_parts.append(f"💊 DOSING: Calculate doses based on patient weight ({patient_info['weight_kg']}kg) and age ({patient_info.get('age')})")

        return '\n'.join(summary_parts)

    async def _validate_clinical_input(
        self,
        clinical_scenario: str,
        verbose: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that the input is actually a clinical consultation.

        Uses Claude to check if the text represents a genuine clinical scenario
        (symptoms, patient presentation, clinical consultation) or if it's off-topic.

        Args:
            clinical_scenario: The text to validate
            verbose: Whether to print validation result

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if this is a clinical consultation, False otherwise
            - error_message: None if valid, error description if invalid
        """
        if not self.anthropic:
            # Skip validation if no Anthropic client
            return (True, None)

        try:
            # Use Claude to validate the input
            validation_prompt = f"""You are a medical consultation validator. Your job is to determine if the following text represents a genuine clinical consultation or medical scenario.

TEXT TO VALIDATE:
{clinical_scenario}

VALID clinical consultations include:
- Patient symptoms and complaints (e.g., "Patient with fever and cough")
- Clinical presentations (e.g., "3-year-old with barking cough and stridor")
- Medical history and examination findings
- Requests for clinical decision support or treatment guidance
- Diagnostic scenarios

INVALID inputs include:
- Random statements unrelated to medicine (e.g., "I am feeling autistic", "What's the weather")
- General questions not about a specific patient case
- Non-medical topics
- Personal statements that aren't medical consultations
- Test inputs or nonsense text

Respond with ONLY a JSON object:
{{
  "is_valid": true/false,
  "reason": "brief explanation of why this is or isn't a clinical consultation"
}}

Do not include any other text besides the JSON object."""

            message = self.anthropic.messages.create(
                model="claude-haiku-4-5",
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": validation_prompt
                }]
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

            # Find JSON object
            if "{" in response_text and "}" in response_text:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                response_text = response_text[json_start:json_end]

            validation_result = json.loads(response_text)

            is_valid = validation_result.get('is_valid', False)
            reason = validation_result.get('reason', 'No reason provided')

            if verbose:
                if is_valid:
                    print(f"✅ Input validation: VALID - {reason}")
                else:
                    print(f"❌ Input validation: INVALID - {reason}")

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
            # If validation fails for any reason, allow processing to continue
            # (fail open rather than closed)
            if verbose:
                print(f"⚠️  Input validation error: {str(e)} - allowing processing to continue")
            return (True, None)

    async def clinical_decision_support(
        self,
        clinical_scenario: str,
        patient_id: Optional[str] = None,
        patient_age: Optional[str] = None,
        allergies: Optional[str] = None,
        location_override: Optional[str] = None,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Streamlined clinical decision support workflow.

        New architecture:
        1. LLM Call 1 WITH TOOLS: Claude analyzes consultation, searches guidelines using MCP tools,
           outputs structured diagnoses + drug names
        2. Direct BNF parsing: search_bnf_drug() → get_bnf_drug_info() → structured data
        3. No second LLM call needed (BNF pages have consistent structure)

        Benefits:
        - Faster: Only 1 LLM call instead of 2-3
        - Cheaper: Saves tokens on additional LLM calls
        - More reliable: Deterministic BNF parsing vs LLM extraction
        - Smarter: Claude chooses which tools to use dynamically

        Args:
            clinical_scenario: Patient case description
            patient_id: Optional patient ID (not used in streamlined version)
            patient_age: Optional patient age (not used in streamlined version)
            allergies: Optional known allergies (not used in streamlined version)
            location_override: Optional country code override (not used in streamlined version)
            verbose: Whether to print workflow steps

        Returns:
            Dictionary with diagnoses (including treatments, drug names, BNF info) and summary
        """
        # Step 0: Validate input is a clinical consultation
        is_valid, error_message = await self._validate_clinical_input(clinical_scenario, verbose=verbose)

        if not is_valid:
            # Return error response indicating invalid input
            return {
                'error': 'invalid_input',
                'error_message': error_message,
                'diagnoses': [],
                'bnf_prescribing_guidance': [],
                'guidelines_searched': [],
                'summary': error_message
            }

        if verbose:
            print("\n" + "="*70)
            print("🏥 STREAMLINED CLINICAL DECISION SUPPORT")
            print("="*70)
            print(f"Consultation: {clinical_scenario[:100]}...")
            print("="*70)

        # Step 1: Claude analyzes consultation WITH TOOLS
        if verbose:
            print("\n🤖 Step 1: Analyzing consultation with Claude (with tools)...")

        # Get all available tools from MCP servers
        tools = await self.get_all_tools_for_claude()

        if verbose:
            print(f"   Available tools: {len(tools)} tools from MCP servers")
            # Show relevant search tools
            relevant_tools = [t['name'] for t in tools if 'search' in t['name'].lower() or 'nice' in t['name'].lower() or 'bnf' in t['name'].lower()]
            print(f"   Relevant tools: {', '.join(relevant_tools[:8])}")

        # Build prompt for Claude
        prompt = f"""Analyze this clinical consultation and provide structured diagnosis and treatment information.

CONSULTATION: {clinical_scenario}

TASK:
1. Use the available tools to search for relevant clinical guidelines and treatment information
2. Based on the consultation and evidence found, identify:
   - The diagnosis (with confidence level: high/medium/low)
   - The source guideline (e.g., "NICE NG138", "BTS/SIGN Asthma Guideline")
   - The guideline URL (if available from your tool searches)
   - Appropriate treatments
   - Specific drug names mentioned or recommended (use generic names, e.g., "Amoxicillin" not "Amoxil")

Return your final answer as JSON ONLY (no other text):

{{
  "diagnoses": [
    {{
      "diagnosis": "medical condition name",
      "confidence": "high|medium|low",
      "source": "guideline name (e.g., NICE NG138)",
      "url": "full guideline URL if available from tools, otherwise empty string",
      "treatments": [
        {{
          "name": "treatment description",
          "drug_names": ["generic drug name 1", "generic drug name 2"],
          "notes": "any relevant clinical notes from guidelines"
        }}
      ]
    }}
  ]
}}"""

        # Call Claude with tools
        messages = [{"role": "user", "content": prompt}]
        diagnoses = []

        try:
            # Initial call to Claude
            response = self.anthropic.messages.create(
                model="claude-haiku-4-5",
                max_tokens=4096,
                tools=tools,
                messages=messages
            )

            if verbose:
                print(f"   Stop reason: {response.stop_reason}")

            # Tool use loop
            while response.stop_reason == "tool_use":
                # Execute tools
                tool_results = []
                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_name = content_block.name
                        tool_input = content_block.input

                        if verbose:
                            print(f"   🔧 Calling tool: {tool_name}({tool_input})")

                        # Call the MCP tool
                        result = await self.call_tool(tool_name, tool_input)
                        result_text = result.content[0].text

                        if verbose:
                            # Parse and show summary
                            try:
                                data = json.loads(result_text)
                                if 'results' in data:
                                    print(f"      → Found {len(data['results'])} results")
                            except:
                                pass

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": result_text
                        })

                # Add assistant response and tool results to conversation
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

                # Continue conversation
                response = self.anthropic.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=4096,
                    tools=tools,
                    messages=messages
                )

                if verbose:
                    print(f"   Stop reason: {response.stop_reason}")

            # Extract final JSON response
            for block in response.content:
                if hasattr(block, 'text'):
                    try:
                        # Try direct JSON parse
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
                print(f"\n   ✓ Extracted {len(diagnoses)} diagnoses")
                for d in diagnoses:
                    print(f"      • {d.get('diagnosis')} ({d.get('confidence')} confidence)")
                    for tx in d.get('treatments', []):
                        drugs = ', '.join(tx.get('drug_names', []))
                        print(f"        - {tx.get('name')}: {drugs}")

        except Exception as e:
            if verbose:
                print(f"   ⚠️  Error: {e}")
                import traceback
                traceback.print_exc()
            diagnoses = []

        # Step 2: Get BNF drug information (direct parsing, no LLM)
        if verbose:
            print(f"\n💊 Step 2: Fetching BNF drug information...")

        # Extract all drug names
        all_drugs = []
        for diag in diagnoses:
            for tx in diag.get('treatments', []):
                all_drugs.extend(tx.get('drug_names', []))

        # Remove duplicates
        all_drugs = list(set(all_drugs))

        # Search BNF and get detailed info for each drug
        async def get_drug_details(drug_name):
            try:
                # Step 2a: Search for drug
                if verbose:
                    print(f"   🔍 Searching BNF for: {drug_name}")

                search_result = await self.call_tool("search_bnf_drug", {
                    "drug_name": drug_name
                })
                search_data = json.loads(search_result.content[0].text)
                results = search_data.get('results', [])

                if not results:
                    if verbose:
                        print(f"      ⚠️  No BNF page found for {drug_name}")
                    return None

                drug_url = results[0].get('url')
                if verbose:
                    print(f"      ✓ Found: {drug_url}")

                # Step 2b: Get detailed drug info
                if verbose:
                    print(f"   📄 Fetching detailed info for: {drug_name}")

                info_result = await self.call_tool("get_bnf_drug_info", {
                    "drug_url": drug_url
                })
                info_data = json.loads(info_result.content[0].text)

                if info_data.get('success'):
                    if verbose:
                        print(f"      ✓ Retrieved structured data")
                    return {
                        'drug_name': drug_name,
                        'url': drug_url,
                        'bnf_data': info_data
                    }
                else:
                    if verbose:
                        print(f"      ⚠️  Failed to parse: {info_data.get('error')}")
                    return None

            except Exception as e:
                if verbose:
                    print(f"   ⚠️  Error with {drug_name}: {e}")
                return None

        drug_details = []
        if all_drugs:
            if verbose:
                print(f"   Found {len(all_drugs)} drugs to look up: {', '.join(all_drugs)}\n")

            # Get details for all drugs in parallel
            results = await asyncio.gather(
                *[get_drug_details(drug) for drug in all_drugs],
                return_exceptions=True
            )

            for result in results:
                if result and not isinstance(result, Exception):
                    drug_details.append(result)

        # Step 3: Add BNF data to diagnoses
        if verbose:
            print(f"\n📋 Step 3: Adding BNF data to diagnoses...")

        # Create lookup dict
        drug_lookup = {d['drug_name']: d for d in drug_details}

        for diag in diagnoses:
            for tx in diag.get('treatments', []):
                tx['bnf_info'] = {}

                for drug_name in tx.get('drug_names', []):
                    if drug_name in drug_lookup:
                        details = drug_lookup[drug_name]
                        bnf_data = details['bnf_data']

                        tx['bnf_info'][drug_name] = {
                            'url': details['url'],
                            'indications': bnf_data.get('indications', 'Not available'),
                            'dosage': bnf_data.get('dosage', 'Not available'),
                            'contraindications': bnf_data.get('contraindications', 'Not available'),
                            'cautions': bnf_data.get('cautions', 'Not available'),
                            'side_effects': bnf_data.get('side_effects', 'Not available'),
                            'interactions': bnf_data.get('interactions', 'Not available'),
                        }

                        if verbose:
                            print(f"   ✓ Added BNF data for: {drug_name}")

        # Step 4: Generate summary
        if verbose:
            print(f"\n📄 Step 4: Generating summary...")

        summary = f"""
CLINICAL DECISION SUPPORT REPORT

DIAGNOSES ({len(diagnoses)}):
"""
        for diag in diagnoses:
            summary += f"\n• {diag.get('diagnosis')} ({diag.get('confidence')} confidence)"
            for tx in diag.get('treatments', []):
                summary += f"\n  Treatment: {tx.get('name')}"

                if tx.get('notes'):
                    summary += f"\n  Notes: {tx.get('notes')}"

                # Add BNF info for each drug
                for drug_name in tx.get('drug_names', []):
                    bnf_info = tx.get('bnf_info', {}).get(drug_name)
                    if bnf_info:
                        summary += f"\n\n  Drug: {drug_name}"
                        summary += f"\n  BNF: {bnf_info['url']}"
                        summary += f"\n  Dosage: {bnf_info['dosage'][:200]}..." if len(bnf_info['dosage']) > 200 else f"\n  Dosage: {bnf_info['dosage']}"
                        summary += f"\n  Contraindications: {bnf_info['contraindications'][:200]}..." if len(bnf_info['contraindications']) > 200 else f"\n  Contraindications: {bnf_info['contraindications']}"

                        if bnf_info['interactions'] and bnf_info['interactions'] != 'Not available':
                            summary += f"\n  Interactions: {bnf_info['interactions'][:200]}..." if len(bnf_info['interactions']) > 200 else f"\n  Interactions: {bnf_info['interactions']}"

        if not diagnoses:
            summary += "\nNo diagnoses identified."

        # Build bnf_prescribing_guidance array for frontend compatibility
        # Extract BNF data from diagnoses and restructure it
        bnf_prescribing_guidance = []
        for diag in diagnoses:
            for tx in diag.get('treatments', []):
                bnf_info = tx.get('bnf_info', {})
                for drug_name, drug_data in bnf_info.items():
                    # Create a medication entry in the format the frontend expects
                    medication_entry = {
                        'medication': drug_name,
                        'url': drug_data.get('url', ''),
                        'indications': drug_data.get('indications', ''),
                        'dosage': drug_data.get('dosage', ''),
                        'contraindications': drug_data.get('contraindications', ''),
                        'cautions': drug_data.get('cautions', ''),
                        'side_effects': drug_data.get('side_effects', ''),
                        'interactions': drug_data.get('interactions', ''),
                        'is_first_line': True,  # Mark as first-line if it's in the primary treatment
                        'treatment_context': tx.get('name', '')  # Include treatment context
                    }
                    bnf_prescribing_guidance.append(medication_entry)

        result = {
            'diagnoses': diagnoses,
            'summary': summary,
            'bnf_prescribing_guidance': bnf_prescribing_guidance
        }

        if verbose:
            print("\n" + "="*70)
            print("✅ STREAMLINED ANALYSIS COMPLETE")
            print("="*70)
            print(f"Diagnoses: {len(diagnoses)}")
            print("="*70)

        return result

    async def clinical_decision_support_old(
        self,
        clinical_scenario: str,
        patient_id: Optional[str] = None,
        patient_age: Optional[str] = None,
        allergies: Optional[str] = None,
        location_override: Optional[str] = None,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Orchestrate clinical decision support workflow.

        Workflow:
        0. Retrieve patient information and seasonal context
        1. Determine location (auto-detect or override)
        2. Search guidelines by region (NICE/FOGSI/PubMed)
        3. Extract possible diagnoses and treatment options from guidelines
        3b. Look up medications in BNF for each treatment option
        4. Check drug-drug interactions with current medications
        5. Generate comprehensive recommendations with patient context

        Args:
            clinical_scenario: Patient case description
            patient_id: Optional patient ID to retrieve full patient information
            patient_age: Optional patient age (overrides patient_id age)
            allergies: Optional known allergies (overrides patient_id allergies)
            location_override: Optional country code override (e.g., "GB")
            verbose: Whether to print workflow steps

        Returns:
            Dictionary with patient info, location, guidelines, diagnoses (with treatments and medications), and summary
        """
        if verbose:
            print("\n" + "="*70)
            print("🏥 CLINICAL DECISION SUPPORT WORKFLOW")
            print("="*70)

        # Step 0: Retrieve patient information and seasonal context
        patient_info, seasonal_context, patient_age, allergies = await self._get_patient_info_and_season(
            patient_id, patient_age, allergies, verbose
        )

        # Step 1: Determine location
        location_info = await self._determine_location(location_override, verbose)

        # Step 1.5: Extract key medical conditions from consultation for focused searching
        search_terms = clinical_scenario  # Default to full text
        if self.anthropic:
            search_terms = await self._extract_search_terms(clinical_scenario, verbose)

        # Step 2: Search guidelines by region
        guidelines, cks_topics, bnf_summaries, pubmed_articles = await self._search_guidelines_by_region(
            location_info, search_terms, verbose
        )

        # Step 3: Fetch guideline details and analyze with Claude
        if verbose:
            print(f"\n🔍 Step 3: Using AI agent to analyze clinical scenario and extract diagnoses/treatments...")

        diagnoses = []
        bnf_prescribing_guidance = []

        # Fetch detailed content in parallel
        guideline_contents, cks_contents, bnf_summary_contents = await self._fetch_guideline_details(
            guidelines, cks_topics, bnf_summaries, verbose
        )

        # Use Claude to analyze guidelines
        total_guideline_resources = len(guideline_contents) + len(cks_contents)
        if total_guideline_resources > 0 and self.anthropic:
            if verbose:
                print(f"\n   🤖 Analyzing {total_guideline_resources} guideline(s) with Claude...")

            diagnoses = await self._analyze_guidelines_with_claude(
                clinical_scenario=clinical_scenario,
                patient_info=patient_info,
                guideline_contents=guideline_contents,
                cks_contents=cks_contents,
                location_info=location_info,
                verbose=verbose
            )
        elif not self.anthropic:
            if verbose:
                print(f"   ⚠️  Anthropic API key not configured - skipping AI analysis")

        # Analyze BNF treatment summaries separately for prescribing guidance
        if bnf_summary_contents and self.anthropic:
            if verbose:
                print(f"\n   💊 Analyzing {len(bnf_summary_contents)} BNF treatment summar{'y' if len(bnf_summary_contents) == 1 else 'ies'} for prescribing guidance...")

            bnf_prescribing_guidance = await self._analyze_bnf_summaries_with_claude(
                clinical_scenario=clinical_scenario,
                patient_info=patient_info,
                diagnoses=diagnoses,
                bnf_summary_contents=bnf_summary_contents,
                verbose=verbose
            )

        # Step 3b: Get BNF details for all medications mentioned in treatments (parallelized)
        if diagnoses:
            if verbose:
                print(f"\n💊 Step 3b: Retrieving BNF medication details for treatment options (parallel)...")

            # Helper function to fetch drug info
            async def fetch_drug_info(med_name, diagnosis_name, treatment_name):
                try:
                    # Search for the drug in BNF
                    search_result = await self.call_tool("search_bnf_drug", {
                        "drug_name": med_name
                    })
                    search_data = json.loads(search_result.content[0].text)

                    if search_data.get('success') and search_data.get('results'):
                        drug_url = search_data['results'][0]['url']

                        # Get detailed drug information
                        info_result = await self.call_tool("get_bnf_drug_info", {
                            "drug_url": drug_url
                        })
                        drug_info = json.loads(info_result.content[0].text)

                        if drug_info.get('success'):
                            return {
                                'diagnosis': diagnosis_name,
                                'treatment': treatment_name,
                                'drug_info': drug_info,
                                'success': True
                            }
                    return {'success': False, 'med_name': med_name}
                except:
                    return {'success': False, 'med_name': med_name}

            # Collect all medication lookup tasks
            med_tasks = []
            for diagnosis in diagnoses:
                for treatment in diagnosis['treatments']:
                    medication_names = treatment.get('medication_names', [])
                    if medication_names:
                        for med_name in medication_names[:3]:  # Limit to 3 meds per treatment
                            med_tasks.append(fetch_drug_info(
                                med_name,
                                diagnosis['diagnosis'],
                                treatment['treatment_name']
                            ))

            # Execute all medication lookups in parallel
            if med_tasks:
                med_results = await asyncio.gather(*med_tasks, return_exceptions=True)

                # Process results and assign to correct treatments
                for result in med_results:
                    if isinstance(result, Exception):
                        continue
                    if result.get('success'):
                        # Find the correct treatment and append drug info
                        for diagnosis in diagnoses:
                            if diagnosis['diagnosis'] == result['diagnosis']:
                                for treatment in diagnosis['treatments']:
                                    if treatment['treatment_name'] == result['treatment']:
                                        treatment['medications_detailed'].append(result['drug_info'])
                                        if verbose:
                                            print(f"      ✓ {result['drug_info']['drug_name']}")
                                        break
                                break
                    elif verbose and 'med_name' in result:
                        print(f"      ✗ {result['med_name']} - BNF lookup failed")
        else:
            if verbose:
                print(f"   No diagnoses with treatment options identified")

        # Step 4: Check for drug-drug interactions with current medications
        drug_interactions = []
        all_medications = []

        # Collect all medications from all diagnoses/treatments
        for diagnosis in diagnoses:
            for treatment in diagnosis['treatments']:
                all_medications.extend(treatment.get('medications_detailed', []))

        if patient_info and patient_info.get('current_medications') and all_medications:
            if verbose:
                print(f"\n💊 Step 4: Checking drug-drug interactions...")

            for current_med in patient_info['current_medications']:
                # Extract medication name (remove dosage)
                med_name = current_med.split()[0].lower()

                for new_drug in all_medications:
                    try:
                        interaction_result = await self.call_tool("get_bnf_drug_interactions", {
                            "drug_name": new_drug['drug_name']
                        })
                        interaction_data = json.loads(interaction_result.content[0].text)

                        if interaction_data.get('success') and interaction_data.get('interactions'):
                            # Check if current medication appears in interactions
                            for interaction in interaction_data['interactions']:
                                if med_name in interaction.get('interacting_drug', '').lower():
                                    drug_interactions.append({
                                        'new_drug': new_drug['drug_name'],
                                        'current_med': current_med,
                                        'description': interaction.get('description', 'Interaction detected')
                                    })
                                    if verbose:
                                        print(f"   ⚠️  Interaction: {new_drug['drug_name']} ↔ {current_med}")
                    except:
                        pass

        # Step 5: Generate summary
        summary = await self._generate_summary(
            patient_info=patient_info,
            patient_age=patient_age,
            allergies=allergies,
            seasonal_context=seasonal_context,
            location_info=location_info,
            guidelines=guidelines,
            cks_topics=cks_topics,
            bnf_summaries=bnf_summaries,
            pubmed_articles=pubmed_articles,
            diagnoses=diagnoses,
            bnf_prescribing_guidance=bnf_prescribing_guidance,
            drug_interactions=drug_interactions,
            verbose=verbose
        )

        result = {
            'patient_info': patient_info,
            'seasonal_context': seasonal_context,
            'location': location_info,
            'clinical_scenario': clinical_scenario,
            'patient_age': patient_age,
            'allergies': allergies,
            'guidelines_found': guidelines,
            'cks_topics': cks_topics,
            'bnf_summaries': bnf_summaries,
            'bnf_prescribing_guidance': bnf_prescribing_guidance,
            'pubmed_articles': pubmed_articles,
            'diagnoses': diagnoses,
            'drug_interactions': drug_interactions,
            'summary': summary
        }

        if verbose:
            print("\n" + "="*70)
            print("SUMMARY")
            print("="*70)
            print(result['summary'])
            print("="*70)

        return result

    async def _analyze_guidelines_with_claude(
        self,
        clinical_scenario: str,
        patient_info: Optional[dict],
        guideline_contents: List[dict],
        cks_contents: List[dict],
        location_info: Optional[dict],
        verbose: bool = True
    ) -> List[dict]:
        """
        Use Claude to analyze clinical scenario and guidelines to extract structured diagnoses and treatments.

        Args:
            clinical_scenario: Patient case description
            patient_info: Patient information dictionary
            guideline_contents: List of NICE guideline contents
            cks_contents: List of CKS guideline contents
            location_info: User location information (country, country_code)
            verbose: Whether to print progress

        Returns:
            List of diagnosis dictionaries with treatments and medications
        """
        if not self.anthropic:
            return []

        # Build context for Claude
        location_context = ""
        if location_info:
            location_context = f"""
User Location:
- Country: {location_info.get('country')} ({location_info.get('country_code')})
- Healthcare System: {'NHS (UK)' if location_info.get('country_code') == 'GB' else 'International'}
"""

        patient_context = ""
        if patient_info and patient_info.get('success'):
            patient_context = f"""
Patient Information:
- Age: {patient_info.get('age')}
- Gender: {patient_info.get('gender')}
- Weight: {patient_info.get('weight_kg')}kg
- Current medications: {', '.join(patient_info.get('current_medications', [])) or 'None'}
- Existing conditions: {', '.join(patient_info.get('existing_conditions', [])) or 'None'}
- Allergies: {', '.join(patient_info.get('allergies', [])) or 'None'}
"""

        # Build guidelines context - combine both NICE guidelines and CKS
        guidelines_context = ""
        guideline_num = 1

        # Add guidelines (NICE or FOGSI)
        for guideline in guideline_contents:
            # Check if this is a NICE guideline (has 'reference') or FOGSI guideline
            if 'reference' in guideline:
                # NICE guideline
                guidelines_context += f"""
--- Guideline {guideline_num}: {guideline['reference']} - {guideline['title']} ---
URL: {guideline['url']}
Published: {guideline['published_date']}
Overview: {guideline['overview'][:1000]}

Sections:
"""
                for section in guideline['sections'][:5]:  # Limit to first 5 sections
                    # sections are strings (section titles), not dictionaries
                    guidelines_context += f"  • {section}\n"
            else:
                # FOGSI guideline
                guidelines_context += f"""
--- Guideline {guideline_num}: {guideline['title']} ---
URL: {guideline['url']}
Category: {guideline.get('category', 'General')}
Overview: {guideline['overview'][:1000]}

Content Summary:
{guideline.get('content', '')[:2000]}

Sections:
"""
                for section in guideline['sections'][:5]:  # Limit to first 5 sections
                    if isinstance(section, dict):
                        guidelines_context += f"  • {section.get('heading', 'Section')}\n"
                    else:
                        guidelines_context += f"  • {section}\n"

            guidelines_context += "\n"
            guideline_num += 1

        # Add CKS guidelines
        for cks in cks_contents:
            guidelines_context += f"""
--- Guideline {guideline_num}: CKS - {cks['title']} ---
URL: {cks['url']}
Summary: {cks['summary']}

Management: {cks['management'][:1000]}

Prescribing: {cks['prescribing'][:1000]}

"""
            guideline_num += 1

        # Create the prompt for Claude
        prompt = f"""You are a clinical decision support AI assistant analyzing medical guidelines for a patient case.

Clinical Scenario:
{clinical_scenario}

{location_context}{patient_context}

Available NICE Guidelines and Clinical Knowledge Summaries:
{guidelines_context}

Based on the clinical scenario and the available guidelines above, identify possible diagnoses and treatment options.

CRITICAL: You MUST respond with valid JSON only. Even if information is limited, return valid JSON format with empty arrays if needed.

Return your analysis in the following JSON format:
{{
  "diagnoses": [
    {{
      "diagnosis": "Diagnosis name (e.g., Community-Acquired Pneumonia)",
      "source": "NICE guideline reference or CKS",
      "guideline_url": "URL from above - MUST match the specific guideline that supports THIS diagnosis",
      "summary": "Brief clinical summary based on scenario and patient info",
      "confidence": "high|medium|low",
      "treatments": [
        {{
          "treatment_name": "Treatment approach (e.g., Antibiotic Therapy, Oxygen Therapy)",
          "description": "Brief description",
          "medication_names": ["medication1", "medication2"],
          "notes": "Important notes"
        }}
      ]
    }}
  ]
}}

Instructions:
- ALWAYS return valid JSON, never plain text
- CRITICAL: For each diagnosis, use the guideline_url from the SPECIFIC guideline that supports that diagnosis. Do not mix up URLs between different diagnoses.
- If guidelines lack specific details, infer reasonable diagnoses from the clinical scenario
- For the scenario "{clinical_scenario}", identify the most likely diagnosis even if full guideline content is not available
- Include treatment approaches that are standard for the identified condition
- Use confidence level "medium" or "low" if inferring from limited information
- Extract medication names when mentioned in the guidelines
- If no specific medications found in guidelines, leave medication_names as empty array
- Order diagnoses by clinical relevance to the scenario"""

        try:
            # Call Claude API
            message = self.anthropic.messages.create(
                model="claude-haiku-4-5",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse Claude's response
            response_text = message.content[0].text

            if verbose:
                print(f"      Claude response preview: {response_text[:200]}...")

            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            # If still no JSON markers found, try to find JSON object directly
            if "{" in response_text and "}" in response_text:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                response_text = response_text[json_start:json_end]

            analysis = json.loads(response_text)

            # Convert to our internal format
            diagnoses = []
            for diag in analysis.get('diagnoses', []):
                diagnosis_entry = {
                    'diagnosis': diag['diagnosis'],
                    'summary': diag.get('summary', ''),
                    'source': diag.get('source', 'NICE CKS'),
                    'url': diag.get('guideline_url', ''),
                    'confidence': diag.get('confidence', 'medium'),
                    'treatments': []
                }

                for treatment in diag.get('treatments', []):
                    treatment_entry = {
                        'treatment_name': treatment['treatment_name'],
                        'description': treatment.get('description', ''),
                        'medication_names': treatment.get('medication_names', []),
                        'medications_detailed': [],  # Will be filled with BNF data
                        'notes': treatment.get('notes', '')
                    }
                    diagnosis_entry['treatments'].append(treatment_entry)

                diagnoses.append(diagnosis_entry)

            if verbose:
                print(f"      ✓ Claude identified {len(diagnoses)} relevant diagnosis/diagnoses")
                for diag in diagnoses:
                    total_meds = sum(len(t.get('medication_names', [])) for t in diag['treatments'])
                    print(f"        • {diag['diagnosis']}: {len(diag['treatments'])} treatment(s), {total_meds} medication(s)")

            return diagnoses

        except Exception as e:
            error_msg = str(e)
            if verbose:
                print(f"      ✗ Claude analysis failed: {error_msg}")

            # Check if this is a credit/billing error - FATAL
            if "credit balance is too low" in error_msg.lower() or "insufficient_quota" in error_msg.lower():
                raise RuntimeError(
                    f"❌ FATAL ERROR: Anthropic API credits exhausted!\n\n"
                    f"Error: {error_msg}\n\n"
                    f"Please add credits at: https://console.anthropic.com/settings/billing\n"
                    f"The application cannot continue without API access."
                ) from e

            return []

    async def _analyze_bnf_summaries_with_claude(
        self,
        clinical_scenario: str,
        patient_info: Optional[dict],
        diagnoses: List[dict],
        bnf_summary_contents: List[dict],
        verbose: bool = True
    ) -> List[dict]:
        """
        Use Claude to analyze BNF treatment summaries and extract specific prescribing guidance.

        Args:
            clinical_scenario: Patient case description
            patient_info: Patient information dictionary
            diagnoses: List of diagnoses from previous guideline analysis
            bnf_summary_contents: List of BNF treatment summary contents
            verbose: Whether to print progress

        Returns:
            List of prescribing guidance dictionaries with first-line treatments, alternatives, dosing
        """
        if not self.anthropic:
            return []

        # Build context for Claude
        patient_context = ""
        if patient_info and patient_info.get('success'):
            patient_context = f"""
Patient Information:
- Age: {patient_info.get('age')}
- Gender: {patient_info.get('gender')}
- Weight: {patient_info.get('weight_kg')}kg
- Current medications: {', '.join(patient_info.get('current_medications', [])) or 'None'}
- Existing conditions: {', '.join(patient_info.get('existing_conditions', [])) or 'None'}
- Allergies: {', '.join(patient_info.get('allergies', [])) or 'None'}
"""

        # Build diagnoses context
        diagnoses_context = ""
        if diagnoses:
            diagnoses_context = "\nPreviously identified diagnoses:\n"
            for diag in diagnoses:
                diagnoses_context += f"- {diag['diagnosis']}\n"

        # Build BNF summaries context
        bnf_context = ""
        for idx, bnf in enumerate(bnf_summary_contents, 1):
            bnf_context += f"""
--- BNF Treatment Summary {idx}: {bnf['title']} ---
URL: {bnf['url']}
Summary: {bnf['summary'][:1000]}

Treatment Recommendations:
"""
            for section in bnf['sections'][:10]:  # Include more sections for prescribing details
                bnf_context += f"\n{section.get('heading', 'Untitled')}:\n"
                if section.get('content'):
                    bnf_context += f"{section['content'][:1000]}\n"

            bnf_context += "\n"

        # Create the prompt for Claude
        prompt = f"""You are a clinical pharmacist analyzing BNF treatment summaries to provide evidence-based prescribing guidance.

Clinical Scenario:
{clinical_scenario}

{patient_context}{diagnoses_context}

Available BNF Treatment Summaries:
{bnf_context}

Based on the clinical scenario, patient information, and BNF treatment summaries, extract specific prescribing recommendations in the following JSON format:

{{
  "prescribing_guidance": [
    {{
      "condition": "Condition or indication from BNF",
      "source": "BNF Treatment Summary title",
      "source_url": "BNF URL",
      "severity_assessment": "Assessment criteria if mentioned (e.g., CURB-65)",
      "first_line_treatments": [
        {{
          "medication": "Generic medication name",
          "bnf_url": "BNF URL for this specific drug (e.g., https://bnf.nice.org.uk/drugs/amoxicillin/)",
          "dose": "Specific dosing (e.g., 500mg every 8 hours)",
          "route": "Route of administration (e.g., oral, IV)",
          "duration": "Treatment duration (e.g., 5 days, 7-10 days)",
          "notes": "Additional notes or indications",
          "drug_interactions": "Interactions with current patient medications: {', '.join(patient_info.get('current_medications', [])) if patient_info else 'None'}"
        }}
      ],
      "alternative_treatments": [
        {{
          "indication": "When to use (e.g., penicillin allergy, severe infection)",
          "medication": "Alternative medication",
          "bnf_url": "BNF URL for this specific drug",
          "dose": "Dosing",
          "route": "Route",
          "duration": "Duration",
          "notes": "Notes",
          "drug_interactions": "Interactions with current patient medications"
        }}
      ],
      "special_considerations": {{
        "renal_impairment": "Dosing adjustments or contraindications",
        "hepatic_impairment": "Dosing adjustments or contraindications",
        "pregnancy": "Safety considerations",
        "elderly": "Special considerations for elderly patients"
      }}
    }}
  ]
}}

CRITICAL INSTRUCTIONS:
1. ALWAYS extract specific medication names from the BNF summaries
2. If BNF summaries mention conditions like "Community-acquired pneumonia", look for the medications listed under that section
3. BNF summaries typically list medications like "Amoxicillin", "Clarithromycin", "Doxycycline" etc. - EXTRACT THESE
4. If dosing details are in the summary, extract them. If not, use "Dosing to be determined" (NOT "Not specified")
5. NEVER return generic placeholders like "Treatment options mentioned but specific medications not provided"

For Dosing (when available):
- Extract ONLY the ADULT dose for the SPECIFIC condition being treated
- Dose must be concise: "500mg three times daily" NOT full dosing tables
- If multiple conditions mentioned, extract dose for the relevant condition only
- If paediatric and adult doses present, extract ONLY adult dose
- Example good: "500mg three times daily for 5 days"
- Example bad: Long paragraphs with every age group and condition

Other Requirements:
- ALWAYS populate medication names - this is MANDATORY
- Include first-line vs alternative treatment distinctions
- Note allergy alternatives (e.g., for penicillin allergy)
- Include routes (oral/IV) and durations when stated
- Generate BNF URL: https://bnf.nice.org.uk/drugs/[lowercase-drug-name-with-hyphens]/
- Check interactions with patient medications: {', '.join(patient_info.get('current_medications', [])) if patient_info else 'None'}

If BNF summary lacks dosing details, the medication will be enriched later from individual BNF drug pages.
- If no specific interactions mentioned in BNF, write "No specific interactions mentioned" for drug_interactions field
- Do NOT include drug_interactions in special_considerations - only include renal_impairment, hepatic_impairment, pregnancy, and elderly
- Focus on the most relevant treatments for the clinical scenario"""

        try:
            # Call Claude API
            message = self.anthropic.messages.create(
                model="claude-haiku-4-5",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse Claude's response
            response_text = message.content[0].text

            if verbose:
                print(f"      Claude response preview: {response_text[:200]}...")

            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            # If still no JSON markers found, try to find JSON object directly
            if "{" in response_text and "}" in response_text:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                response_text = response_text[json_start:json_end]

            analysis = json.loads(response_text)

            prescribing_guidance = analysis.get('prescribing_guidance', [])

            if verbose:
                print(f"      ✓ Claude extracted {len(prescribing_guidance)} prescribing recommendation(s)")
                for guidance in prescribing_guidance:
                    first_line_count = len(guidance.get('first_line_treatments', []))
                    alt_count = len(guidance.get('alternative_treatments', []))
                    print(f"        • {guidance['condition']}: {first_line_count} first-line, {alt_count} alternative treatment(s)")

            # Enrich medications that are missing dosing details
            prescribing_guidance = await self._enrich_missing_drug_details(
                prescribing_guidance,
                verbose=verbose
            )

            return prescribing_guidance

        except Exception as e:
            error_msg = str(e)
            if verbose:
                print(f"      ✗ BNF analysis failed: {error_msg}")

            # Check if this is a credit/billing error - FATAL
            if "credit balance is too low" in error_msg.lower() or "insufficient_quota" in error_msg.lower():
                raise RuntimeError(
                    f"❌ FATAL ERROR: Anthropic API credits exhausted!\n\n"
                    f"Error: {error_msg}\n\n"
                    f"Please add credits at: https://console.anthropic.com/settings/billing\n"
                    f"The application cannot continue without API access."
                ) from e

            return []

    async def _enrich_missing_drug_details(
        self,
        prescribing_guidance: list,
        verbose: bool = False
    ) -> list:
        """
        Enrich medications that are missing dosing details by fetching from BNF drug pages.
        Only fetches details for medications with missing/placeholder information.

        Args:
            prescribing_guidance: List of prescribing guidance from Claude
            verbose: Whether to print progress

        Returns:
            Enriched prescribing guidance with complete drug information
        """
        if not prescribing_guidance or not self.anthropic:
            return prescribing_guidance

        for guidance in prescribing_guidance:
            condition = guidance.get('condition', '')

            # Check first-line treatments
            for treatment in guidance.get('first_line_treatments', []):
                if self._needs_enrichment(treatment):
                    await self._fetch_and_enrich_drug(treatment, condition, verbose)

            # Check alternative treatments
            for treatment in guidance.get('alternative_treatments', []):
                if self._needs_enrichment(treatment):
                    await self._fetch_and_enrich_drug(treatment, condition, verbose)

            # Check special considerations
            special_considerations = guidance.get('special_considerations', {})
            if self._needs_special_considerations_enrichment(special_considerations):
                # Try to enrich from first drug mentioned
                first_drug = None
                if guidance.get('first_line_treatments'):
                    first_drug = guidance['first_line_treatments'][0].get('medication')

                if first_drug:
                    await self._fetch_special_considerations(
                        first_drug,
                        special_considerations,
                        verbose
                    )

        return prescribing_guidance

    def _needs_enrichment(self, treatment: dict) -> bool:
        """Check if a treatment needs enrichment."""
        dose = treatment.get('dose', '')
        route = treatment.get('route', '')

        # Check for missing or placeholder values
        missing_indicators = [
            'not specified',
            'not available',
            'treatment details not available',
            'cannot assess',
            'dosing to be determined',
            'to be determined'
        ]

        dose_lower = dose.lower() if dose else ''
        route_lower = route.lower() if route else ''

        # Needs enrichment if dose or route contains placeholder text or is very short
        return (
            not dose or
            not route or
            any(indicator in dose_lower for indicator in missing_indicators) or
            any(indicator in route_lower for indicator in missing_indicators) or
            len(dose) < 10
        )

    def _needs_special_considerations_enrichment(self, special_considerations: dict) -> bool:
        """Check if special considerations need enrichment."""
        if not special_considerations:
            return True

        missing_indicators = ['not specified', 'not available']

        for key in ['renal_impairment', 'hepatic_impairment', 'pregnancy', 'elderly']:
            value = special_considerations.get(key, '')
            if not value or any(indicator in value.lower() for indicator in missing_indicators):
                return True

        return False

    async def _fetch_and_enrich_drug(
        self,
        treatment: dict,
        condition: str,
        verbose: bool = False
    ):
        """Fetch detailed drug information and enrich the treatment."""
        medication_name = treatment.get('medication', '')
        if not medication_name:
            return

        try:
            if verbose:
                print(f"      📊 Enriching {medication_name} dosing from BNF drug page...")

            # Search for the drug
            search_result = await self.call_tool("search_bnf_drug", {
                "drug_name": medication_name
            })
            search_data = json.loads(search_result.content[0].text)

            if not search_data.get('success') or search_data.get('count', 0) == 0:
                if verbose:
                    print(f"         ⚠ Drug not found: {medication_name}")
                return

            # Get drug page
            drug_url = search_data['results'][0]['url']
            drug_info_result = await self.call_tool("get_bnf_drug_info", {
                "drug_url": drug_url
            })
            drug_info = json.loads(drug_info_result.content[0].text)

            if not drug_info.get('success'):
                if verbose:
                    print(f"         ⚠ Could not fetch drug info: {medication_name}")
                return

            # Extract relevant dosing using Claude
            dosage_text = drug_info.get('dosage', '')
            if dosage_text and len(dosage_text) > 50:
                prompt = f"""Extract the ADULT dosing for {medication_name} for treating {condition}.

BNF Dosage Information (first 2000 characters):
{dosage_text[:2000]}

Return ONLY a JSON object with these fields:
{{
  "dose": "concise adult dose (e.g., 500mg three times daily)",
  "route": "oral/intravenous/intramuscular",
  "duration": "treatment duration (e.g., 5-7 days)"
}}

Focus on: {condition}. Be concise. If not found, use most common adult dose."""

                response = self.anthropic.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=200,
                    messages=[{"role": "user", "content": prompt}]
                )

                response_text = response.content[0].text

                # Extract JSON
                if "{" in response_text and "}" in response_text:
                    json_start = response_text.find("{")
                    json_end = response_text.rfind("}") + 1
                    parsed = json.loads(response_text[json_start:json_end])

                    # Update only if we got better information
                    if parsed.get('dose') and len(parsed['dose']) > 5:
                        treatment['dose'] = parsed['dose']
                    if parsed.get('route'):
                        treatment['route'] = parsed['route']
                    if parsed.get('duration'):
                        treatment['duration'] = parsed['duration']

                    if verbose:
                        print(f"         ✓ {medication_name}: {parsed.get('dose', 'N/A')}")

        except Exception as e:
            error_msg = str(e)
            if verbose:
                print(f"         ✗ Error enriching {medication_name}: {error_msg}")

            # Check if this is a credit/billing error - FATAL
            if "credit balance is too low" in error_msg.lower() or "insufficient_quota" in error_msg.lower():
                raise RuntimeError(
                    f"❌ FATAL ERROR: Anthropic API credits exhausted!\n\n"
                    f"Error: {error_msg}\n\n"
                    f"Please add credits at: https://console.anthropic.com/settings/billing\n"
                    f"The application cannot continue without API access."
                ) from e

    async def _fetch_special_considerations(
        self,
        drug_name: str,
        special_considerations: dict,
        verbose: bool = False
    ):
        """Fetch special considerations from BNF drug page."""
        try:
            if verbose:
                print(f"      📋 Fetching special considerations for {drug_name}...")

            # Search and get drug info
            search_result = await self.call_tool("search_bnf_drug", {"drug_name": drug_name})
            search_data = json.loads(search_result.content[0].text)

            if not search_data.get('success') or search_data.get('count', 0) == 0:
                return

            drug_url = search_data['results'][0]['url']
            drug_info_result = await self.call_tool("get_bnf_drug_info", {"drug_url": drug_url})
            drug_info = json.loads(drug_info_result.content[0].text)

            if not drug_info.get('success'):
                return

            # Use Claude to extract concise summaries
            bnf_text = {
                'renal_impairment': drug_info.get('renal_impairment', ''),
                'hepatic_impairment': drug_info.get('hepatic_impairment', ''),
                'pregnancy': drug_info.get('pregnancy', '')
            }

            if any(bnf_text.values()) and self.anthropic:
                prompt = f"""Extract CONCISE special considerations for {drug_name}.

BNF Information:
Renal Impairment: {bnf_text['renal_impairment'][:800]}
Hepatic Impairment: {bnf_text['hepatic_impairment'][:800]}
Pregnancy: {bnf_text['pregnancy'][:800]}

Return ONLY a JSON object with BRIEF (1-2 sentence) summaries:
{{
  "renal_impairment": "brief summary or 'No specific adjustments mentioned'",
  "hepatic_impairment": "brief summary or 'No specific adjustments mentioned'",
  "pregnancy": "brief summary or 'No specific concerns mentioned'"
}}

Be extremely concise. Focus on key dose adjustments and safety warnings only."""

                response = self.anthropic.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}]
                )

                response_text = response.content[0].text
                if "{" in response_text and "}" in response_text:
                    json_start = response_text.find("{")
                    json_end = response_text.rfind("}") + 1
                    parsed = json.loads(response_text[json_start:json_end])

                    # Update with concise summaries
                    if parsed.get('renal_impairment'):
                        special_considerations['renal_impairment'] = parsed['renal_impairment']
                    if parsed.get('hepatic_impairment'):
                        special_considerations['hepatic_impairment'] = parsed['hepatic_impairment']
                    if parsed.get('pregnancy'):
                        special_considerations['pregnancy'] = parsed['pregnancy']

            # Elderly is often not a separate field, so keep generic advice if not found
            if not special_considerations.get('elderly') or 'not specified' in special_considerations.get('elderly', '').lower():
                special_considerations['elderly'] = "Use with caution; consider dose reduction and monitor closely"

            if verbose:
                print(f"         ✓ Special considerations updated")

        except Exception as e:
            error_msg = str(e)
            if verbose:
                print(f"         ✗ Error fetching special considerations: {error_msg}")

            # Check if this is a credit/billing error - FATAL
            if "credit balance is too low" in error_msg.lower() or "insufficient_quota" in error_msg.lower():
                raise RuntimeError(
                    f"❌ FATAL ERROR: Anthropic API credits exhausted!\n\n"
                    f"Error: {error_msg}\n\n"
                    f"Please add credits at: https://console.anthropic.com/settings/billing\n"
                    f"The application cannot continue without API access."
                ) from e

    async def cleanup(self):
        """Clean up resources."""
        try:
            await self.exit_stack.aclose()
        except (RuntimeError, ExceptionGroup) as e:
            # Known issue with Python 3.13 + anyio + multiple MCP servers
            # The cleanup still happens, we just suppress the task scope error
            if "cancel scope" not in str(e).lower():
                raise  # Re-raise if it's a different error




__all__ = ['ClinicalDecisionSupportClient']
