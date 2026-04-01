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

# Install test deps if pytest isn't available
if ! python -c "import pytest" &>/dev/null; then
    echo "Installing test dependencies from $REQUIREMENTS..."
    pip install -q -r "$REQUIREMENTS"
fi

# Also install Pillow if not present (needed for conftest stubs to import cleanly)
if ! python -c "import PIL" &>/dev/null; then
    echo "Installing Pillow (required by project imports)..."
    pip install -q Pillow
fi

# Install envsubst if not present
if ! python -c "import envsubst" &>/dev/null; then
    echo "Installing envsubst..."
    pip install -q envsubst
fi

echo ""
echo "Running tests..."
python -m pytest tests/ -v --tb=short "$@"
