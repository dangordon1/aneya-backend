# Quick Start Guide - MCP Client Tests

## Installation

```bash
# Navigate to the tests directory
cd /Users/dgordon/python/hackathons/aneya-country-clients/backend/servers

# Install test dependencies
pip install pytest pytest-asyncio pytest-cov
```

## Running Tests

### Run Everything
```bash
pytest
```

### Run with Verbose Output
```bash
pytest -v
```

### Run Specific Test File
```bash
pytest tests/test_uk_mcp_client.py
pytest tests/test_india_mcp_client.py
pytest tests/test_mcp_client_selector.py
```

### Run Specific Test Class
```bash
pytest tests/test_uk_mcp_client.py::TestUKMCPClientNICEGuidelines
```

### Run Specific Test Function
```bash
pytest tests/test_uk_mcp_client.py::TestUKMCPClientNICEGuidelines::test_search_nice_guidelines
```

### Run Tests by Pattern
```bash
# Run all connection tests
pytest -k "connection"

# Run all search tests
pytest -k "search"

# Run all error handling tests
pytest -k "error"
```

### Run with Coverage
```bash
# Show coverage in terminal
pytest --cov=. --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=. --cov-report=html
# Then open: htmlcov/index.html
```

### Skip Slow Tests
```bash
pytest -m "not slow"
```

### Run Only Integration Tests
```bash
pytest -m integration
```

## Verify Test Suite

### Count Tests
```bash
# Total test count
pytest --collect-only | grep "test session starts" -A 1

# Count by file
pytest --collect-only -q
```

### Check Test Structure
```bash
# List all test functions
grep -r "def test_" tests/*.py

# List all test classes
grep -r "class Test" tests/*.py
```

## Expected Results

When you run `pytest`, you should see:

```
============================== test session starts ==============================
platform darwin -- Python 3.12.x, pytest-7.x.x, pluggy-1.x.x
rootdir: /Users/dgordon/python/hackathons/aneya-country-clients/backend/servers
configfile: pytest.ini
testpaths: tests
plugins: asyncio-0.x.x, cov-4.x.x
collected 188 items

tests/test_mcp_client_base.py ..........................................  [ 33%]
tests/test_uk_mcp_client.py ..............................             [ 48%]
tests/test_india_mcp_client.py .................................        [ 67%]
tests/test_us_mcp_client.py ................................            [ 84%]
tests/test_australia_mcp_client.py ....................                 [ 94%]
tests/test_international_mcp_client.py ...............                  [ 98%]
tests/test_mcp_client_selector.py ..................                    [100%]

============================== 188 passed in 5.23s ==============================
```

## Common Issues

### Import Errors
If you see `ModuleNotFoundError`:
```bash
# Make sure you're in the correct directory
cd /Users/dgordon/python/hackathons/aneya-country-clients/backend/servers

# Add parent directory to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Async Warnings
If you see asyncio warnings:
```bash
# Make sure pytest-asyncio is installed
pip install pytest-asyncio
```

### Missing Coverage
If coverage isn't working:
```bash
# Install pytest-cov
pip install pytest-cov
```

## Quick Validation

Run this to verify everything is set up correctly:

```bash
# Should show 188 tests collected
pytest --collect-only -q | tail -1

# Should show test file count
ls tests/test_*.py | wc -l
# Expected: 7

# Should show fixture count
grep "@pytest.fixture" tests/conftest.py | wc -l
# Expected: ~15
```

## Test Examples

### UK Client Test
```bash
pytest tests/test_uk_mcp_client.py::TestUKMCPClientNICEGuidelines::test_search_nice_guidelines -v
```

### India Client Test
```bash
pytest tests/test_india_mcp_client.py::TestIndiaMCPClientRSSDI::test_search_rssdi_diabetes_guidelines -v
```

### Selector Test
```bash
pytest tests/test_mcp_client_selector.py::TestGetMCPClientForCountry::test_get_uk_client_with_gb_code -v
```

## Development Workflow

1. **Run all tests**: `pytest`
2. **Check coverage**: `pytest --cov=. --cov-report=html`
3. **View coverage**: Open `htmlcov/index.html`
4. **Add new tests**: Follow patterns in existing test files
5. **Re-run**: `pytest`

## CI/CD Command

For CI/CD pipelines, use:
```bash
pytest --cov=. --cov-report=xml --cov-report=term-missing -v
```

## Debugging Tests

### Run with detailed output
```bash
pytest -vv --showlocals
```

### Run with print statements visible
```bash
pytest -s
```

### Run with PDB on failure
```bash
pytest --pdb
```

### Run last failed tests only
```bash
pytest --lf
```

## Performance

Expected test execution time:
- **All tests**: ~5-10 seconds
- **Single file**: ~1-2 seconds
- **Integration tests**: ~10-20 seconds (if running real servers)

## Next Steps

1. Run `pytest` to verify all tests pass
2. Check coverage with `pytest --cov`
3. Review any failures
4. Add tests for new features
5. Keep coverage >90%

## Help

For more information:
- **Full documentation**: See `README.md`
- **Test summary**: See `TEST_SUMMARY.md`
- **Pytest docs**: https://docs.pytest.org/
- **Pytest-asyncio docs**: https://pytest-asyncio.readthedocs.io/
