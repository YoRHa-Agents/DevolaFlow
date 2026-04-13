#!/usr/bin/env bash
# Generate test coverage in multiple formats for NineS consumption
set -e
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

python -m pytest tests/ \
    --cov=devolaflow \
    --cov-report=term-missing \
    --cov-report=xml:coverage.xml \
    --cov-report=json:coverage.json \
    -q \
    -W ignore::DeprecationWarning \
    "$@"

echo ""
echo "Coverage reports generated:"
echo "  coverage.xml  (Cobertura format)"
echo "  coverage.json (JSON format)"
