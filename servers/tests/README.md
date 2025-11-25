# MCP Client Test Suite

Comprehensive test suite for all country-specific MCP clients and the client selector factory.

## Test Files

### Core Tests

- **`test_mcp_client_base.py`** - Tests for the base MCPClient class
  - Connection management
  - Tool routing
  - Session management
  - Error handling
  - Cleanup and resource management

- **`test_mcp_client_selector.py`** - Tests for the client selector factory
  - Country code mapping (GB → UK, IN → India, etc.)
  - Case-insensitive matching
  - Fallback to InternationalMCPClient
  - Verbose mode output
  - Error handling

### Country-Specific Tests

- **`test_uk_mcp_client.py`** - Tests for UK client (NICE, BNF)
  - NICE guideline search
  - BNF drug information lookup
  - Patient info management
  - 3 servers: NICE, BNF, patient_info

- **`test_india_mcp_client.py`** - Tests for India client (7 Indian servers)
  - FOGSI (obstetrics/gynecology)
  - ICMR (medical research)
  - STG (standard treatment guidelines)
  - RSSDI (diabetes)
  - CSI (cardiology)
  - NCG (cancer)
  - IAP (pediatrics)
  - 8 servers total including patient_info

- **`test_us_mcp_client.py`** - Tests for US client (6 US servers)
  - USPSTF (preventive services)
  - CDC (public health)
  - IDSA (infectious diseases)
  - ADA (diabetes)
  - AHA/ACC (cardiovascular)
  - AAP (pediatrics)
  - 7 servers total including patient_info

- **`test_australia_mcp_client.py`** - Tests for Australia client (NHMRC)
  - NHMRC guideline search
  - Patient info management
  - 2 servers: NHMRC, patient_info

- **`test_international_mcp_client.py`** - Tests for International fallback client
  - PubMed medical literature search (35M+ articles)
  - Patient info management
  - Fallback for unsupported countries
  - 2 servers: PubMed, patient_info

### Shared Fixtures

- **`conftest.py`** - Pytest configuration and shared fixtures
  - Event loop configuration for async tests
  - Mock server fixtures
  - Mock tool definitions
  - Sample clinical scenarios
  - Mock response fixtures (NICE, BNF, PubMed, etc.)

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest test_uk_mcp_client.py
pytest test_india_mcp_client.py
pytest test_mcp_client_selector.py
```

### Run Specific Test Class

```bash
pytest test_uk_mcp_client.py::TestUKMCPClientInitialization
```

### Run Specific Test

```bash
pytest test_uk_mcp_client.py::TestUKMCPClientNICEGuidelines::test_search_nice_guidelines
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage

```bash
pytest --cov=. --cov-report=html
```

### Run Tests Matching Pattern

```bash
pytest -k "test_search"
pytest -k "connection"
pytest -k "error_handling"
```

### Run Tests by Marker

```bash
# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

## Test Categories

### Unit Tests (Majority)
- Mock all external dependencies
- Fast execution
- Test individual components in isolation

### Integration Tests (Marked)
- May connect to real servers
- Slower execution
- Test end-to-end workflows
- Marked with `@pytest.mark.integration`

### Slow Tests (Marked)
- Long-running tests
- Marked with `@pytest.mark.slow`
- Can be skipped with `-m "not slow"`

## Test Structure

Each test file follows a consistent structure:

1. **Initialization Tests** - Test client setup and configuration
2. **Connection Tests** - Test server connection functionality
3. **Tool Tests** - Test tool availability and routing
4. **Functional Tests** - Test specific functionality (guideline search, etc.)
5. **Error Handling Tests** - Test error cases and edge conditions
6. **Integration Tests** - Test complete workflows
7. **Context Manager Tests** - Test async context manager usage

## Mock Strategy

Tests use mocking to avoid hitting real servers:

- **`mock_stdio_transport`** - Mock stdio transport for MCP communication
- **`mock_client_session`** - Mock MCP ClientSession
- **`mock_server_tools`** - Mock tool definitions for different servers
- **`mock_nice_guideline_response`** - Mock NICE guideline data
- **`mock_bnf_drug_response`** - Mock BNF drug data
- **`mock_pubmed_response`** - Mock PubMed article data
- **`mock_patient_info_response`** - Mock patient data

## Sample Clinical Scenarios

The `test_clinical_scenarios` fixture provides realistic test cases:

- **pediatric_fever** - 3-year-old with fever
- **diabetes_management** - Type 2 diabetes case
- **hypertension** - High blood pressure case
- **pregnancy** - Gestational hypertension case
- **cardiac** - Angina/chest pain case
- **infectious_disease** - Tuberculosis case

## Assertions

Tests verify:

1. **Correct client selection** - Right client class for country code
2. **Server connectivity** - All expected servers connected
3. **Tool availability** - Expected tools are available
4. **Tool routing** - Tools route to correct servers
5. **Response handling** - Responses are processed correctly
6. **Error handling** - Errors are caught and handled properly
7. **Cleanup** - Resources are cleaned up properly

## Coverage Goals

- **Line coverage**: >90%
- **Branch coverage**: >85%
- **Test all country clients**: UK, India, US, Australia, International
- **Test all error paths**: Connection failures, tool errors, timeouts
- **Test edge cases**: Case sensitivity, whitespace, invalid codes

## Common Issues

### Import Errors

If you see import errors, ensure you're in the correct directory:

```bash
cd /Users/dgordon/python/hackathons/aneya-country-clients/backend/servers
pytest tests/
```

### Async Warnings

If you see async warnings, ensure pytest-asyncio is installed:

```bash
pip install pytest-asyncio
```

### Mock Issues

If mocks aren't working, check that you're patching the correct module:

```python
# Patch where it's imported, not where it's defined
with patch('mcp_client_base.stdio_client', ...):  # Correct
with patch('mcp.client.stdio.stdio_client', ...):  # May not work
```

## Best Practices

1. **Use fixtures** - Reuse common setup via conftest.py fixtures
2. **Test one thing** - Each test should verify one specific behavior
3. **Use parametrize** - Test multiple inputs with `@pytest.mark.parametrize`
4. **Clear names** - Test names should describe what they test
5. **Mock external calls** - Don't hit real servers in unit tests
6. **Clean up** - Always clean up resources in tests
7. **Use async properly** - Mark async tests with `@pytest.mark.asyncio`

## Contributing

When adding new tests:

1. Follow existing test structure and naming conventions
2. Add docstrings to test classes and functions
3. Use appropriate fixtures from conftest.py
4. Mock external dependencies
5. Test both positive and negative cases
6. Update this README if adding new test categories

## CI/CD Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pytest --cov=. --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## Dependencies

Required packages for running tests:

- pytest
- pytest-asyncio
- pytest-cov (for coverage)
- pytest-httpx (for HTTP mocking, if needed)

Install with:

```bash
pip install pytest pytest-asyncio pytest-cov
```
