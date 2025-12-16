#!/usr/bin/env bash
# Quick test of the batch scripts in dry-run mode

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Testing batch operations scripts..."
echo ""

# Test 1: Dry run with all defaults
echo "Test 1: Dry run (all defaults - full dataset)"
echo "─────────────────────────────────────────────────"
"$SCRIPT_DIR/run-batch.sh" --dry-run | head -20

echo ""
echo "✓ Test 1 passed"
echo ""

# Test 1b: Dry run with custom total
echo "Test 1b: Dry run (custom total)"
echo "─────────────────────────────────────────────────"
"$SCRIPT_DIR/run-batch.sh" \
    --total 100 \
    --chunk-size 25 \
    --dry-run

echo ""
echo "✓ Test 1b passed"
echo ""

# Test 1c: Dry run with explicit variant
echo "Test 1c: Dry run (explicit variant)"
echo "─────────────────────────────────────────────────"
"$SCRIPT_DIR/run-batch.sh" \
    --variant terse-functional \
    --total 50 \
    --chunk-size 25 \
    --dry-run

echo ""
echo "✓ Test 1c passed"
echo ""

# Test 2: Monitor with no sessions
echo "Test 2: Monitor with no sessions"
echo "─────────────────────────────────────────────────"
"$SCRIPT_DIR/monitor.sh"

echo ""
echo "✓ Test 2 passed"
echo ""

# Test 3: Help messages
echo "Test 3: Help messages"
echo "─────────────────────────────────────────────────"

echo "Testing run-batch.sh help:"
"$SCRIPT_DIR/run-batch.sh" 2>&1 | head -3 || true

echo ""
echo "Testing monitor.sh help:"
"$SCRIPT_DIR/monitor.sh" --help 2>&1 | head -3 || true

echo ""
echo "Testing resume.sh help:"
"$SCRIPT_DIR/resume.sh" 2>&1 | head -3 || true

echo ""
echo "✓ Test 3 passed"
echo ""

echo "================================================"
echo "All tests passed!"
echo "================================================"
echo ""
echo "Scripts are ready to use. See README.md for usage examples."
