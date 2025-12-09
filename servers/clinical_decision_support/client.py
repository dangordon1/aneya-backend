"""
Client module for Clinical Decision Support system.

This module contains the main ClinicalDecisionSupportClient class which orchestrates
the clinical decision support workflow by coordinating the DiagnosisEngine and
DrugInfoRetriever classes.
"""

import json
import os
import httpx
from typing import Dict, List, Any, Optional, Callable

from .diagnosis_engine import DiagnosisEngine
from .drug_info_retriever import DrugInfoRetriever


class ClinicalDecisionSupportClient:
    """
    Orchestrates clinical decision support workflow.

    Coordinates DiagnosisEngine and DrugInfoRetriever, emits all progress events
    to the frontend. This class is responsible for:
    - Managing connections to both sub-engines
    - Orchestrating the diagnosis -> drug lookup workflow
    - Emitting all progress events (diagnoses, drug_update, tool_call, error)
    - Generating the final summary report
    """

    def __init__(self, anthropic_api_key: Optional[str] = None):
        """
        Initialize the clinical decision support orchestrator.

        Args:
            anthropic_api_key: Anthropic API key for Claude. If None, reads from env.
        """
        api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")

        # Initialize sub-engines with shared API key
        self.diagnosis_engine = DiagnosisEngine(api_key)
        self.drug_retriever = DrugInfoRetriever(api_key)

        # Track current region
        self.current_region: Optional[str] = None

    async def get_location_from_ip(self, user_ip: Optional[str] = None) -> dict:
        """
        Get location information from IP address using direct HTTP call.

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
            if user_ip:
                url = f"http://ip-api.com/json/{user_ip}?fields=status,message,country,countryCode"
            else:
                url = "http://ip-api.com/json/?fields=status,message,country,countryCode"

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                if data.get('status') == 'fail':
                    print(f"Geolocation failed: {data.get('message', 'Unknown error')}")
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
            print(f"Geolocation error: {str(e)}")
            return {
                'country': 'Unknown',
                'country_code': 'XX',
                'ip': user_ip or 'unknown'
            }

    async def connect_to_servers(self, country_code: Optional[str] = None, verbose: bool = True):
        """
        Connect both engines to their respective MCP servers.

        Args:
            country_code: ISO country code (e.g., 'GB', 'IN', 'US').
            verbose: Whether to print connection status.
        """
        normalized_code = country_code.upper() if country_code else None

        # Check if we need to reconnect
        if self.current_region != normalized_code:
            if verbose and self.current_region:
                print(f"Region changed from {self.current_region} to {normalized_code}")

        if verbose:
            print(f"\n[Orchestrator] Connecting to MCP servers for region: {normalized_code or 'default'}")

        # Connect both engines in parallel
        import asyncio
        await asyncio.gather(
            self.diagnosis_engine.connect_guideline_servers(country_code, verbose),
            self.drug_retriever.connect_drug_servers(country_code, verbose)
        )

        self.current_region = normalized_code

        if verbose:
            print(f"[Orchestrator] Connected to region: {self.current_region}")

    async def disconnect_servers(self):
        """Disconnect both engines from their MCP servers."""
        import asyncio
        await asyncio.gather(
            self.diagnosis_engine.disconnect(),
            self.drug_retriever.disconnect(),
            return_exceptions=True
        )
        self.current_region = None

    async def cleanup(self):
        """Clean up all resources."""
        await self.disconnect_servers()

    async def clinical_decision_support(
        self,
        clinical_scenario: str,
        patient_id: Optional[str] = None,
        patient_age: Optional[str] = None,
        allergies: Optional[str] = None,
        location_override: Optional[str] = None,
        verbose: bool = True,
        progress_callback: Optional[Callable] = None,
        max_drugs: int = 10
    ) -> Dict[str, Any]:
        """
        Main clinical decision support workflow.

        This orchestrates the full workflow:
        1. Validate input is a clinical consultation
        2. Analyze consultation with guideline tools -> diagnoses
        3. PubMed fallback if guidelines insufficient
        4. Look up drug details from BNF
        5. Generate summary

        All progress events are emitted here, not in sub-classes.

        Args:
            clinical_scenario: Patient case description.
            patient_id: Optional patient ID (not used in current version).
            patient_age: Optional patient age (not used in current version).
            allergies: Optional known allergies (not used in current version).
            location_override: Optional country code override.
            verbose: Whether to print workflow steps.
            progress_callback: Async callback for progress events.
            max_drugs: Maximum number of drugs to look up.

        Returns:
            Dictionary with diagnoses, summary, and prescribing guidance.
        """
        # Step 0: Validate input
        if verbose:
            print("\n" + "="*70)
            print("CLINICAL DECISION SUPPORT")
            print("="*70)
            print(f"Consultation: {clinical_scenario[:100]}...")

        is_valid, error_message = await self.diagnosis_engine.validate_clinical_input(
            clinical_scenario, verbose=verbose
        )

        if not is_valid:
            return {
                'error': 'invalid_input',
                'error_message': error_message,
                'diagnoses': [],
                'bnf_prescribing_guidance': [],
                'guidelines_searched': [],
                'summary': error_message
            }

        # Step 1: Analyze with guidelines
        if verbose:
            print(f"\nStep 1: Analyzing with guideline tools...")

        diagnoses, tool_calls = await self.diagnosis_engine.analyze_with_guidelines(
            clinical_scenario, verbose=verbose
        )

        # Emit tool_call events for progress
        for tool_call in tool_calls:
            if progress_callback:
                await progress_callback("tool_call", tool_call)

        if verbose:
            print(f"   Extracted {len(diagnoses)} diagnoses")

        # Step 1.5: PubMed fallback if needed
        MIN_DIAGNOSES_THRESHOLD = 1

        if len(diagnoses) < MIN_DIAGNOSES_THRESHOLD:
            if verbose:
                print(f"\nStep 1.5: PubMed fallback (only {len(diagnoses)} diagnoses)...")

            diagnoses, pubmed_tool_calls = await self.diagnosis_engine.pubmed_fallback(
                clinical_scenario, diagnoses, verbose=verbose
            )

            for tool_call in pubmed_tool_calls:
                if progress_callback:
                    await progress_callback("tool_call", tool_call)

        # Step 2: Extract drugs from diagnoses
        all_drugs = self._extract_drugs_from_diagnoses(diagnoses)

        print(f"[DEBUG] Extracted {len(all_drugs)} drugs from diagnoses")
        for drug in all_drugs[:5]:
            print(f"[DEBUG]    - {drug.get('drug_name')}")

        # Emit diagnoses event with pending drugs
        if progress_callback:
            drugs_pending = [d['drug_name'] for d in all_drugs]
            await progress_callback("diagnoses", {
                "diagnoses": diagnoses,
                "drugs_pending": drugs_pending
            })

        if verbose:
            print(f"\nStep 2: Drug information lookup ({len(all_drugs)} drugs)...")

        # Limit drugs
        drugs_to_lookup = all_drugs[:max_drugs]

        if verbose:
            print(f"[Orchestrator] Will lookup {len(drugs_to_lookup)} drugs")

        # Step 3: Look up drug details with patient context for personalization
        if drugs_to_lookup:
            print(f"[DEBUG] Starting drug lookup for {len(drugs_to_lookup)} drugs...", flush=True)

            # Build patient context for personalization
            patient_context = {
                'clinical_scenario': clinical_scenario,
                'patient_age': patient_age or 'Not specified',
                'allergies': allergies or 'None known',
                'diagnosis': diagnoses[0].get('diagnosis', '') if diagnoses else ''
            }

            try:
                # Use personalized drug lookup
                drug_results = await self.drug_retriever.lookup_drugs_batch_with_context(
                    drugs_to_lookup,
                    patient_context,
                    verbose=verbose
                )

                print(f"[DEBUG] Drug lookup completed: {len(drug_results)} results", flush=True)

                # Emit drug_update events for each result
                for result in drug_results:
                    print(f"[DEBUG] Emitting drug_update for {result.get('drug_name')}: {result.get('status')}", flush=True)
                    if progress_callback:
                        print(f"[DEBUG] Calling progress_callback...", flush=True)
                        if result.get('status') == 'success':
                            await progress_callback("drug_update", {
                                "drug_name": result['drug_name'],
                                "status": "complete",
                                "source": result.get('source', 'bnf'),
                                "details": result.get('details')
                            })
                        else:
                            await progress_callback("drug_update", {
                                "drug_name": result['drug_name'],
                                "status": "failed",
                                "error": result.get('error', 'Unknown error')
                            })
                        print(f"[DEBUG] progress_callback completed for {result.get('drug_name')}", flush=True)

            except Exception as e:
                print(f"[DEBUG] ERROR in drug lookup: {e}", flush=True)
                import traceback
                traceback.print_exc()

        # Step 4: Generate summary
        if verbose:
            print(f"\nStep 3: Generating summary...")

        summary = self._generate_summary(diagnoses)

        result = {
            'diagnoses': diagnoses,
            'summary': summary,
            'bnf_prescribing_guidance': []  # Drug details streamed separately
        }

        if verbose:
            print("\n" + "="*70)
            print("ANALYSIS COMPLETE")
            print("="*70)
            print(f"Diagnoses: {len(diagnoses)}")
            print(f"Drugs looked up: {len(drugs_to_lookup)}")

        return result

    def _extract_drugs_from_diagnoses(self, diagnoses: List[dict]) -> List[dict]:
        """
        Extract all drug objects from diagnoses structure.

        Args:
            diagnoses: List of diagnosis dictionaries.

        Returns:
            List of drug objects with 'drug_name' and 'variations'.
        """
        all_drugs = []

        for diag in diagnoses:
            # Primary care medications
            primary_care = diag.get('primary_care', {})
            medications = primary_care.get('medications', [])
            for med in medications:
                if isinstance(med, str):
                    all_drugs.append({'drug_name': med, 'variations': [med]})
                elif isinstance(med, dict):
                    all_drugs.append({
                        'drug_name': med.get('drug_name', ''),
                        'variations': med.get('variations', [med.get('drug_name', '')])
                    })

            # Surgery phase medications
            surgery = diag.get('surgery', {})
            if surgery.get('indicated'):
                phases = surgery.get('phases', {})

                # Pre-op medications
                preop = phases.get('preoperative', {})
                for med in preop.get('medications', []):
                    if isinstance(med, str):
                        all_drugs.append({'drug_name': med, 'variations': [med]})
                    elif isinstance(med, dict):
                        all_drugs.append({
                            'drug_name': med.get('drug_name', ''),
                            'variations': med.get('variations', [med.get('drug_name', '')])
                        })

                # Post-op medications
                postop = phases.get('postoperative', {})
                for med in postop.get('medications', []):
                    if isinstance(med, str):
                        all_drugs.append({'drug_name': med, 'variations': [med]})
                    elif isinstance(med, dict):
                        all_drugs.append({
                            'drug_name': med.get('drug_name', ''),
                            'variations': med.get('variations', [med.get('drug_name', '')])
                        })

        # Remove duplicates by drug_name
        seen_drugs = {}
        for drug in all_drugs:
            drug_name = drug['drug_name']
            if drug_name and drug_name not in seen_drugs:
                seen_drugs[drug_name] = drug

        return list(seen_drugs.values())

    def _generate_summary(self, diagnoses: List[dict]) -> str:
        """
        Generate text summary of diagnoses.

        Args:
            diagnoses: List of diagnosis dictionaries.

        Returns:
            Formatted summary string.
        """
        summary = f"""
CLINICAL DECISION SUPPORT REPORT

DIAGNOSES ({len(diagnoses)}):
"""
        for diag in diagnoses:
            summary += f"\n- {diag.get('diagnosis')} ({diag.get('confidence')} confidence)"

        if not diagnoses:
            summary += "\nNo diagnoses identified."

        return summary


__all__ = ['ClinicalDecisionSupportClient']
