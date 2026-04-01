#!/usr/bin/env bash
# run_tests.sh — set up venv if needed and run the test suite
set -euo pipefail

VENV_DIR=".venv"
REQUIREMENTS="requirements-test.txt"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

# Activate
source "$VENV_DIR/bin/activate"

# Install all test dependencies from the single source of truth
echo "Installing test dependencies from $REQUIREMENTS..."
pip install -q -r "$REQUIREMENTS"

echo ""
echo "Running tests..."
python -m pytest tests/ -v --tb=short "$@"
