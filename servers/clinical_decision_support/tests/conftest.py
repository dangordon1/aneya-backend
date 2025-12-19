"""
Pytest configuration for Clinical Decision Support tests.

Loads environment variables from .env file before running tests.
"""

import os
import sys
from pathlib import Path

import pytest


def pytest_configure(config):
    """Load .env file before tests run."""
    # Find the backend directory (where .env is located)
    tests_dir = Path(__file__).parent
    backend_dir = tests_dir.parent.parent.parent  # servers/clinical_decision_support/tests -> backend
    env_file = backend_dir / ".env"

    if env_file.exists():
        print(f"\nLoading environment from: {env_file}")
        # Parse .env file manually (to avoid adding python-dotenv dependency)
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    os.environ[key] = value

        # Verify API key is loaded
        if os.getenv("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY loaded successfully")
        else:
            print("WARNING: ANTHROPIC_API_KEY not found in .env file")
    else:
        print(f"\nWARNING: .env file not found at {env_file}")
