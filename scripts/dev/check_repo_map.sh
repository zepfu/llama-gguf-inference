#!/usr/bin/env bash
# ==============================================================================
# check_repo_map.sh - Check if REPO_MAP.md is current
#
# This script verifies that REPO_MAP.md matches the current repository structure.
# Used as a pre-commit hook to ensure documentation stays up-to-date.
#
# Usage:
#   bash scripts/dev/check_repo_map.sh
#
# Exit codes:
#   0 - REPO_MAP.md is current
#   1 - REPO_MAP.md is outdated or check failed
# ==============================================================================

set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Checking if REPO_MAP.md is current..."

# Check if REPO_MAP.md exists
if [[ ! -f docs/auto/REPO_MAP.md ]]; then
    echo -e "${YELLOW}⚠️  REPO_MAP.md not found${NC}"
    echo ""
    echo "Generate it with:"
    echo "  make map"
    echo ""
    exit 1
fi

# URL to repo_map.py script
REPO_MAP_URL="https://raw.githubusercontent.com/zepfu/repo-standards/main/scripts/repo_map.py"

# Generate to temp location
TEMP_MAP=$(mktemp)
trap 'rm -f "$TEMP_MAP"' EXIT

if ! curl -fsSL "$REPO_MAP_URL" | python3 - --output "$TEMP_MAP" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Could not check repo map (network issue?)${NC}"
    echo "   Skipping check..."
    exit 0  # Don't fail commit on network error
fi

# Compare (ignore whitespace differences)
if ! diff -q -w REPO_MAP.md "$TEMP_MAP" >/dev/null 2>&1; then
    echo ""
    echo -e "${RED}❌ REPO_MAP.md is outdated!${NC}"
    echo ""
    echo "To fix, run:"
    echo "  make map"
    echo ""
    echo "Or skip this check with:"
    echo "  git commit --no-verify"
    echo ""

    # Show what changed (first few lines)
    echo "Changes detected:"
    diff -u REPO_MAP.md "$TEMP_MAP" | head -20 || true
    echo ""

    exit 1
fi

echo -e "${GREEN}✓ REPO_MAP.md is current${NC}"
exit 0
