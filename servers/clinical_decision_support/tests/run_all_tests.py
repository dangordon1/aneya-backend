"""
Test runner that runs unit tests before integration test.

Run with: python -m servers.clinical_decision_support.tests.run_all_tests
"""

import subprocess
import sys
import os


def run_unit_tests():
    """Run unit tests for DiagnosisEngine and DrugInfoRetriever."""
    print("\n" + "="*70)
    print("Running Unit Tests")
    print("="*70)

    # Change to the backend directory
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    os.chdir(backend_dir)

    tests_passed = True

    # Run DiagnosisEngine tests
    print("\n📋 Testing DiagnosisEngine...")
    result = subprocess.run(
        ["python", "-m", "pytest",
         "servers/clinical_decision_support/tests/test_diagnosis_engine.py",
         "-v", "-s", "--tb=short"],
        capture_output=False
    )
    if result.returncode != 0:
        print("❌ DiagnosisEngine tests FAILED")
        tests_passed = False
    else:
        print("✅ DiagnosisEngine tests PASSED")

    # Run DrugInfoRetriever tests
    print("\n📋 Testing DrugInfoRetriever...")
    result = subprocess.run(
        ["python", "-m", "pytest",
         "servers/clinical_decision_support/tests/test_drug_info_retriever.py",
         "-v", "-s", "--tb=short"],
        capture_output=False
    )
    if result.returncode != 0:
        print("❌ DrugInfoRetriever tests FAILED")
        tests_passed = False
    else:
        print("✅ DrugInfoRetriever tests PASSED")

    return tests_passed


def run_integration_test():
    """Run full frontend-backend integration test."""
    print("\n" + "="*70)
    print("Running Integration Test")
    print("="*70)

    # Change to parent (aneya) directory
    aneya_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    os.chdir(aneya_dir)

    result = subprocess.run(
        ["python", "test_frontend_backend_integration.py"],
        capture_output=False
    )

    return result.returncode == 0


def main():
    """Main test runner."""
    print("\n" + "="*70)
    print("🧪 CLINICAL DECISION SUPPORT TEST SUITE")
    print("="*70)

    # Run unit tests first
    unit_tests_passed = run_unit_tests()

    if not unit_tests_passed:
        print("\n" + "="*70)
        print("❌ UNIT TESTS FAILED - Skipping integration test")
        print("="*70)
        sys.exit(1)

    print("\n✅ Unit tests passed - proceeding to integration test")

    # Run integration test
    integration_passed = run_integration_test()

    print("\n" + "="*70)
    if integration_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ INTEGRATION TEST FAILED")
    print("="*70)

    sys.exit(0 if integration_passed else 1)


if __name__ == "__main__":
    main()
