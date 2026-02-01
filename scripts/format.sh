#!/bin/bash

# Code formatting script using Black
# Usage: ./scripts/format.sh [--check]

set -e

cd "$(dirname "$0")/.."

if [ "$1" = "--check" ]; then
    echo "Checking code formatting..."
    uv run black --check backend/ main.py
else
    echo "Formatting code with Black..."
    uv run black backend/ main.py
fi

echo "Done!"
