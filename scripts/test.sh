#!/bin/bash
# Test runner script for aneya-backend
# Usage:
#   ./scripts/test.sh              # Run all tests
#   ./scripts/test.sh --record     # Record VCR cassettes
#   ./scripts/test.sh --coverage   # Run with coverage report

set -e

cd "$(dirname "$0")/.."

if [[ "$1" == "--record" ]]; then
    echo "Running tests with VCR recording..."
    uv run python -m pytest tests/ -v --record-mode=once
elif [[ "$1" == "--coverage" ]]; then
    echo "Running tests with coverage..."
    uv run python -m pytest tests/ --cov=api --cov-report=html --cov-report=term-missing
elif [[ "$1" == "--block-network" ]]; then
    echo "Running tests with network blocked (replay only)..."
    uv run python -m pytest tests/ -v --block-network
else
    echo "Running all tests..."
    uv run python -m pytest tests/ -v "$@"
fi
