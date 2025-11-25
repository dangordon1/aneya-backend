#!/usr/bin/env python3
"""
Test script to verify the refactored clinical_decision_support package.

Tests:
1. Import from the new package structure
2. Import from the backward compatibility shim
3. Verify all main classes and functions are accessible
4. Basic instantiation test
"""

import sys
from pathlib import Path

# Add the servers directory to Python path
servers_dir = Path(__file__).parent
sys.path.insert(0, str(servers_dir))

def test_new_package_imports():
    """Test importing from the new modular package."""
    print("=" * 80)
    print("TEST 1: Importing from new package structure")
    print("=" * 80)

    try:
        # Import main classes
        from clinical_decision_support import (
            ClinicalDecisionSupportClient,
            RegionalSearchService,
            ResourceType,
            REGION_CONFIGS,
            COUNTRY_TO_REGION
        )

        print("✓ Successfully imported ClinicalDecisionSupportClient")
        print("✓ Successfully imported RegionalSearchService")
        print("✓ Successfully imported ResourceType enum")
        print("✓ Successfully imported REGION_CONFIGS")
        print("✓ Successfully imported COUNTRY_TO_REGION")

        # Verify enum values
        assert ResourceType.GUIDELINE.value == "guideline"
        assert ResourceType.CKS.value == "cks"
        print("✓ ResourceType enum values verified")

        # Verify config
        assert "UK" in REGION_CONFIGS
        assert "INDIA" in REGION_CONFIGS
        assert "INTERNATIONAL" in REGION_CONFIGS
        print("✓ REGION_CONFIGS contains expected regions")

        assert "GB" in COUNTRY_TO_REGION
        assert "IN" in COUNTRY_TO_REGION
        print("✓ COUNTRY_TO_REGION mappings verified")

        return True

    except Exception as e:
        print(f"✗ Import from new package failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backward_compatibility():
    """Test importing from the backward compatibility shim."""
    print("\n" + "=" * 80)
    print("TEST 2: Backward compatibility imports")
    print("=" * 80)

    try:
        # Import from the original location (should work via shim)
        from clinical_decision_support_client import (
            ClinicalDecisionSupportClient as Client_BC,
            RegionalSearchService as RegionalSearch_BC,
            REGION_CONFIGS as Configs_BC
        )

        print("✓ Successfully imported via backward compatibility shim")
        print("✓ ClinicalDecisionSupportClient accessible")
        print("✓ RegionalSearchService accessible")
        print("✓ REGION_CONFIGS accessible")

        # Verify they're the same classes
        from clinical_decision_support import ClinicalDecisionSupportClient
        assert Client_BC is ClinicalDecisionSupportClient
        print("✓ Backward compatibility imports reference same classes")

        return True

    except Exception as e:
        print(f"✗ Backward compatibility import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_instantiation():
    """Test basic instantiation of main classes."""
    print("\n" + "=" * 80)
    print("TEST 3: Class instantiation")
    print("=" * 80)

    try:
        from clinical_decision_support import ClinicalDecisionSupportClient

        # Try to instantiate without API key (should work, just won't have Claude features)
        client = ClinicalDecisionSupportClient(anthropic_api_key=None)

        print("✓ ClinicalDecisionSupportClient instantiated successfully")
        print(f"  - Sessions dict: {type(client.sessions)}")
        print(f"  - Tool registry: {type(client.tool_registry)}")
        print(f"  - Exit stack: {type(client.exit_stack)}")
        print(f"  - Regional search service: {type(client.regional_search)}")

        # Verify regional search service has the client reference
        assert client.regional_search.client is client
        print("✓ RegionalSearchService correctly initialized with client reference")

        return True

    except Exception as e:
        print(f"✗ Instantiation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_package_structure():
    """Verify the package structure exists."""
    print("\n" + "=" * 80)
    print("TEST 4: Package structure verification")
    print("=" * 80)

    expected_files = [
        "clinical_decision_support/__init__.py",
        "clinical_decision_support/config.py",
        "clinical_decision_support/regional_search.py",
        "clinical_decision_support/client.py",
        "clinical_decision_support/utils.py",
        "clinical_decision_support_client.py",  # Backward compatibility shim
    ]

    all_exist = True
    for file_path in expected_files:
        full_path = servers_dir / file_path
        if full_path.exists():
            size = full_path.stat().st_size
            print(f"✓ {file_path} ({size:,} bytes)")
        else:
            print(f"✗ {file_path} - NOT FOUND")
            all_exist = False

    return all_exist


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("CLINICAL DECISION SUPPORT REFACTORING TESTS")
    print("=" * 80 + "\n")

    results = {
        "Package Structure": test_package_structure(),
        "New Package Imports": test_new_package_imports(),
        "Backward Compatibility": test_backward_compatibility(),
        "Instantiation": test_instantiation(),
    }

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    all_passed = True
    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}: {status}")
        if not result:
            all_passed = False

    print("=" * 80)

    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Refactoring successful.")
        print("\nThe clinical_decision_support_client.py has been successfully refactored into:")
        print("  📁 clinical_decision_support/")
        print("     ├── __init__.py         - Package exports")
        print("     ├── config.py            - Configuration and constants")
        print("     ├── regional_search.py   - Regional search service")
        print("     ├── client.py            - Main client class (complete)")
        print("     └── utils.py             - Utility functions")
        print("\n  📄 clinical_decision_support_client.py - Backward compatibility shim")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED. Please review the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
