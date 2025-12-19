"""
Unit tests for DrugInfoRetriever.

These tests verify the DrugInfoRetriever can:
1. Connect to drug MCP servers (BNF, DrugBank)
2. Look up single drugs
3. Look up multiple drugs in batch
4. Fall back to LLM when drug not found in BNF
"""

import pytest
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Skip all tests if ANTHROPIC_API_KEY is not set
pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)


class TestDrugInfoRetrieverConnection:
    """Test MCP server connection functionality."""

    @pytest.mark.asyncio
    async def test_connect_drug_servers(self):
        """Test connecting to drug servers."""
        from servers.clinical_decision_support.drug_info_retriever import DrugInfoRetriever

        retriever = DrugInfoRetriever()

        try:
            await retriever.connect_drug_servers("IN", verbose=True)

            # Verify sessions were created
            assert len(retriever.sessions) > 0, "No sessions created"
            print(f"✓ {len(retriever.sessions)} sessions created")

            # Verify tools were discovered
            assert len(retriever.tool_registry) > 0, "No tools discovered"
            print(f"✓ {len(retriever.tool_registry)} tools discovered")

            # Print available tools
            for tool_name in retriever.tool_registry:
                print(f"   - {tool_name}")

        finally:
            await retriever.disconnect()


class TestDrugInfoRetrieverLookup:
    """Test drug lookup functionality."""

    @pytest.mark.asyncio
    async def test_lookup_single_drug_amoxicillin(self):
        """Test looking up Amoxicillin (common antibiotic)."""
        from servers.clinical_decision_support.drug_info_retriever import DrugInfoRetriever

        retriever = DrugInfoRetriever()

        try:
            await retriever.connect_drug_servers("GB", verbose=True)

            result = await retriever.lookup_drug(
                {"drug_name": "Amoxicillin", "variations": ["Amoxicillin"]},
                verbose=True
            )

            assert result is not None, "No result returned"
            assert result.get('drug_name') == "Amoxicillin"
            assert result.get('status') in ['success', 'failed']

            print(f"✓ Drug lookup status: {result.get('status')}")
            print(f"✓ Source: {result.get('source')}")

            if result.get('status') == 'success':
                details = result.get('details', {})
                print(f"✓ URL: {details.get('url')}")

        finally:
            await retriever.disconnect()

    @pytest.mark.asyncio
    async def test_lookup_drugs_batch(self):
        """Test looking up multiple drugs in batch."""
        from servers.clinical_decision_support.drug_info_retriever import DrugInfoRetriever

        retriever = DrugInfoRetriever()

        try:
            await retriever.connect_drug_servers("GB", verbose=True)

            drugs = [
                {"drug_name": "Amoxicillin", "variations": ["Amoxicillin"]},
                {"drug_name": "Paracetamol", "variations": ["Paracetamol"]},
            ]

            results = await retriever.lookup_drugs_batch(drugs, verbose=True)

            assert len(results) == len(drugs), f"Expected {len(drugs)} results, got {len(results)}"

            for result in results:
                print(f"✓ {result.get('drug_name')}: {result.get('status')} ({result.get('source')})")

        finally:
            await retriever.disconnect()


class TestDrugInfoRetrieverLLMFallback:
    """Test LLM fallback functionality."""

    @pytest.mark.asyncio
    async def test_validate_real_drug(self):
        """Test validation of a real drug name."""
        from servers.clinical_decision_support.drug_info_retriever import DrugInfoRetriever

        retriever = DrugInfoRetriever()

        result = await retriever.validate_drug_exists("Paracetamol")

        assert result.get('is_real') is True, f"Paracetamol not recognized: {result.get('reasoning')}"
        print(f"✓ Paracetamol validated as real drug")
        print(f"   Generic name: {result.get('generic_name')}")

    @pytest.mark.asyncio
    async def test_validate_fake_drug(self):
        """Test validation of a fake drug name."""
        from servers.clinical_decision_support.drug_info_retriever import DrugInfoRetriever

        retriever = DrugInfoRetriever()

        result = await retriever.validate_drug_exists("Xyzzylox")

        assert result.get('is_real') is False, f"Fake drug was validated: {result.get('reasoning')}"
        print(f"✓ Fake drug rejected")
        print(f"   Reason: {result.get('reasoning')}")

    @pytest.mark.asyncio
    async def test_generate_drug_info_llm(self):
        """Test LLM drug info generation."""
        from servers.clinical_decision_support.drug_info_retriever import DrugInfoRetriever

        retriever = DrugInfoRetriever()

        result = await retriever.generate_drug_info_llm("Ibuprofen", "Ibuprofen")

        assert result.get('success') is True, f"LLM generation failed: {result.get('error')}"
        assert result.get('source') == 'llm'
        assert result.get('drug_name') is not None

        print(f"✓ LLM generated info for Ibuprofen")
        print(f"   Indications: {result.get('indications', 'N/A')[:100]}...")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
