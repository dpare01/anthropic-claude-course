#!/bin/bash

# Run all code quality checks
# Usage: ./scripts/quality.sh

set -e

cd "$(dirname "$0")/.."

echo "=== Running Code Quality Checks ==="
echo

echo "1. Checking code formatting with Black..."
uv run black --check backend/ main.py
echo "   Formatting check passed!"
echo

echo "=== All quality checks passed! ==="
