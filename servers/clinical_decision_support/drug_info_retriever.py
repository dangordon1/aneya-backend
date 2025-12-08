"""
Drug Information Retriever for Clinical Decision Support.

Simplified architecture:
1. Use local BNF index for fuzzy drug name search (no MCP call needed)
2. Call BNF MCP server only for fetching drug details by slug

This avoids unnecessary async calls for the index search step.
"""

import asyncio
import json
import os
import re
from pathlib import Path
from contextlib import AsyncExitStack
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Dict, List, Any, Optional

from .config import MCP_SERVERS, REGION_SERVERS, DRUG_SERVERS
from .prompts import (
    get_drug_validation_prompt,
    get_drug_info_generation_prompt,
    get_patient_tailored_drug_prompt,
)

# Import BNF functions directly for local fuzzy search and drug fetch (no MCP call needed)
from servers.drug_lookup.bnf_index_utils import get_bnf_index, BNFIndex
from servers.drug_lookup.bnf_server import _get_bnf_drug_info_impl as fetch_bnf_drug_info


class DrugInfoRetriever:
    """
    Handles drug information lookup using drug MCP servers.

    This class owns its own MCP server connections for:
    - bnf: British National Formulary drug information
    - drugbank: DrugBank drug information (India + International)
    """

    def __init__(self, anthropic_api_key: Optional[str] = None):
        """
        Initialize the drug info retriever.

        Args:
            anthropic_api_key: Anthropic API key for LLM fallback.
        """
        self.sessions: Dict[str, ClientSession] = {}
        self.tool_registry: Dict[str, str] = {}
        self.exit_stack = AsyncExitStack()
        self.current_region: Optional[str] = None

        api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.anthropic = Anthropic(api_key=api_key) if api_key else None

    async def connect_drug_servers(self, country_code: Optional[str] = None, verbose: bool = True):
        """
        Connect to drug MCP servers.

        Args:
            country_code: ISO country code. Currently BNF is used for all regions.
            verbose: Whether to print connection status.
        """
        normalized_code = country_code.upper() if country_code else None

        # Check if we need to reconnect
        if self.sessions and self.current_region != normalized_code:
            if verbose:
                print(f"   [DrugInfoRetriever] Region changed, reconnecting...")
            await self.disconnect()

        # Skip if already connected
        if self.sessions and self.current_region == normalized_code:
            if verbose:
                print(f"   [DrugInfoRetriever] Already connected")
            return

        # Get region-specific servers, filtered to only drug servers
        if country_code:
            region_servers = REGION_SERVERS.get(country_code.upper(), REGION_SERVERS.get("default", []))
            servers_to_connect = [s for s in region_servers if s in DRUG_SERVERS]
        else:
            # Default to just BNF
            servers_to_connect = ["bnf"]

        # BNF is always included as it's used for all regions
        if "bnf" not in servers_to_connect:
            servers_to_connect.append("bnf")

        # Build server dict
        servers = {
            name: MCP_SERVERS[name]
            for name in servers_to_connect
            if name in MCP_SERVERS and Path(MCP_SERVERS[name]).exists()
        }

        if verbose:
            print(f"   [DrugInfoRetriever] Connecting to {len(servers)} drug server(s): {', '.join(servers.keys())}")

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
                print(f"      [DrugInfoRetriever] Failed to connect {server_name}: {e}")

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

    async def lookup_drugs_batch(
        self,
        drugs: List[dict],
        verbose: bool = True
    ) -> List[dict]:
        """
        Look up multiple drugs using batch API.

        Args:
            drugs: List of drug objects with 'drug_name' and optional 'variations'.
            verbose: Whether to print progress.

        Returns:
            List of drug result dictionaries with:
            - drug_name: The drug name
            - status: 'success' or 'failed'
            - source: 'bnf' or 'llm'
            - details: Drug details if successful
            - error: Error message if failed
        """
        if not drugs:
            return []

        drug_names = [drug.get('drug_name', '') for drug in drugs if drug.get('drug_name')]

        if verbose:
            print(f"   [DrugInfoRetriever] Looking up {len(drug_names)} drugs: {', '.join(drug_names[:5])}...")

        results = []

        try:
            # Use batch BNF lookup tool
            if "get_multiple_bnf_drugs_parallel" in self.tool_registry:
                batch_result = await self.call_tool("get_multiple_bnf_drugs_parallel", {
                    "drug_names": drug_names
                })
                batch_data = json.loads(batch_result.content[0].text)

                if verbose:
                    successful = batch_data.get('successful_lookups', 0)
                    print(f"   [DrugInfoRetriever] Batch lookup: {successful}/{len(drug_names)} successful")

                # Process each result
                for drug_result in batch_data.get('drugs', []):
                    medication_name = drug_result['drug_name']
                    status = drug_result['status']

                    if status == 'success':
                        drug_data = drug_result['data']
                        drug_data['source'] = 'bnf'

                        results.append({
                            'drug_name': medication_name,
                            'status': 'success',
                            'source': 'bnf',
                            'details': {
                                'drug_name': medication_name,
                                'url': drug_data['url'],
                                'bnf_data': drug_data
                            }
                        })

                    elif status == 'not_found':
                        # Drug not in BNF index - skip (no LLM fallback for simpler flow)
                        if verbose:
                            print(f"   [DrugInfoRetriever] {medication_name}: Not in BNF index, skipping")

                        results.append({
                            'drug_name': medication_name,
                            'status': 'not_found',
                            'source': 'bnf',
                            'error': f'Drug "{medication_name}" not found in BNF index'
                        })

                    else:
                        # Error status
                        results.append({
                            'drug_name': medication_name,
                            'status': 'failed',
                            'source': 'bnf',
                            'error': drug_result.get('error', 'Unknown error')
                        })

            else:
                # Fallback to individual lookups
                if verbose:
                    print(f"   [DrugInfoRetriever] Batch tool not available, using individual lookups")

                for drug in drugs:
                    result = await self.lookup_drug(drug, verbose)
                    results.append(result)

        except Exception as e:
            if verbose:
                print(f"   [DrugInfoRetriever] Batch lookup error: {e}")

            # Return failed results for all drugs
            for drug in drugs:
                drug_name = drug.get('drug_name', 'Unknown')
                results.append({
                    'drug_name': drug_name,
                    'status': 'failed',
                    'source': 'bnf',
                    'error': f'Batch lookup failed: {str(e)}'
                })

        return results

    async def lookup_drug(
        self,
        drug_obj: dict,
        verbose: bool = True
    ) -> dict:
        """
        Look up a single drug using local index search + MCP fetch.

        Simplified flow:
        1. Search local BNF index for drug name (fuzzy match) - NO async needed
        2. Fetch drug details by slug via MCP

        Args:
            drug_obj: Drug object with 'drug_name'.
            verbose: Whether to print progress.

        Returns:
            Drug result dictionary.
        """
        drug_name = drug_obj.get('drug_name', '')

        if not drug_name:
            return {
                'drug_name': 'Unknown',
                'status': 'failed',
                'error': 'No drug name provided'
            }

        try:
            # Step 1: Search local BNF index (synchronous - no MCP call needed)
            index = get_bnf_index()
            matches = index.search(drug_name, limit=1)

            if not matches:
                if verbose:
                    print(f"   [DrugInfoRetriever] {drug_name}: Not found in BNF index")
                return {
                    'drug_name': drug_name,
                    'status': 'not_found',
                    'source': 'bnf',
                    'error': f'Drug "{drug_name}" not found in BNF index'
                }

            # Get best match
            best_match = matches[0]
            slug = best_match.get('slug')

            if verbose:
                print(f"   [DrugInfoRetriever] {drug_name} -> {best_match['name']} (slug: {slug})")

            # Step 2: Fetch drug details by slug via MCP
            info_result = await self.call_tool("get_bnf_drug_by_slug", {
                "slug": slug
            })
            info_data = json.loads(info_result.content[0].text)

            if info_data.get('success'):
                return {
                    'drug_name': drug_name,
                    'status': 'success',
                    'source': 'bnf',
                    'details': {
                        'drug_name': drug_name,
                        'url': info_data.get('url'),
                        'bnf_data': info_data
                    }
                }
            else:
                return {
                    'drug_name': drug_name,
                    'status': 'failed',
                    'source': 'bnf',
                    'error': info_data.get('error', 'Failed to fetch drug info')
                }

        except Exception as e:
            if verbose:
                print(f"   [DrugInfoRetriever] Error with {drug_name}: {e}")
            return {
                'drug_name': drug_name,
                'status': 'failed',
                'source': 'bnf',
                'error': str(e)
            }

    async def _llm_fallback(self, drug_name: str, verbose: bool = True) -> dict:
        """
        Use LLM to generate drug info when BNF lookup fails.

        Args:
            drug_name: The drug name.
            verbose: Whether to print progress.

        Returns:
            Drug result dictionary.
        """
        if not self.anthropic:
            return {
                'drug_name': drug_name,
                'status': 'failed',
                'source': 'llm',
                'error': 'No Anthropic client for LLM fallback'
            }

        try:
            # Step 1: Validate drug exists
            validation = await self.validate_drug_exists(drug_name)

            if not validation.get('is_real', False):
                if verbose:
                    print(f"   [DrugInfoRetriever] {drug_name}: Not a real drug - {validation.get('reasoning')}")
                return {
                    'drug_name': drug_name,
                    'status': 'failed',
                    'source': 'llm',
                    'error': f"Not a recognized medication: {validation.get('reasoning')}"
                }

            # Step 2: Generate drug info
            if verbose:
                print(f"   [DrugInfoRetriever] {drug_name}: Generating LLM info...")

            llm_info = await self.generate_drug_info_llm(drug_name, validation.get('generic_name'))

            if llm_info.get('success'):
                return {
                    'drug_name': drug_name,
                    'status': 'success',
                    'source': 'llm',
                    'details': {
                        'drug_name': drug_name,
                        'url': None,
                        'bnf_data': llm_info
                    }
                }
            else:
                return {
                    'drug_name': drug_name,
                    'status': 'failed',
                    'source': 'llm',
                    'error': llm_info.get('error', 'LLM generation failed')
                }

        except Exception as e:
            if verbose:
                print(f"   [DrugInfoRetriever] LLM fallback error for {drug_name}: {e}")
            return {
                'drug_name': drug_name,
                'status': 'failed',
                'source': 'llm',
                'error': str(e)
            }

    async def validate_drug_exists(self, drug_name: str) -> dict:
        """
        Validate that a drug name refers to a real medication.

        Args:
            drug_name: The drug name to validate.

        Returns:
            {'is_real': bool, 'reasoning': str, 'generic_name': str}
        """
        if not self.anthropic:
            return {'is_real': False, 'reasoning': 'No Anthropic client', 'generic_name': ''}

        prompt = get_drug_validation_prompt(drug_name)

        try:
            response = self.anthropic.messages.create(
                model="claude-haiku-4-5",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # Extract JSON
            if '```json' in response_text:
                json_match = re.search(r'```json\s*(\{.+?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)

            return json.loads(response_text)

        except Exception as e:
            return {
                'is_real': False,
                'reasoning': f'Validation error: {str(e)}',
                'generic_name': ''
            }

    async def generate_drug_info_llm(self, drug_name: str, generic_name: str = None) -> dict:
        """
        Generate drug information using Claude's medical knowledge.

        Args:
            drug_name: The drug name (original query).
            generic_name: Generic name if known (from validation).

        Returns:
            BNF-compatible structure with 'source': 'llm'.
        """
        if not self.anthropic:
            return {
                'drug_name': drug_name,
                'success': False,
                'error': 'No Anthropic client',
                'source': 'llm'
            }

        name_to_use = generic_name or drug_name
        prompt = get_drug_info_generation_prompt(drug_name, generic_name)

        try:
            response = self.anthropic.messages.create(
                model="claude-haiku-4-5",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # Extract JSON
            if '```json' in response_text:
                json_match = re.search(r'```json\s*(\{.+?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            elif '```' in response_text:
                json_match = re.search(r'```\s*(\{.+?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)

            drug_info = json.loads(response_text)

            # Add metadata
            drug_info['url'] = None
            drug_info['success'] = True
            drug_info['error'] = None
            drug_info['source'] = 'llm'

            return drug_info

        except Exception as e:
            return {
                'drug_name': name_to_use,
                'url': None,
                'success': False,
                'error': f'LLM generation failed: {str(e)}',
                'source': 'llm'
            }

    async def tailor_drug_to_patient(
        self,
        drug_name: str,
        bnf_data: dict,
        patient_context: dict,
        verbose: bool = True
    ) -> dict:
        """
        Tailor drug prescribing information to a specific patient.

        Takes raw BNF/LLM drug data and generates personalized prescribing
        guidance considering the patient's age, comorbidities, current
        medications, allergies, and clinical presentation.

        Args:
            drug_name: The drug name.
            bnf_data: Raw BNF or LLM-generated drug data.
            patient_context: Dictionary with:
                - clinical_scenario: Full clinical presentation
                - patient_age: Patient's age
                - allergies: Known allergies
                - diagnosis: The diagnosis this drug is for

        Returns:
            Dictionary with personalized prescribing guidance.
        """
        if not self.anthropic:
            if verbose:
                print(f"   [DrugInfoRetriever] No Anthropic client for tailoring {drug_name}")
            return {
                'drug_name': drug_name,
                'personalized': False,
                'error': 'No Anthropic client for personalization',
                'raw_data': bnf_data
            }

        prompt = get_patient_tailored_drug_prompt(drug_name, bnf_data, patient_context)

        try:
            if verbose:
                print(f"   [DrugInfoRetriever] Tailoring {drug_name} to patient context...")

            response = self.anthropic.messages.create(
                model="claude-haiku-4-5",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # Extract JSON
            if '```json' in response_text:
                json_match = re.search(r'```json\s*(\{.+?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            elif '```' in response_text:
                json_match = re.search(r'```\s*(\{.+?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)

            tailored_data = json.loads(response_text)
            tailored_data['personalized'] = True
            tailored_data['raw_bnf_data'] = bnf_data

            if verbose:
                safe = tailored_data.get('contraindication_check', {}).get('safe_to_prescribe', True)
                status = "SAFE" if safe else "CONCERNS"
                print(f"   [DrugInfoRetriever] {drug_name}: Personalized ({status})")

            return tailored_data

        except Exception as e:
            if verbose:
                print(f"   [DrugInfoRetriever] Tailoring error for {drug_name}: {e}")
            return {
                'drug_name': drug_name,
                'personalized': False,
                'error': f'Tailoring failed: {str(e)}',
                'raw_data': bnf_data
            }

    async def _personalize_drug_for_patient(
        self,
        bnf_data: dict,
        patient_context: dict,
        verbose: bool = True
    ) -> dict:
        """
        Personalize BNF drug data for a specific patient using Claude.

        Args:
            bnf_data: Raw BNF drug data from fetch_bnf_drug_info
            patient_context: Patient information (scenario, age, allergies, diagnosis)
            verbose: Whether to print progress

        Returns:
            Dictionary with personalized drug data in BNF format fields
        """
        if not self.anthropic:
            # No API key - return raw data
            if verbose:
                print(f"   [DrugInfoRetriever] No Anthropic API key - returning raw BNF data")
            return bnf_data

        # Format BNF sections for prompt
        bnf_fields = ['indications', 'dosage', 'contraindications', 'cautions',
                      'side_effects', 'interactions', 'pregnancy', 'renal_impairment',
                      'hepatic_impairment']
        bnf_text = "\n".join([
            f"{k.upper()}: {bnf_data.get(k)}"
            for k in bnf_fields
            if bnf_data.get(k) and bnf_data.get(k) != 'Not specified'
        ])

        drug_name = bnf_data.get('drug_name', 'Unknown')

        prompt = f"""You are a clinical pharmacist. Extract PERSONALIZED drug information for this specific patient.

PATIENT:
- Clinical Presentation: {patient_context.get('clinical_scenario', '')[:1500]}
- Age: {patient_context.get('patient_age', 'Not specified')}
- Allergies: {patient_context.get('allergies', 'None known')}
- Diagnosis: {patient_context.get('diagnosis', 'Not specified')}

DRUG: {drug_name}

BNF DATA:
{bnf_text[:3000]}

Based on the patient's specific details, provide PERSONALIZED drug information. Consider:
1. Age-appropriate dosing (select the correct dose for this patient's age)
2. Route of administration appropriate for the condition
3. Any relevant adjustments for comorbidities
4. Drug interactions with any mentioned current medications
5. Warnings specific to this patient's situation

Return ONLY valid JSON with these exact fields:
{{
  "drug_name": "{drug_name}",
  "dosage": "The specific dose for THIS patient - include dose amount, route (oral/IV/etc), frequency, and duration. Be specific, e.g., '1g orally every 6 hours for 5-7 days'",
  "side_effects": "Key side effects this patient should watch for, considering their conditions",
  "interactions": "Any drug interactions relevant to medications mentioned in the presentation, or 'None identified' if no other medications mentioned",
  "cautions": "Patient-specific warnings based on their age, conditions, and allergies",
  "success": true
}}"""

        try:
            if verbose:
                print(f"   [DrugInfoRetriever] Calling Claude Haiku for personalization...")

            response = self.anthropic.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # Extract JSON from response (handle markdown code blocks)
            if '```json' in response_text:
                match = re.search(r'```json\s*(\{.+?\})\s*```', response_text, re.DOTALL)
                if match:
                    response_text = match.group(1)
            elif '```' in response_text:
                match = re.search(r'```\s*(\{.+?\})\s*```', response_text, re.DOTALL)
                if match:
                    response_text = match.group(1)

            personalized = json.loads(response_text)

            if verbose:
                print(f"   [DrugInfoRetriever] ✅ Personalized {drug_name} successfully")

            return personalized

        except Exception as e:
            if verbose:
                print(f"   [DrugInfoRetriever] ⚠️  Personalization failed for {drug_name}: {e}")
            # Return raw BNF data as fallback
            return bnf_data

    async def lookup_drugs_batch_with_context(
        self,
        drugs: List[dict],
        patient_context: dict,
        verbose: bool = True
    ) -> List[dict]:
        """
        Look up drugs with patient context using direct function calls.

        This method:
        1. Searches local BNF index for drug slug
        2. Fetches raw BNF data directly (no MCP)
        3. Personalizes data for patient using Claude

        Args:
            drugs: List of drug objects with 'drug_name'.
            patient_context: Dictionary with:
                - clinical_scenario: Full clinical presentation
                - patient_age: Patient's age
                - allergies: Known allergies
                - diagnosis: The diagnosis

        Returns:
            List of personalized drug result dictionaries.
        """
        if not drugs:
            return []

        if verbose:
            print(f"   [DrugInfoRetriever] Looking up {len(drugs)} drugs with patient context...")

        results = []
        index = get_bnf_index()

        for drug_obj in drugs:
            drug_name = drug_obj.get('drug_name', '')
            if not drug_name:
                continue

            try:
                # Step 1: Search local index for slug
                matches = index.search(drug_name, limit=1)

                if not matches:
                    if verbose:
                        print(f"   [DrugInfoRetriever] {drug_name}: Not in BNF index")
                    results.append({
                        'drug_name': drug_name,
                        'status': 'not_found',
                        'source': 'bnf',
                        'error': f'Drug "{drug_name}" not found in BNF index'
                    })
                    continue

                slug = matches[0]['slug']
                matched_name = matches[0]['name']

                if verbose:
                    print(f"   [DrugInfoRetriever] {drug_name} -> {matched_name}")

                # Step 2: Fetch raw BNF data directly (no MCP)
                drug_url = f"https://bnf.nice.org.uk/drugs/{slug}/"
                if verbose:
                    print(f"   [DrugInfoRetriever] Fetching BNF data for {slug}...")

                bnf_data = fetch_bnf_drug_info(drug_url)

                if not bnf_data.get('success'):
                    results.append({
                        'drug_name': drug_name,
                        'status': 'failed',
                        'source': 'bnf',
                        'error': bnf_data.get('error', 'Failed to fetch BNF data')
                    })
                    continue

                # Step 3: Personalize with Claude
                if verbose:
                    print(f"   [DrugInfoRetriever] Personalizing {matched_name} for patient...")

                personalized_data = await self._personalize_drug_for_patient(
                    bnf_data, patient_context, verbose
                )

                results.append({
                    'drug_name': drug_name,
                    'status': 'success',
                    'source': 'bnf',
                    'details': {
                        'drug_name': personalized_data.get('drug_name', matched_name),
                        'url': bnf_data.get('url'),
                        'bnf_data': personalized_data  # Personalized data in BNF format
                    }
                })

            except Exception as e:
                if verbose:
                    print(f"   [DrugInfoRetriever] Error with {drug_name}: {e}")
                results.append({
                    'drug_name': drug_name,
                    'status': 'failed',
                    'source': 'bnf',
                    'error': str(e)
                })

        if verbose:
            successful = sum(1 for r in results if r.get('status') == 'success')
            print(f"   [DrugInfoRetriever] Completed {successful}/{len(drugs)} drugs")

        return results


__all__ = ['DrugInfoRetriever']
