#!/usr/bin/env python
"""
Clinical Decision Support Client

Multi-server MCP client that orchestrates geolocation, NICE guidelines, and BNF
servers to provide evidence-based clinical recommendations.

Architecture:
- Connects to 3 independent FastMCP servers via stdio
- Routes tool calls to appropriate servers
- Implements clinical decision support workflow with parallel execution
"""

import sys
import asyncio
import json
from pathlib import Path
from contextlib import AsyncExitStack
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Dict, List, Any, Optional
import os


# Server paths
SERVERS_DIR = Path(__file__).parent
MCP_SERVERS = {
    "geolocation": str(SERVERS_DIR / "geolocation_server.py"),
    "patient_info": str(SERVERS_DIR / "patient_info_server.py"),
    "nice": str(SERVERS_DIR / "nice_guidelines_server.py"),
    "bnf": str(SERVERS_DIR / "bnf_server.py")
}


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

    async def connect_to_servers(self, server_paths: Optional[Dict[str, str]] = None, verbose: bool = True):
        """
        Connect to multiple MCP servers in parallel.

        Args:
            server_paths: Optional dict of server_name -> server_path. Uses defaults if None.
            verbose: Whether to print connection status
        """
        servers = server_paths or MCP_SERVERS

        if verbose:
            print(f"🔄 Connecting to {len(servers)} servers in parallel...")

        # Validate all servers exist
        for server_name, server_path in servers.items():
            if not Path(server_path).exists():
                raise FileNotFoundError(f"Server not found: {server_path}")

        # Connect to all servers in parallel using asyncio.gather
        connection_tasks = [
            self._connect_single_server(server_name, server_path, verbose)
            for server_name, server_path in servers.items()
        ]

        await asyncio.gather(*connection_tasks)

        # Build tool registry by listing tools from all servers in parallel
        await self._discover_tools(verbose)

    async def _connect_single_server(self, server_name: str, server_path: str, verbose: bool = True):
        """Connect to a single MCP server."""
        try:
            if verbose:
                print(f"  ⏳ Connecting to {server_name}...")

            server_params = StdioServerParameters(
                command="fastmcp",
                args=["run", server_path, "--transport", "stdio", "--no-banner"]
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
        Orchestrate clinical decision support workflow.

        Workflow:
        0. Retrieve patient information and seasonal context
        1. Determine location (auto-detect or override)
        2. Search NICE guidelines and CKS for condition
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

        # Step 1: Determine location
        if verbose:
            print("\n📍 Step 1: Determining location...")

        if location_override:
            location_info = {
                'country_code': location_override.upper(),
                'country': 'Detected from IP' if location_override else 'User specified'
            }
            if verbose:
                print(f"   Location: {location_override} (detected from IP address)")
        else:
            result = await self.call_tool("get_user_country", {})
            location_info = json.loads(result.content[0].text)  # Parse the returned dict
            if verbose:
                print(f"   Auto-detected: {location_info['country']} ({location_info['country_code']})")

        # Step 2: Search NICE guidelines, CKS, and BNF treatment summaries (UK only)
        guidelines = []
        cks_topics = []
        bnf_summaries = []
        pubmed_articles = []

        if location_info['country_code'] in ['GB', 'UK']:
            if verbose:
                print(f"\n📚 Step 2: Searching NICE and BNF resources...")

            # Extract key medical terms from scenario for better search
            # Look for common condition keywords
            scenario_lower = clinical_scenario.lower()
            search_terms = []

            # Common conditions to extract
            conditions = ['croup', 'bronchiolitis', 'asthma', 'pneumonia', 'sepsis',
                         'fever', 'cough', 'uti', 'infection', 'pain']
            for condition in conditions:
                if condition in scenario_lower:
                    search_terms.append(condition)

            # Add broader search terms for BNF treatment summaries AT THE BEGINNING
            # Map specific conditions to broader categories for better BNF matching
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

            # Search NICE Guidelines with key terms
            for term in search_terms[:2]:  # Try up to 2 terms
                result = await self.call_tool("search_nice_guidelines", {
                    "keyword": term,
                    "max_results": 3
                })
                guidelines_data = json.loads(result.content[0].text)
                guidelines.extend(guidelines_data.get('results', []))

            # Also search CKS (Clinical Knowledge Summaries)
            for term in search_terms[:2]:  # Try up to 2 terms
                try:
                    result = await self.call_tool("search_cks_topics", {
                        "topic": term
                    })
                    cks_data = json.loads(result.content[0].text)
                    if cks_data.get('success') and cks_data.get('results'):
                        cks_topics.extend(cks_data['results'])
                except:
                    pass  # CKS might be geo-restricted or topic not found

            # Search BNF Treatment Summaries
            for term in search_terms[:2]:  # Try up to 2 terms
                try:
                    result = await self.call_tool("search_bnf_treatment_summaries", {
                        "condition": term,
                        "max_results": 3
                    })
                    bnf_data = json.loads(result.content[0].text)
                    if bnf_data.get('success') and bnf_data.get('results'):
                        bnf_summaries.extend(bnf_data['results'])
                except:
                    pass  # BNF might not have treatment summaries for this condition

            # Remove duplicates from guidelines
            seen_refs = set()
            unique_guidelines = []
            for g in guidelines:
                ref = g.get('reference', g.get('url'))
                if ref not in seen_refs:
                    seen_refs.add(ref)
                    unique_guidelines.append(g)
            guidelines = unique_guidelines[:5]  # Limit to 5 total

            # Remove duplicates from BNF summaries
            seen_bnf_urls = set()
            unique_bnf = []
            for b in bnf_summaries:
                if b['url'] not in seen_bnf_urls:
                    seen_bnf_urls.add(b['url'])
                    unique_bnf.append(b)
            bnf_summaries = unique_bnf[:3]  # Limit to 3 total

            if verbose:
                print(f"   Found {len(guidelines)} guideline(s), {len(cks_topics)} CKS topic(s), and {len(bnf_summaries)} BNF treatment summar{'y' if len(bnf_summaries) == 1 else 'ies'}")
                for g in guidelines[:3]:
                    print(f"      • Guideline {g['reference']}: {g['title'][:50]}...")
                for topic in cks_topics[:3]:
                    print(f"      • CKS: {topic['title'][:50]}...")
                for bnf in bnf_summaries[:3]:
                    print(f"      • BNF: {bnf['title'][:50]}...")

            # Step 2b: If no/few resources found (guidelines + CKS), search PubMed for evidence
            total_nice_resources = len(guidelines) + len(cks_topics)
            if total_nice_resources < 2:
                if verbose:
                    print(f"\n📰 Step 2b: Limited guidelines found, searching PubMed for evidence...")

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
        else:
            # For non-UK locations, go straight to PubMed
            if verbose:
                print(f"\n📚 Step 2: NICE guidelines not available for {location_info['country_code']}")
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

        # Step 3: Use Claude to analyze clinical scenario and extract diagnoses/treatments from guidelines
        if verbose:
            print(f"\n🔍 Step 3: Using AI agent to analyze clinical scenario and extract diagnoses/treatments...")

        diagnoses = []  # List of {diagnosis, treatments: [{treatment_name, medications: []}]}

        # Collect full guideline content
        guideline_contents = []
        if guidelines:
            if verbose:
                print(f"   Retrieving full guideline content for {len(guidelines[:3])} guideline(s)...")

            for guideline in guidelines[:3]:  # Get details for top 3 guidelines
                try:
                    result = await self.call_tool("get_guideline_details", {
                        "identifier": guideline['reference']
                    })
                    guideline_detail = json.loads(result.content[0].text)

                    if guideline_detail.get('success'):
                        guideline_contents.append({
                            'title': guideline['title'],
                            'reference': guideline['reference'],
                            'url': guideline['url'],
                            'overview': guideline_detail.get('overview', ''),
                            'sections': guideline_detail.get('sections', []),
                            'published_date': guideline_detail.get('published_date', '')
                        })
                        if verbose:
                            print(f"      ✓ Retrieved: {guideline['reference']}")
                    else:
                        if verbose:
                            error_msg = guideline_detail.get('error', 'Unknown error')
                            print(f"      ✗ Failed to retrieve {guideline['reference']}: {error_msg}")
                except Exception as e:
                    if verbose:
                        print(f"      ✗ Failed to retrieve {guideline.get('reference', 'guideline')}: {str(e)}")

        # Collect CKS content
        cks_contents = []
        if cks_topics:
            if verbose:
                print(f"   Retrieving full CKS content for {len(cks_topics[:3])} topic(s)...")

            for topic in cks_topics[:3]:  # Get details for top 3 CKS topics
                try:
                    result = await self.call_tool("get_cks_topic", {
                        "topic": topic['title'].lower().replace(' ', '-')
                    })
                    cks_content = json.loads(result.content[0].text)

                    if cks_content.get('success'):
                        cks_contents.append({
                            'title': topic['title'],
                            'url': topic['url'],
                            'summary': topic.get('summary', ''),
                            'management': cks_content.get('management', ''),
                            'prescribing': cks_content.get('prescribing', ''),
                            'full_text': cks_content.get('full_text', '')
                        })
                        if verbose:
                            print(f"      ✓ Retrieved: {topic['title']}")
                except Exception as e:
                    if verbose:
                        print(f"      ✗ Failed to retrieve {topic.get('title', 'topic')}")

        # Collect BNF Treatment Summary content
        bnf_summary_contents = []
        if bnf_summaries:
            if verbose:
                print(f"   Retrieving full BNF treatment summar{'y' if len(bnf_summaries[:3]) == 1 else 'ies'} for {len(bnf_summaries[:3])} resource(s)...")

            for bnf in bnf_summaries[:3]:  # Get details for top 3 BNF summaries
                try:
                    result = await self.call_tool("get_bnf_treatment_summary", {
                        "url": bnf['url']
                    })
                    bnf_content = json.loads(result.content[0].text)

                    if bnf_content.get('success'):
                        bnf_summary_contents.append({
                            'title': bnf['title'],
                            'url': bnf['url'],
                            'summary': bnf_content.get('summary', ''),
                            'sections': bnf_content.get('sections', [])
                        })
                        if verbose:
                            print(f"      ✓ Retrieved: {bnf['title']}")
                except Exception as e:
                    if verbose:
                        print(f"      ✗ Failed to retrieve {bnf.get('title', 'BNF summary')}")

        # Use Claude to analyze and extract structured information
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
        bnf_prescribing_guidance = []
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

        # Step 3b: Get BNF details for all medications mentioned in treatments
        if diagnoses:
            if verbose:
                print(f"\n💊 Step 3b: Retrieving BNF medication details for treatment options...")

            for diagnosis in diagnoses:
                for treatment in diagnosis['treatments']:
                    medication_names = treatment.get('medication_names', [])

                    if not medication_names:
                        continue

                    if verbose:
                        print(f"   {diagnosis['diagnosis']} - {treatment['treatment_name']}:")

                    for med_name in medication_names[:3]:  # Limit to 3 meds per treatment
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
                                    treatment['medications_detailed'].append(drug_info)
                                    if verbose:
                                        print(f"      ✓ {drug_info['drug_name']}")
                        except:
                            if verbose:
                                print(f"      ✗ {med_name} - BNF lookup failed")
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
                print(f"\n💊 Step 3b: Checking drug-drug interactions...")

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
            summary_parts.append(f"\n📚 Found {len(guidelines)} relevant NICE guideline(s):")
            for g in guidelines[:3]:
                summary_parts.append(f"   • {g['reference']}: {g['title']}")
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
            'bnf_prescribing_guidance': bnf_prescribing_guidance,  # Prescribing recommendations from BNF
            'pubmed_articles': pubmed_articles,
            'diagnoses': diagnoses,  # Structured diagnoses from guidelines
            'drug_interactions': drug_interactions,
            'summary': '\n'.join(summary_parts)
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

        # Add NICE guidelines
        for guideline in guideline_contents:
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
      "guideline_url": "URL from above",
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
                model="claude-sonnet-4-20250514",
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
                model="claude-sonnet-4-20250514",
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
                    model="claude-sonnet-4-20250514",
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
                    model="claude-sonnet-4-20250514",
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


async def main():
    """Example usage of the Clinical Decision Support Client."""

    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️  Warning: ANTHROPIC_API_KEY not set in environment")
        print("   Claude integration features will be disabled")
        print("   Testing server connections and tool orchestration only\n")

    # Create client
    client = ClinicalDecisionSupportClient(anthropic_api_key=api_key)

    try:
        # Connect to servers
        await client.connect_to_servers()

        print("\n" + "="*70)
        print("EXAMPLE CLINICAL CASES")
        print("="*70)

        # Example 1: Pediatric croup
        print("\n\n### CASE 1: Pediatric Croup ###\n")
        await client.clinical_decision_support(
            clinical_scenario="3-year-old with croup, moderate stridor at rest, barking cough",
            patient_age="3 years",
            location_override="GB"
        )

        await asyncio.sleep(1)  # Brief pause between cases

        # Example 2: Post-op sepsis with allergy
        print("\n\n### CASE 2: Post-Operative Sepsis ###\n")
        await client.clinical_decision_support(
            clinical_scenario="Post-operative sepsis, fever 38.5C, tachycardia, suspected wound infection",
            patient_age="65 years",
            allergies="penicillin",
            location_override="GB"
        )

    finally:
        # Clean up
        await client.cleanup()
        print("\n✅ Client cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
